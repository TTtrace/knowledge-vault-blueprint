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
import string
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit


EXIT_INPUT = 2
EXIT_CONFLICT = 3
EXIT_STORAGE = 4
ROLLUP_MARKER = "<!-- vault-capture:annotation-rollup -->"
ENTRIES_START = "<!-- vault-capture:entries:start -->"
ENTRIES_END = "<!-- vault-capture:entries:end -->"
SOURCE_START = "<!-- source-content:start -->"
SOURCE_END = "<!-- source-content:end -->"
ENTRY_RE = re.compile(r"(?m)^<!-- vault-capture:entry (\{.*\}) -->$")
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
        if isinstance(value, list):
            if value:
                lines.append(f"{key}:")
                lines.extend(f"  - {yaml_scalar(item)}" for item in value)
            else:
                lines.append(f"{key}: []")
        else:
            lines.append(f"{key}: {yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


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
    for line in lines:
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):", line)
        if match and match.group(1) in updates:
            key = match.group(1)
            output.append(f"{key}: {yaml_scalar(updates[key])}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}: {yaml_scalar(value)}")
    return f"---\n{'\n'.join(output)}\n---\n\n{body.lstrip()}"


def sanitize_filename(value: str, fallback: str) -> str:
    value = inline(value) or fallback
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "-", value)
    value = re.sub(r"[. ]+$", "", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-.")
    return (value or fallback)[:80]


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
    identity = run_git(vault, ["var", "GIT_AUTHOR_IDENT"], check=False)
    if identity.returncode != 0:
        raise CaptureError("Git author identity is not configured", EXIT_INPUT)
    required = ["sources/web", "sources/transcripts", "sources/documents", "notes/annotations", "notes/ideas"]
    if any(not vault_path(vault, item).is_dir() for item in required):
        raise CaptureError("Vault is missing required capture directories", EXIT_INPUT)
    ignored = run_git(vault, ["check-ignore", "-q", ".queue/vault-capture/probe"], check=False)
    if ignored.returncode != 0:
        raise CaptureError(".queue/vault-capture must be ignored by Git", EXIT_INPUT)


def path_dirty(vault: Path, path: Path) -> bool:
    rel = relative(vault, path)
    result = run_git(vault, ["status", "--porcelain", "--untracked-files=all", "--", rel])
    return bool(result.stdout.strip())


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


def commit_paths(vault: Path, paths: list[Path], message: str) -> str:
    rels = [relative(vault, path) for path in paths]
    run_git(vault, ["add", "--", *rels])
    result = run_git(vault, ["commit", "--only", "-m", message, "--", *rels], check=False)
    if result.returncode != 0:
        raise CaptureError("Git commit failed; captured files remain on disk", EXIT_STORAGE, paths=rels)
    return run_git(vault, ["rev-parse", "HEAD"]).stdout.strip()


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
    why_saved: str,
    priority: int,
    topics: list[str],
    text: str,
) -> str:
    fields = [
        ("schema_version", 1),
        ("id", source_id),
        ("type", "source"),
        ("medium", medium),
        ("title", title),
        ("url", url),
        ("canonical_url", canonical_url),
        ("author", []),
        ("published", None),
        ("captured", captured_at),
        ("retrieved_at", None),
        ("language", None),
        ("ingest_status", status),
        ("read_status", "unread"),
        ("engagement", "captured"),
        ("priority", priority),
        ("estimated_minutes", None),
        ("why_saved", why_saved),
        ("capture_method", "openclaw"),
        ("topics", topics),
        ("tags", []),
    ]
    body_text = safe_user_text(text)
    body = [f"# {inline(title)}", "", "> [!info] 来源"]
    if url:
        body.append(f"> [打开原网页]({url})")
    body.extend(["", "## 摘要", "", "", "## 原文", "", SOURCE_START, ""])
    if body_text:
        body.append(body_text)
        body.append("")
    body.extend([SOURCE_END, ""])
    return yaml_document(fields) + "\n\n" + "\n".join(body)


