#!/usr/bin/env python3
"""Shared, fail-closed SSRF policy for vault-capture.

Centralizes domain-only URL syntax validation, system-DNS address
classification, Fake-IP detection, trusted DoH resolution, and redirect
validation so that every outbound target is checked before a connection is
made. This module is intentionally self-contained and standard-library-only.

Design rules (see SPEC 2026-08-09-vault-capture-fake-ip-ssrf and D-019):

- Default mode requires every system resolver answer to be globally routable or
  in the exact exempt ``198.18.0.0/16`` range. Exempt addresses pass without any
  DoH request.
- Clash Fake-IP mode: a system answer in ``198.19.0.0/16`` (the residual half of
  the full ``198.18.0.0/15`` Fake-IP range) is treated only as a signal to
  resolve A and AAAA independently over a fixed, trusted HTTPS DoH provider; at
  least one real address must exist and every returned address must be globally
  routable. Exempt ``198.18.0.0/16`` answers never trigger DoH, including when
  combined with residual Fake-IP answers (which still require DoH).
- Fake-IP is never treated as a real destination. Direct IPv4/IPv6 literals,
  including public and Fake-IP literals, are always rejected.
- The exemption is address-classification-only and unconditional: it applies in
  both default and Clash modes and requires no environment variable.
- Production code must not read any private-fetch bypass environment variable.
  Local fixture tests inject scoped fake policies/transports directly and must
  not be reachable through runtime environment configuration.

Safe error text never contains raw DNS payloads, host configuration, stack
traces, or absolute paths.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import urllib.request
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit

FAKE_IP_NETWORK = ipaddress.ip_network("198.18.0.0/15")
# Exact canonical trust-exemption range (D-019): answers inside 198.18.0.0/16
# pass unconditionally without DoH in both default and Clash modes. The full
# 198.18.0.0/15 Fake-IP range above is retained to represent the residual
# 198.19.0.0/16 half that still follows the D-018 Clash/DoH behavior.
EXEMPT_NETWORK = ipaddress.ip_network("198.18.0.0/16")

MODE_DEFAULT = "default"
MODE_CLASH = "clash"

ENV_FAKE_IP_MODE = "VAULT_CAPTURE_SSRF_FAKE_IP_MODE"
ENV_DOH_PROVIDER = "VAULT_CAPTURE_SSRF_DOH_PROVIDER"

# Fixed, code-owned HTTPS DNS JSON endpoints. Arbitrary endpoint configuration
# and insecure HTTP are forbidden.
DOH_PROVIDERS = {
    "cloudflare": {
        "url": "https://cloudflare-dns.com/dns-query",
        "name_param": "name",
        "type_param": "type",
    },
    "google": {
        "url": "https://dns.google/resolve",
        "name_param": "name",
        "type_param": "type",
    },
}

# DNS JSON "Answer" record types we accept as IP addresses (A=1, AAAA=28).
_TYPE_A = 1
_TYPE_AAAA = 28

DOH_TIMEOUT = 5
DOH_MAX_BYTES = 64 * 1024
DOH_MAX_REDIRECTS = 0  # DoH endpoints must not follow uncontrolled redirects


class NetworkPolicyError(Exception):
    """Fail-closed policy violation with a short, safe reason."""

    def __init__(self, reason: str, *, recoverable: bool = True) -> None:
        super().__init__(reason)
        self.reason = reason
        self.recoverable = recoverable


class InvalidNetworkConfig(NetworkPolicyError):
    """Fake-IP/DoH environment configuration is missing, partial, or unknown.

    Such configuration must fail closed: no ingest may proceed, and there is
    never a fallback to private-network access.
    """


@dataclass(frozen=True)
class ValidationResult:
    """Non-sensitive result of validating a URL before connection."""

    url: str
    fake_ip_observed: bool = False
    provider: str | None = None


def _safe_reason(message: str) -> str:
    """Return a short, non-sensitive, human-readable failure reason."""
    return message


def _ascii_host(host: str) -> str:
    """Deterministically convert a hostname to ASCII IDNA.

    Raises NetworkPolicyError with a short safe reason if the hostname cannot be
    encoded. Valid IDN hosts are converted to their punycode form so the system
    resolver, DoH, and any downstream request all use a consistent ASCII name
    and never trigger an uncaught UnicodeEncodeError.
    """
    try:
        return host.encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError) as exc:
        raise NetworkPolicyError("Hostname is not a valid DNS name", recoverable=False) from exc


def _reject_literal_host(host: str) -> None:
    """Raise NetworkPolicyError if an ASCII host is any IP literal.

    Covers canonical IPv4/IPv6 and legacy glibc/inet_aton numeric IPv4 forms
    (one-part decimal/hex, octal, shorthand). socket.inet_aton raises OSError
    for real DNS hostnames, so normal domains are unaffected; ipaddress covers
    canonical IPv6.
    """
    try:
        ipaddress.ip_address(host)
        raise NetworkPolicyError(
            "IP address literals are not allowed; use a DNS hostname", recoverable=False
        )
    except ValueError:
        pass
    if host.isascii():
        try:
            socket.inet_aton(host)
            raise NetworkPolicyError(
                "IP address literals are not allowed; use a DNS hostname", recoverable=False
            )
        except OSError:
            pass


def _literal_candidates(ascii_host: str) -> list[str]:
    """Return the ASCII host plus its single-trailing-dot-stripped form.

    A single trailing dot is a legal FQDN root marker (``example.com.``), so the
    host itself stays legal, but numeric spellings with a trailing dot
    (``1.2.3.4.``, ``2130706433.``) must be caught by also checking the stripped
    form.
    """
    if ascii_host.endswith("."):
        return [ascii_host, ascii_host[:-1]]
    return [ascii_host]


def validate_domain_url_syntax(url: str) -> str:
    """Network-free validation that a URL is an absolute, domain-only HTTP(S) URL.

    Rejects non-HTTP(S) schemes, missing hostnames, embedded credentials, and
    any IP literal (canonical IPv4/IPv6 or legacy numeric IPv4 forms such as
    one-part decimal, hex, octal, and shorthand), including globally routable
    numeric forms and IDNA-mapped numeric spellings (fullwidth digits,
    ideographic dots) and single-trailing-dot numeric forms. Does not perform
    DNS. Returns the normalized/trimmed URL.
    """
    if not isinstance(url, str) or not url.strip():
        raise NetworkPolicyError("URL is empty", recoverable=False)
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"}:
        raise NetworkPolicyError("Only absolute HTTP(S) URLs are supported", recoverable=False)
    if not parts.hostname:
        raise NetworkPolicyError("URL has no hostname", recoverable=False)
    if parts.username or parts.password:
        raise NetworkPolicyError("URLs with credentials are not allowed", recoverable=False)
    host = parts.hostname.lower()
    if not host:
        raise NetworkPolicyError("URL has no hostname", recoverable=False)
    # Canonical ASCII IDNA host (also rejects unencodable Unicode hostnames).
    ascii_host = _ascii_host(host)
    # Literal checks run on the IDNA-mapped host and its single-trailing-dot-
    # stripped form so fullwidth/ideographic-dot/trailing-dot numeric spellings
    # that map to a canonical IPv4 are rejected here (before any resolver/DoH).
    for candidate in _literal_candidates(ascii_host):
        _reject_literal_host(candidate)
    # Validate port parsing (rejects malformed ports).
    try:
        parts.port
    except ValueError:
        raise NetworkPolicyError("Invalid port in URL", recoverable=False)
    return url


def _system_resolve(host: str, port: int) -> set[str]:
    """Resolve a host via the system resolver; returns a set of IP strings.

    Raises NetworkPolicyError on failure (no result, or resolver error).
    """
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise NetworkPolicyError("Host could not be resolved") from exc
    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise NetworkPolicyError("Host could not be resolved")
    return addresses


def _classify(address: str) -> str:
    """Classify an address as global / exempt / residual_fake / non_global."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError as exc:
        raise NetworkPolicyError("Host resolved to a malformed address") from exc
    if ip.is_global:
        return "global"
    if ip in EXEMPT_NETWORK:
        return "exempt"
    if ip in FAKE_IP_NETWORK:
        # Residual 198.19.0.0/16 half of the full Fake-IP /15 range.
        return "residual_fake"
    return "non_global"


