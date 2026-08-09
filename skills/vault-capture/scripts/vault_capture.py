#!/usr/bin/env python3
"""Deterministic Vault capture, annotation rollup, queue, and Git operations."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import string
import subprocess
import sys
import tempfile
import unicodedata
import urllib.request
from pathlib import Path
from typing import Any, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import web_extract
except ImportError:
    web_extract = None  # type: ignore[assignment]
import network_security
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit, urljoin
from urllib.request import Request, build_opener


EXIT_INPUT = 2
EXIT_CONFLICT = 3
EXIT_STORAGE = 4
ROLLUP_MARKER = "<!-- vault-capture:annotation-rollup -->"
ENTRIES_START = "<!-- vault-capture:entries:start -->"
ENTRIES_END = "<!-- vault-capture:entries:end -->"
SOURCE_START = "<!-- source-content:start -->"
SOURCE_END = "<!-- source-content:end -->"
ENTRY_RE = re.compile(r"(?m)^<!-- vault-capture:entry (\{.*\}) -->$")
STAGE_FIELDS = {
    "kind",
    "url",
    "title",
    "text",
    "topics",
    "priority",
    "medium",
    "captured_at",
    "annotations",
    "author",
    "publisher",
    "published",
}
FINALIZE_FIELDS = {
    "title",
    "author",
    "publisher",
    "published",
    "summary",
    "markdown",
    "images",
    "images_complete",
    "final_url",
    "retrieved_at",
    "language",
    "methods_attempted",
}
IMAGE_TOKEN_RE = re.compile(r"vault-image://([a-zA-Z0-9_-]+)")
IMAGE_TYPES = {
    "image/jpeg": ("jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    "image/png": ("png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/webp": ("webp", lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"),
    "image/gif": ("gif", lambda data: data.startswith((b"GIF87a", b"GIF89a"))),
}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_ARTICLE_IMAGE_BYTES = 100 * 1024 * 1024
TRACKING_KEYS = {
    "fbclid",
    "gclid",
    "dclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "ref_src",
    "spm",
}
SOURCE_MEDIA = {
    "article",
    "transcript",
    "paper",
    "book",
    "chapter",
    "report",
    "video",
    "audio",
    "ai_conversation",
    "document",
}


class CaptureError(Exception):
    def __init__(self, message: str, code: int, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def emit(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()


def content_hash(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


def safe_user_text(value: str) -> str:
    value = value.replace("\x00", "").replace("<!-- vault-capture:", "&lt;!-- vault-capture:")
    return value.strip()


def inline(value: str) -> str:
    return normalize_text(safe_user_text(value))


def parse_time(value: Any | None = None) -> str:
    if value in (None, ""):
        current = dt.datetime.now().astimezone().replace(microsecond=0)
    else:
        if not isinstance(value, str):
            raise CaptureError("Datetime must be an ISO 8601 string", EXIT_INPUT)
        try:
            current = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CaptureError("Invalid ISO 8601 datetime", EXIT_INPUT) from exc
        if current.tzinfo is None:
            raise CaptureError("Datetime must include a timezone", EXIT_INPUT)
        current = current.replace(microsecond=0)
    return current.isoformat()


def normalize_url(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise CaptureError("A non-empty URL is required", EXIT_INPUT)
    raw = raw.strip()
    if any(ord(char) < 32 for char in raw):
        raise CaptureError("URL contains control characters", EXIT_INPUT)
    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or not parts.hostname:
        raise CaptureError("Only absolute HTTP(S) URLs are supported", EXIT_INPUT)
    if parts.username or parts.password:
        raise CaptureError("URLs containing credentials are not allowed", EXIT_INPUT)
    try:
        host = parts.hostname.encode("idna").decode("ascii").lower()
        port = parts.port
    except (UnicodeError, ValueError) as exc:
        raise CaptureError("URL host or port is invalid", EXIT_INPUT) from exc
    host_rendered = f"[{host}]" if ":" in host and not host.startswith("[") else host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host_rendered = f"{host_rendered}:{port}"
    path = re.sub(r"/{2,}", "/", unquote(parts.path or "/"))
    if path != "/":
        path = path.rstrip("/") or "/"
    path = quote(path, safe="/%:@!$&'()*+,;=-._~")
    query_items = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in TRACKING_KEYS:
            continue
        query_items.append((key, value))
    query_items.sort(key=lambda item: (item[0], item[1]))
    return urlunsplit((scheme, host_rendered, path, urlencode(query_items, doseq=True), ""))


def reject_unknown_fields(data: dict[str, Any], allowed: set[str], command: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise CaptureError(f"Unsupported {command} fields: {', '.join(unknown)}", EXIT_INPUT)


def validate_author(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise CaptureError("author must be a list of strings", EXIT_INPUT)
    return [inline(item) for item in value if inline(item)]


def validate_published(value: Any) -> str:
    if value in (None, ""):
        return ""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise CaptureError("published must use YYYY-MM-DD", EXIT_INPUT)
    try:
        dt.date.fromisoformat(value)
    except ValueError as exc:
        raise CaptureError("published must be a valid date", EXIT_INPUT) from exc
    return value


def credit_label(author: list[str], publisher: str, url: str) -> str:
    if author:
        return "、".join(author)
    if publisher:
        return publisher
    host = urlsplit(url).hostname if url else ""
    return host or "未知作者"


def final_stem(author: list[str], publisher: str, url: str, title: str, captured_at: str, source_id: str) -> str:
    author_part = sanitize_component(credit_label(author, publisher, url), "未知作者", 32)
    title_part = sanitize_component(title, source_id, 80)
    captured_date = dt.datetime.fromisoformat(captured_at).date().isoformat()
    return f"{author_part}--{title_part}--{captured_date}--{source_id}"


def source_folder(kind: str) -> str:
    if kind == "web":
        return "sources/web"
    if kind == "transcript":
        return "sources/transcripts"
    return "sources/documents"


def source_path_for(
    vault: Path,
    kind: str,
    source_id: str,
    title: str,
    author: list[str],
    publisher: str,
    url: str,
    captured_at: str,
) -> Path:
    folder = source_folder(kind)
    if not title:
        return vault_path(vault, f"{folder}/{source_id}.md")
    stem = final_stem(author, publisher, url, title, captured_at, source_id)
    return vault_path(vault, f"{folder}/{stem}.md")


def annotation_path_for(vault: Path, source_id: str, final_source_stem: str | None = None) -> Path:
    stem = f"annotated_{final_source_stem}" if final_source_stem else f"annotated_{source_id}"
    return vault_path(vault, f"notes/annotations/{stem}.md")


class _NoRedirectImageHandler(urllib.request.HTTPRedirectHandler):
    """Prevent urllib from following image redirects automatically.

    Redirects are handled manually so each Location can be syntax/address
    validated before a new connection is made.
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