def append_capture_history(text: str, reason: str, captured_at: str) -> tuple[str, bool]:
    reason = safe_user_text(reason)
    if not reason:
        return text, False
    normalized = normalize_text(reason)
    original = normalize_text(str(get_field(text, "why_saved", "")))
    reason_key = content_hash(normalized)
    if normalized == original or f"<!-- vault-capture:reason {reason_key} -->" in text:
        return text, False
    reason_lines = reason.splitlines() or [""]
    rendered_reason = reason_lines[0]
    if len(reason_lines) > 1:
        rendered_reason += "\n" + "\n".join(f"  {line}" for line in reason_lines[1:])
    addition = f"<!-- vault-capture:reason {reason_key} -->\n- {captured_at} — {rendered_reason}\n"
    heading = "## 捕获历史"
    if heading not in text:
        block = f"\n{heading}\n\n{addition}\n"
        marker = "\n## 摘要\n"
        return (text.replace(marker, block + "## 摘要\n", 1) if marker in text else text + block), True
    start = text.index(heading) + len(heading)
    next_heading = text.find("\n## ", start)
    insert_at = len(text) if next_heading < 0 else next_heading
    return text[:insert_at].rstrip() + "\n" + addition + "\n" + text[insert_at:].lstrip("\n"), True


def validate_annotations(raw: Any, default_time: str) -> list[dict[str, str]]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise CaptureError("annotations must be a list", EXIT_INPUT)
    result: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise CaptureError("Each annotation must be an object", EXIT_INPUT)
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
    rendered = f"- {captured_at} — {lines[0]}"
    if len(lines) > 1:
        rendered += "\n" + "\n".join(f"  {line}" for line in lines[1:])
    return f"<!-- vault-capture:comment {key} -->\n{rendered}"


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
        entries.append({"meta": meta, "block": region[match.end() : block_end]})
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
        ("title", title),
        ("source", f"[[{source_link}]]"),
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
    body = f"# {inline(title)}\n\n{ROLLUP_MARKER}\n\n## 摘录与批注\n\n{ENTRIES_START}\n{ENTRIES_END}\n"
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
            meta = {"key": key, "quote": bool(quote_norm), "comments": [comment_key] if comment_key else []}
            locator = item["locator"] or "未定位"
            block_parts = [f"\n\n## {item['captured_at']} · {locator}\n"]
            if item["quote"]:
                block_parts.extend(["", quote_markdown(item["quote"]), ""])
            target = source_link + (f"#{item['locator'].replace(']', '')}" if item["locator"] else "")
            block_parts.append(f"来源：[[{target}]]" + (f" · [原文]({source_url})" if source_url else ""))
            block_parts.extend(["", "评论：", ""])
            if comment_key:
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
    for entry in entries:
        meta_json = json.dumps(entry["meta"], ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        region_parts.append(f"\n<!-- vault-capture:entry {meta_json} -->{entry['block'].rstrip()}\n")
    merged_body = prefix + "".join(region_parts) + suffix
    merged = f"---\n{frontmatter}\n---\n\n{merged_body.lstrip()}"
    merged = set_fields(merged, {"annotation_kind": kind, "engagement": engagement})
    return merged, added, kind, engagement


def replace_heading(body: str, title: str) -> str:
    return re.sub(r"(?m)^# .*$", f"# {inline(title)}", body, count=1)


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
    text = safe_user_text(str(data.get("text", "")))
    if kind == "idea" and not text:
        raise CaptureError("idea capture requires text", EXIT_INPUT)
    medium_default = {"web": "article", "transcript": "transcript", "document": "document", "ocr": "document"}.get(kind, "")
    medium = str(data.get("medium") or medium_default)
    if kind != "idea" and medium not in SOURCE_MEDIA:
        raise CaptureError("Unsupported Source medium", EXIT_INPUT)
    return {
        "kind": kind,
        "captured_at": captured_at,
        "topics": [inline(item) for item in topics if inline(item)],
        "priority": priority,
        "url": url,
        "canonical_url": canonical_url,
        "title": inline(str(data.get("title", ""))),
        "text": text,
        "why_saved": safe_user_text(str(data.get("why_saved", ""))),
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
        commit = commit_paths(vault, [path], f"capture(idea): add {idea_id}")
    except CaptureError as exc:
        exc.details.update({"id": idea_id, "source_path": relative(vault, path), "committed": False})
        raise
    return {
        "ok": True,
        "result": "created",
        "id": idea_id,
        "source_path": relative(vault, path),
        "annotation_path": None,
        "committed": True,
        "commit": commit,
        "job_created": False,
        "ingest_status": "ready",
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
            host = urlsplit(data["canonical_url"]).hostname if data["canonical_url"] else data["kind"]
            title = data["title"] or (f"待抓取：{host}" if data["kind"] == "web" else f"待处理：{data['kind']}")
            folder = "sources/web" if data["kind"] == "web" else (
                "sources/transcripts" if data["kind"] == "transcript" else "sources/documents"
            )
            source = vault_path(vault, f"{folder}/{source_id}--{sanitize_filename(title, data['kind'])}.md")
            status = "pending" if data["kind"] == "web" else "manual"
            source_text = render_source(
                source_id,
                title,
                data["medium"],
                data["url"],
                data["canonical_url"],
                data["captured_at"],
                status,
                data["why_saved"],
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
        history_added = False
        if not is_new:
            source_text, history_added = append_capture_history(source_text, data["why_saved"], data["captured_at"])
        rollups = find_rollups(vault, source_id)
        if len(rollups) > 1:
            raise CaptureError("More than one capture-managed Annotation rollup exists", EXIT_CONFLICT)
        rollup_path = rollups[0] if rollups else None
        annotation_added = 0
        if data["annotations"]:
            if rollup_path is None:
                annotation_id = new_id(data["captured_at"])
                rollup_title = f"{title}——批注"
                rollup_path = vault_path(
                    vault, f"notes/annotations/{annotation_id}--{sanitize_filename(rollup_title, 'annotations')}.md"
                )
                rollup_text = render_rollup(
                    annotation_id,
                    source_id,
                    title,
                    data["url"] or str(get_field(source_text, "url")),
                    source.stem,
                    data["captured_at"],
                    data["topics"],
                )
            else:
                rollup_text = rollup_path.read_text(encoding="utf-8")
            rollup_text, annotation_added, _kind, engagement = merge_rollup(
                rollup_text,
                data["annotations"],
                source.stem,
                data["url"] or str(get_field(source_text, "url")),
            )
            if annotation_added:
                source_text = set_fields(source_text, {"engagement": engagement})
        source_changed = is_new or history_added or annotation_added > 0
        if source_changed and not is_new and path_dirty(vault, source):
            raise CaptureError("Source has uncommitted changes", EXIT_CONFLICT, id=source_id)
        if annotation_added and rollup_path and rollup_path.exists() and path_dirty(vault, rollup_path):
            raise CaptureError("Annotation has uncommitted changes", EXIT_CONFLICT, id=source_id)
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
                "committed": True,
                "commit": None,
                "job_created": False,
                "ingest_status": status,
            }
        message = (
            f"capture(source+annotations): add {source_id} with {annotation_added} entries"
            if annotation_added
            else f"capture(source): add queued source {source_id}"
        )
        try:
            commit = commit_paths(vault, changed_paths, message)
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
            "committed": True,
            "commit": commit,
            "job_created": job_created,
            "ingest_status": status,
            "annotation_entries_added": annotation_added,
            "capture_history_added": history_added,
        }


def job_source(vault: Path, job: dict[str, Any]) -> Path:
    source = vault_path(vault, str(job.get("source_path", "")))
    if not source.is_file() or str(get_field(source.read_text(encoding="utf-8"), "id")) != job.get("id"):
        raise CaptureError("Capture job Source is missing or mismatched", EXIT_STORAGE)
    return source


def cmd_finalize(vault: Path, source_id: str, input_file: str | None = None) -> dict[str, Any]:
    data = read_json_input(input_file)
    title = inline(str(data.get("title", "")))
    markdown = safe_user_text(str(data.get("markdown", "")))
    if not title or not markdown:
        raise CaptureError("finalize requires non-empty title and markdown", EXIT_INPUT)
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
                "committed": True,
                "commit": None,
                "ingest_status": "ready",
                "content_hash": get_field(source_text, "content_hash"),
            }
        rollups = find_rollups(vault, source_id)
        if len(rollups) > 1:
            raise CaptureError("More than one capture-managed Annotation rollup exists", EXIT_CONFLICT)
        targets = [source, *rollups]
        if any(path_dirty(vault, path) for path in targets):
            job["state"] = "conflict"
            write_job(vault, job)
            raise CaptureError("Capture target has uncommitted changes", EXIT_CONFLICT, id=source_id)
        if canonical_final:
            collision = find_source_by_url(vault, canonical_final)
            if collision and collision.resolve() != source.resolve():
                job["state"] = "conflict"
                job["last_error"] = "Final URL matches another Source"
                write_job(vault, job)
                raise CaptureError("Final URL matches another Source", EXIT_CONFLICT, id=source_id)
        text = source.read_text(encoding="utf-8")
        frontmatter, body = split_frontmatter(text)
        body = replace_heading(body, title)
        body = replace_summary(body, summary)
        body = replace_source_content(body, markdown)
        text = f"---\n{frontmatter}\n---\n\n{body.lstrip()}"
        updates: dict[str, Any] = {
            "title": title,
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
        for rollup in rollups:
            rollup_text = rollup.read_text(encoding="utf-8")
            rollup_title = f"{title}——批注"
            rollup_text = set_fields(rollup_text, {"title": rollup_title, "source_title": title})
            fm, rollup_body = split_frontmatter(rollup_text)
            rollup_body = replace_heading(rollup_body, rollup_title)
            atomic_write(rollup, f"---\n{fm}\n---\n\n{rollup_body.lstrip()}")
            changed.append(rollup)
        try:
            commit = commit_paths(vault, changed, f"ingest(source): fetch {source_id}")
        except CaptureError:
            job["state"] = "blocked_git"
            write_job(vault, job)
            raise
        job["state"] = "ready"
        job["attempts"] = int(job.get("attempts", 0)) + 1
        job["completed_at"] = retrieved_at
        job["last_error"] = ""
        write_job(vault, job)
        return {
            "ok": True,
            "id": source_id,
            "source_path": relative(vault, source),
            "committed": True,
            "commit": commit,
            "ingest_status": "ready",
            "content_hash": updates["content_hash"],
        }


def sanitize_error(value: Any) -> str:
    text = inline(str(value))
    text = re.sub(r"(?i)(authorization|cookie|token|api[-_ ]?key|password)\s*[:=]\s*\S+", r"\1=[redacted]", text)
    text = re.sub(r"(?:[A-Za-z]:\\|/)[^\s]+", "[path]", text)
    return text[:300] or "Unspecified ingest failure"


def cmd_fail(vault: Path, source_id: str, input_file: str | None = None) -> dict[str, Any]:
    data = read_json_input(input_file)
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
        if path_dirty(vault, source):
            job["state"] = "conflict"
            write_job(vault, job)
            raise CaptureError("Source has uncommitted changes", EXIT_CONFLICT, id=source_id)
        text = source.read_text(encoding="utf-8")
        text = set_fields(
            text,
            {"ingest_status": status, "ingest_error": error, "retry_after": retry_after},
        )
        atomic_write(source, text)
        try:
            commit = commit_paths(vault, [source], f"ingest(source): mark {source_id} {status}")
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
            "committed": True,
            "commit": commit,
            "ingest_status": status,
            "error": error,
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
    text = source.read_text(encoding="utf-8")
    return {
        "ok": True,
        "job": public,
        "source_path": relative(vault, source),
        "ingest_status": get_field(text, "ingest_status"),
        "title": get_field(text, "title"),
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
        else:
            result = cmd_list_retryable(vault, args.id)
        emit(result)
        return 0
    except CaptureError as exc:
        payload = {"ok": False, "error": str(exc), **exc.details}
        payload.setdefault("committed", False)
        emit(payload)
        return exc.code
    except OSError:
        emit({"ok": False, "error": "Filesystem operation failed", "committed": False})
        return EXIT_STORAGE


if __name__ == "__main__":
    raise SystemExit(main())
