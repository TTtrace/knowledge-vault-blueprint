"""Tests for web_extract: static fetch, WeChat adapter, Trafilatura, and fallback.

Localhost fixture tests use a scoped permissive fake policy injected through
the ``policy`` parameter. This is a test-only injection and is never reachable
through a production environment switch.
"""

from __future__ import annotations

import contextlib
import http.server
import importlib.util
import json
import os
import re
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "vault-capture" / "scripts" / "web_extract.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "web"

if str(SCRIPT.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT.parent))

SPEC = importlib.util.spec_from_file_location("web_extract", SCRIPT)
assert SPEC and SPEC.loader
web_extract = importlib.util.module_from_spec(SPEC)
sys.modules["web_extract"] = web_extract
SPEC.loader.exec_module(web_extract)

import network_security  # noqa: E402


class _PermissiveResult:
    def __init__(self, url: str) -> None:
        self.url = url


class ScopedFixturePolicy:
    """Test-only scoped policy permitting only the localhost fixture host.

    It permits the loopback fixture host (bypassing the production IP-literal
    rejection) but still rejects embedded credentials and any other target.
    It is constructed only here and injected explicitly; production never
    constructs or enables it via environment configuration.
    """

    def validate_url(self, url: str, *, force_refresh: bool = False) -> _PermissiveResult:
        parts = urlsplit(url)
        if parts.username or parts.password:
            raise network_security.NetworkPolicyError("URLs with credentials are not allowed", recoverable=False)
        if parts.hostname == "127.0.0.1":
            return _PermissiveResult(url)
        raise network_security.NetworkPolicyError("URL resolves to a non-public address", recoverable=False)

    def validate_url_syntax(self, url: str) -> str:
        return url


PERMISSIVE = ScopedFixturePolicy()


