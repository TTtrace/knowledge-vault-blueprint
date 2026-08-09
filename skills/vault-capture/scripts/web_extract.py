#!/usr/bin/env python3
"""Deterministic web article extraction for vault-capture.

Static HTTP fetch first, then Trafilatura generic extraction, with a
dedicated WeChat adapter and Playwright rendered-page fallback.
"""

from __future__ import annotations

import os
import re
import socket
import ssl
import sys
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request

# Make the sibling shared policy importable when this file is executed directly
# or loaded by tests via a module spec.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import network_security

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
MAX_RESPONSE_BYTES = 25 * 1024 * 1024
CONNECT_TIMEOUT = 15
MAX_REDIRECTS = 5
MIN_BODY_CHARS = 200

WECHAT_HOST = "mp.weixin.qq.com"

WECHAT_CHALLENGE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"verif(y|ication)",
        r"captcha",
        r"rate.?limit",
        r"too many requests",
    ]
]
WECHAT_CHALLENGE_CN = [
    "\u8bf7\u5b8c\u6210\u5b89\u5168\u9a8c\u8bc1",
    "\u73af\u5883\u5f02\u5e38",
    "\u8bbf\u95ee\u8fc7\u4e8e\u9891\u7e41",
    "\u53bb\u9a8c\u8bc1",
    "\u8bf7\u5728\u5fae\u4fe1\u5ba2\u6237\u7aef\u6253\u5f00",
]

TRACKING_IMG_RE = re.compile(
    r"(?:spm|track|pixel|beacon|stat|counter|analytics|logo|avatar|qrcode|qr_code|icon)",
    re.IGNORECASE,
)
PX_1X1_RE = re.compile(r"[_-](?:1x1|1_1|1px|tracking|beacon|spacer|blank)[_.-]", re.IGNORECASE)

