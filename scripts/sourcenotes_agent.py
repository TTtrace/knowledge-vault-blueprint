#!/usr/bin/env python3
"""Controlled single entrypoint for the NotesVaulter agent (Capture/Query/Maintenance).

The entrypoint reads its target exclusively from the host-provided ``VAULT_ROOT``
environment variable; there is no flag that lets a model choose an arbitrary
vault/root.  Every command returns one stable JSON object on stdout and an
exit code (0 done, 2 invalid input/config, 3 conflict, 4 filesystem/git).

Capture delegates to the existing ``vault_capture.py`` transaction contract and
never re-implements write logic.  Query and Maintenance are strictly read-only.
Errors never leak absolute host/Vault paths.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Iterator

SCRIPT_DIR = Path(__file__).resolve().parent
CAPTURE_SCRIPTS = SCRIPT_DIR.parent / "skills" / "vault-capture" / "scripts"
sys.path.insert(0, str(CAPTURE_SCRIPTS))
import vault_capture  # noqa: E402  (reuse the exact capture transaction contract)

EXIT_INPUT = 2
EXIT_CONFLICT = 3
EXIT_STORAGE = 4

# Input/output bounds (see specifications/agent-operations.md §5).
MAX_STAGE_INPUT_BYTES = 1024 * 1024
MAX_QUERY_LEN = 500
MAX_RESULTS = 20
MAX_SNIPPET_CHARS = 300
MAX_BODY_EXCERPT_CHARS = 2000
MAX_OUTPUT_BYTES = 256 * 1024
MAX_LIST_ITEMS = 20
MAX_ID_LEN = 128
MAX_TITLE_LEN = 300
MAX_PATH_LEN = 512
MAX_ERROR_LEN = 500
MAX_DETAIL_LEN = 500

ID_RE = re.compile(r"[0-9]{8}-[0-9]{6}-[a-z0-9]{4}")
ID_STRICT_RE = re.compile(r"^[a-zA-Z0-9-]+$")

SKIP_DIRS = {".git", ".obsidian", ".queue", ".trash", ".smart-env", "assets"}

WARN_IMAGE_OVER_5MIB = 5 * 1024 * 1024
WARN_SOURCE_OVER_30MIB = 30 * 1024 * 1024
GATE_ATTACHMENTS_2GIB = 2 * 1024 * 1024 * 1024


class OpsError(Exception):
    def __init__(self, message: str, code: int, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def cap_str(value: Any, limit: int) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"


def cap_value(value: Any, limit: int) -> Any:
    if isinstance(value, str):
        return cap_str(value, limit)
    if isinstance(value, (list, tuple)):
        return [cap_value(item, limit) for item in value][:MAX_LIST_ITEMS]
    if isinstance(value, dict):
        return {cap_str(key, limit): cap_value(item, limit) for key, item in value.items()}
    return value


def emit(data: dict[str, Any]) -> int:
    """Serialize and print one JSON object; enforce the global UTF-8 byte cap so
    stdout is always a single valid JSON object.  Returns the exit code to use
    (0 on success, EXIT_INPUT when the payload exceeded the cap and a short
    safe error was printed instead)."""
    text = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if len(text.encode("utf-8")) > MAX_OUTPUT_BYTES:
        fallback = {"ok": False, "error": "Output limit exceeded", "truncated": True}
        print(json.dumps(fallback, ensure_ascii=False, sort_keys=True))
        return EXIT_INPUT
    print(text)
    return 0


def fail(message: str, code: int = EXIT_INPUT, **details: Any) -> int:
    payload: dict[str, Any] = {"ok": False, "error": cap_str(message, MAX_ERROR_LEN)}
    payload.update(cap_value(details, MAX_DETAIL_LEN))
    emit_code = emit(payload)
    return code if emit_code == 0 else emit_code


def run_git(vault: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(vault), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise OpsError("Git could not be executed", EXIT_STORAGE) from exc


def resolve_vault() -> Path:
    raw = os.environ.get("VAULT_ROOT", "")
    if not raw:
        raise OpsError("VAULT_ROOT is not configured", EXIT_INPUT)
    vault = Path(raw).expanduser().resolve()
    if not vault.is_dir():
        raise OpsError("VAULT_ROOT is not a directory", EXIT_INPUT)
    if shutil.which("git") is None:
        raise OpsError("Git is not available", EXIT_INPUT)
    result = run_git(vault, ["rev-parse", "--show-toplevel"])
    if result.returncode != 0 or Path(result.stdout.strip()).resolve() != vault:
        raise OpsError("VAULT_ROOT must be the root of a Git repository", EXIT_INPUT)
    return vault


def require_vault_layout(vault: Path) -> None:
    if not any((vault / item).is_dir() for item in ("sources", "notes")):
        raise OpsError("Vault is missing required note directories", EXIT_INPUT)


def validate_id(source_id: str) -> str:
    if not ID_STRICT_RE.fullmatch(source_id):
        raise OpsError("Invalid source ID", EXIT_INPUT)
    return source_id


def read_capped_stdin() -> bytes:
    raw = sys.stdin.buffer.read(MAX_STAGE_INPUT_BYTES + 1)
    if len(raw) > MAX_STAGE_INPUT_BYTES:
        raise OpsError("Stage input is too large", EXIT_INPUT)
    return raw


# ---------------------------------------------------------------------------
# capture family: delegate to the existing vault_capture.py transaction
# ---------------------------------------------------------------------------

def cmd_capture_preflight(vault: Path) -> dict[str, Any]:
    vault_capture.ensure_repo(vault)
    return {"ok": True, "git": True, "queue_ignored": True, "layout": True}


def cmd_capture_stage(vault: Path, json_file: str | None) -> dict[str, Any]:
    vault_capture.ensure_repo(vault)
    if json_file:
        return vault_capture.cmd_stage(vault, json_file)
    raw = read_capped_stdin()
    try:
        text = raw.decode("utf-8")
        json.loads(text)  # early syntax validation
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OpsError("Stage input must contain one UTF-8 JSON object", EXIT_INPUT) from exc
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        handle.write(text)
        temp_path = handle.name
    try:
        return vault_capture.cmd_stage(vault, temp_path)
    finally:
        with __import__("contextlib").suppress(OSError):
            os.unlink(temp_path)


def cmd_capture_ingest(vault: Path, source_id: str) -> dict[str, Any]:
    vault_capture.ensure_repo(vault)
    return vault_capture.cmd_ingest_web(vault, validate_id(source_id))


def cmd_capture_inspect(vault: Path, source_id: str) -> dict[str, Any]:
    vault_capture.ensure_repo(vault)
    return vault_capture.cmd_inspect(vault, validate_id(source_id))


def cmd_capture_list_retryable(vault: Path, source_id: str | None) -> dict[str, Any]:
    vault_capture.ensure_repo(vault)
    return vault_capture.cmd_list_retryable(vault, validate_id(source_id) if source_id else None)


# ---------------------------------------------------------------------------
# query family: strictly read-only, bounded, path-safe
# ---------------------------------------------------------------------------

def vault_relative(vault: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(vault.resolve()).as_posix()
    except ValueError as exc:
        raise OpsError("Path escapes the Vault", EXIT_INPUT) from exc


def ensure_path_safe(vault: Path, path: Path) -> None:
    """Fail closed on any symlink in the relative path (the file itself or any
    parent component) and on any path that resolves outside the Vault root.
    Shared by iter_markdown and safe_vault_path so search/show/related all obey
    the same safety boundary."""
    vault_root = vault.resolve()
    cursor = vault_root
    for part in path.relative_to(vault).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise OpsError("Vault contains a symlinked note path; refusing to read", EXIT_INPUT)
    try:
        path.resolve().relative_to(vault_root)
    except ValueError as exc:
        raise OpsError("Path escapes the Vault", EXIT_INPUT) from exc


def safe_vault_path(vault: Path, rel: str) -> Path:
    if not isinstance(rel, str) or not rel.strip():
        raise OpsError("A Vault-relative path is required", EXIT_INPUT)
    if Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise OpsError("Absolute paths and parent traversal are not allowed", EXIT_INPUT)
    candidate = vault / Path(rel)
    ensure_path_safe(vault, candidate)
    if not candidate.is_file() or candidate.suffix.lower() != ".md":
        raise OpsError("Only Markdown files inside the Vault can be shown", EXIT_INPUT)
    return candidate


def iter_markdown(vault: Path) -> Iterator[Path]:
    """Yield Vault-relative Markdown files, failing closed on ANY symlink (file or
    directory) inside the queryable note tree.  Ignored system directories listed
    in SKIP_DIRS are fully excluded per contract, so symlinks inside them are never
    scanned and never cause a failure."""
    for root, dirs, files in os.walk(vault, followlinks=False):
        dirs[:] = sorted(item for item in dirs if item not in SKIP_DIRS)
        root_path = Path(root)
        for name in dirs:
            candidate = root_path / name
            if candidate.is_symlink():
                raise OpsError("Vault contains a symlinked directory; refusing to read", EXIT_INPUT)
        for name in sorted(files):
            if not name.endswith(".md"):
                continue
            path = root_path / name
            if any(part in SKIP_DIRS for part in path.relative_to(vault).parts):
                continue
            ensure_path_safe(vault, path)
            yield path


def read_note(path: Path) -> str:
    try:
        data = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise OpsError("Note could not be read", EXIT_STORAGE) from exc
    if len(data) > 4 * 1024 * 1024:
        raise OpsError("Note is too large", EXIT_STORAGE)
    return data


def note_meta(text: str) -> tuple[str | None, str | None, str | None]:
    """Extract (id, title, type) from frontmatter when parseable, else None."""
    try:
        frontmatter, body = vault_capture.split_frontmatter(text)
    except vault_capture.CaptureError:
        return None, None, None
    note_id = str(vault_capture.get_field(text, "id") or "") or None
    title = str(vault_capture.get_field(text, "title") or "") or None
    note_type = str(vault_capture.get_field(text, "type") or "") or None
    if not title:
        match = re.search(r"(?m)^#\s+(.+)$", body)
        if match:
            title = match.group(1).strip()
    return note_id, title, note_type


def excerpt_around(text: str, needle: str, radius: int = 150) -> str:
    position = text.lower().find(needle.lower())
    if position < 0:
        return text[:MAX_SNIPPET_CHARS]
    start = max(0, position - radius)
    end = min(len(text), position + len(needle) + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return (prefix + re.sub(r"\s+", " ", text[start:end]).strip() + suffix)[:MAX_SNIPPET_CHARS]


def cmd_query_search(vault: Path, query: str) -> dict[str, Any]:
    require_vault_layout(vault)
    if not query.strip():
        raise OpsError("A non-empty query is required", EXIT_INPUT)
    if len(query) > MAX_QUERY_LEN:
        raise OpsError("Query is too long", EXIT_INPUT)
    needle = " ".join(query.split())
    results: list[dict[str, Any]] = []
    for path in iter_markdown(vault):
        if len(results) >= MAX_RESULTS:
            break
        text = read_note(path)
        if needle.lower() not in text.lower():
            continue
        note_id, title, _note_type = note_meta(text)
        results.append(
            {
                "id": cap_str(note_id, MAX_ID_LEN) if note_id else None,
                "path": cap_str(vault_relative(vault, path), MAX_PATH_LEN),
                "title": cap_str(title, MAX_TITLE_LEN) if title else None,
                "excerpt": excerpt_around(text, needle),
            }
        )
    return {"ok": True, "results": results, "count": len(results)}


def cmd_query_show(vault: Path, rel: str) -> dict[str, Any]:
    require_vault_layout(vault)
    path = safe_vault_path(vault, rel)
    text = read_note(path)
    note_id, title, note_type = note_meta(text)
    body = text
    try:
        _fm, body = vault_capture.split_frontmatter(text)
    except vault_capture.CaptureError:
        pass
    return {
        "ok": True,
        "id": cap_str(note_id, MAX_ID_LEN) if note_id else None,
        "title": cap_str(title, MAX_TITLE_LEN) if title else None,
        "type": cap_str(note_type, MAX_TITLE_LEN) if note_type else None,
        "path": cap_str(vault_relative(vault, path), MAX_PATH_LEN),
        "excerpt": body.strip()[:MAX_BODY_EXCERPT_CHARS],
        "excerpt_truncated": len(body.strip()) > MAX_BODY_EXCERPT_CHARS,
    }


def link_keys(target: str) -> list[str]:
    keys: list[str] = []
    if ID_STRICT_RE.fullmatch(target):
        keys.append(target)
    stem = target
    if stem.endswith(".md"):
        stem = stem[: -len(".md")]
    keys.append(stem)
    return list(dict.fromkeys(key for key in keys if key))


def cmd_query_related(vault: Path, target: str) -> dict[str, Any]:
    require_vault_layout(vault)
    keys = link_keys(target)
    results: list[dict[str, Any]] = []
    for path in iter_markdown(vault):
        if len(results) >= MAX_RESULTS:
            break
        text = read_note(path)
        link_pattern = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
        found: str | None = None
        for match in link_pattern.finditer(text):
            inner = match.group(1).strip()
            if any(inner == key or inner.endswith("/" + key) for key in keys):
                found = match.group(0)
                break
        if found is None:
            continue
        note_id, title, _note_type = note_meta(text)
        results.append(
            {
                "id": cap_str(note_id, MAX_ID_LEN) if note_id else None,
                "path": cap_str(vault_relative(vault, path), MAX_PATH_LEN),
                "title": cap_str(title, MAX_TITLE_LEN) if title else None,
                "excerpt": excerpt_around(text, found),
            }
        )
    return {"ok": True, "results": results, "count": len(results)}


# ---------------------------------------------------------------------------
# maintenance family: strictly read-only report
# ---------------------------------------------------------------------------

def git_state(vault: Path) -> dict[str, Any]:
    branch_result = run_git(vault, ["rev-parse", "--abbrev-ref", "HEAD"])
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unborn"
    head_result = run_git(vault, ["rev-parse", "HEAD"])
    head = head_result.stdout.strip() if head_result.returncode == 0 else ""
    upstream = ""
    upstream_result = run_git(vault, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    ahead: int | None = None
    behind: int | None = None
    if upstream_result.returncode == 0:
        upstream = upstream_result.stdout.strip()
        count_result = run_git(vault, ["rev-list", "--left-right", "--count", f"{upstream}...HEAD"])
        if count_result.returncode == 0:
            parts = count_result.stdout.split()
            if len(parts) == 2:
                behind, ahead = int(parts[0]), int(parts[1])
    dirty_result = run_git(vault, ["status", "--porcelain", "--untracked-files=all"])
    dirty_lines = [line for line in dirty_result.stdout.splitlines() if line.strip()]
    staged_result = run_git(vault, ["diff", "--cached", "--name-only"])
    staged_lines = [line for line in staged_result.stdout.splitlines() if line.strip()]
    return {
        "branch": cap_str(branch, MAX_PATH_LEN),
        "head": cap_str(head, MAX_PATH_LEN),
        "upstream": cap_str(upstream, MAX_PATH_LEN) or None,
        "ahead": ahead,
        "behind": behind,
        "dirty_count": len(dirty_lines),
        "dirty_paths": [cap_str(line, MAX_PATH_LEN) for line in dirty_lines[:MAX_LIST_ITEMS]],
        "staged_count": len(staged_lines),
        "staged_paths": [cap_str(line, MAX_PATH_LEN) for line in staged_lines[:MAX_LIST_ITEMS]],
    }


def source_status(vault: Path) -> dict[str, Any]:
    total = 0
    failed: list[dict[str, str]] = []
    manual: list[dict[str, str]] = []
    sources_dir = vault / "sources"
    if sources_dir.is_dir():
        for path in sorted(sources_dir.rglob("*.md")):
            total += 1
            try:
                text = path.read_text(encoding="utf-8")
                status = str(vault_capture.get_field(text, "ingest_status") or "")
                note_id = str(vault_capture.get_field(text, "id") or "")
            except (OSError, UnicodeError, vault_capture.CaptureError):
                continue
            if status == "failed" and len(failed) < MAX_LIST_ITEMS:
                failed.append({"id": cap_str(note_id, MAX_ID_LEN), "path": cap_str(vault_relative(vault, path), MAX_PATH_LEN)})
            elif status == "manual" and len(manual) < MAX_LIST_ITEMS:
                manual.append({"id": cap_str(note_id, MAX_ID_LEN), "path": cap_str(vault_relative(vault, path), MAX_PATH_LEN)})
    return {
        "total": total,
        "failed_count": len(failed),
        "failed_paths": failed,
        "manual_count": len(manual),
        "manual_paths": manual,
    }


def missing_references(vault: Path) -> list[dict[str, str]]:
    """Annotations/analyses that reference a Source id which does not exist."""
    existing_ids: set[str] = set()
    sources_dir = vault / "sources"
    if sources_dir.is_dir():
        for path in sources_dir.rglob("*.md"):
            try:
                note_id = str(vault_capture.get_field(path.read_text(encoding="utf-8"), "id") or "")
            except (OSError, UnicodeError, vault_capture.CaptureError):
                continue
            if note_id:
                existing_ids.add(note_id)
    missing: list[dict[str, str]] = []
    for folder in ("notes/annotations", "notes/analyses"):
        folder_path = vault / folder
        if not folder_path.is_dir():
            continue
        for path in sorted(folder_path.rglob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
                source_id = str(vault_capture.get_field(text, "source_id") or "")
            except (OSError, UnicodeError, vault_capture.CaptureError):
                continue
            if source_id and source_id not in existing_ids and len(missing) < MAX_LIST_ITEMS:
                missing.append(
                    {
                        "referrer": cap_str(vault_relative(vault, path), MAX_PATH_LEN),
                        "missing_id": cap_str(source_id, MAX_ID_LEN),
                    }
                )
    return missing


def attachment_report(vault: Path) -> dict[str, Any]:
    """Attachment budget report.

    The 30 MiB threshold is evaluated per Source: only the physical bytes under
    ``assets/images/<source-id>/`` count toward that Source.  Files anywhere else
    under ``assets/`` are reported separately as unassigned and never mixed into a
    Source.  The 2 GiB gate uses the total bytes of all attachment files.
    """
    assets_dir = vault / "assets"
    count = 0
    total_bytes = 0
    over_5mib: list[dict[str, str]] = []
    source_bytes: dict[str, int] = {}
    unassigned_total = 0
    unassigned: list[dict[str, Any]] = []
    if assets_dir.is_dir():
        for path in assets_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            count += 1
            total_bytes += size
            if size > WARN_IMAGE_OVER_5MIB and len(over_5mib) < MAX_LIST_ITEMS:
                over_5mib.append({"path": cap_str(vault_relative(vault, path), MAX_PATH_LEN), "bytes": size})
            rel = path.relative_to(vault).as_posix()
            parts = rel.split("/")
            source_id = (
                parts[2]
                if len(parts) >= 3 and parts[0] == "assets" and parts[1] == "images" and ID_STRICT_RE.fullmatch(parts[2])
                else None
            )
            if source_id:
                source_key = f"assets/images/{source_id}"
                source_bytes[source_key] = source_bytes.get(source_key, 0) + size
            else:
                unassigned_total += 1
                if len(unassigned) < MAX_LIST_ITEMS:
                    unassigned.append({"path": cap_str(rel, MAX_PATH_LEN), "bytes": size})
    over_30mib: list[dict[str, Any]] = []
    for source_key in sorted(source_bytes):
        size = source_bytes[source_key]
        if size > WARN_SOURCE_OVER_30MIB and len(over_30mib) < MAX_LIST_ITEMS:
            over_30mib.append({"source_dir": cap_str(source_key, MAX_PATH_LEN), "bytes": size})
    return {
        "count": count,
        "total_bytes": total_bytes,
        "over_5MiB_count": len(over_5mib),
        "over_5MiB_paths": over_5mib,
        "sources_over_30MiB_count": len(over_30mib),
        "sources_over_30MiB_paths": over_30mib,
        "unassigned_count": unassigned_total,
        "unassigned_paths": unassigned,
        "gate_2GiB": total_bytes >= GATE_ATTACHMENTS_2GIB,
    }


def cmd_maintenance_report(vault: Path) -> dict[str, Any]:
    require_vault_layout(vault)
    return {
        "ok": True,
        "report": {
            "git": git_state(vault),
            "sources": source_status(vault),
            "missing_source_references": missing_references(vault),
            "attachments": attachment_report(vault),
        },
    }


# ---------------------------------------------------------------------------
# bounded JSON output
# ---------------------------------------------------------------------------

def bounded_output(payload: dict[str, Any]) -> dict[str, Any]:
    """Truncate ``results`` until the serialized payload fits the output cap."""
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return payload
    if len(json.dumps(payload, ensure_ascii=False, sort_keys=True)) <= MAX_OUTPUT_BYTES:
        return payload
    kept: list[dict[str, Any]] = []
    for item in results:
        candidate = {**payload, "results": kept + [item], "truncated": True}
        if len(json.dumps(candidate, ensure_ascii=False, sort_keys=True)) > MAX_OUTPUT_BYTES:
            break
        kept.append(item)
    return {**payload, "results": kept, "count": len(kept), "truncated": True}


# ---------------------------------------------------------------------------
# CLI dispatch
# ---------------------------------------------------------------------------

def dispatch(argv: list[str]) -> int:
    if len(argv) < 2:
        raise OpsError("A command family is required: capture | query | maintenance", EXIT_INPUT)
    family, rest = argv[0], argv[1:]
    if family not in {"capture", "query", "maintenance"}:
        raise OpsError(f"Unknown command family: {family}", EXIT_INPUT)
    if not rest:
        raise OpsError(f"{family} requires a subcommand", EXIT_INPUT)
    sub, args = rest[0], rest[1:]

    if family == "capture":
        if sub == "preflight":
            if args:
                raise OpsError("preflight takes no arguments", EXIT_INPUT)
            return emit_done(cmd_capture_preflight(resolve_vault()))
        if sub == "stage":
            json_file = None
            if args and args[0] == "--json-file":
                if len(args) != 2:
                    raise OpsError("--json-file requires a path", EXIT_INPUT)
                json_file = args[1]
            elif args:
                raise OpsError("Unknown stage arguments", EXIT_INPUT)
            return emit_done(cmd_capture_stage(resolve_vault(), json_file))
        if sub == "ingest":
            if len(args) != 1:
                raise OpsError("ingest requires a source ID", EXIT_INPUT)
            return emit_done(cmd_capture_ingest(resolve_vault(), args[0]))
        if sub == "inspect":
            if len(args) != 1:
                raise OpsError("inspect requires a source ID", EXIT_INPUT)
            return emit_done(cmd_capture_inspect(resolve_vault(), args[0]))
        if sub == "list-retryable":
            if len(args) > 1:
                raise OpsError("list-retryable takes at most one ID", EXIT_INPUT)
            return emit_done(cmd_capture_list_retryable(resolve_vault(), args[0] if args else None))
        raise OpsError(f"Unknown capture subcommand: {sub}", EXIT_INPUT)

    if family == "query":
        if sub == "search":
            if not args:
                raise OpsError("search requires a query", EXIT_INPUT)
            return emit_done(bounded_output(cmd_query_search(resolve_vault(), " ".join(args))))
        if sub == "show":
            if len(args) != 1:
                raise OpsError("show requires a Vault-relative path", EXIT_INPUT)
            return emit_done(bounded_output(cmd_query_show(resolve_vault(), args[0])))
        if sub == "related":
            if len(args) != 1:
                raise OpsError("related requires a note ID or relative path", EXIT_INPUT)
            return emit_done(bounded_output(cmd_query_related(resolve_vault(), args[0])))
        raise OpsError(f"Unknown query subcommand: {sub}", EXIT_INPUT)

    if family == "maintenance":
        if sub == "report":
            if args:
                raise OpsError("report takes no arguments", EXIT_INPUT)
            return emit_done(cmd_maintenance_report(resolve_vault()))
        raise OpsError(f"Unknown maintenance subcommand: {sub}", EXIT_INPUT)
    raise OpsError(f"Unknown command: {family} {sub}", EXIT_INPUT)  # pragma: no cover


def emit_done(payload: dict[str, Any]) -> int:
    return emit(payload)


def main() -> int:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    try:
        return dispatch(sys.argv[1:])
    except OpsError as exc:
        return fail(str(exc), exc.code, **cap_value(exc.details, MAX_DETAIL_LEN))
    except vault_capture.CaptureError as exc:
        payload: dict[str, Any] = {"ok": False, "error": cap_str(str(exc), MAX_ERROR_LEN)}
        payload.update(cap_value(exc.details, MAX_DETAIL_LEN))
        payload.setdefault("staged", False)
        emit_code = emit(payload)
        return exc.code if emit_code == 0 else emit_code
    except OSError:
        return fail("Filesystem operation failed", EXIT_STORAGE)


if __name__ == "__main__":
    raise SystemExit(main())