@contextlib.contextmanager
def fixture_server(filenames: dict[str, str], content_type: str = "text/html; charset=utf-8"):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.lstrip("/")
            if path in filenames:
                data = (FIXTURES / filenames[path]).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif self.path == "/redirect":
                self.send_response(302)
                target = next(iter(filenames))
                self.send_header("Location", f"/{target}")
                self.end_headers()
            elif self.path == "/redirect-creds":
                self.send_response(302)
                self.send_header("Location", "http://user:pass@127.0.0.1:1/secret")
                self.end_headers()
            elif self.path == "/ratelimit":
                self.send_response(429)
                self.end_headers()
            elif self.path == "/server-error":
                self.send_response(503)
                self.end_headers()
            elif self.path == "/non-html":
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.end_headers()
                self.wfile.write(b"%PDF-1.4")
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *_args):
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class WebExtractTests(unittest.TestCase):
    def test_validate_url_rejects_private_and_credentials(self):
        with self.assertRaises(web_extract.ExtractionError):
            web_extract._validate_url("https://user:pass@example.com/")
        with self.assertRaises(web_extract.ExtractionError):
            web_extract._validate_url("ftp://example.com/x")
        with self.assertRaises(web_extract.ExtractionError):
            web_extract._validate_url("https://127.0.0.1/")

    def test_is_wechat_url(self):
        self.assertTrue(web_extract.is_wechat_url("https://mp.weixin.qq.com/s/aBc123"))
        self.assertFalse(web_extract.is_wechat_url("https://example.com/article"))

    def test_generic_extraction_from_fixture(self):
        html = (FIXTURES / "generic_article.html").read_text(encoding="utf-8")
        result = web_extract.extract_generic(html, "https://example.org/article")
        self.assertIsNotNone(result)
        if result is None:
            return
        self.assertEqual(result.title, "Generic Article Title")
        self.assertIn("Jane Doe", result.author)
        self.assertEqual(result.publisher, "Example Blog")
        self.assertEqual(result.published, "2026-07-15")
        md = result.markdown
        self.assertIn("## First Section", md)
        self.assertIn("This is the first paragraph", md)
        self.assertIn("> This is a blockquote", md)
        self.assertIn("bold text", md)
        self.assertIn("italic text", md)
        self.assertIn("| Column A", md)
        self.assertIn("```python", md)
        self.assertIn("vault-image://img001", md)
        self.assertEqual(len(result.images), 1)
        self.assertEqual(result.images[0].url, "https://images.example.com/photo-1.jpg")
        self.assertNotIn("Recommended", md)
        self.assertNotIn("User comment", md)
        md_lower = md.lower()
        self.assertNotIn("tracking", md_lower)
        self.assertNotIn("banner", md_lower)
        self.assertNotIn("beacon", md_lower)
        # Order preservation
        self.assertLess(md.index("## First Section"), md.index("| Column A"))
        self.assertLess(md.index("vault-image://img001"), md.index("| Column A"))

    def test_generic_quality_gate(self):
        html = (FIXTURES / "generic_article.html").read_text(encoding="utf-8")
        result = web_extract.extract_generic(html, "https://example.org/article")
        self.assertIsNotNone(result)
        if result is None:
            return
        # Should pass
        web_extract.quality_gate(result)
        # Title-only should fail
        title_html = (FIXTURES / "title_only.html").read_text(encoding="utf-8")
        title_only = web_extract.extract_generic(title_html, "https://example.org/title")
        if title_only is not None:
            with self.assertRaises(web_extract.ExtractionError):
                web_extract.quality_gate(title_only)

    def test_wechat_extraction_from_fixture(self):
        html = (FIXTURES / "wechat_article.html").read_text(encoding="utf-8")
        result = web_extract.extract_wechat(html, "https://mp.weixin.qq.com/s/test")
        self.assertIsNotNone(result)
        if result is None:
            return
        self.assertEqual(result.title, "WeChat Article Title")
        self.assertEqual(result.author, ["Author Name"])
        self.assertEqual(result.publisher, "Account Name")
        self.assertEqual(result.published, "2026-07-20")
        # Two body images only
        self.assertEqual(len(result.images), 2)
        self.assertEqual(result.images[0].url, "https://mmbiz.qpic.cn/mmbiz_jpg/bodyimage1/640?wx_fmt=jpeg")
        self.assertEqual(result.images[1].url, "https://mmbiz.qpic.cn/mmbiz_png/bodyimage2/640?wx_fmt=png")
        md = result.markdown
        self.assertIn("## Section One", md)
        self.assertIn("bold emphasis", md)
        self.assertIn("vault-image://img001", md)
        self.assertIn("vault-image://img002", md)
        self.assertIn("> A quoted passage", md)
        self.assertNotIn("spm_tracking", md)
        self.assertNotIn("qrcode", md)
        self.assertNotIn("avatar", md)
        self.assertNotIn("comment_item", md)
        self.assertNotIn("Recommended article", md)

    def test_wechat_verification_detected(self):
        html = (FIXTURES / "wechat_verification.html").read_text(encoding="utf-8")
        with self.assertRaises(web_extract.ExtractionError) as ctx:
            web_extract.extract_wechat(html, "https://mp.weixin.qq.com/s/verify")
        self.assertEqual(ctx.exception.state, "manual")

    def test_wechat_rate_limit_detected(self):
        html = (FIXTURES / "wechat_rate_limit.html").read_text(encoding="utf-8")
        with self.assertRaises(web_extract.ExtractionError) as ctx:
            web_extract.extract_wechat(html, "https://mp.weixin.qq.com/s/rate")
        self.assertEqual(ctx.exception.state, "manual")

    def test_static_fetch_redirect(self):
        with fixture_server({"article.html": "generic_article.html"}) as base:
            url = f"{base}/redirect"
            final_url, content_type, html = web_extract.static_fetch(url, policy=PERMISSIVE)
            self.assertEqual(content_type, "text/html")
            self.assertIn("Generic Article Title", html)

    def test_static_fetch_unsupported_content_type(self):
        with fixture_server({}) as base:
            with self.assertRaises(web_extract.ExtractionError) as ctx:
                web_extract.static_fetch(f"{base}/non-html", policy=PERMISSIVE)
            self.assertEqual(ctx.exception.state, "failed")

    def test_static_fetch_server_error(self):
        with fixture_server({}) as base:
            with self.assertRaises(web_extract.ExtractionError) as ctx:
                web_extract.static_fetch(f"{base}/server-error", policy=PERMISSIVE)
            self.assertEqual(ctx.exception.state, "failed")

    def test_static_fetch_rate_limit(self):
        with fixture_server({}) as base:
            with self.assertRaises(web_extract.ExtractionError) as ctx:
                web_extract.static_fetch(f"{base}/ratelimit", policy=PERMISSIVE)
            self.assertEqual(ctx.exception.state, "manual")

    def test_extract_article_generic_through_server(self):
        with fixture_server({"article.html": "generic_article.html"}) as base:
            result = web_extract.extract_article(f"{base}/article.html", policy=PERMISSIVE)
            self.assertEqual(result.method, "trafilatura")
            self.assertEqual(result.title, "Generic Article Title")
            web_extract.quality_gate(result)

    def test_extract_article_title_only_insufficient(self):
        with fixture_server({"title.html": "title_only.html"}) as base:
            result = web_extract.extract_generic(
                (FIXTURES / "title_only.html").read_text(encoding="utf-8"),
                f"{base}/title.html",
            )
            if result is not None:
                with self.assertRaises(web_extract.ExtractionError):
                    web_extract.quality_gate(result)

    def test_check_dependencies_structure(self):
        status = web_extract.check_dependencies()
        self.assertIn("trafilatura", status)
        self.assertIn("playwright", status)
        self.assertIn("chromium", status)
        self.assertIsInstance(status["trafilatura"], bool)

    def test_delayed_render_succeeds_through_playwright(self):
        # AC-03: local delayed-render fixture is insufficient under static fetch
        # but succeeds through the Playwright fallback.
        with fixture_server({"delayed.html": "delayed_render.html"}) as base:
            url = f"{base}/delayed.html"
            result = web_extract.extract_article(url, policy=PERMISSIVE)
            self.assertEqual(result.method, "browser-trafilatura")
            self.assertEqual(result.title, "Delayed Render Title")
            self.assertIn("Delayed Render Title", result.markdown)
            self.assertIn("rendered by JavaScript", result.markdown)
            self.assertGreaterEqual(len(result.images), 1)
            web_extract.quality_gate(result)

    def test_methods_attempted_recorded_static_and_browser(self):
        # F-08: methods_attempted must be observable so callers can prove
        # browser fallback actually ran before a manual/ready result.
        with fixture_server({"article.html": "generic_article.html"}) as base:
            result = web_extract.extract_article(f"{base}/article.html", policy=PERMISSIVE)
            self.assertIn("static-fetch", result.methods_attempted)
            self.assertIn("trafilatura", result.methods_attempted)
        with fixture_server({"delayed.html": "delayed_render.html"}) as base:
            result = web_extract.extract_article(f"{base}/delayed.html", policy=PERMISSIVE)
            self.assertIn("static-fetch", result.methods_attempted)
            self.assertIn("trafilatura", result.methods_attempted)
            self.assertIn("browser-trafilatura", result.methods_attempted)

    def test_methods_attempted_on_extraction_error(self):
        # F-08: when extraction fails, the error must carry methods_attempted
        # so callers can observe which methods ran before the failure.
        with fixture_server({}) as base:
            with self.assertRaises(web_extract.ExtractionError) as ctx:
                web_extract.extract_article(f"{base}/server-error", policy=PERMISSIVE)
            self.assertEqual(ctx.exception.state, "failed")
            self.assertIn("static-fetch", ctx.exception.methods_attempted)

    def test_static_fetch_rejects_redirect_to_credentials(self):
        # F-01: redirect to a credentials-bearing URL must be rejected.
        # The permissive policy still enforces the syntax-level credential
        # rejection for redirect targets.
        with fixture_server({"a.html": "generic_article.html"}) as base:
            with self.assertRaises(web_extract.ExtractionError) as ctx:
                web_extract.static_fetch(f"{base}/redirect-creds", policy=PERMISSIVE)
            self.assertEqual(ctx.exception.state, "failed")

    def test_relative_image_urls_token_rewrite(self):
        # F-04: relative and protocol-relative image URLs must be normalized
        # to absolute in both the manifest and the token rewrite.
        html = (FIXTURES / "relative_images.html").read_text(encoding="utf-8")
        result = web_extract.extract_generic(html, "https://example.org/article")
        self.assertIsNotNone(result)
        if result is None:
            return
        web_extract.quality_gate(result)
        self.assertGreaterEqual(len(result.images), 2)
        for img in result.images:
            self.assertTrue(img.url.startswith("http"), f"URL not absolute: {img.url}")
        md = result.markdown
        self.assertIn("vault-image://img001", md)
        self.assertIn("vault-image://img002", md)
        self.assertNotIn("/img/photo-1.jpg", md)
        self.assertNotIn("//cdn.example.com/img/photo-2.jpg", md)

    def test_generic_nested_list_and_caption(self):
        # F-07: nested list items must be indented, and figcaption text must
        # be captured exactly rather than copying the entire output buffer.
        html = (FIXTURES / "generic_article.html").read_text(encoding="utf-8")
        result = web_extract.extract_generic(html, "https://example.org/article")
        self.assertIsNotNone(result)
        if result is None:
            return
        md = result.markdown
        # Nested list: "Nested item A" must be indented relative to parent
        lines = md.splitlines()
        nested_idx = None
        for i, line in enumerate(lines):
            if "Nested item A" in line:
                nested_idx = i
                break
        self.assertIsNotNone(nested_idx, f"Nested item A not found in:\n{md}")
        nested_line = lines[nested_idx]
        self.assertTrue(
            nested_line.startswith("  - ") or nested_line.startswith("    - "),
            f"Nested item not indented: {repr(nested_line)}",
        )
        # Parent item should have less indentation (search backwards for non-blank)
        parent_line = ""
        for j in range(nested_idx - 1, -1, -1):
            if lines[j].strip():
                parent_line = lines[j]
                break
        self.assertIn("Second list item", parent_line)
        self.assertFalse(
            parent_line.startswith("  "),
            f"Parent should not be indented: {repr(parent_line)}",
        )
        # Figcaption: exact caption text must be present
        self.assertIn("图注：Figure 1: Caption for the body image", md)

    def test_playwright_uses_persistent_profile(self):
        # F-02: when profile_dir is provided, launch_persistent_context must
        # be used and the profile directory must contain Chromium data.
        with tempfile.TemporaryDirectory(prefix="vault-profile-test-") as profile:
            with fixture_server({"delayed.html": "delayed_render.html"}) as base:
                url = f"{base}/delayed.html"
                final_url, html = web_extract.playwright_fetch(
                    url, profile_dir=profile, policy=PERMISSIVE
                )
                self.assertIn("Delayed Render Title", html)
                # Persistent context creates Chromium profile data in the dir
                profile_path = Path(profile)
                has_profile_data = any(profile_path.iterdir())
                self.assertTrue(has_profile_data, "Profile directory is empty")

    def test_playwright_concurrent_profile_rejected(self):
        # F-02: a second process attempting the same profile must be rejected.
        with tempfile.TemporaryDirectory(prefix="vault-profile-lock-") as profile:
            lock_file = Path(profile) / ".vault-capture.lock"
            lock_file.write_text("locked", encoding="utf-8")
            with fixture_server({"delayed.html": "delayed_render.html"}) as base:
                with self.assertRaises(web_extract.ExtractionError) as ctx:
                    web_extract.playwright_fetch(
                        f"{base}/delayed.html",
                        profile_dir=profile,
                        policy=PERMISSIVE,
                    )
                self.assertEqual(ctx.exception.state, "failed")

