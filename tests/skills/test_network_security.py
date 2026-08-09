"""Unit tests for the shared Fake-IP-aware SSRF policy.

These tests use fake resolvers and fake DoH transports; they never touch the
public network. Injection is through constructor parameters only, never through
a production environment switch.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "vault-capture" / "scripts" / "network_security.py"

if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))

SPEC = importlib.util.spec_from_file_location("network_security", SCRIPT)
assert SPEC and SPEC.loader
ns = importlib.util.module_from_spec(SPEC)
sys.modules["network_security"] = ns
SPEC.loader.exec_module(ns)

GLOBAL_A = "93.184.216.34"
GLOBAL_AAAA = "2606:2800:220:1:248:1893:25c8:1946"
PRIVATE_A = "10.0.0.5"
LOOPBACK = "127.0.0.1"
FAKE_IP_A = "198.18.0.7"
LINK_LOCAL = "169.254.1.1"
RESERVED = "192.0.2.1"
MALFORMED = "not-an-ip"


def make_policy(*, resolver=None, doh_transport=None, mode=ns.MODE_DEFAULT, provider=None):
    return ns.NetworkPolicy(
        mode=mode,
        doh_provider=provider,
        resolver=resolver or (lambda host, port: {GLOBAL_A}),
        doh_transport=doh_transport,
    )


class FakeResponse:
    def __init__(self, url, payload, content_type="application/json"):
        self._url = url
        self._payload = payload
        self.headers = _FakeHeaders(content_type)

    def geturl(self):
        return self._url

    def read(self, _n=-1):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeHeaders:
    def __init__(self, content_type):
        self._ct = content_type

    def get_content_type(self):
        return self._ct


class FakeOpener:
    """Minimal urllib opener that returns a fixed FakeResponse or raises."""

    def __init__(self, response=None, error=None, responses=None):
        self.response = response
        self.error = error
        self.responses = responses or {}
        self.calls = []

    def open(self, req, timeout=None):
        self.calls.append(req.full_url)
        if self.error is not None:
            raise self.error
        if req.full_url in self.responses:
            return self.responses[req.full_url]
        if self.response is not None:
            return self.response
        raise AssertionError("FakeOpener configured without a response")


def dns_json_answer(addresses, status=0):
    return json.dumps(
        {"Status": status, "Answer": [{"name": "x", "type": 1, "TTL": 60, "data": a} for a in addresses]}
    ).encode("utf-8")


class SyntaxTests(unittest.TestCase):
    def test_domain_http_https_ok(self):
        self.assertEqual(ns.validate_domain_url_syntax("https://example.com/a"), "https://example.com/a")
        self.assertEqual(ns.validate_domain_url_syntax("http://example.com/a"), "http://example.com/a")
        self.assertEqual(ns.validate_domain_url_syntax("  https://example.com/a  "), "https://example.com/a")

    def test_credentials_rejected(self):
        for url in ["https://user:pass@example.com/", "https://user@example.com/"]:
            with self.assertRaises(ns.NetworkPolicyError):
                ns.validate_domain_url_syntax(url)

    def test_non_http_rejected(self):
        for url in ["ftp://example.com/x", "file:///etc/passwd", "javascript:alert(1)"]:
            with self.assertRaises(ns.NetworkPolicyError):
                ns.validate_domain_url_syntax(url)

    def test_ip_literals_rejected(self):
        for url in [
            "https://127.0.0.1/",
            "https://93.184.216.34/",
            "https://198.18.0.7/",
            "https://[::1]/",
            "https://[2606:2800:220:1:248:1893:25c8:1946]/",
        ]:
            with self.assertRaises(ns.NetworkPolicyError):
                ns.validate_domain_url_syntax(url)

    def test_missing_host_and_bad_port_rejected(self):
        with self.assertRaises(ns.NetworkPolicyError):
            ns.validate_domain_url_syntax("https:///path")
        with self.assertRaises(ns.NetworkPolicyError):
            ns.validate_domain_url_syntax("https://example.com:notaport/")


class LegacyNumericSyntaxTests(unittest.TestCase):
    def test_legacy_numeric_ipv4_rejected(self):
        # glibc/inet_aton forms: one-part decimal, hex, octal, shorthand, and
        # canonical, including forms representing globally routable addresses.
        for literal in [
            "0x5db8d822",      # hex -> 93.184.216.34 (global)
            "2130706433",      # one-part decimal -> 127.0.0.1 (loopback)
            "0301.0250.0330.042",  # octal shorthand
            "93.184",          # two-part shorthand
            "127.1",           # two-part shorthand -> 127.0.0.1
            "0x7f000001",      # hex -> 127.0.0.1
            "1.2.3.4",         # canonical dotted
            "198.18.0.7",      # Fake-IP literal
            "93.184.216.34",   # canonical global
        ]:
            with self.subTest(literal=literal):
                with self.assertRaises(ns.NetworkPolicyError):
                    ns.validate_domain_url_syntax(f"http://{literal}/")

    def test_canonical_ipv6_rejected(self):
        for literal in ["[::1]", "[2606:2800:220:1:248:1893:25c8:1946]"]:
            with self.subTest(literal=literal):
                with self.assertRaises(ns.NetworkPolicyError):
                    ns.validate_domain_url_syntax(f"https://{literal}/")

    def test_legacy_numeric_rejected_at_validate_url(self):
        # A globally-routable numeric literal must still be rejected by the
        # full validate_url even if the resolver would classify it as global.
        policy = make_policy(resolver=lambda h, p: {"93.184.216.34"})
        for url in ["http://0x5db8d822/", "http://93.184/"]:
            with self.subTest(url=url):
                with self.assertRaises(ns.NetworkPolicyError):
                    policy.validate_url(url)

    def test_normal_domains_pass(self):
        for host in ["example.com", "localhost", "sub.example.co.uk", "foo_bar.com"]:
            with self.subTest(host=host):
                self.assertEqual(
                    ns.validate_domain_url_syntax(f"https://{host}/x"), f"https://{host}/x"
                )

    def test_idna_mapped_numeric_spellings_rejected(self):
        # Fullwidth digits and ideographic dots IDNA-map to a canonical IPv4;
        # they must be rejected at syntax (before any resolver/DoH).
        for literal in [
            "１２３.0.0.1",      # fullwidth digits
            "123。0。0。1",      # ideographic dots
            "123.0.0.１",        # mixed fullwidth digit
            "１２３。０。０。１",   # all fullwidth + ideographic dots
            "０ｘ５ｄｂ８ｄ８２２",  # fullwidth hex spellings
        ]:
            with self.subTest(literal=literal):
                with self.assertRaises(ns.NetworkPolicyError):
                    ns.validate_domain_url_syntax(f"http://{literal}/")

    def test_trailing_dot_numeric_spellings_rejected(self):
        # A single trailing dot is a legal FQDN marker, but numeric spellings
        # with a trailing dot must still be rejected as literals.
        for literal in ["1.2.3.4.", "2130706433.", "0x5db8d822.", "93.184."]:
            with self.subTest(literal=literal):
                with self.assertRaises(ns.NetworkPolicyError):
                    ns.validate_domain_url_syntax(f"http://{literal}/")

    def test_trailing_dot_and_idn_domains_allowed(self):
        # Normal FQDN trailing dot and valid IDN must remain allowed.
        for host in ["example.com.", "sub.example.org.", "例子.测试", "xn--fsqu00a.xn--0zwm56d"]:
            with self.subTest(host=host):
                self.assertEqual(
                    ns.validate_domain_url_syntax(f"https://{host}/x"), f"https://{host}/x"
                )

    def test_numeric_spellings_do_not_call_resolver(self):
        # Every numeric spelling must be rejected in validate_domain_url_syntax,
        # so the full validate_url must not call the resolver or DoH for them.
        calls = []

        def resolver(host, port):
            calls.append(host)
            return {"93.184.216.34"}

        policy = ns.NetworkPolicy(resolver=resolver)
        for literal in [
            "１２３.0.0.1",
            "123。0。0。1",
            "123.0.0.１",
            "1.2.3.4.",
            "2130706433.",
            "0x5db8d822",
        ]:
            with self.subTest(literal=literal):
                with self.assertRaises(ns.NetworkPolicyError):
                    policy.validate_url(f"http://{literal}/")
        self.assertEqual(calls, [])

    def test_idna_mapped_numeric_rejected_at_validate_url(self):
        # Even when the resolver would classify the mapped address as global,
        # full validate_url must reject at syntax (resolver never consulted).
        policy = make_policy(resolver=lambda h, p: {"93.184.216.34"})
        for url in ["http://１２３.0.0.1/", "http://1.2.3.4./"]:
            with self.subTest(url=url):
                with self.assertRaises(ns.NetworkPolicyError):
                    policy.validate_url(url)


class DoHEncodingTests(unittest.TestCase):
    def test_idn_host_converted_to_punycode_in_query(self):
        opener = FakeOpener(response=FakeResponse(ns.DOH_PROVIDERS["cloudflare"]["url"], dns_json_answer([GLOBAL_A])))
        ns._doh_query("cloudflare", "例子.测试", 1, opener=opener)
        self.assertEqual(len(opener.calls), 1)
        url = opener.calls[0]
        self.assertIn("xn--fsqu00a.xn--0zwm56d", url)
        self.assertNotIn("例子", url)

    def test_query_parameters_percent_encoded(self):
        # Reserved characters (& = space) in a hostname must be percent-encoded
        # so they cannot pollute the fixed provider's query parameters.
        opener = FakeOpener(response=FakeResponse(ns.DOH_PROVIDERS["cloudflare"]["url"], dns_json_answer([GLOBAL_A])))
        ns._doh_query("cloudflare", "a&b=c.example", 1, opener=opener)
        url = opener.calls[0]
        # Reserved characters must be percent-encoded so they cannot become a
        # real query separator or key/value delimiter.
        self.assertIn("%26", url)
        self.assertIn("%3D", url)
        self.assertNotIn("&b=", url)

    def test_doH_resolve_a_and_aaaa_use_encoded_query(self):
        base = ns.DOH_PROVIDERS["google"]["url"]
        opener = FakeOpener(
            responses={
                f"{base}?name=xn--fsqu00a.xn--0zwm56d&type=1": FakeResponse(base, dns_json_answer([GLOBAL_A])),
                f"{base}?name=xn--fsqu00a.xn--0zwm56d&type=28": FakeResponse(base, dns_json_answer([GLOBAL_AAAA])),
            }
        )
        result = ns._doh_resolve("google", "例子.测试", opener=opener)
        self.assertIn(GLOBAL_A, result)
        self.assertIn(GLOBAL_AAAA, result)

    def test_invalid_idn_safely_rejected(self):
        # A hostname that cannot be IDNA-encoded must raise a short
        # NetworkPolicyError rather than a raw Unicode traceback.
        with self.assertRaises(ns.NetworkPolicyError):
            ns.validate_domain_url_syntax("https://\ud800.Example/")

    def test_transport_error_mapped_to_policy_error(self):
        # Forcing a UnicodeEncodeError-equivalent transport failure must map to
        # NetworkPolicyError, not escape as a raw exception.
        class BadResponse:
            def geturl(self):
                return ns.DOH_PROVIDERS["cloudflare"]["url"]

            headers = _FakeHeaders("application/json")

            def read(self, _n=-1):
                return b'{"Status":0,"Answer":[]}'

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        class BadOpener:
            def open(self, req, timeout=None):
                raise UnicodeError("forced encode failure")

        with self.assertRaises(ns.NetworkPolicyError):
            ns._doh_query("cloudflare", "example.com", 1, opener=BadOpener())


class DefaultModeTests(unittest.TestCase):
    def test_all_global_passes(self):
        policy = make_policy(resolver=lambda h, p: {GLOBAL_A})
        result = policy.validate_url("https://example.com/a")
        self.assertEqual(result.url, "https://example.com/a")
        self.assertFalse(result.fake_ip_observed)

    def test_default_fake_ip_fails(self):
        policy = make_policy(resolver=lambda h, p: {FAKE_IP_A})
        with self.assertRaises(ns.NetworkPolicyError):
            policy.validate_url("https://example.com/a")

    def test_any_non_global_fails(self):
        policy = make_policy(resolver=lambda h, p: {GLOBAL_A, PRIVATE_A})
        with self.assertRaises(ns.NetworkPolicyError):
            policy.validate_url("https://example.com/a")

    def test_no_resolver_result_fails(self):
        policy = make_policy(resolver=lambda h, p: set())
        with self.assertRaises(ns.NetworkPolicyError):
            policy.validate_url("https://example.com/a")


class EnvironmentModeTests(unittest.TestCase):
    def _clear(self):
        for k in (ns.ENV_FAKE_IP_MODE, ns.ENV_DOH_PROVIDER):
            os.environ.pop(k, None)

    def test_unset_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            self._clear()
            policy = ns.NetworkPolicy.from_environment()
            self.assertEqual(policy.mode, ns.MODE_DEFAULT)
            self.assertIsNone(policy.doh_provider)

    def test_valid_clash_combinations(self):
        for provider in ("cloudflare", "google"):
            with mock.patch.dict(
                os.environ,
                {ns.ENV_FAKE_IP_MODE: "clash", ns.ENV_DOH_PROVIDER: provider},
                clear=False,
            ):
                policy = ns.NetworkPolicy.from_environment()
                self.assertEqual(policy.mode, ns.MODE_CLASH)
                self.assertEqual(policy.doh_provider, provider)

    def test_partial_fails_closed(self):
        cases = [
            {ns.ENV_FAKE_IP_MODE: "clash"},
            {ns.ENV_DOH_PROVIDER: "cloudflare"},
        ]
        for env in cases:
            with mock.patch.dict(os.environ, env, clear=False):
                self._clear()
                os.environ.update(env)
                with self.assertRaises(ns.InvalidNetworkConfig):
                    ns.NetworkPolicy.from_environment()

    def test_unknown_fails_closed(self):
        for env in [
            {ns.ENV_FAKE_IP_MODE: "clash", ns.ENV_DOH_PROVIDER: "evil.example"},
            {ns.ENV_FAKE_IP_MODE: "other", ns.ENV_DOH_PROVIDER: "cloudflare"},
            {ns.ENV_FAKE_IP_MODE: "other", ns.ENV_DOH_PROVIDER: "evil"},
        ]:
            with mock.patch.dict(os.environ, env, clear=False):
                with self.assertRaises(ns.InvalidNetworkConfig):
                    ns.NetworkPolicy.from_environment()


class ClashDoHTests(unittest.TestCase):
    def test_fake_ip_triggers_doh_and_all_public_passes(self):
        seen = []

        def doh(host):
            seen.append(host)
            return {GLOBAL_A, GLOBAL_AAAA}

        policy = make_policy(
            mode=ns.MODE_CLASH,
            provider="cloudflare",
            resolver=lambda h, p: {FAKE_IP_A},
            doh_transport=doh,
        )
        result = policy.validate_url("https://example.com/a")
        self.assertTrue(result.fake_ip_observed)
        self.assertEqual(result.provider, "cloudflare")
        self.assertEqual(seen, ["example.com"])

    def test_non_fake_system_answer_does_not_query_doh(self):
        seen = []

        def doh(host):
            seen.append(host)
            return {GLOBAL_A}

        policy = make_policy(
            mode=ns.MODE_CLASH,
            provider="cloudflare",
            resolver=lambda h, p: {GLOBAL_A},
            doh_transport=doh,
        )
        policy.validate_url("https://example.com/a")
        self.assertEqual(seen, [])

    def test_any_doh_private_answer_fails(self):
        for bad in [PRIVATE_A, LOOPBACK, LINK_LOCAL, RESERVED, FAKE_IP_A, MALFORMED]:
            policy = make_policy(
                mode=ns.MODE_CLASH,
                provider="cloudflare",
                resolver=lambda h, p: {FAKE_IP_A},
                doh_transport=lambda h: {GLOBAL_A, bad},
            )
            with self.assertRaises(ns.NetworkPolicyError):
                policy.validate_url("https://example.com/a")

    def test_doh_empty_fails(self):
        policy = make_policy(
            mode=ns.MODE_CLASH,
            provider="cloudflare",
            resolver=lambda h, p: {FAKE_IP_A},
            doh_transport=lambda h: set(),
        )
        with self.assertRaises(ns.NetworkPolicyError):
            policy.validate_url("https://example.com/a")

    def test_clash_system_non_global_fails(self):
        policy = make_policy(
            mode=ns.MODE_CLASH,
            provider="cloudflare",
            resolver=lambda h, p: {PRIVATE_A},
            doh_transport=lambda h: {GLOBAL_A},
        )
        with self.assertRaises(ns.NetworkPolicyError):
            policy.validate_url("https://example.com/a")


class DoHClientTests(unittest.TestCase):
    def test_doh_query_a_and_aaaa_via_fake_opener(self):
        opener = FakeOpener(response=FakeResponse(ns.DOH_PROVIDERS["cloudflare"]["url"], dns_json_answer([GLOBAL_A])))
        result = ns._doh_resolve("cloudflare", "example.com", opener=opener)
        self.assertIn(GLOBAL_A, result)
        self.assertEqual(len(opener.calls), 2)  # A and AAAA

    def test_a_only_aaaa_nodata_passes(self):
        # AAAA returns no Answer; A returns a global address.
        base = ns.DOH_PROVIDERS["google"]["url"]
        opener = FakeOpener(
            responses={
                f"{base}?name=example.com&type=1": FakeResponse(base, dns_json_answer([GLOBAL_A])),
                f"{base}?name=example.com&type=28": FakeResponse(base, b'{"Status":0,"Answer":[]}'),
            }
        )
        result = ns._doh_resolve("google", "example.com", opener=opener)
        self.assertIn(GLOBAL_A, result)

    def test_both_empty_fails(self):
        opener = FakeOpener(response=FakeResponse(ns.DOH_PROVIDERS["cloudflare"]["url"], b'{"Status":0,"Answer":[]}'))
        with self.assertRaises(ns.NetworkPolicyError):
            ns._doh_resolve("cloudflare", "example.com", opener=opener)

    def test_nonzero_dns_status_fails(self):
        opener = FakeOpener(response=FakeResponse(ns.DOH_PROVIDERS["cloudflare"]["url"], b'{"Status":3,"Answer":[]}'))
        with self.assertRaises(ns.NetworkPolicyError):
            ns._doh_query("cloudflare", "example.com", 1, opener=opener)

    def test_malformed_json_fails(self):
        opener = FakeOpener(response=FakeResponse(ns.DOH_PROVIDERS["cloudflare"]["url"], b"not json"))
        with self.assertRaises(ns.NetworkPolicyError):
            ns._doh_query("cloudflare", "example.com", 1, opener=opener)

    def test_oversized_json_fails(self):
        big = dns_json_answer([GLOBAL_A]) + b"x" * (ns.DOH_MAX_BYTES + 1)
        opener = FakeOpener(response=FakeResponse(ns.DOH_PROVIDERS["cloudflare"]["url"], big))
        with self.assertRaises(ns.NetworkPolicyError):
            ns._doh_query("cloudflare", "example.com", 1, opener=opener)

    def test_wrong_content_type_fails(self):
        opener = FakeOpener(
            response=FakeResponse(
                ns.DOH_PROVIDERS["cloudflare"]["url"],
                dns_json_answer([GLOBAL_A]),
                content_type="text/html",
            )
        )
        with self.assertRaises(ns.NetworkPolicyError):
            ns._doh_query("cloudflare", "example.com", 1, opener=opener)

    def test_redirect_rejected(self):
        # A response from a redirected (different) URL must fail closed.
        opener = FakeOpener(
            response=FakeResponse("https://evil.example/dns-query", dns_json_answer([GLOBAL_A]))
        )
        with self.assertRaises(ns.NetworkPolicyError):
            ns._doh_query("cloudflare", "example.com", 1, opener=opener)

    def test_http_error_fails(self):
        from urllib.error import HTTPError

        opener = FakeOpener(error=HTTPError("url", 500, "err", {}, io.BytesIO()))
        with self.assertRaises(ns.NetworkPolicyError):
            ns._doh_query("cloudflare", "example.com", 1, opener=opener)


class ProviderFixednessTests(unittest.TestCase):
    def test_providers_are_fixed_https_endpoints(self):
        for provider in ns.DOH_PROVIDERS.values():
            self.assertTrue(provider["url"].startswith("https://"))
            self.assertNotIn("@", provider["url"])

    def test_arbitrary_provider_rejected(self):
        with mock.patch.dict(
            os.environ,
            {ns.ENV_FAKE_IP_MODE: "clash", ns.ENV_DOH_PROVIDER: "https://evil.example/dns-query"},
            clear=False,
        ):
            with self.assertRaises(ns.InvalidNetworkConfig):
                ns.NetworkPolicy.from_environment()

    def test_http_provider_rejected(self):
        with mock.patch.dict(
            os.environ,
            {ns.ENV_FAKE_IP_MODE: "clash", ns.ENV_DOH_PROVIDER: "http://cloudflare-dns.com/dns-query"},
            clear=False,
        ):
            with self.assertRaises(ns.InvalidNetworkConfig):
                ns.NetworkPolicy.from_environment()


class RevalidationTests(unittest.TestCase):
    def test_every_validate_url_revalidates_no_cache(self):
        # The policy must not skip address validation for repeated or distinct
        # targets; the resolver is invoked for each call.
        calls = []

        def resolver(host, port):
            calls.append(host)
            return {GLOBAL_A}

        policy = make_policy(resolver=resolver)
        for _ in range(3):
            policy.validate_url("https://example.com/a")
        self.assertEqual(len(calls), 3)

    def test_distinct_hosts_each_validated(self):
        calls = []

        def resolver(host, port):
            calls.append(host)
            return {GLOBAL_A}

        policy = make_policy(resolver=resolver)
        policy.validate_url("https://one.example/a")
        policy.validate_url("https://two.example/b")
        self.assertEqual(sorted(calls), ["one.example", "two.example"])


if __name__ == "__main__":
    unittest.main()