def _classify_all(addresses: set[str]) -> tuple[bool, bool, bool, bool]:
    """Return (any_global, any_exempt, any_residual, any_non_global)."""
    any_global = False
    any_exempt = False
    any_residual = False
    any_non_global = False
    for addr in addresses:
        cls = _classify(addr)
        if cls == "global":
            any_global = True
        elif cls == "exempt":
            any_exempt = True
        elif cls == "residual_fake":
            any_residual = True
        else:
            any_non_global = True
    return any_global, any_exempt, any_residual, any_non_global


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, headers):
        raise HTTPError(req.full_url, code, msg, headers, fp)

    def http_error_302(self, req, fp, code, msg, headers):
        raise HTTPError(req.full_url, code, msg, headers, fp)

    def http_error_303(self, req, fp, code, msg, headers):
        raise HTTPError(req.full_url, code, msg, headers, fp)

    def http_error_307(self, req, fp, code, msg, headers):
        raise HTTPError(req.full_url, code, msg, headers, fp)

    def http_error_308(self, req, fp, code, msg, headers):
        raise HTTPError(req.full_url, code, msg, headers, fp)


def _doh_query(provider_id: str, host: str, qtype: int, *, opener: urllib.request.OpenerDirector | None = None) -> list[str]:
    """Query one fixed trusted DoH provider for a DNS record type.

    Returns the list of IP address strings from type-1/type-28 answers.
    Raises NetworkPolicyError on any protocol/parse/safety failure (fail closed).
    """
    provider = DOH_PROVIDERS[provider_id]
    # Convert the host to ASCII IDNA and percent-encode query parameters with
    # urlencode, so & and = in a hostname cannot pollute the fixed provider's
    # query and a Unicode hostname cannot cause an uncaught UnicodeEncodeError.
    host_ascii = _ascii_host(host)
    query = urlencode(
        {provider["name_param"]: host_ascii, provider["type_param"]: str(qtype)}
    )
    sep = "&" if "?" in provider["url"] else "?"
    url = f'{provider["url"]}{sep}{query}'
    if opener is None:
        opener = urllib.request.build_opener(_NoRedirectHandler)
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/dns-json",
            "User-Agent": "vault-capture/1.0",
        },
    )
    try:
        with opener.open(req, timeout=DOH_TIMEOUT) as response:
            final_url = response.geturl()
            if final_url.split("?", 1)[0] != provider["url"]:
                raise NetworkPolicyError("DoH provider redirected unexpectedly", recoverable=False)
            content_type = response.headers.get_content_type().lower()
            if content_type not in {"application/json", "text/json", "application/dns-json"}:
                raise NetworkPolicyError("DoH provider returned an unexpected content type")
            raw = response.read(DOH_MAX_BYTES + 1)
            if len(raw) > DOH_MAX_BYTES:
                raise NetworkPolicyError("DoH response exceeds maximum size")
    except HTTPError as exc:
        raise NetworkPolicyError(f"DoH provider returned HTTP {exc.code}") from exc
    except (URLError, OSError, socket.timeout, TimeoutError, UnicodeError, ValueError) as exc:
        raise NetworkPolicyError("DoH provider request failed") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NetworkPolicyError("DoH provider returned malformed data") from exc
    if not isinstance(payload, dict):
        raise NetworkPolicyError("DoH provider returned malformed data")
    status = payload.get("Status")
    if status != 0:
        raise NetworkPolicyError("DoH provider returned a non-success DNS status")
    answers = payload.get("Answer")
    if not isinstance(answers, list):
        raise NetworkPolicyError("DoH provider returned malformed data")
    result: list[str] = []
    for answer in answers:
        if not isinstance(answer, dict):
            continue
        if answer.get("type") not in {_TYPE_A, _TYPE_AAAA}:
            continue
        data = answer.get("data")
        if not isinstance(data, str):
            continue
        # Validate it parses as an IP before trusting it.
        try:
            ipaddress.ip_address(data)
        except ValueError:
            raise NetworkPolicyError("DoH provider returned a malformed address")
        result.append(data)
    return result