class WebExtractSecurityTests(unittest.TestCase):
    def test_ssrf_validation_rejects_loopback(self):
        with self.assertRaises(web_extract.ExtractionError):
            web_extract._validate_url("https://127.0.0.1:9999/")
        with self.assertRaises(web_extract.ExtractionError):
            web_extract._validate_url("https://localhost/")

    def test_credentials_rejected(self):
        with self.assertRaises(web_extract.ExtractionError):
            web_extract._validate_url("https://user:token@example.com/")

    def test_ip_literal_rejected_without_network(self):
        # Direct public/Fake-IP/exempt-range literals are rejected by syntax
        # without DNS; the 198.18.0.0/16 exemption never applies to literals.
        for url in [
            "https://93.184.216.34/",
            "https://198.18.0.7/",
            "https://198.18.0.0/",
            "https://198.18.255.255/",
            "https://[::1]/",
        ]:
            with self.assertRaises(web_extract.ExtractionError):
                web_extract._validate_url(url)

    def test_redirect_revalidation(self):
        # Redirect to a private address must be rejected in non-override mode.
        with fixture_server({"a.html": "generic_article.html"}) as base:
            # The server is on 127.0.0.1; a default policy rejects the literal.
            with self.assertRaises(web_extract.ExtractionError):
                web_extract._validate_url(f"{base}/a.html")