MAX_IMAGE_REDIRECTS = 5


def _policy_for(policy):
    """Resolve a caller-supplied policy or build one from the environment.

    Build errors from the environment are translated to CaptureError so that no
    NetworkPolicyError (or raw traceback) can escape the CLI on any path.
    """
    if policy is not None:
        return policy
    try:
        return network_security.NetworkPolicy.from_environment()
    except network_security.NetworkPolicyError as exc:
        raise CaptureError(exc.reason, EXIT_INPUT) from exc


def _validate_web_url_syntax(url: str) -> None:
    """Domain-only, network-free URL validation for stage/network boundaries.

    Rejects non-HTTP(S), credentials, and IPv4/IPv6 literals with exit code 2.
    """
    try:
        network_security.validate_domain_url_syntax(url)
    except network_security.NetworkPolicyError as exc:
        raise CaptureError(exc.reason, EXIT_INPUT) from exc


def _validate_image_url(policy, url: str) -> None:
    """Validate an image URL (and each redirect hop) via the shared policy."""
    try:
        policy.validate_url(url)
    except network_security.NetworkPolicyError as exc:
        raise CaptureError(exc.reason, EXIT_INPUT) from exc


def download_image_assets(
    vault: Path,
    source_id: str,
    markdown: str,
    raw_images: Any,
    source_url: str,
    *,
    policy=None,
) -> tuple[str, Path | None, list[tuple[Path, Path]]]:
    policy = _policy_for(policy)
    if not isinstance(raw_images, list):
        raise CaptureError("images must be a list", EXIT_INPUT)
    images: list[dict[str, str]] = []
    tokens: set[str] = set()
    for raw in raw_images:
        if not isinstance(raw, dict) or set(raw) != {"token", "url"}:
            raise CaptureError("Each image must contain only token and url", EXIT_INPUT)
        token = str(raw["token"])
        url = str(raw["url"]).strip()
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", token) or token in tokens:
            raise CaptureError("Image tokens must be unique safe identifiers", EXIT_INPUT)
        _validate_image_url(policy, url)
        tokens.add(token)
        images.append({"token": token, "url": url})
    markdown_tokens = IMAGE_TOKEN_RE.findall(markdown)
    if len(markdown_tokens) != len(set(markdown_tokens)) or set(markdown_tokens) != tokens:
        raise CaptureError("Markdown image placeholders must match the image manifest exactly", EXIT_INPUT)
    if not images:
        return markdown, None, []

    queue_root = vault_path(vault, ".queue")
    queue_root.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix=f"vault-capture-{source_id}-", dir=queue_root))
    moves: list[tuple[Path, Path]] = []
    total = 0
    rewritten = markdown
    opener = build_opener(_NoRedirectImageHandler)
    try:
        for index, image in enumerate(images, start=1):
            current_url = image["url"]
            _validate_image_url(policy, current_url)
            data = None
            content_type = ""
            for redirect_count in range(MAX_IMAGE_REDIRECTS + 1):
                request = Request(
                    current_url,
                    headers={"User-Agent": "vault-capture/1.0", "Referer": source_url},
                )
                try:
                    with opener.open(request, timeout=20) as response:
                        content_type = response.headers.get_content_type().lower()
                        data = response.read(MAX_IMAGE_BYTES + 1)
                    break
                except HTTPError as exc:
                    if exc.code in (301, 302, 303, 307, 308):
                        location = exc.headers.get("Location")
                        if not location or redirect_count >= MAX_IMAGE_REDIRECTS:
                            raise CaptureError("Image redirect limit exceeded", EXIT_INPUT) from exc
                        current_url = urljoin(current_url, location)
                        # Validate the redirect target before the next connection.
                        _validate_image_url(policy, current_url)
                        continue
                    raise CaptureError("Image download failed", EXIT_STORAGE) from exc
                except URLError as exc:
                    raise CaptureError("Image download failed", EXIT_STORAGE) from exc
                except (socket.timeout, TimeoutError) as exc:
                    raise CaptureError("Image download timed out", EXIT_STORAGE) from exc
            if data is None:
                raise CaptureError("Image download failed", EXIT_STORAGE)
            if len(data) > MAX_IMAGE_BYTES:
                raise CaptureError("An image exceeds the 20 MB limit", EXIT_INPUT)
            total += len(data)
            if total > MAX_ARTICLE_IMAGE_BYTES:
                raise CaptureError("Article images exceed the 100 MB limit", EXIT_INPUT)
            image_type = IMAGE_TYPES.get(content_type)
            if image_type is None or not image_type[1](data):
                raise CaptureError("Image content type or signature is unsupported", EXIT_INPUT)
            digest = hashlib.sha256(data).hexdigest()[:12]
            filename = f"{index:03d}-{digest}.{image_type[0]}"
            staged = temp_root / filename
            staged.write_bytes(data)
            destination = vault_path(vault, f"assets/images/{source_id}/{filename}")
            moves.append((staged, destination))
            rewritten = rewritten.replace(f"vault-image://{image['token']}", f"../../assets/images/{source_id}/{filename}")
        return rewritten, temp_root, moves
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise


def yaml_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def yaml_document(fields: list[tuple[str, Any]]) -> str:
    lines = ["---"]
    for key, value in fields:
        lines.extend(yaml_field_lines(key, value))
    lines.append("---")
    return "\n".join(lines)


def yaml_field_lines(key: str, value: Any) -> list[str]:
    if isinstance(value, list):
        if value:
            return [f"{key}:", *(f"  - {yaml_scalar(item)}" for item in value)]
        return [f"{key}: []"]
    return [f"{key}: {yaml_scalar(value)}"]


def split_frontmatter(text: str) -> tuple[str, str]:
    text = text.replace("\r\n", "\n")
    match = re.match(r"\A---\n(.*?)\n---\n?", text, re.DOTALL)
    if not match:
        raise CaptureError("Markdown file has invalid frontmatter", EXIT_STORAGE)
    return match.group(1), text[match.end() :]


def parse_scalar(raw: str) -> Any:
    raw = raw.strip()
    if raw == "":
        return ""
    if raw in {"true", "false"}:
        return raw == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if raw.startswith(('"', "'")):
        try:
            return json.loads(raw) if raw.startswith('"') else raw[1:-1]
        except json.JSONDecodeError:
            return raw.strip('"')
    return raw


def get_field(text: str, key: str, default: Any = "") -> Any:
    frontmatter, _ = split_frontmatter(text)
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.*)$", frontmatter)
    return parse_scalar(match.group(1)) if match else default