def _doh_resolve(provider_id: str, host: str, *, opener: urllib.request.OpenerDirector | None = None) -> set[str]:
    """Resolve both A and AAAA via the trusted provider; fail closed."""
    a = _doh_query(provider_id, host, _TYPE_A, opener=opener)
    aaaa = _doh_query(provider_id, host, _TYPE_AAAA, opener=opener)
    combined = set(a) | set(aaaa)
    if not combined:
        raise NetworkPolicyError("DoH provider returned no addresses")
    return combined


class NetworkPolicy:
    """Fail-closed URL/address policy shared by all outbound surfaces.

    ``resolver`` and ``doh_transport`` are injectable for local fixture tests
    only; production uses the system resolver and the built-in DoH client.
    """

    def __init__(
        self,
        mode: str = MODE_DEFAULT,
        doh_provider: str | None = None,
        *,
        resolver=None,
        doh_transport=None,
    ) -> None:
        self.mode = mode
        self.doh_provider = doh_provider
        self._resolver = resolver if resolver is not None else _system_resolve
        self._doh_transport = doh_transport

    @classmethod
    def from_environment(cls) -> "NetworkPolicy":
        """Build a policy from the two exact Fake-IP environment settings.

        Both settings unset => default fail-closed mode. Both set to their only
        valid values => Clash mode with the selected built-in provider.
        Anything partial or unknown => InvalidNetworkConfig (fail closed).
        """
        mode = os.environ.get(ENV_FAKE_IP_MODE, "") or ""
        provider = os.environ.get(ENV_DOH_PROVIDER, "") or ""
        mode_set = bool(mode)
        provider_set = bool(provider)
        if not mode_set and not provider_set:
            return cls(mode=MODE_DEFAULT, doh_provider=None)
        if mode == "clash" and provider in DOH_PROVIDERS:
            return cls(mode=MODE_CLASH, doh_provider=provider)
        raise InvalidNetworkConfig(
            "Fake-IP SSRF configuration is invalid; both "
            f"{ENV_FAKE_IP_MODE}=clash and {ENV_DOH_PROVIDER}=cloudflare|google "
            "must be set together"
        )

    def validate_url_syntax(self, url: str) -> str:
        return validate_domain_url_syntax(url)

    def _resolve_addresses(self, host: str, port: int) -> set[str]:
        return self._resolver(host, port)

    def _resolve_doh(self, host: str) -> set[str]:
        if self.mode != MODE_CLASH or not self.doh_provider:
            raise NetworkPolicyError("DoH resolution is not enabled")
        if self._doh_transport is not None:
            result = self._doh_transport(host)
            result = set(result)
            if not result:
                raise NetworkPolicyError("DoH provider returned no addresses")
            return result
        return _doh_resolve(self.doh_provider, host)

    def validate_url(self, url: str, *, force_refresh: bool = False) -> ValidationResult:
        """Syntax- and address-validate a URL before a connection is made.

        Never connects itself. Returns a non-sensitive ValidationResult on
        success and raises NetworkPolicyError otherwise (fail closed).
        """
        url = validate_domain_url_syntax(url)
        parts = urlsplit(url)
        raw_host = parts.hostname.lower()
        host = _ascii_host(raw_host)
        default_port = 443 if parts.scheme.lower() == "https" else 80
        try:
            port = parts.port
        except ValueError:
            raise NetworkPolicyError("Invalid port in URL", recoverable=False)
        addresses = self._resolve_addresses(host, port or default_port)
        if not addresses:
            raise NetworkPolicyError("Host could not be resolved")

        _, any_exempt, any_residual, any_non_global = _classify_all(addresses)

        if self.mode == MODE_DEFAULT:
            # Default: global and exact exempt 198.18.0.0/16 pass; any other
            # non-global answer (including residual 198.19.0.0/16) fails closed.
            if any_non_global or any_residual:
                raise NetworkPolicyError("URL resolves to a non-public address", recoverable=False)
            return ValidationResult(url=url, fake_ip_observed=any_exempt)

        # Clash mode: no non-global answer outside the full Fake-IP /15 range.
        if any_non_global:
            raise NetworkPolicyError("URL resolves to a non-public address", recoverable=False)
        if any_residual:
            # Residual 198.19.0.0/16 Fake-IP present: independently verify real
            # A and AAAA via DoH; all returned addresses must be global.
            real = self._resolve_doh(host)
            for addr in real:
                if _classify(addr) != "global":
                    raise NetworkPolicyError(
                        "Resolved target is not globally routable", recoverable=False
                    )
            return ValidationResult(url=url, fake_ip_observed=True, provider=self.doh_provider)
        if any_exempt:
            # Only global and/or exempt answers: pass without any DoH request.
            return ValidationResult(url=url, fake_ip_observed=True)
        return ValidationResult(url=url)


_default_policy = None


def default_policy() -> NetworkPolicy:
    """Return a module-level default policy built once from the environment.

    Raises InvalidNetworkConfig when environment configuration is invalid.
    """
    global _default_policy
    if _default_policy is None:
        _default_policy = NetworkPolicy.from_environment()
    return _default_policy