class FakeRequest:
    def __init__(self, url: str, resource_type: str) -> None:
        self.url = url
        self.resource_type = resource_type


class FakeRoute:
    def __init__(self, url: str, resource_type: str) -> None:
        self.request = FakeRequest(url, resource_type)
        self.aborted = False
        self.continued = False

    def abort(self) -> None:
        self.aborted = True

    def continue_(self) -> None:
        self.continued = True


class NavigationGuardTests(unittest.TestCase):
    def _default_guard(self):
        return web_extract._make_navigation_guard(network_security.NetworkPolicy())

    def test_guard_aborts_private_subresource(self):
        # F-01: subresources (not just documents) must be validated. A fake
        # private image request under the default guard must abort.
        guard = self._default_guard()
        route = FakeRoute("http://127.0.0.1/private.png", "image")
        guard(route)
        self.assertTrue(route.aborted)
        self.assertFalse(route.continued)

    def test_guard_aborts_private_document(self):
        # F-01: private document requests must still abort.
        guard = self._default_guard()
        route = FakeRoute("http://127.0.0.1/", "document")
        guard(route)
        self.assertTrue(route.aborted)
        self.assertFalse(route.continued)

    def test_guard_allows_scoped_permissive_policy(self):
        # Test-only injection: a scoped permissive policy lets fixture requests
        # through. Not reachable through production environment configuration.
        guard = web_extract._make_navigation_guard(PERMISSIVE)
        route = FakeRoute("http://127.0.0.1/private.png", "image")
        guard(route)
        self.assertFalse(route.aborted)
        self.assertTrue(route.continued)

    def test_guard_allows_non_network_scheme_without_bypass(self):
        # A non-HTTP(S) scheme (data:) does not open an external connection and
        # continues; external HTTP(S) requests remain validated by the guard.
        guard = self._default_guard()
        route = FakeRoute("data:text/html,<b>hi</b>", "document")
        guard(route)
        self.assertFalse(route.aborted)
        self.assertTrue(route.continued)

    def test_guard_aborts_file_scheme(self):
        # file: is not an approved local browser scheme; it must abort.
        guard = self._default_guard()
        route = FakeRoute("file:///etc/passwd", "document")
        guard(route)
        self.assertTrue(route.aborted)
        self.assertFalse(route.continued)

    def test_guard_allows_explicit_local_schemes(self):
        # data/blob/about/chrome are the approved local browser schemes.
        for scheme_url in [
            "data:text/plain,abc",
            "blob:https://example.com/uuid",
            "about:blank",
            "chrome://settings",
        ]:
            with self.subTest(url=scheme_url):
                guard = self._default_guard()
                route = FakeRoute(scheme_url, "document")
                guard(route)
                self.assertFalse(route.aborted, f"{scheme_url} should continue")
                self.assertTrue(route.continued, f"{scheme_url} should continue")

    def test_guard_aborts_other_scheme(self):
        # An unapproved non-HTTP(S) scheme must abort.
        guard = self._default_guard()
        route = FakeRoute("ftp://example.com/x", "document")
        guard(route)
        self.assertTrue(route.aborted)
        self.assertFalse(route.continued)

    def test_browser_manual_challenge_records_browser_method(self):
        # F-08: when the browser fallback raises a WeChat verification/rate-limit
        # manual challenge before returning a result, the error must record that
        # the browser was attempted so the smoke tool can accept the manual state.
        with mock.patch.object(
            web_extract, "_validate_url",
            side_effect=lambda url, policy=None: url,
        ), mock.patch.object(
            web_extract, "static_fetch",
            side_effect=web_extract.ExtractionError("network down", state="failed"),
        ), mock.patch.object(
            web_extract, "_try_playwright",
            side_effect=web_extract.ExtractionError("Verification required", state="manual"),
        ):
            with self.assertRaises(web_extract.ExtractionError) as ctx:
                web_extract.extract_article(
                    "https://mp.weixin.qq.com/s/test", policy=PERMISSIVE
                )
            self.assertEqual(ctx.exception.state, "manual")
            self.assertIn("static-fetch", ctx.exception.methods_attempted)
            self.assertIn("browser", ctx.exception.methods_attempted)


if __name__ == "__main__":
    unittest.main()