def set_fields(text: str, updates: dict[str, Any]) -> str:
    frontmatter, body = split_frontmatter(text)
    lines = frontmatter.splitlines()
    seen: set[str] = set()
    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):", line)
        if match and match.group(1) in updates:
            key = match.group(1)
            output.extend(yaml_field_lines(key, updates[key]))
            seen.add(key)
            index += 1
            while index < len(lines) and (lines[index].startswith(" ") or not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*:", lines[index])):
                index += 1
        else:
            output.append(line)
            index += 1
    for key, value in updates.items():
        if key not in seen:
            output.extend(yaml_field_lines(key, value))
    return f"---\n{'\n'.join(output)}\n---\n\n{body.lstrip()}"


def sanitize_filename(value: str, fallback: str) -> str:
    value = inline(value) or fallback
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "-", value)
    value = re.sub(r"[. ]+$", "", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-.")
    return (value or fallback)[:80]


def sanitize_component(value: str, fallback: str, limit: int) -> str:
    value = inline(value) or fallback
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "-", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return (value or fallback)[:limit].rstrip(" .")


def new_id(timestamp: str) -> str:
    value = dt.datetime.fromisoformat(timestamp)
    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    return value.strftime("%Y%m%d-%H%M%S-") + suffix


def read_json_input(path: str | None = None) -> dict[str, Any]:
    try:
        if path:
            input_path = Path(path).expanduser().resolve()
            if not input_path.is_file() or input_path.stat().st_size > 10 * 1024 * 1024:
                raise CaptureError("JSON input file is missing or too large", EXIT_INPUT)
            data = json.loads(input_path.read_text(encoding="utf-8"))
        else:
            data = json.load(sys.stdin)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CaptureError("Input must contain one UTF-8 JSON object", EXIT_INPUT) from exc
    if not isinstance(data, dict):
        raise CaptureError("Standard input must contain a JSON object", EXIT_INPUT)
    return data


def run_git(vault: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(vault), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise CaptureError("Git could not be executed", EXIT_STORAGE) from exc
    if check and result.returncode != 0:
        raise CaptureError("Git operation failed", EXIT_STORAGE)
    return result


def relative(vault: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(vault.resolve()).as_posix()
    except ValueError as exc:
        raise CaptureError("Resolved path escapes the Vault", EXIT_CONFLICT) from exc


def vault_path(vault: Path, rel: str) -> Path:
    candidate = (vault / Path(rel)).resolve()
    try:
        candidate.relative_to(vault.resolve())
    except ValueError as exc:
        raise CaptureError("Resolved path escapes the Vault", EXIT_CONFLICT) from exc
    return candidate


def ensure_repo(vault: Path) -> None:
    if not vault.is_dir():
        raise CaptureError("VAULT_ROOT must be an existing directory", EXIT_INPUT)
    if shutil.which("git") is None:
        raise CaptureError("Git is not available", EXIT_INPUT)
    result = run_git(vault, ["rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0 or Path(result.stdout.strip()).resolve() != vault.resolve():
        raise CaptureError("VAULT_ROOT must be the root of a Git repository", EXIT_INPUT)
    required = ["sources/web", "sources/transcripts", "sources/documents", "notes/annotations", "notes/ideas"]
    if any(not vault_path(vault, item).is_dir() for item in required):
        raise CaptureError("Vault is missing required capture directories", EXIT_INPUT)
    ignored = run_git(vault, ["check-ignore", "-q", ".queue/vault-capture/probe"], check=False)
    if ignored.returncode != 0:
        raise CaptureError(".queue/vault-capture must be ignored by Git", EXIT_INPUT)


def path_has_unstaged_changes(vault: Path, path: Path) -> bool:
    rel = relative(vault, path)
    result = run_git(vault, ["status", "--porcelain", "--untracked-files=all", "--", rel])
    for line in result.stdout.splitlines():
        status = line[:2]
        if status == "??" or (len(status) == 2 and status[1] != " "):
            return True
    return False


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text.rstrip() + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp_name)


@contextlib.contextmanager
def capture_lock(vault: Path) -> Iterator[None]:
    lock_path = vault_path(vault, ".queue/vault-capture.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt

            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if os.name == "nt":
            handle.seek(0)
            with contextlib.suppress(OSError):
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            with contextlib.suppress(OSError):
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def stage_paths(vault: Path, paths: list[Path]) -> list[str]:
    rels = [relative(vault, path) for path in paths]
    result = run_git(vault, ["add", "--", *rels], check=False)
    if result.returncode != 0:
        raise CaptureError("Git add failed; captured files remain on disk", EXIT_STORAGE, paths=rels)
    return rels


def source_files(vault: Path) -> Iterator[Path]:
    yield from vault_path(vault, "sources").rglob("*.md")


def find_source_by_url(vault: Path, canonical_url: str) -> Path | None:
    for path in source_files(vault):
        try:
            if get_field(path.read_text(encoding="utf-8"), "canonical_url") == canonical_url:
                return path
        except (OSError, CaptureError):
            continue
    return None


def find_source_by_id(vault: Path, source_id: str) -> Path | None:
    for path in source_files(vault):
        try:
            if get_field(path.read_text(encoding="utf-8"), "id") == source_id:
                return path
        except (OSError, CaptureError):
            continue
    return None


def find_rollups(vault: Path, source_id: str) -> list[Path]:
    matches: list[Path] = []
    for path in vault_path(vault, "notes/annotations").rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
            if ROLLUP_MARKER in text and get_field(text, "source_id") == source_id:
                matches.append(path)
        except (OSError, CaptureError):
            continue
    return matches


def render_source(
    source_id: str,
    title: str,
    medium: str,
    url: str,
    canonical_url: str,
    captured_at: str,
    status: str,
    author: list[str],
    publisher: str,
    published: str,
    priority: int,
    topics: list[str],
    text: str,
) -> str:
    fields = [
        ("schema_version", 1),
        ("id", source_id),
        ("type", "source"),
        ("aliases", [source_id]),
        ("medium", medium),
        ("title", title),
        ("url", url),
        ("canonical_url", canonical_url),
        ("author", author),
        ("publisher", publisher or None),
        ("published", published or None),
        ("captured", captured_at),
        ("retrieved_at", None),
        ("language", None),
        ("ingest_status", status),
        ("read_status", "unread"),
        ("engagement", "captured"),
        ("priority", priority),
        ("estimated_minutes", None),
        ("capture_method", "openclaw"),
        ("topics", topics),
        ("tags", []),
    ]
    body_text = safe_user_text(text)
    body = [f"# {inline(title) or source_id}", "", "> [!info] 来源"]
    if url:
        body.append(f"> [打开原网页]({url})")
    body.extend(["", "## 摘要", "", "", "## 原文", "", SOURCE_START, ""])
    if body_text:
        body.append(body_text)
        body.append("")
    body.extend([SOURCE_END, ""])
    return yaml_document(fields) + "\n\n" + "\n".join(body)


def validate_annotations(raw: Any, default_time: str) -> list[dict[str, str]]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise CaptureError("annotations must be a list", EXIT_INPUT)
    result: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise CaptureError("Each annotation must be an object", EXIT_INPUT)
        unknown = sorted(set(item) - {"quote", "comment", "locator", "captured_at"})
        if unknown:
            raise CaptureError(f"Unsupported annotation fields: {', '.join(unknown)}", EXIT_INPUT)
        quote_text = safe_user_text(str(item.get("quote", "")))
        comment = safe_user_text(str(item.get("comment", "")))
        if not normalize_text(quote_text) and not normalize_text(comment):
            raise CaptureError("Each annotation needs a quote or comment", EXIT_INPUT)
        result.append(
            {
                "quote": quote_text,
                "comment": comment,
                "locator": inline(str(item.get("locator", ""))),
                "captured_at": parse_time(item.get("captured_at") or default_time),
            }
        )
    return result


def quote_markdown(value: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in value.splitlines())


def comment_markdown(value: str, captured_at: str, key: str) -> str:
    lines = value.splitlines() or [""]
    rendered = f"- {lines[0]}"
    if len(lines) > 1:
        rendered += "\n" + "\n".join(f"  {line}" for line in lines[1:])
    meta = json.dumps({"captured_at": captured_at, "key": key}, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"<!-- vault-capture:comment {meta} -->\n{rendered}"


def parse_entries(body: str) -> tuple[str, list[dict[str, Any]], str]:
    if ENTRIES_START not in body or ENTRIES_END not in body:
        raise CaptureError("Annotation rollup markers are invalid", EXIT_STORAGE)
    start_pos = body.index(ENTRIES_START) + len(ENTRIES_START)
    end_pos = body.index(ENTRIES_END, start_pos)
    region = body[start_pos:end_pos]
    matches = list(ENTRY_RE.finditer(region))
    prefix = body[:start_pos]
    suffix = body[end_pos:]
    entries: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(region)
        try:
            meta = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise CaptureError("Annotation entry metadata is invalid", EXIT_STORAGE) from exc
        if not isinstance(meta, dict) or not isinstance(meta.get("key"), str):
            raise CaptureError("Annotation entry metadata is incomplete", EXIT_STORAGE)
        comments = meta.get("comments", [])
        if not isinstance(comments, list):
            raise CaptureError("Annotation comment metadata is invalid", EXIT_STORAGE)
        block = region[match.end() : block_end]
        legacy_heading = re.search(r"(?m)^## (?P<captured_at>\d{4}-\d{2}-\d{2}T\S+) · (?P<locator>.*)$", block)
        if legacy_heading:
            meta.setdefault("captured_at", legacy_heading.group("captured_at"))
            locator = legacy_heading.group("locator").strip()
            meta.setdefault("locator", "" if locator == "未定位" else locator)
        meta.setdefault("captured_at", "")
        meta.setdefault("locator", "")
        entries.append({"meta": meta, "block": block})
    return prefix, entries, suffix


def annotation_kind(entries: list[dict[str, Any]]) -> tuple[str, str]:
    has_quote = [bool(entry["meta"].get("quote")) for entry in entries]
    has_comment = [bool(entry["meta"].get("comments")) for entry in entries]
    if entries and all(has_quote) and not any(has_comment):
        return "highlights", "highlighted"
    if entries and not any(has_quote) and all(has_comment):
        return "comments", "annotated"
    return "mixed", "annotated"


def render_rollup(
    annotation_id: str,
    source_id: str,
    source_title: str,
    source_url: str,
    source_link: str,
    created: str,
    topics: list[str],
) -> str:
    title = f"{source_title}——批注"
    fields = [
        ("schema_version", 1),
        ("id", annotation_id),
        ("type", "annotation"),
        ("aliases", [annotation_id]),
        ("title", title),
        ("source", f"[[{source_id}]]"),
        ("source_id", source_id),
        ("source_title", source_title),
        ("source_url", source_url),
        ("zotero_uri", None),
        ("annotation_kind", "mixed"),
        ("engagement", "annotated"),
        ("created", created),
        ("topics", topics),
        ("tags", []),
    ]
    source_line = f"来源：[[{source_id}|{inline(source_title)}]] · [原文]({source_url})"
    body = f"# {inline(title)}\n\n{source_line}\n\n{ROLLUP_MARKER}\n\n{ENTRIES_START}\n{ENTRIES_END}\n"
    return yaml_document(fields) + "\n\n" + body


def merge_rollup(
    text: str,
    annotations: list[dict[str, str]],
    source_link: str,
    source_url: str,
) -> tuple[str, int, str, str]:
    frontmatter, body = split_frontmatter(text)
    prefix, entries, suffix = parse_entries(body)
    by_key = {entry["meta"]["key"]: entry for entry in entries}
    added = 0
    for item in annotations:
        quote_norm = normalize_text(item["quote"])
        comment_norm = normalize_text(item["comment"])
        key = ("q:" + content_hash(quote_norm)) if quote_norm else ("c:" + content_hash(comment_norm))
        comment_key = content_hash(comment_norm) if comment_norm else ""
        entry = by_key.get(key)
        if entry is None:
            meta = {
                "captured_at": item["captured_at"],
                "comments": [comment_key] if comment_key else [],
                "key": key,
                "locator": item["locator"],
                "quote": bool(quote_norm),
            }
            block_parts = [""]
            if item["quote"]:
                block_parts.extend(["", quote_markdown(item["quote"]), ""])
            if comment_key:
                block_parts.extend(["", "批注：", ""])
                block_parts.append(comment_markdown(item["comment"], item["captured_at"], comment_key))
            entry = {"meta": meta, "block": "\n".join(block_parts).rstrip() + "\n"}
            entries.append(entry)
            by_key[key] = entry
            added += 1
        elif comment_key and comment_key not in entry["meta"].get("comments", []):
            entry["meta"].setdefault("comments", []).append(comment_key)
            entry["block"] = entry["block"].rstrip() + "\n\n" + comment_markdown(
                item["comment"], item["captured_at"], comment_key
            ) + "\n"
            added += 1
    kind, engagement = annotation_kind(entries)
    region_parts: list[str] = []
    for index, entry in enumerate(entries, start=1):
        meta_json = json.dumps(entry["meta"], ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        block = re.sub(r"(?m)^\s*## .*?\n", "", entry["block"], count=1).strip()
        block = re.sub(r"(?m)^<!-- vault-capture:comment ([a-f0-9]{64}) -->$", lambda match: (
            "<!-- vault-capture:comment "
            + json.dumps({"captured_at": entry["meta"].get("captured_at", ""), "key": match.group(1)}, separators=(",", ":"), sort_keys=True)
            + " -->"
        ), block)
        block = re.sub(r"(?m)^来源：\[\[[^\n]+\]\](?:\s*·\s*\[[^\]]+\]\([^)]+\))?\n?", "", block)
        block = re.sub(r"(?m)^评论：\s*\n?", "", block)
        if "<!-- vault-capture:comment" in block and "批注：" not in block:
            block = re.sub(
                r"(?m)^(<!-- vault-capture:comment )",
                r"批注：\n\n\1",
                block,
                count=1,
            )
        region_parts.append(f"\n<!-- vault-capture:entry {meta_json} -->\n\n## 标注 {index}\n\n{block}\n")
    merged_body = prefix + "".join(region_parts) + suffix
    merged = f"---\n{frontmatter}\n---\n\n{merged_body.lstrip()}"
    merged = set_fields(merged, {"annotation_kind": kind, "engagement": engagement})
    return merged, added, kind, engagement


def replace_heading(body: str, title: str) -> str:
    return re.sub(r"(?m)^# .*$", f"# {inline(title)}", body, count=1)


def normalize_rollup_links(text: str, source_id: str, source_title: str) -> str:
    frontmatter, body = split_frontmatter(text)
    pattern = re.compile(r"来源：\[\[[^\]#|]+(?P<anchor>#[^\]|]+)?(?:\|[^\]]+)?\]\]")
    body = pattern.sub(
        lambda match: f"来源：[[{source_id}{match.group('anchor') or ''}|{source_title}]]",
        body,
    )
    return f"---\n{frontmatter}\n---\n\n{body.lstrip()}"


def replace_source_content(body: str, markdown: str) -> str:
    if SOURCE_START not in body or SOURCE_END not in body:
        raise CaptureError("Source content markers are missing", EXIT_STORAGE)
    markdown = safe_user_text(markdown).replace(SOURCE_START, "&lt;!-- source-content:start -->").replace(
        SOURCE_END, "&lt;!-- source-content:end -->"
    )
    start = body.index(SOURCE_START) + len(SOURCE_START)
    end = body.index(SOURCE_END, start)
    return body[:start] + "\n\n" + markdown.strip() + "\n\n" + body[end:]


def replace_summary(body: str, summary: str) -> str:
    start_marker = "## 摘要"
    end_marker = "## 原文"
    if start_marker not in body or end_marker not in body:
        raise CaptureError("Source summary markers are missing", EXIT_STORAGE)
    start = body.index(start_marker) + len(start_marker)
    end = body.index(end_marker, start)
    summary = safe_user_text(summary)
    rendered = ""
    if summary:
        rendered = "> [!note] AI 摘要（未核实）\n" + "\n".join(f"> {line}" for line in summary.splitlines())
    return body[:start] + "\n\n" + rendered + "\n\n" + body[end:]


def queue_path(vault: Path, source_id: str) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9-]+", source_id):
        raise CaptureError("Invalid source ID", EXIT_INPUT)
    return vault_path(vault, f".queue/vault-capture/{source_id}.json")


def read_job(vault: Path, source_id: str) -> dict[str, Any]:
    path = queue_path(vault, source_id)
    if not path.is_file():
        raise CaptureError("Capture job not found", EXIT_INPUT)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureError("Capture job is unreadable", EXIT_STORAGE) from exc
    if not isinstance(data, dict) or data.get("id") != source_id:
        raise CaptureError("Capture job is invalid", EXIT_STORAGE)
    return data


def write_job(vault: Path, job: dict[str, Any]) -> None:
    atomic_write(queue_path(vault, str(job["id"])), json.dumps(job, ensure_ascii=False, indent=2, sort_keys=True))


def validate_stage(data: dict[str, Any]) -> dict[str, Any]:
    reject_unknown_fields(data, STAGE_FIELDS, "stage")
    kind = str(data.get("kind", "web")).lower()
    if kind not in {"web", "transcript", "document", "ocr", "idea"}:
        raise CaptureError("Unsupported capture kind", EXIT_INPUT)
    captured_at = parse_time(data.get("captured_at"))
    topics = data.get("topics", [])
    if not isinstance(topics, list) or any(not isinstance(item, str) for item in topics):
        raise CaptureError("topics must be a list of strings", EXIT_INPUT)
    priority = data.get("priority", 2)
    if not isinstance(priority, int) or priority not in {1, 2, 3}:
        raise CaptureError("priority must be 1, 2, or 3", EXIT_INPUT)
    url = str(data.get("url", "")).strip()
    canonical_url = normalize_url(url) if url else ""
    if kind == "web" and not canonical_url:
        raise CaptureError("web capture requires a URL", EXIT_INPUT)
    if kind == "web":
        # Domain-only, network-free validation before any network activity.
        _validate_web_url_syntax(url)
    text = safe_user_text(str(data.get("text", "")))
    if kind == "idea" and not text:
        raise CaptureError("idea capture requires text", EXIT_INPUT)
    medium_default = {"web": "article", "transcript": "transcript", "document": "document", "ocr": "document"}.get(kind, "")
    medium = str(data.get("medium") or medium_default)
    if kind != "idea" and medium not in SOURCE_MEDIA:
        raise CaptureError("Unsupported Source medium", EXIT_INPUT)
    author = validate_author(data.get("author"))
    publisher = inline(str(data.get("publisher", "")))
    published = validate_published(data.get("published"))
    return {
        "kind": kind,
        "captured_at": captured_at,
        "topics": [inline(item) for item in topics if inline(item)],
        "priority": priority,
        "url": url,
        "canonical_url": canonical_url,
        "title": inline(str(data.get("title", ""))),
        "text": text,
        "author": author,
        "publisher": publisher,
        "published": published,
        "medium": medium,
        "annotations": validate_annotations(data.get("annotations", []), captured_at),
    }


def stage_idea(vault: Path, data: dict[str, Any]) -> dict[str, Any]:
    idea_id = new_id(data["captured_at"])
    title = data["title"] or inline(data["text"][:48]) or "未命名想法"
    path = vault_path(vault, f"notes/ideas/{idea_id}--{sanitize_filename(title, 'idea')}.md")
    fields = [
        ("schema_version", 1),
        ("id", idea_id),
        ("type", "idea"),
        ("title", title),
        ("created", data["captured_at"]),
        ("provenance", "personal"),
        ("maturity", "seed"),
        ("derived_from", []),
        ("related", []),
        ("topics", data["topics"]),
        ("tags", []),
    ]
    atomic_write(path, yaml_document(fields) + f"\n\n# {title}\n\n{data['text']}\n")
    try:
        staged_paths = stage_paths(vault, [path])
    except CaptureError as exc:
        exc.details.update({"id": idea_id, "source_path": relative(vault, path), "staged": False})
        raise
    return {
        "ok": True,
        "result": "created",
        "id": idea_id,
        "source_path": relative(vault, path),
        "annotation_path": None,
        "staged": True,
        "staged_paths": staged_paths,
        "job_created": False,
        "ingest_status": "ready",
        "paths_final": True,
    }


def cmd_stage(vault: Path, input_file: str | None = None) -> dict[str, Any]:
    data = validate_stage(read_json_input(input_file))
    with capture_lock(vault):
        if data["kind"] == "idea":
            return stage_idea(vault, data)
        source = find_source_by_url(vault, data["canonical_url"]) if data["canonical_url"] else None
        is_new = source is None
        if is_new:
            source_id = new_id(data["captured_at"])
            title = data["title"]
            source = source_path_for(
                vault,
                data["kind"],
                source_id,
                title,
                data["author"],
                data["publisher"],
                data["url"],
                data["captured_at"],
            )
            status = "pending" if data["kind"] == "web" else "manual"
            source_text = render_source(
                source_id,
                title,
                data["medium"],
                data["url"],
                data["canonical_url"],
                data["captured_at"],
                status,
                data["author"],
                data["publisher"],
                data["published"],
                data["priority"],
                data["topics"],
                data["text"],
            )
        else:
            source_text = source.read_text(encoding="utf-8")
            source_id = str(get_field(source_text, "id"))
            title = str(get_field(source_text, "title"))
            status = str(get_field(source_text, "ingest_status"))
        changed_paths: list[Path] = []
        rollups = find_rollups(vault, source_id)
        if len(rollups) > 1:
            raise CaptureError("More than one capture-managed Annotation rollup exists", EXIT_CONFLICT)
        rollup_path = rollups[0] if rollups else None
        annotation_added = 0
        if data["annotations"]:
            if rollup_path is None:
                annotation_id = new_id(data["captured_at"])
                rollup_path = annotation_path_for(vault, source_id, source.stem if title else None)
                rollup_text = render_rollup(
                    annotation_id,
                    source_id,
                    title or source_id,
                    data["url"] or str(get_field(source_text, "url")),
                    source_id,
                    data["captured_at"],
                    data["topics"],
                )
            else:
                rollup_text = rollup_path.read_text(encoding="utf-8")
            rollup_text, annotation_added, _kind, engagement = merge_rollup(
                rollup_text,
                data["annotations"],
                source_id,
                data["url"] or str(get_field(source_text, "url")),
            )
            if annotation_added:
                source_text = set_fields(source_text, {"engagement": engagement})
        source_changed = is_new or annotation_added > 0
        if source_changed and not is_new and path_has_unstaged_changes(vault, source):
            raise CaptureError("Source has unstaged changes", EXIT_CONFLICT, id=source_id)
        if annotation_added and rollup_path and rollup_path.exists() and path_has_unstaged_changes(vault, rollup_path):
            raise CaptureError("Annotation has unstaged changes", EXIT_CONFLICT, id=source_id)
        if source_changed:
            atomic_write(source, source_text)
            changed_paths.append(source)
        if annotation_added and rollup_path:
            atomic_write(rollup_path, rollup_text)
            changed_paths.append(rollup_path)
        job_created = bool(is_new and data["kind"] == "web")
        job: dict[str, Any] | None = None
        if job_created:
            job = {
                "id": source_id,
                "source_path": relative(vault, source),
                "url": data["url"],
                "canonical_url": data["canonical_url"],
                "state": "queued",
                "attempts": 0,
                "created_at": data["captured_at"],
                "last_error": "",
            }
            write_job(vault, job)
        if not changed_paths:
            return {
                "ok": True,
                "result": "duplicate",
                "id": source_id,
                "source_path": relative(vault, source),
                "annotation_path": relative(vault, rollup_path) if rollup_path else None,
                "staged": True,
                "staged_paths": [],
                "job_created": False,
                "ingest_status": status,
                "paths_final": status != "pending" and bool(title),
            }
        try:
            staged_paths = stage_paths(vault, changed_paths)
        except CaptureError:
            if job:
                job["state"] = "blocked_git"
                write_job(vault, job)
            raise
        return {
            "ok": True,
            "result": "created" if is_new else "updated",
            "id": source_id,
            "source_path": relative(vault, source),
            "annotation_path": relative(vault, rollup_path) if rollup_path else None,
            "staged": True,
            "staged_paths": staged_paths,
            "job_created": job_created,
            "ingest_status": status,
            "annotation_entries_added": annotation_added,
            "paths_final": not job_created and bool(title),
        }


def job_source(vault: Path, job: dict[str, Any]) -> Path:
    source = vault_path(vault, str(job.get("source_path", "")))
    if not source.is_file() or str(get_field(source.read_text(encoding="utf-8"), "id")) != job.get("id"):
        raise CaptureError("Capture job Source is missing or mismatched", EXIT_STORAGE)
    return source


def cmd_finalize(vault: Path, source_id: str, input_file: str | None = None, *, _data: dict[str, Any] | None = None, _policy=None) -> dict[str, Any]:
    data = _data if _data is not None else read_json_input(input_file)
    reject_unknown_fields(data, FINALIZE_FIELDS, "finalize")
    title = inline(str(data.get("title", "")))
    markdown = safe_user_text(str(data.get("markdown", "")))
    if not title or not markdown:
        raise CaptureError("finalize requires non-empty title and markdown", EXIT_INPUT)
    if data.get("images_complete") is not True:
        raise CaptureError("finalize requires images_complete: true", EXIT_INPUT)
    author = validate_author(data.get("author"))
    publisher = inline(str(data.get("publisher", "")))
    published = validate_published(data.get("published"))
    retrieved_at = parse_time(data.get("retrieved_at"))
    summary = safe_user_text(str(data.get("summary", "")))
    language = inline(str(data.get("language", "")))
    final_url = str(data.get("final_url", "")).strip()
    canonical_final = normalize_url(final_url) if final_url else ""
    with capture_lock(vault):
        job = read_job(vault, source_id)
        source = job_source(vault, job)
        if job.get("state") == "ready":
            source_text = source.read_text(encoding="utf-8")
            return {
                "ok": True,
                "result": "duplicate",
                "id": source_id,
                "source_path": relative(vault, source),
                "staged": True,
                "staged_paths": [],
                "ingest_status": "ready",
                "content_hash": get_field(source_text, "content_hash"),
                "annotation_path": job.get("annotation_path"),
                "asset_paths": job.get("asset_paths", []),
                "paths_final": True,
            }
        rollups = find_rollups(vault, source_id)
        if len(rollups) > 1:
            raise CaptureError("More than one capture-managed Annotation rollup exists", EXIT_CONFLICT)
        targets = [source, *rollups]
        if any(path_has_unstaged_changes(vault, path) for path in targets):
            job["state"] = "conflict"
            write_job(vault, job)
            raise CaptureError("Capture target has unstaged changes", EXIT_CONFLICT, id=source_id)
        if canonical_final:
            collision = find_source_by_url(vault, canonical_final)
            if collision and collision.resolve() != source.resolve():
                job["state"] = "conflict"
                job["last_error"] = "Final URL matches another Source"
                write_job(vault, job)
                raise CaptureError("Final URL matches another Source", EXIT_CONFLICT, id=source_id)
        source_text = source.read_text(encoding="utf-8")
        source_url = final_url or str(get_field(source_text, "url"))
        captured_at = str(get_field(source_text, "captured"))
        final_source = source_path_for(
            vault,
            "web",
            source_id,
            title,
            author,
            publisher,
            source_url,
            captured_at,
        )
        if final_source != source and final_source.exists():
            raise CaptureError("Final Source path already exists", EXIT_CONFLICT, id=source_id)
        planned_final_rollup = annotation_path_for(vault, source_id, final_source.stem) if rollups else None
        if planned_final_rollup and planned_final_rollup != rollups[0] and planned_final_rollup.exists():
            raise CaptureError("Final Annotation path already exists", EXIT_CONFLICT, id=source_id)

        temp_root: Path | None = None
        moves: list[tuple[Path, Path]] = []
        try:
            markdown, temp_root, moves = download_image_assets(
                vault,
                source_id,
                markdown,
                data.get("images", []),
                source_url,
                policy=_policy,
            )
            for _staged, destination in moves:
                if destination.exists():
                    raise CaptureError("Final image path already exists", EXIT_CONFLICT, id=source_id)

            frontmatter, body = split_frontmatter(source_text)
            body = replace_heading(body, title)
            body = replace_summary(body, summary)
            body = replace_source_content(body, markdown)
            text = f"---\n{frontmatter}\n---\n\n{body.lstrip()}"
            updates: dict[str, Any] = {
                "title": title,
                "author": author,
                "publisher": publisher,
                "published": published,
                "retrieved_at": retrieved_at,
                "ingest_status": "ready",
                "content_hash": content_hash(markdown),
                "ingest_error": "",
                "retry_after": "",
            }
            if canonical_final:
                updates["canonical_url"] = canonical_final
            if language:
                updates["language"] = language
            if summary:
                updates["verification"] = "unverified"
            text = set_fields(text, updates)
            atomic_write(source, text)

            changed = [source]
            if final_source != source:
                os.replace(source, final_source)
                changed.append(final_source)

            final_rollup: Path | None = None
            for rollup in rollups:
                rollup_text = rollup.read_text(encoding="utf-8")
                rollup_title = f"{title}——批注"
                rollup_text = set_fields(
                    rollup_text,
                    {
                        "title": rollup_title,
                        "source": f"[[{source_id}]]",
                        "source_title": title,
                        "source_url": source_url,
                    },
                )
                rollup_text = normalize_rollup_links(rollup_text, source_id, title)
                rollup_text, _added, _kind, _engagement = merge_rollup(rollup_text, [], source_id, source_url)
                fm, rollup_body = split_frontmatter(rollup_text)
                rollup_body = replace_heading(rollup_body, rollup_title)
                atomic_write(rollup, f"---\n{fm}\n---\n\n{rollup_body.lstrip()}")
                final_rollup = planned_final_rollup
                assert final_rollup is not None
                if final_rollup != rollup:
                    os.replace(rollup, final_rollup)
                    changed.extend([rollup, final_rollup])
                else:
                    changed.append(rollup)

            asset_paths: list[Path] = []
            for staged, destination in moves:
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, destination)
                asset_paths.append(destination)
                changed.append(destination)

            job["source_path"] = relative(vault, final_source)
            job["annotation_path"] = relative(vault, final_rollup) if final_rollup else None
            job["asset_paths"] = [relative(vault, path) for path in asset_paths]
            write_job(vault, job)
            try:
                staged_paths = stage_paths(vault, changed)
            except CaptureError:
                job["state"] = "blocked_git"
                write_job(vault, job)
                raise
        finally:
            if temp_root:
                shutil.rmtree(temp_root, ignore_errors=True)
        job["state"] = "ready"
        job["attempts"] = int(job.get("attempts", 0)) + 1
        job["completed_at"] = retrieved_at
        job["last_error"] = ""
        write_job(vault, job)
        return {
            "ok": True,
            "id": source_id,
            "source_path": relative(vault, final_source),
            "annotation_path": job.get("annotation_path"),
            "asset_paths": job.get("asset_paths", []),
            "staged": True,
            "staged_paths": staged_paths,
            "ingest_status": "ready",
            "content_hash": updates["content_hash"],
            "paths_final": True,
            "methods_attempted": list(data.get("methods_attempted") or []),
        }


def sanitize_error(value: Any) -> str:
    text = inline(str(value))
    text = re.sub(r"(?i)(authorization|cookie|token|api[-_ ]?key|password)\s*[:=]\s*\S+", r"\1=[redacted]", text)
    text = re.sub(r"(?:[A-Za-z]:\\|/)[^\s]+", "[path]", text)
    return text[:300] or "Unspecified ingest failure"


def cmd_fail(vault: Path, source_id: str, input_file: str | None = None, *, _data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = _data if _data is not None else read_json_input(input_file)
    status = str(data.get("status", "failed"))
    if status not in {"failed", "manual"}:
        raise CaptureError("fail status must be failed or manual", EXIT_INPUT)
    error = sanitize_error(data.get("error", ""))
    retry_after = parse_time(data["retry_after"]) if data.get("retry_after") else ""
    with capture_lock(vault):
        job = read_job(vault, source_id)
        source = job_source(vault, job)
        if job.get("state") == "ready":
            raise CaptureError("A ready job cannot be marked failed", EXIT_CONFLICT, id=source_id)
        if path_has_unstaged_changes(vault, source):
            job["state"] = "conflict"
            write_job(vault, job)
            raise CaptureError("Source has unstaged changes", EXIT_CONFLICT, id=source_id)
        text = source.read_text(encoding="utf-8")
        text = set_fields(
            text,
            {"ingest_status": status, "ingest_error": error, "retry_after": retry_after},
        )
        atomic_write(source, text)
        try:
            staged_paths = stage_paths(vault, [source])
        except CaptureError:
            job["state"] = "blocked_git"
            write_job(vault, job)
            raise
        job["state"] = status
        job["attempts"] = int(job.get("attempts", 0)) + 1
        job["last_error"] = error
        job["retry_after"] = retry_after
        write_job(vault, job)
        return {
            "ok": True,
            "id": source_id,
            "source_path": relative(vault, source),
            "staged": True,
            "staged_paths": staged_paths,
            "ingest_status": status,
            "error": error,
            "paths_final": False,
            "methods_attempted": list(data.get("methods_attempted") or []),
        }


def public_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job.get("id"),
        "source_path": job.get("source_path"),
        "url": job.get("url"),
        "canonical_url": job.get("canonical_url"),
        "state": job.get("state"),
        "attempts": job.get("attempts", 0),
        "last_error": job.get("last_error", ""),
        "retry_after": job.get("retry_after", ""),
        "annotation_path": job.get("annotation_path"),
        "asset_paths": job.get("asset_paths", []),
        "paths_final": job.get("state") == "ready",
    }


def cmd_inspect(vault: Path, source_id: str) -> dict[str, Any]:
    job_file = queue_path(vault, source_id)
    if job_file.is_file():
        job = read_job(vault, source_id)
        source = job_source(vault, job)
        public = public_job(job)
    else:
        source = find_source_by_id(vault, source_id)
        if source is None:
            raise CaptureError("Source not found", EXIT_INPUT)
        public = None
    rollups = find_rollups(vault, source_id)
    annotation_path = public.get("annotation_path") if public else (relative(vault, rollups[0]) if len(rollups) == 1 else None)
    paths_final = bool(public and public.get("state") == "ready") if public else source.stem != source_id
    text = source.read_text(encoding="utf-8")
    return {
        "ok": True,
        "job": public,
        "source_path": relative(vault, source),
        "ingest_status": get_field(text, "ingest_status"),
        "title": get_field(text, "title"),
        "annotation_path": annotation_path,
        "asset_paths": public.get("asset_paths", []) if public else [],
        "paths_final": paths_final,
    }


def cmd_list_retryable(vault: Path, source_id: str | None) -> dict[str, Any]:
    jobs: list[dict[str, Any]] = []
    if source_id:
        job = read_job(vault, source_id)
        if job.get("state") in {"failed", "manual"}:
            jobs.append(public_job(job))
    else:
        queue_dir = vault_path(vault, ".queue/vault-capture")
        if queue_dir.is_dir():
            for path in sorted(queue_dir.glob("*.json")):
                try:
                    job = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if isinstance(job, dict) and job.get("state") == "failed":
                    jobs.append(public_job(job))
    return {"ok": True, "jobs": jobs, "count": len(jobs)}


def resolve_vault(argument: str | None) -> Path:
    raw = argument or os.environ.get("VAULT_ROOT", "")
    if not raw:
        raise CaptureError("VAULT_ROOT is not configured", EXIT_INPUT)
    return Path(raw).expanduser().resolve()


def cmd_ingest_web(vault: Path, source_id: str) -> dict[str, Any]:
    if web_extract is None:
        raise CaptureError(
            "web_extract dependencies are not installed; run pip install -r requirements-web.txt",
            EXIT_STORAGE,
        )
    # Read the job and handle the already-ready duplicate under the lock, then
    # release before calling finalize/fail (each re-acquires the lock itself).
    with capture_lock(vault):
        job = read_job(vault, source_id)
        if job.get("state") == "ready":
            source = job_source(vault, job)
            source_text = source.read_text(encoding="utf-8")
            return {
                "ok": True,
                "result": "duplicate",
                "id": source_id,
                "source_path": relative(vault, source),
                "staged": True,
                "staged_paths": [],
                "ingest_status": "ready",
                "content_hash": get_field(source_text, "content_hash"),
                "annotation_path": job.get("annotation_path"),
                "asset_paths": job.get("asset_paths", []),
                "paths_final": True,
            }
        url = str(job.get("url", "")).strip()
    if not url:
        raise CaptureError("Capture job has no URL", EXIT_INPUT)
    profile_dir = os.environ.get("VAULT_CAPTURE_BROWSER_PROFILE", "") or None
    try:
        policy = network_security.NetworkPolicy.from_environment()
    except network_security.NetworkPolicyError as exc:
        # Invalid/partial Fake-IP configuration fails closed with a short,
        # non-sensitive error and preserves the staged Source.
        return cmd_fail(
            vault, source_id,
            _data={"status": "failed", "error": exc.reason},
        )
    try:
        result = web_extract.extract_article(url, profile_dir=profile_dir, policy=policy)
    except web_extract.ExtractionError as exc:
        status = exc.state if exc.state in ("failed", "manual") else "failed"
        return cmd_fail(
            vault, source_id,
            _data={
                "status": status,
                "error": exc.reason,
                "methods_attempted": list(exc.methods_attempted),
            },
        )
    retrieved_at = dt.datetime.now().astimezone().replace(microsecond=0).isoformat()
    finalize_data = {
        "title": result.title,
        "author": result.author,
        "publisher": result.publisher,
        "published": result.published,
        "markdown": result.markdown,
        "images": [{"token": img.token, "url": img.url} for img in result.images],
        "images_complete": True,
        "final_url": result.final_url or url,
        "retrieved_at": retrieved_at,
        "language": result.language,
        "methods_attempted": list(result.methods_attempted),
    }
    try:
        return cmd_finalize(vault, source_id, _data=finalize_data, _policy=policy)
    except CaptureError as exc:
        if exc.code == EXIT_CONFLICT:
            raise
        sanitized = sanitize_error(str(exc))
        return cmd_fail(vault, source_id, _data={"status": "failed", "error": sanitized})



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    stage = sub.add_parser("stage")
    stage.add_argument("--json-file")
    final = sub.add_parser("finalize")
    final.add_argument("id")
    final.add_argument("--json-file")
    failure = sub.add_parser("fail")
    failure.add_argument("id")
    failure.add_argument("--json-file")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("id")
    retry = sub.add_parser("list-retryable")
    retry.add_argument("id", nargs="?")
    ingest_web = sub.add_parser("ingest-web")
    ingest_web.add_argument("id")
    return parser


def main() -> int:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    parser = build_parser()
    args = parser.parse_args()
    try:
        vault = resolve_vault(args.vault)
        ensure_repo(vault)
        if args.command == "preflight":
            result = {"ok": True, "git": True, "queue_ignored": True, "layout": True}
        elif args.command == "stage":
            result = cmd_stage(vault, args.json_file)
        elif args.command == "finalize":
            result = cmd_finalize(vault, args.id, args.json_file)
        elif args.command == "fail":
            result = cmd_fail(vault, args.id, args.json_file)
        elif args.command == "inspect":
            result = cmd_inspect(vault, args.id)
        elif args.command == "ingest-web":
            result = cmd_ingest_web(vault, args.id)
        else:
            result = cmd_list_retryable(vault, args.id)
        emit(result)
        return 0
    except CaptureError as exc:
        payload = {"ok": False, "error": str(exc), **exc.details}
        payload.setdefault("staged", False)
        emit(payload)
        return exc.code
    except network_security.NetworkPolicyError as exc:
        # Defensive safety net: a network-policy error must never surface a raw
        # traceback/environment/absolute path from the CLI. Emit a short safe
        # error and fail closed.
        emit({"ok": False, "error": exc.reason, "staged": False})
        return EXIT_INPUT
    except OSError:
        emit({"ok": False, "error": "Filesystem operation failed", "staged": False})
        return EXIT_STORAGE


if __name__ == "__main__":
    raise SystemExit(main())