# Void elements have no closing tag; they must not perturb depth tracking.
VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class ExtractionError(Exception):
    def __init__(
        self,
        reason: str,
        *,
        state: str = "failed",
        recoverable: bool = True,
        methods_attempted: list[str] | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.state = state
        self.recoverable = recoverable
        self.methods_attempted: list[str] = list(methods_attempted) if methods_attempted else []


@dataclass
class ImageRef:
    token: str
    url: str
    alt: str = ""


@dataclass
class ExtractionResult:
    title: str
    author: list[str] = field(default_factory=list)
    publisher: str = ""
    published: str = ""
    markdown: str = ""
    images: list[ImageRef] = field(default_factory=list)
    final_url: str = ""
    language: str = ""
    method: str = ""
    body_length: int = 0
    methods_attempted: list[str] = field(default_factory=list)


def _ensure_policy(policy) -> "network_security.NetworkPolicy":
    """Resolve a caller-supplied policy or build one from the environment.

    Tests may inject a scoped fake policy; production always builds from the
    environment (which fails closed on invalid Fake-IP configuration).
    """
    if policy is not None:
        return policy
    return network_security.NetworkPolicy.from_environment()


def _validate_url(url: str, *, policy=None) -> str:
    """Validate a URL through the shared policy and return its URL form.

    Raises ExtractionError (mapped from NetworkPolicyError) on failure.
    """
    return _run_policy(lambda p: p.validate_url(url), policy).url


def _run_policy(action, policy=None):
    """Run an action against a resolved policy, mapping failures to ExtractionError."""
    resolved = _ensure_policy(policy)
    try:
        return action(resolved)
    except network_security.NetworkPolicyError as exc:
        raise ExtractionError(exc.reason, state="failed", recoverable=exc.recoverable) from exc


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent urllib from following redirects automatically.

    Redirects are handled manually so each Location can be validated before a
    new connection is made.
    """

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


def static_fetch(url: str, *, policy=None) -> tuple[str, str, str]:
    """Fetch a URL via static HTTP with size/timeout/redirect limits.

    Returns (final_url, content_type, html_text).
    """
    current_url = _validate_url(url, policy=policy)
    opener = urllib.request.build_opener(_NoRedirectHandler)
    for redirect_count in range(MAX_REDIRECTS + 1):
        req = Request(
            current_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "identity",
            },
        )
        try:
            ctx = ssl.create_default_context()
            with opener.open(req, timeout=CONNECT_TIMEOUT) as response:
                final_url = response.geturl()
                content_type = response.headers.get_content_type().lower()
                if content_type not in {"text/html", "application/xhtml+xml"}:
                    raise ExtractionError(
                        f"Unsupported content type: {content_type}",
                        state="failed",
                        recoverable=False,
                    )
                charset = response.headers.get_content_charset() or "utf-8"
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ExtractionError("Response exceeds maximum size", state="failed")
                try:
                    html = raw.decode(charset, errors="replace")
                except (LookupError, TypeError):
                    html = raw.decode("utf-8", errors="replace")
                return final_url, content_type, html
        except HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                location = exc.headers.get("Location")
                if not location or redirect_count >= MAX_REDIRECTS:
                    raise ExtractionError("Too many redirects", state="failed") from exc
                current_url = urljoin(current_url, location)
                # Validate the redirect target before the next connection.
                current_url = _validate_url(current_url, policy=policy)
                continue
            if 500 <= exc.code < 600:
                raise ExtractionError(f"HTTP {exc.code}", state="failed") from exc
            if exc.code == 429:
                raise ExtractionError("Rate limited", state="manual", recoverable=True) from exc
            if exc.code in (401, 403):
                reason = {401: "Authentication required", 403: "Access denied"}[exc.code]
                raise ExtractionError(reason, state="manual", recoverable=False) from exc
            raise ExtractionError(f"HTTP {exc.code}", state="failed", recoverable=False) from exc
        except URLError as exc:
            reason = str(exc.reason) if exc.reason else "Network error"
            rl = reason.lower()
            if "timed out" in rl or "timeout" in rl:
                raise ExtractionError("Connection timed out", state="failed") from exc
            if "name or service not known" in rl or "getaddrinfo" in rl:
                raise ExtractionError("Host could not be resolved", state="failed") from exc
            raise ExtractionError("Network error", state="failed") from exc
        except (socket.timeout, TimeoutError) as exc:
            raise ExtractionError("Connection timed out", state="failed") from exc
    raise ExtractionError("Too many redirects", state="failed")


# ---------------------------------------------------------------------------
# WeChat adapter
# ---------------------------------------------------------------------------

class _WeChatMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.author = ""
        self.account = ""
        self.publish_time = ""
        self._in_title = False
        self._in_author = False
        self._in_account = False
        self._in_publish = False
        self._content_enter_depth = 0
        self._in_content = 0
        self.images: list[dict[str, str]] = []
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        elem_id = attr_dict.get("id", "")
        classes = attr_dict.get("class", "")
        if elem_id == "activity-name":
            self._in_title = True
        if "rich_media_meta_text" in classes and not self.author:
            self._in_author = True
        if elem_id == "js_name":
            self._in_account = True
        if elem_id == "publish_time":
            self._in_publish = True
        if elem_id == "js_content":
            self._in_content += 1
            self._content_enter_depth = self._depth
        if self._in_content and tag == "img":
            src = (
                attr_dict.get("data-src")
                or attr_dict.get("data-original")
                or attr_dict.get("src", "")
            )
            alt = attr_dict.get("alt", "")
            if src and _is_valid_wechat_image(src, attr_dict):
                self.images.append({"url": src, "alt": alt})
        if tag not in VOID_ELEMENTS:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag not in VOID_ELEMENTS:
            self._depth -= 1
        self._in_title = False
        self._in_author = False
        self._in_account = False
        self._in_publish = False
        if self._in_content and self._depth <= self._content_enter_depth:
            self._in_content = 0

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif self._in_author:
            self.author += data
        elif self._in_account:
            self.account += data
        elif self._in_publish:
            self.publish_time += data

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "img" and self._in_content:
            attr_dict = {k.lower(): (v or "") for k, v in attrs}
            src = (
                attr_dict.get("data-src")
                or attr_dict.get("data-original")
                or attr_dict.get("src", "")
            )
            alt = attr_dict.get("alt", "")
            if src and _is_valid_wechat_image(src, attr_dict):
                self.images.append({"url": src, "alt": alt})


def _is_valid_wechat_image(url: str, attrs: dict[str, str]) -> bool:
    if not url:
        return False
    if url.startswith("data:"):
        return False
    lowered = url.lower()
    if TRACKING_IMG_RE.search(lowered):
        return False
    if PX_1X1_RE.search(lowered):
        return False
    if lowered.endswith(".svg") or "image/svg" in lowered:
        return False
    width = attrs.get("data-w", attrs.get("width", ""))
    height = attrs.get("data-h", attrs.get("height", ""))
    try:
        w = int(width) if width else 0
        h = int(height) if height else 0
        if w and h and (w <= 5 or h <= 5):
            return False
    except (ValueError, TypeError):
        pass
    return True


def _detect_wechat_challenge(html: str) -> str | None:
    head_end = html.lower().find("</head>")
    if head_end < 0:
        head_end = min(len(html), 5000)
    head_section = html[:head_end]
    body_start = html.lower().find("<body")
    body_section = html[body_start : body_start + 3000] if body_start >= 0 else html[:3000]
    check_text = head_section + "\n" + body_section
    for cn in WECHAT_CHALLENGE_CN:
        if cn in check_text:
            if "\u9891\u7e41" in cn or "rate" in cn.lower():
                return "Rate limited; try again later"
            return "Verification required"
    for pattern in WECHAT_CHALLENGE_PATTERNS:
        if pattern.search(check_text):
            label = pattern.pattern.lower()
            if "rate" in label or "many" in label:
                return "Rate limited; try again later"
            return "Verification required"
    if "js_content" not in html:
        for cn in ["\u9a8c\u8bc1", "\u73af\u5883\u5f02\u5e38"]:
            if cn in check_text:
                return "Verification required"
    return None


def _normalise_wechat_date(raw: str) -> str:
    raw = raw.strip()
    m = re.search(r"(\d{4})[-\u5e74/](\d{1,2})[-\u6708/](\d{1,2})", raw)
    if m:
        y, mo, d = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    return ""


def _absolutise_wechat_url(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://mp.weixin.qq.com" + url
    return url


class _WeChatBodyExtractor(HTMLParser):
    def __init__(self, images: list[ImageRef]) -> None:
        super().__init__()
        self._content_enter_depth = 0
        self._in_content = 0
        self._depth = 0
        self._chunks: list[str] = []
        self._image_map = {img.url: img for img in images}
        self._skip_depth = 0
        self._current_link = ""
        self._list_depth = 0
        self._in_pre = False
        self._in_blockquote = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        if attr_dict.get("id") == "js_content":
            self._in_content = 1
            self._content_enter_depth = self._depth
        if tag not in VOID_ELEMENTS:
            self._depth += 1
        if not self._in_content:
            return
        if tag in ("script", "style", "noscript"):
            self._skip_depth = self._depth
            return
        if self._skip_depth:
            return
        if tag == "img":
            src = (
                attr_dict.get("data-src")
                or attr_dict.get("data-original")
                or attr_dict.get("src", "")
            )
            if src:
                src = _absolutise_wechat_url(src)
                img = self._image_map.get(src)
                if img:
                    alt = img.alt or "image"
                    self._chunks.append(f"\n\n![{alt}](vault-image://{img.token})\n\n")
            return
        if tag in ("p", "div", "section"):
            self._chunks.append("\n")
        elif tag == "br":
            self._chunks.append("\n")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self._chunks.append(f"\n\n{'#' * level} ")
        elif tag == "blockquote":
            self._in_blockquote += 1
            self._chunks.append("\n")
        elif tag in ("ul", "ol"):
            self._list_depth += 1
            self._chunks.append("\n")
        elif tag == "li":
            indent = "  " * (self._list_depth - 1)
            self._chunks.append(f"\n{indent}- ")
        elif tag in ("strong", "b"):
            self._chunks.append("**")
        elif tag in ("em", "i"):
            self._chunks.append("*")
        elif tag == "a":
            href = attr_dict.get("href", "")
            if href and not href.startswith("javascript:"):
                self._chunks.append("[")
                self._current_link = href
        elif tag == "pre":
            self._in_pre = True
            self._chunks.append("\n\n```\n")
        elif tag == "code" and not self._in_pre:
            self._chunks.append("`")
        elif tag == "table":
            self._chunks.append("\n\n")
        elif tag == "tr":
            self._chunks.append("\n")
        elif tag in ("td", "th"):
            self._chunks.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        if tag not in VOID_ELEMENTS:
            self._depth -= 1
        if self._skip_depth:
            if self._depth < self._skip_depth:
                self._skip_depth = 0
            return
        if not self._in_content:
            return
        if tag in ("script", "style", "noscript"):
            return
        if tag in ("p", "div", "section"):
            self._chunks.append("\n")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._chunks.append("\n")
        elif tag == "blockquote":
            self._in_blockquote = max(0, self._in_blockquote - 1)
            self._chunks.append("\n")
        elif tag in ("ul", "ol"):
            self._list_depth = max(0, self._list_depth - 1)
            self._chunks.append("\n")
        elif tag in ("strong", "b"):
            self._chunks.append("**")
        elif tag in ("em", "i"):
            self._chunks.append("*")
        elif tag == "a":
            if self._current_link:
                self._chunks.append(f"]({self._current_link})")
                self._current_link = ""
        elif tag == "pre":
            self._in_pre = False
            self._chunks.append("\n```\n\n")
        elif tag == "code" and not self._in_pre:
            self._chunks.append("`")
        if self._in_content and self._depth <= self._content_enter_depth:
            self._in_content = 0

    def handle_data(self, data: str) -> None:
        if self._in_content and not self._skip_depth:
            if self._in_blockquote:
                for line in data.splitlines(keepends=True):
                    stripped = line.rstrip("\n")
                    self._chunks.append("> " + stripped + "\n")
            else:
                self._chunks.append(data)

    def get_markdown(self) -> str:
        text = "".join(self._chunks)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        return text.strip()


def _wechat_html_to_markdown(html: str, images: list[ImageRef]) -> str:
    extractor = _WeChatBodyExtractor(images)
    try:
        extractor.feed(html)
    except Exception:
        return ""
    return extractor.get_markdown()


def extract_wechat(html: str, url: str) -> ExtractionResult | None:
    challenge = _detect_wechat_challenge(html)
    if challenge:
        lowered = challenge.lower()
        is_manual = "verif" in lowered or "restrict" in lowered or "rate" in lowered
        state = "manual" if is_manual else "failed"
        raise ExtractionError(challenge, state=state, recoverable=(state == "failed"))
    parser = _WeChatMetaParser()
    try:
        parser.feed(html)
    except Exception as exc:
        raise ExtractionError("WeChat HTML parse error", state="failed") from exc
    title = parser.title.strip()
    if not title or "js_content" not in html:
        return None
    author = parser.author.strip()
    account = parser.account.strip()
    published = _normalise_wechat_date(parser.publish_time)
    images: list[ImageRef] = []
    seen_urls: set[str] = set()
    for i, img in enumerate(parser.images):
        img_url = _absolutise_wechat_url(img["url"])
        if img_url in seen_urls:
            continue
        seen_urls.add(img_url)
        token = f"img{i + 1:03d}"
        images.append(ImageRef(token=token, url=img_url, alt=img.get("alt", "")))
    markdown = _wechat_html_to_markdown(html, images)
    return ExtractionResult(
        title=title,
        author=[author] if author else [],
        publisher=account,
        published=published,
        markdown=markdown,
        images=images,
        final_url=url,
        method="wechat-static",
        body_length=len(markdown),
    )


# ---------------------------------------------------------------------------
# Generic extraction via Trafilatura
# ---------------------------------------------------------------------------

def _extract_title_from_html(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return ""


class _GenericHtmlToMarkdown(HTMLParser):
    """Convert Trafilatura's cleaned article HTML to preservation-safe Markdown.

    Trafilatura's own Markdown mode drops blockquote markers and code language,
    so we convert its cleaned HTML output instead. This handles standard tags
    plus Trafilatura's normalised forms (``graphic``, ``row``/``cell``, and
    double-nested ``pre``).
    """

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._depth = 0
        self._pre_depth = 0
        self._code_lang = ""
        self._languages: list[str] = []
        self._list_stack: list[bool] = []  # True = ordered
        self._in_blockquote = 0
        self._link_href = ""
        self._skip_depth = 0
        self._table_rows: list[list[str]] = []
        self._table_headers: list[str] = []
        self._current_row: list[str] = []
        self._current_cell: list[str] = []
        self._in_cell = False
        self._in_figure = 0
        self._caption_chunks: list[str] | None = None
        self._caption_text: str = ""

    def _flush_cell(self) -> None:
        if self._in_cell:
            self._current_row.append("".join(self._current_cell).strip())
            self._current_cell = []
            self._in_cell = False

    def _flush_row(self) -> None:
        self._flush_cell()
        if self._current_row:
            self._table_rows.append(self._current_row)
            self._current_row = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        if tag in ("script", "style", "noscript"):
            self._skip_depth = self._depth
            self._depth += 1
            return
        if self._skip_depth:
            self._depth += 1
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._chunks.append(f"\n\n{'#' * int(tag[1])} ")
        elif tag == "p":
            self._chunks.append("\n\n")
        elif tag == "blockquote":
            self._in_blockquote += 1
            self._chunks.append("\n\n")
        elif tag == "br":
            self._chunks.append("\n")
        elif tag in ("ul", "ol"):
            self._list_stack.append(tag == "ol")
            self._chunks.append("\n")
        elif tag == "li":
            indent = "  " * (len(self._list_stack) - 1) if self._list_stack else ""
            marker = "1. " if (self._list_stack and self._list_stack[-1]) else "- "
            self._chunks.append(f"\n{indent}{marker}")
        elif tag in ("strong", "b"):
            self._chunks.append("**")
        elif tag in ("em", "i"):
            self._chunks.append("*")
        elif tag == "a":
            href = attr_dict.get("href", "")
            if href and not href.startswith("javascript:"):
                self._chunks.append("[")
                self._link_href = href
        elif tag == "pre":
            self._pre_depth += 1
            if self._pre_depth == 1:
                if not self._code_lang and self._languages:
                    self._code_lang = self._languages.pop(0)
                self._chunks.append("\n\n```" + self._code_lang + "\n")
        elif tag == "code":
            if self._pre_depth == 0:
                self._chunks.append("`")
            else:
                lang = attr_dict.get("class", "")
                m = re.search(r"language-([a-zA-Z0-9_+-]+)", lang)
                if m:
                    self._code_lang = m.group(1)
        elif tag in ("table",):
            self._chunks.append("\n\n")
        elif tag in ("tr", "row"):
            self._flush_row()
        elif tag in ("td", "th", "cell"):
            self._flush_cell()
            self._in_cell = True
        elif tag in ("figure",):
            self._in_figure += 1
            self._chunks.append("\n\n")
        elif tag in ("figcaption",):
            self._caption_chunks = []
            self._chunks.append("\n")
        elif tag == "img":
            src = attr_dict.get("data-src") or attr_dict.get("data-original") or attr_dict.get("src", "")
            alt = attr_dict.get("alt", "")
            if src:
                if self._in_figure == 0:
                    self._chunks.append(f"\n\n![{alt}]({src})\n\n")
                else:
                    self._chunks.append(f"![{alt}]({src})")
        elif tag == "graphic":
            src = attr_dict.get("src", "")
            alt = attr_dict.get("alt", "")
            if self._in_figure == 0:
                self._chunks.append(f"\n\n![{alt}]({src})\n\n")
            else:
                self._chunks.append(f"![{alt}]({src})")
        if tag not in VOID_ELEMENTS:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth:
            self._depth -= 1
            if self._depth <= self._skip_depth:
                self._skip_depth = 0
            return
        if tag not in VOID_ELEMENTS:
            self._depth -= 1
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._chunks.append("\n")
        elif tag == "p":
            self._chunks.append("\n")
        elif tag == "blockquote":
            self._in_blockquote = max(0, self._in_blockquote - 1)
            self._chunks.append("\n")
        elif tag in ("strong", "b"):
            self._chunks.append("**")
        elif tag in ("em", "i"):
            self._chunks.append("*")
        elif tag == "a":
            if self._link_href:
                self._chunks.append(f"]({self._link_href})")
                self._link_href = ""
        elif tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
            self._chunks.append("\n")
        elif tag == "pre":
            self._pre_depth = max(0, self._pre_depth - 1)
            if self._pre_depth == 0:
                self._chunks.append("\n```\n\n")
                self._code_lang = ""
        elif tag == "code":
            if self._pre_depth == 0:
                self._chunks.append("`")
        elif tag in ("tr", "row"):
            self._flush_row()
        elif tag in ("td", "th", "cell"):
            self._flush_cell()
        elif tag == "table":
            self._flush_row()
            rendered = _render_table(self._table_rows)
            if rendered:
                self._chunks.append(rendered)
            self._table_rows = []
            self._table_headers = []
        elif tag == "figure":
            self._in_figure = max(0, self._in_figure - 1)
            if self._caption_text:
                self._chunks.append(f"\n> 图注：{self._caption_text}\n")
            self._caption_text = ""
            self._caption_chunks = None
            self._chunks.append("\n")
        elif tag == "figcaption":
            if self._caption_chunks is not None:
                self._caption_text = "".join(self._caption_chunks).strip()
            self._caption_chunks = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_cell:
            self._current_cell.append(data)
            return
        if self._caption_chunks is not None:
            self._caption_chunks.append(data)
            return
        if self._in_blockquote:
            for line in data.splitlines(keepends=True):
                stripped = line.rstrip("\n")
                self._chunks.append("> " + stripped + "\n")
        else:
            self._chunks.append(data)

    def get_markdown(self) -> str:
        text = "".join(self._chunks)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n>\s*\n", "\n> \n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def _render_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    widths = len(max(rows, key=len))
    normalized: list[list[str]] = []
    for row in rows:
        row = [cell.replace("|", "\\|") for cell in row]
        while len(row) < widths:
            row.append("")
        normalized.append(row[:widths])
    header = normalized[0]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for row in normalized[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _extract_code_languages(html: str) -> list[str]:
    languages: list[str] = []
    for match in re.finditer(r'<code[^>]*class="[^"]*language-([a-zA-Z0-9_+-]+)[^"]*"', html, re.IGNORECASE):
        lang = match.group(1)
        if lang not in languages:
            languages.append(lang)
    return languages


def _generic_html_to_markdown(cleaned_html: str, original_html: str = "") -> str:
    parser = _GenericHtmlToMarkdown()
    parser._languages = _extract_code_languages(original_html)
    try:
        parser.feed(cleaned_html)
    except Exception:
        return ""
    return parser.get_markdown()


def _extract_images_from_markdown(markdown: str, base_url: str) -> list[ImageRef]:
    images: list[ImageRef] = []
    seen: set[str] = set()
    pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    idx = 0
    for match in pattern.finditer(markdown):
        alt = match.group(1)
        url = match.group(2).strip()
        if url.startswith("data:"):
            continue
        if url.startswith("vault-image://"):
            continue
        if TRACKING_IMG_RE.search(url) or PX_1X1_RE.search(url):
            continue
        full_url = urljoin(base_url, url)
        if full_url in seen:
            continue
        seen.add(full_url)
        idx += 1
        token = f"img{idx:03d}"
        images.append(ImageRef(token=token, url=full_url, alt=alt))
    return images


def _rewrite_image_tokens(markdown: str, images: list[ImageRef], base_url: str = "") -> str:
    url_to_token = {img.url: img.token for img in images}

    def replacer(match: re.Match[str]) -> str:
        alt = match.group(1)
        url = match.group(2).strip()
        if url.startswith("vault-image://") or url.startswith("data:"):
            return match.group(0)
        lookup_url = urljoin(base_url, url) if base_url else url
        if lookup_url in url_to_token:
            return f"![{alt}](vault-image://{url_to_token[lookup_url]})"
        return match.group(0)

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replacer, markdown)


def _extract_figcaptions(html: str, base_url: str) -> dict[str, str]:
    """Extract image src → figcaption text mapping from original HTML."""
    captions: dict[str, str] = {}
    pattern = re.compile(
        r"<figure[^>]*>(.*?)</figure>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html):
        block = match.group(1)
        src_match = re.search(r'<img[^>]*\ssrc="([^"]*)"', block, re.IGNORECASE)
        cap_match = re.search(r"<figcaption[^>]*>(.*?)</figcaption>", block, re.IGNORECASE | re.DOTALL)
        if src_match and cap_match:
            raw_src = src_match.group(1)
            full_src = urljoin(base_url, raw_src)
            caption = re.sub(r"<[^>]+>", "", cap_match.group(1)).strip()
            if caption:
                captions[full_src] = caption
    return captions


def extract_generic(html: str, url: str) -> ExtractionResult | None:
    try:
        import trafilatura
    except ImportError as exc:
        raise ExtractionError(
            "trafilatura is not installed; run pip install -r requirements-web.txt",
            state="failed",
            recoverable=False,
        ) from exc

    figcaptions = _extract_figcaptions(html, url)

    downloaded = trafilatura.load_html(html)
    if downloaded is None:
        return None

    metadata = trafilatura.extract_metadata(downloaded)
    title = ""
    author: list[str] = []
    publisher = ""
    published = ""
    if metadata is not None:
        title = (metadata.title or "").strip()
        if metadata.author:
            author = [a.strip() for a in re.split(r"[,;]", metadata.author) if a.strip()]
        publisher = (metadata.sitename or "").strip()
        date_str = metadata.date or ""
        if date_str:
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_str)
            if m:
                published = m.group(0)

    cleaned_html = trafilatura.extract(
        downloaded,
        output_format="html",
        include_links=True,
        include_images=True,
        include_tables=True,
        include_formatting=True,
        include_comments=False,
        favor_recall=True,
    )

    if not cleaned_html or not cleaned_html.strip():
        return None

    markdown = _generic_html_to_markdown(cleaned_html, html)
    if not markdown or not markdown.strip():
        return None

    images = _extract_images_from_markdown(markdown, url)
    markdown = _rewrite_image_tokens(markdown, images, base_url=url)

    for img in images:
        caption = figcaptions.get(img.url)
        if caption:
            markdown = markdown.replace(
                f"](vault-image://{img.token})",
                f"](vault-image://{img.token})\n\n> 图注：{caption}\n",
                1,
            )

    if not title:
        title = _extract_title_from_html(html)

    return ExtractionResult(
        title=title or url,
        author=author,
        publisher=publisher,
        published=published,
        markdown=markdown.strip(),
        images=images,
        final_url=url,
        method="trafilatura",
        body_length=len(markdown.strip()),
    )


# ---------------------------------------------------------------------------
# Playwright rendered-page fallback
# ---------------------------------------------------------------------------

def _scroll_for_lazy_images(page: Any) -> None:
    try:
        page.evaluate(
            """
            async () => {
                await new Promise((resolve) => {
                    let totalHeight = 0;
                    const distance = 500;
                    const timer = setInterval(() => {
                        const scrollHeight = document.body.scrollHeight;
                        window.scrollBy(0, distance);
                        totalHeight += distance;
                        if (totalHeight >= scrollHeight) {
                            clearInterval(timer);
                            window.scrollTo(0, 0);
                            resolve();
                        }
                    }, 100);
                });
            }
            """
        )
    except Exception:
        pass


def _make_navigation_guard(policy=None):
    """Create a Playwright route handler that validates every request URL.

    Documents and subresources are both validated, so a public page whose
    subresource (or a redirect target) points at a private/non-global address
    is aborted before a connection is made. Playwright invokes the handler for
    each request, including redirected ones, so redirect targets are covered.
    """
    from playwright.sync_api import Route

    # Explicitly required local browser schemes that do not open an external
    # connection. Everything else non-HTTP(S) (including `file`) is aborted so
    # the guard is deny-by-default at the policy layer.
    LOCAL_SCHEMES = {"data", "blob", "about", "chrome"}

    resolved = _ensure_policy(policy)

    def handler(route: Route) -> None:
        url = route.request.url
        try:
            parts = urlsplit(url)
            scheme = parts.scheme.lower()
            if scheme in {"http", "https"}:
                resolved.validate_url(url)
            elif scheme in LOCAL_SCHEMES:
                # Local browser scheme: no external connection; allow explicitly.
                pass
            else:
                # Unapproved non-HTTP(S) scheme (e.g. file:): abort.
                route.abort()
                return
        except network_security.NetworkPolicyError:
            route.abort()
            return
        route.continue_()

    return handler


def playwright_fetch(
    url: str,
    *,
    profile_dir: str | None = None,
    timeout_ms: int = 30000,
    policy=None,
) -> tuple[str, str]:
    _validate_url(url, policy=policy)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ExtractionError(
            "playwright is not installed; run pip install -r requirements-web.txt",
            state="failed",
            recoverable=False,
        ) from exc

    launch_args = ["--no-sandbox", "--disable-dev-shm-usage"]
    lock_path: Path | None = None
    if profile_dir:
        profile_path = Path(profile_dir)
        profile_path.mkdir(parents=True, exist_ok=True)
        lock_path = profile_path / ".vault-capture.lock"
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, b"locked")
            os.close(fd)
        except FileExistsError as exc:
            raise ExtractionError(
                "Browser profile is in use by another process",
                state="failed",
                recoverable=False,
            ) from exc

    try:
        with sync_playwright() as p:
            guard = _make_navigation_guard(policy)
            if profile_dir:
                context = p.chromium.launch_persistent_context(
                    profile_dir,
                    args=launch_args,
                    user_agent=USER_AGENT,
                    locale="zh-CN",
                    viewport={"width": 1280, "height": 900},
                )
                browser = None
            else:
                browser = p.chromium.launch(args=launch_args)
                context = browser.new_context(
                    user_agent=USER_AGENT,
                    locale="zh-CN",
                    viewport={"width": 1280, "height": 900},
                )
            try:
                context.route("**/*", guard)
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                _scroll_for_lazy_images(page)
                try:
                    page.wait_for_selector("#js_content", timeout=5000)
                except Exception:
                    pass
                final_url = page.url
                # Re-validate the final document URL; never mark a page ready
                # that resolved to an unsafe address.
                _validate_url(final_url, policy=policy)
                html = page.content()
            finally:
                context.close()
                if browser:
                    browser.close()
        return final_url, html
    except ExtractionError:
        raise
    except Exception as exc:
        reason = str(exc)
        rl = reason.lower()
        if "timeout" in rl or "timed out" in rl:
            raise ExtractionError("Browser render timed out", state="failed") from exc
        if "browser" in rl or "chromium" in rl or "executable" in rl:
            raise ExtractionError(
                "Browser is not available; install Chromium",
                state="failed",
                recoverable=False,
            ) from exc
        raise ExtractionError("Browser render failed", state="failed") from exc
    finally:
        if lock_path and lock_path.exists():
            try:
                lock_path.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Quality gates
# ---------------------------------------------------------------------------

def quality_gate(result: ExtractionResult) -> None:
    if not result.title or not result.title.strip():
        raise ExtractionError("Title is missing", state="failed", recoverable=False)
    body = result.markdown.strip()
    if not body:
        raise ExtractionError("Article body is empty", state="failed")
    text_only = re.sub(r"!\[[^\]]*\]\(vault-image://[^)]+\)", "", body)
    text_only = re.sub(r"[#*`>\-|\s]", "", text_only)
    if len(text_only) < MIN_BODY_CHARS:
        raise ExtractionError(
            "Article body is too short (title-only or metadata-only extraction)",
            state="failed",
        )
    md_tokens = re.findall(r"vault-image://([a-zA-Z0-9_-]+)", body)
    manifest_tokens = {img.token for img in result.images}
    if len(md_tokens) != len(set(md_tokens)):
        raise ExtractionError("Duplicate image tokens in Markdown", state="failed", recoverable=False)
    if set(md_tokens) != manifest_tokens:
        raise ExtractionError(
            "Markdown image tokens do not match image manifest",
            state="failed",
            recoverable=False,
        )


# ---------------------------------------------------------------------------
# Main extraction orchestration
# ---------------------------------------------------------------------------

def is_wechat_url(url: str) -> bool:
    parts = urlsplit(url)
    return bool(parts.hostname and parts.hostname.lower() == WECHAT_HOST)


def _try_playwright(
    url: str,
    *,
    wechat: bool,
    profile_dir: str | None,
    policy,
) -> ExtractionResult:
    final_url, html = playwright_fetch(
        url,
        profile_dir=profile_dir,
        policy=policy,
    )
    if wechat:
        challenge = _detect_wechat_challenge(html)
        if challenge:
            lowered = challenge.lower()
            is_manual = "verif" in lowered or "restrict" in lowered or "rate" in lowered
            state = "manual" if is_manual else "failed"
            raise ExtractionError(challenge, state=state, recoverable=(state == "failed"))
        result = extract_wechat(html, final_url)
        if result is not None:
            result.method = "wechat-browser"
            return result
    result = extract_generic(html, final_url)
    if result is not None:
        result.method = "browser-trafilatura"
        return result
    raise ExtractionError("Rendered page extraction produced no content", state="failed")


BROWSER_METHOD = "browser"


def _attempt_browser(
    *,
    url: str,
    wechat: bool,
    profile_dir: str | None,
    policy,
    methods: list[str],
) -> ExtractionResult:
    """Run the Playwright fallback, recording that the browser was attempted.

    The browser marker is recorded even when the fallback raises (for example a
    WeChat verification/rate-limit `manual` challenge), so callers can prove
    static extraction was rejected and the browser fallback actually ran.
    """
    try:
        result = _try_playwright(
            url,
            wechat=wechat,
            profile_dir=profile_dir,
            policy=policy,
        )
        methods.append(result.method)
        quality_gate(result)
        result.methods_attempted = list(methods)
        return result
    except ExtractionError as inner:
        inner.methods_attempted = list(methods) + [BROWSER_METHOD] + inner.methods_attempted
        raise


def extract_article(
    url: str,
    *,
    profile_dir: str | None = None,
    policy=None,
) -> ExtractionResult:
    """Extract an article from a URL.

    Static fetch first, then site-specific or generic extraction.
    Playwright fallback is used only when static extraction is insufficient.
    Methods attempted are recorded so callers can prove browser fallback ran.
    """
    _validate_url(url, policy=policy)

    wechat = is_wechat_url(url)
    final_url = url
    static_html = ""
    methods: list[str] = []

    try:
        final_url, _ct, static_html = static_fetch(url, policy=policy)
        methods.append("static-fetch")
    except ExtractionError as exc:
        methods.append("static-fetch")
        if wechat:
            try:
                return _attempt_browser(
                    url=url, wechat=True, profile_dir=profile_dir,
                    policy=policy, methods=methods,
                )
            except ExtractionError:
                raise
        exc.methods_attempted = methods
        raise

    if wechat:
        result = extract_wechat(static_html, final_url)
        if result is not None:
            result.method = result.method or "wechat-static"
            methods.append(result.method)
            try:
                quality_gate(result)
                result.methods_attempted = methods
                return result
            except ExtractionError:
                pass
        try:
            return _attempt_browser(
                url=final_url, wechat=True, profile_dir=profile_dir,
                policy=policy, methods=methods,
            )
        except ExtractionError:
            raise

    result = extract_generic(static_html, final_url)
    if result is not None:
        result.method = result.method or "trafilatura"
        methods.append(result.method)
        try:
            quality_gate(result)
            result.methods_attempted = methods
            return result
        except ExtractionError:
            pass

    try:
        return _attempt_browser(
            url=final_url, wechat=False, profile_dir=profile_dir,
            policy=policy, methods=methods,
        )
    except ExtractionError:
        raise


def check_dependencies() -> dict[str, bool]:
    status = {"trafilatura": False, "playwright": False, "chromium": False}
    try:
        import trafilatura  # noqa: F401
        status["trafilatura"] = True
    except ImportError:
        pass
    try:
        import playwright  # noqa: F401
        status["playwright"] = True
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(args=["--no-sandbox"])
                browser.close()
            status["chromium"] = True
        except Exception:
            pass
    except ImportError:
        pass
    return status
