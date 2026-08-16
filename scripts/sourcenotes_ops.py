#!/usr/bin/env python3
"""Operator tooling for SourceNotes: audit, manifest migration, health, ledger, incident.

Every operator path is resolved and validated before use; no command ever writes
inside a Vault or the public blueprint repository, and no error silently leaves a
partial success behind.  Output is one stable JSON object per invocation.

Subcommands:
  audit                 --vault PATH [--output FILE]
  validate-manifest     --manifest FILE --source-vault PATH
  migrate               --manifest FILE --source-vault PATH --target-vault PATH
                        [--dry-run | --apply]
  health                --vault PATH [--state-file PATH]
  ledger                --dir PATH add --type release|operation --data JSON
                        | list
  incident              --vault PATH --out-dir PATH --metadata JSON_OR_FILE
                        [--diagnostics FILE ...]
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sourcenotes_agent  # noqa: E402  (reuse maintenance metrics + OpsError)
from sourcenotes_agent import OpsError  # noqa: E402

EXIT_INPUT = 2
EXIT_CONFLICT = 3
EXIT_STORAGE = 4

BLUEPRINT_ROOT = Path(__file__).resolve().parent.parent

SOURCE_START = "<!-- source-content:start -->"
SOURCE_END = "<!-- source-content:end -->"
ROLLUP_MARKER = "<!-- vault-capture:annotation-rollup -->"
ENTRY_MARKER = "<!-- vault-capture:entry "

MANIFEST_ACTIONS = {"migrate", "repair_then_migrate", "exclude"}
VALID_LEDGER_TYPES = {"release", "operation"}
GATE_ATTACHMENTS_2GIB = 2 * 1024 * 1024 * 1024

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----")),
    ("authorization_header", re.compile(r"(?i)\bauthorization\s*[:=]\s*(?:bearer\s+)?\S+")),
    ("cookie_header", re.compile(r"(?i)\bcookie\s*[:=]\s*\S+")),
    ("api_key", re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?key)\b\s*[:=]\s*\S+")),
    ("token_secret", re.compile(r"(?i)\b(?:token|secret)\b\s*[:=]\s*\S+")),
    ("password", re.compile(r"(?i)\b(?:password|passwd|pwd)\b\s*[:=]\s*\S+")),
    ("sk_token", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
]


def emit(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))


def fail(message: str, code: int = EXIT_INPUT, **details: Any) -> int:
    emit({"ok": False, "error": message, **details})
    return code


def run_git(path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise OpsError("Git could not be executed", EXIT_STORAGE) from exc


def ensure_git_root(path: str | Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        raise OpsError("Path is not a directory", EXIT_INPUT)
    if shutil.which("git") is None:
        raise OpsError("Git is not available", EXIT_INPUT)
    result = run_git(resolved, ["rev-parse", "--show-toplevel"])
    if result.returncode != 0 or Path(result.stdout.strip()).resolve() != resolved:
        raise OpsError("Path must be the root of a Git repository", EXIT_INPUT)
    return resolved


def outside_repos(path: Path, vaults: Iterable[Path]) -> bool:
    """True when the resolved path is inside neither the blueprint repo nor any Vault."""
    resolved = path.resolve()
    blueprint = BLUEPRINT_ROOT.resolve()
    if resolved == blueprint or blueprint in resolved.parents:
        return False
    for vault in vaults:
        vault_root = Path(vault).resolve()
        if resolved == vault_root or vault_root in resolved.parents:
            return False
    return True


def require_external_dir(path: str | Path, vaults: Iterable[Path]) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not outside_repos(resolved, vaults):
        raise OpsError("Output location must be outside the Vault and the blueprint repository", EXIT_INPUT)
    return resolved


def atomic_write(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, mode)
        os.replace(temp_name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp_name)


def read_json_file(path: str | Path) -> dict[str, Any]:
    json_path = Path(path).expanduser().resolve()
    if not json_path.is_file() or json_path.stat().st_size > 10 * 1024 * 1024:
        raise OpsError("JSON input file is missing or too large", EXIT_INPUT)
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OpsError("JSON input file is invalid", EXIT_INPUT) from exc
    if not isinstance(data, dict):
        raise OpsError("JSON input must be an object", EXIT_INPUT)
    return data


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


FILENAME_SECRET_RE = re.compile(
    r"(?i)(?:^|[^a-z0-9])(?:token|password|passwd|secret|apikey|api[_-]?key|authorization|cookie|bearer|private[_-]?key)(?:[=_-]|[^a-z0-9]|$)"
)


def scan_secrets(text: str) -> list[str]:
    hits: list[str] = []
    for category, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            hits.append(category)
    return hits


def scan_filename(text: str) -> list[str]:
    """Content-level scan plus filename/key-word scan for paths and basenames."""
    hits = scan_secrets(text)
    if FILENAME_SECRET_RE.search(text):
        hits.append("filename")
    return hits


def scan_bytes_for_secrets(data: bytes) -> list[str]:
    try:
        text = data.decode("utf-8", errors="replace")
    except UnicodeDecodeError:
        return []
    return scan_secrets(text)


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------

def body_disposition(region: str) -> tuple[str, int]:
    """Content between source markers counts as body only when it contains
    non-whitespace, non-comment text.  Returns (disposition, stripped_bytes)."""
    no_comments = re.sub(r"<!--.*?-->", "", region, flags=re.DOTALL)
    stripped = re.sub(r"\s+", "", no_comments)
    if stripped:
        return "body", len(stripped.encode("utf-8"))
    return "empty", 0


def parse_frontmatter(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    match = re.match(r"\A---\n(.*?)\n---\n?", text, re.DOTALL)
    if not match:
        return fields
    for line in match.group(1).splitlines():
        fm = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)$", line)
        if fm:
            fields[fm.group(1)] = fm.group(2).strip().strip('"')
    return fields


def source_report(vault: Path) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    sources_dir = vault / "sources"
    if not sources_dir.is_dir():
        return report
    for path in sorted(sources_dir.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        fields = parse_frontmatter(text)
        if SOURCE_START in text and SOURCE_END in text:
            start = text.index(SOURCE_START) + len(SOURCE_START)
            end = text.index(SOURCE_END, start)
            disposition, body_bytes = body_disposition(text[start:end])
        else:
            disposition, body_bytes = "no_markers", 0
        source_id = fields.get("id", "")
        attachment_count = 0
        attachment_bytes = 0
        if source_id:
            asset_dir = vault / "assets" / "images" / source_id
            if asset_dir.is_dir():
                for asset in asset_dir.rglob("*"):
                    if asset.is_file():
                        attachment_count += 1
                        try:
                            attachment_bytes += asset.stat().st_size
                        except OSError:
                            pass
        report.append(
            {
                "id": source_id,
                "path": path.relative_to(vault).as_posix(),
                "title": fields.get("title", ""),
                "ingest_status": fields.get("ingest_status", ""),
                "canonical_url": fields.get("canonical_url", ""),
                "marker": "present" if SOURCE_START in text and SOURCE_END in text else "missing",
                "has_body": disposition == "body",
                "body_bytes": body_bytes,
                "attachment_count": attachment_count,
                "attachment_bytes": attachment_bytes,
                "disposition": disposition,
            }
        )
    return report


def annotation_report(vault: Path) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    notes_dir = vault / "notes" / "annotations"
    if not notes_dir.is_dir():
        return report
    for path in sorted(notes_dir.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        fields = parse_frontmatter(text)
        has_entries = ENTRY_MARKER in text
        report.append(
            {
                "id": fields.get("id", ""),
                "path": path.relative_to(vault).as_posix(),
                "source_id": fields.get("source_id", ""),
                "has_entries": has_entries,
                "disposition": "entries" if has_entries else "empty",
            }
        )
    return report


def attachment_report_items(vault: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    assets_dir = vault / "assets"
    if not assets_dir.is_dir():
        return items
    for path in sorted(assets_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        items.append({"path": path.relative_to(vault).as_posix(), "bytes": size, "disposition": "attached"})
    return items


def cmd_audit(vault_arg: str, output_file: str | None) -> dict[str, Any]:
    vault = ensure_git_root(vault_arg)
    report = {
        "vault": "redacted",
        "sources": source_report(vault),
        "annotations": annotation_report(vault),
        "attachments": attachment_report_items(vault),
    }
    if output_file:
        out = Path(output_file).expanduser().resolve()
        atomic_write(out, (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"), mode=0o600)
        return {"ok": True, "report": report, "written_to": str(out)}
    return {"ok": True, "report": report}


# ---------------------------------------------------------------------------
# manifest validation and migration
# ---------------------------------------------------------------------------

def load_manifest(path_arg: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = read_json_file(path_arg)
    if manifest.get("manifest_version") != 1:
        raise OpsError("Unsupported manifest_version", EXIT_INPUT)
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise OpsError("manifest.entries must be a non-empty list", EXIT_INPUT)
    return manifest, entries


def entry_declared_paths(entry: dict[str, Any]) -> list[str]:
    raw = entry.get("paths")
    if not isinstance(raw, dict):
        return []
    return [item for item in raw.get("attachments", []) if isinstance(item, str) and item]


def validate_manifest(vault_arg: str, path_arg: str) -> dict[str, Any]:
    vault = ensure_git_root(vault_arg)
    _manifest, entries = load_manifest(path_arg)
    seen_ids: set[str] = set()
    seen_source_paths: set[str] = set()
    seen_attachment_paths: set[str] = set()
    canonical_by_id: dict[str, str] = {}
    validated: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise OpsError("Each manifest entry must be an object", EXIT_INPUT)
        source_id = str(entry.get("source_id", ""))
        action = entry.get("action")
        reason = entry.get("reason")
        if not re.fullmatch(r"[a-zA-Z0-9-]+", source_id):
            raise OpsError(f"Invalid source_id: {source_id!r}", EXIT_INPUT)
        if source_id in seen_ids:
            raise OpsError(f"Duplicate manifest entry for source_id {source_id}", EXIT_INPUT)
        if action not in MANIFEST_ACTIONS:
            raise OpsError(f"Unknown action {action!r} for {source_id}", EXIT_INPUT)
        if not isinstance(reason, str) or not reason.strip():
            raise OpsError(f"Entry {source_id} is missing a reason", EXIT_INPUT)
        seen_ids.add(source_id)
        paths = entry.get("paths")
        if action != "exclude":
            if not isinstance(paths, dict) or not isinstance(paths.get("source"), str) or not paths["source"]:
                raise OpsError(f"Entry {source_id} must declare a source path", EXIT_INPUT)
            declared: list[str] = [paths["source"]]
            if isinstance(paths.get("annotation"), str) and paths["annotation"]:
                declared.append(paths["annotation"])
            declared.extend(entry_declared_paths(entry))
            for rel in declared:
                candidate = (vault / Path(rel)).resolve()
                try:
                    candidate.relative_to(vault.resolve())
                except ValueError as exc:
                    raise OpsError(f"Entry {source_id} path escapes the Vault: {rel}", EXIT_INPUT) from exc
                if not candidate.is_file():
                    raise OpsError(f"Entry {source_id} declares a missing path: {rel}", EXIT_INPUT)
            if paths["source"] in seen_source_paths:
                raise OpsError(f"Source path declared twice: {paths['source']}", EXIT_INPUT)
            seen_source_paths.add(paths["source"])
            source_text = (vault / Path(paths["source"])).resolve().read_text(encoding="utf-8")
            fields = parse_frontmatter(source_text)
            if fields.get("id", "") != source_id:
                raise OpsError(f"Entry {source_id} source path id mismatch", EXIT_INPUT)
            canonical = fields.get("canonical_url", "")
            if canonical:
                other = canonical_by_id.get(canonical)
                if other is not None and other != source_id:
                    raise OpsError(f"Canonical URL conflict between {other} and {source_id}", EXIT_INPUT)
                canonical_by_id[canonical] = source_id
            for attachment in entry_declared_paths(entry):
                if attachment in seen_attachment_paths:
                    raise OpsError(f"Attachment declared twice: {attachment}", EXIT_INPUT)
                seen_attachment_paths.add(attachment)
            actual_assets: list[str] = []
            asset_dir = vault / "assets" / "images" / source_id
            if asset_dir.is_dir():
                for asset in sorted(asset_dir.rglob("*")):
                    if asset.is_file():
                        actual_assets.append(asset.relative_to(vault).as_posix())
            declared_attachments = set(entry_declared_paths(entry))
            omitted = [item for item in actual_assets if item not in declared_attachments]
            if omitted:
                raise OpsError(
                    f"Entry {source_id} omits existing attachments: {', '.join(sorted(omitted))}",
                    EXIT_INPUT,
                )
            for attachment in entry_declared_paths(entry):
                candidate = (vault / Path(attachment)).resolve()
                if not candidate.is_file():
                    raise OpsError(f"Entry {source_id} declares a missing attachment: {attachment}", EXIT_INPUT)
        validated.append(
            {
                "source_id": source_id,
                "action": action,
                "reason": reason,
                "paths": paths,
                "status": "excluded" if action == "exclude" else ("repair_required" if action == "repair_then_migrate" else "ready"),
            }
        )
    return {"ok": True, "entries": validated, "count": len(validated)}


def check_target_path_safety(target: Path, rel: str) -> None:
    """Reject target paths whose final path or any existing parent component is a
    symlink, and any path that resolves outside the target Vault root."""
    target_root = target.resolve()
    cursor = target_root
    for part in Path(rel).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise OpsError(f"Target path contains a symlink: {rel}", EXIT_INPUT)
    resolved = (target / Path(rel)).resolve()
    try:
        resolved.relative_to(target_root)
    except ValueError as exc:
        raise OpsError(f"Target path escapes the Vault: {rel}", EXIT_INPUT) from exc


def collect_target_conflicts(source: Path, target: Path, entries: list[dict[str, Any]]) -> list[str]:
    """Gather ALL target-side conflicts across every entry before any write."""
    conflicts: list[str] = []
    for entry in entries:
        if entry.get("action") != "migrate":
            continue
        source_id = str(entry["source_id"])
        declared = [str(entry["paths"]["source"])]
        annotation = entry["paths"].get("annotation")
        if isinstance(annotation, str) and annotation:
            declared.append(annotation)
        declared.extend(entry_declared_paths(entry))
        for rel in declared:
            # Path safety first so symlink escapes are reported as such instead
            # of being shadowed by the existence check (which follows symlinks).
            try:
                check_target_path_safety(target, rel)
            except OpsError as exc:
                conflicts.append(str(exc))
            candidate = (target / Path(rel)).resolve()
            if candidate.exists():
                conflicts.append(f"target path already exists: {rel}")
        src_canonical = ""
        source_path = (source / Path(entry["paths"]["source"])).resolve()
        try:
            src_canonical = parse_frontmatter(source_path.read_text(encoding="utf-8")).get("canonical_url", "")
        except (OSError, UnicodeError):
            pass
        target_sources = list(target.joinpath("sources").rglob("*.md")) if target.joinpath("sources").is_dir() else []
        for path in target_sources:
            try:
                fields = parse_frontmatter(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError):
                continue
            if fields.get("id") == source_id:
                conflicts.append(f"target already has source id {source_id}")
            if src_canonical and fields.get("canonical_url") == src_canonical:
                conflicts.append(f"target already has canonical_url {src_canonical}")
    return conflicts


def plan_migration(source: Path, target: Path, entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Preflight ALL entries and target state; any failure raises with zero target changes.

    Returns (planned, skipped).  Planned items carry source bytes/hash captured before
    any target write, so the target can never see a partially-migrated manifest.
    """
    skipped: list[dict[str, Any]] = []
    planned: list[dict[str, Any]] = []
    for entry in entries:
        action = entry.get("action")
        if action == "exclude":
            skipped.append({"source_id": entry["source_id"], "action": "exclude", "reason": entry.get("reason", "")})
            continue
        if action == "repair_then_migrate":
            skipped.append({"source_id": entry["source_id"], "action": "repair_then_migrate", "reason": entry.get("reason", "")})
            continue
        declared = [str(entry["paths"]["source"])]
        annotation = entry["paths"].get("annotation")
        if isinstance(annotation, str) and annotation:
            declared.append(annotation)
        declared.extend(entry_declared_paths(entry))
        for rel in declared:
            src_path = (source / Path(rel)).resolve()
            try:
                data = src_path.read_bytes()
                mode = src_path.stat().st_mode & 0o777
            except OSError as exc:
                raise OpsError(f"Source file could not be read: {rel}", EXIT_STORAGE) from exc
            planned.append(
                {
                    "source_id": entry["source_id"],
                    "rel": rel,
                    "bytes": data,
                    "sha": sha256_bytes(data),
                    "mode": mode,
                }
            )
    conflicts = collect_target_conflicts(source, target, entries)
    if conflicts:
        raise OpsError(
            f"Migration conflicts (target unchanged): {conflicts[0]}",
            EXIT_CONFLICT,
            conflicts=conflicts[:10],
        )
    return planned, skipped


def open_rel_dir(root_fd: int, rel: str, *, create: bool = False) -> int:
    """Open a directory path anchored at ``root_fd`` component-wise with
    ``O_DIRECTORY|O_NOFOLLOW`` so no symlink is ever followed.  Raises OpsError
    on a symlink or non-directory component.

    fd ownership: ``root_fd`` is borrowed and never closed here; the caller owns
    the returned fd.  When ``rel`` has no components (``"."`` / empty), the
    returned fd IS the borrowed ``root_fd`` itself and the caller must treat it
    as borrowed -- never close it.  Every intermediate fd this helper opened is
    closed exactly once -- after the ownership transfer to the next component or
    on any error path -- so repeated failures never accumulate descriptors."""
    parts = Path(rel).parts
    fd = root_fd
    for part in parts:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            try:
                nfd = os.open(part, flags, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise OpsError(f"Target directory is missing: {rel}", EXIT_STORAGE)
                try:
                    os.mkdir(part, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
                try:
                    nfd = os.open(part, flags, dir_fd=fd)
                except OSError as exc:
                    raise OpsError(f"Target path is not a safe directory: {rel}", EXIT_INPUT) from exc
            except OSError as exc:
                raise OpsError(f"Target path contains a symlink or unsafe component: {rel}", EXIT_INPUT) from exc
        except (OSError, OpsError):
            # The currently held fd (owned intermediate, never root) is closed
            # before the failure propagates.
            if fd != root_fd:
                os.close(fd)
            raise
        if fd != root_fd:
            os.close(fd)
        fd = nfd
    return fd


def ensure_target_parents(root_fd: int, rel: str, created_dirs: list[str]) -> tuple[int, bool]:
    """Open (creating as needed) the parent directories of ``rel`` anchored at
    ``root_fd`` with no-follow semantics; appends newly-created directory rel
    paths to ``created_dirs`` in creation order (only directories this call
    actually created, so rollback removes exactly those).

    Returns an explicit ``(fd, owned)`` pair so the caller never has to infer
    ownership from fd equality: ``owned`` is True exactly when ``rel`` has at
    least one parent component and the returned fd was newly opened by this
    call (the caller owns it and must close it exactly once); ``owned`` is
    False when ``rel`` is a top-level target, in which case the returned fd is
    the borrowed ``root_fd`` and the caller must NOT close it.  ``root_fd`` is
    never closed here.  Any intermediate fd opened by this helper is closed
    exactly once, including on every failure branch."""
    parts = Path(rel).parts[:-1]
    owned = len(parts) > 0
    if not owned:
        return root_fd, False
    fd = root_fd
    for index, part in enumerate(parts):
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        created = False
        try:
            try:
                nfd = os.open(part, flags, dir_fd=fd)
            except FileNotFoundError:
                try:
                    os.mkdir(part, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
                else:
                    created = True
                try:
                    nfd = os.open(part, flags, dir_fd=fd)
                except OSError as exc:
                    raise OpsError(f"Target path is not a safe directory: {rel}", EXIT_INPUT) from exc
            except OSError as exc:
                raise OpsError(f"Target path contains a symlink or unsafe component: {rel}", EXIT_INPUT) from exc
        except (OSError, OpsError):
            if fd != root_fd:
                os.close(fd)
            raise
        if created:
            created_dirs.append(str(Path(*parts[: index + 1])))
        if fd != root_fd:
            os.close(fd)
        fd = nfd
    return fd, True


def read_rel_bytes_anchored(root_fd: int, rel: str) -> bytes:
    """Read a regular file anchored at ``root_fd`` with ``O_NOFOLLOW`` on the
    final component and no-follow parent resolution.  Refuses symlinks."""
    parent_rel = str(Path(rel).parent)
    if parent_rel == ".":
        parent_fd = root_fd
    else:
        parent_fd = open_rel_dir(root_fd, parent_rel, create=False)
    try:
        try:
            fd = os.open(Path(rel).name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        except OSError as exc:
            raise OpsError(f"Published file could not be verified: {rel}", EXIT_STORAGE) from exc
        with os.fdopen(fd, "rb") as handle:
            return handle.read()
    finally:
        if parent_fd != root_fd:
            os.close(parent_fd)


def _listdir_anchored(fd: int) -> list[str]:
    """List directory entries anchored to an opened directory fd via
    /proc/self/fd (immune to path renames and symlink swaps)."""
    return os.listdir(f"/proc/self/fd/{fd}")


def _rmtree_anchored(dir_fd: int, names: list[str]) -> None:
    for name in names:
        try:
            sub_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)
        except OSError:
            _unlink_anchored(dir_fd, name)
        else:
            # sub_fd is owned here and closed exactly once, even when the
            # recursion below fails mid-way.
            try:
                _rmtree_anchored(sub_fd, _listdir_anchored(sub_fd))
            finally:
                os.close(sub_fd)
            _rmdir_anchored(dir_fd, name)


def remove_tree_anchored(root_fd: int, rel: str) -> None:
    """Remove the directory tree at ``rel`` (anchored, no-follow), then the
    directory itself."""
    parts = Path(rel).parts
    basename = parts[-1]
    parent_rel = str(Path(*parts[:-1])) if len(parts) > 1 else ""
    if parent_rel:
        parent_fd = open_rel_dir(root_fd, parent_rel, create=False)
    else:
        parent_fd = root_fd
    try:
        fd = os.open(basename, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            _rmtree_anchored(fd, _listdir_anchored(fd))
        finally:
            os.close(fd)
        _rmdir_anchored(parent_fd, basename)
    finally:
        if parent_fd != root_fd:
            os.close(parent_fd)


def _unlink_anchored(parent_fd: int, name: str) -> None:
    os.unlink(name, dir_fd=parent_fd)


def _rmdir_anchored(parent_fd: int, name: str) -> None:
    os.rmdir(name, dir_fd=parent_fd)


_ROLLBACK_ERROR_LIMIT = 200
_ORIGINAL_ERROR_LIMIT = 200

# Absolute host paths that may appear inside raw OS error text are redacted so
# error records never leak machine paths: POSIX, Windows drive-letter and
# Windows UNC (``\\\\server\\share\\...``) forms.
_ABSOLUTE_PATH_RE = re.compile(
    r"(?:\\\\[^\\\s'\"]+[\\/][^\s'\"]*|[A-Za-z]:[\\/][^\s'\"]*|/[^\s'\"]*)"
)

# Compound credential keys (snake/kebab/camel identifiers, e.g. client_secret,
# access_token, my-password, userCredential, api-key) whose identifier is built
# from letters/digits/underscore/hyphens and ENDS in a sensitive stem
# (credential/secret/password/token/api-key/auth/...).  The sensitive word must
# be the key suffix (optionally pluralized or digit-suffixed) so ordinary words
# such as "tokenizer" or "author" are never treated as secret keys.  The VALUE
# is replaced with a placeholder while the key name is kept for diagnostics.
# The value is matched as a THREE-way alternative: a double-quoted or
# single-quoted literal (quotes consumed together with the match, so
# credential="TOPSECRET" / credential='TOPSECRET' redact the value and keep the
# key), or a bare token that stops at whitespace, quotes, comma, semicolon,
# colon, pipe, ampersand and every bracket/brace/paren form
# (| & : , ; ) ] } > ( [ {) so values never swallow the following diagnostic
# text (e.g. `|retry=3|ending`, `: retry=3`, `; ending` all survive).
_COMPOUND_SECRET_KEY_RE = re.compile(
    r"(?i)\b([a-z0-9_-]*(?:credential|secret|password|passwd|pwd|token|api[_-]?key|auth(?:orization)?|bearer)s?(?:_?\d+)?)\s*[:=]\s*(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s'\",;:|&()\[\]{}<>]+)"
)


def _sanitize_message(text: str) -> str:
    """Single-line, host-path-free, secret-redacted rendering of an error text.

    Redacts absolute paths (POSIX, Windows drive-letter and UNC forms) and
    credential-like key/value or known token formats via ``SECRET_PATTERNS``
    plus a compound sensitive-key pass that keeps the key name and redacts only
    the value; collapses control characters and escapes newlines so the result
    is one safe line.  Diagnostic categories of the exception itself
    (``OSError``, ``OpsError``, ...) are preserved.
    """
    text = _ABSOLUTE_PATH_RE.sub("<path>", text)
    for category, pattern in SECRET_PATTERNS:
        text = pattern.sub(f"<{category}>", text)
    text = _COMPOUND_SECRET_KEY_RE.sub(r"\1=<redacted>", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "?", text)
    text = text.replace("\n", "\\n").replace("\r", "\\r")
    return text


def _bounded_message(exc: BaseException, limit: int) -> str:
    """Bounded, path-safe single-line summary of a failure: relative paths only,
    never secrets or host paths, never an unbounded exception repr.

    If the exception's ``__str__`` itself raises (a hostile or broken ``__str__``
    must never crash the summary), fall back to a safe type-only summary that
    leaks nothing."""
    try:
        text = _sanitize_message(f"{type(exc).__name__}: {exc}")
    except Exception:
        text = f"{type(exc).__name__}: <unprintable>"
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _bounded_entry(prefix: str, exc: BaseException, limit: int) -> str:
    """Compose ``prefix`` (e.g. the ``action rel`` anchor) and a sanitized
    summary of ``exc`` into a single entry whose TOTAL length (prefix included)
    never exceeds ``limit``; the prefix is sanitized too."""
    text = f"{_sanitize_message(prefix)}: {_bounded_message(exc, limit)}"
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def rollback_transaction(
    root_fd: int,
    published: list[str],
    created_dirs: list[str],
    staging_rel: str,
    *,
    staging_created: bool = True,
) -> list[str]:
    """Restore every path created this round to its pre-call state (nonexistence),
    anchored at ``root_fd`` with no-follow operations.  Returns bounded rollback
    errors; never raises for ordinary runtime failures (``Exception``, but never
    ``BaseException``: ``KeyboardInterrupt``/``SystemExit`` still propagate) so
    the original migration failure is preserved.  Each cleanup action is
    independent: one failure never blocks the remaining cleanups.  Pass
    ``staging_created=False`` when the staging directory was never actually
    created (e.g. staging ``mkdir`` itself failed) so its cleanup is skipped
    instead of being misreported as a rollback error."""
    errors: list[str] = []
    for rel in reversed(published):
        parent_rel = str(Path(rel).parent)
        name = Path(rel).name
        try:
            parent_fd = root_fd if parent_rel == "." else open_rel_dir(root_fd, parent_rel, create=False)
            try:
                _unlink_anchored(parent_fd, name)
            finally:
                if parent_fd != root_fd:
                    os.close(parent_fd)
        except Exception as exc:
            errors.append(_bounded_entry(f"unlink {rel}", exc, _ROLLBACK_ERROR_LIMIT))
    for rel in reversed(created_dirs):
        parent_rel = str(Path(rel).parent)
        name = Path(rel).name
        try:
            parent_fd = root_fd if parent_rel == "." else open_rel_dir(root_fd, parent_rel, create=False)
            try:
                _rmdir_anchored(parent_fd, name)
            finally:
                if parent_fd != root_fd:
                    os.close(parent_fd)
        except Exception as exc:
            errors.append(_bounded_entry(f"rmdir {rel}", exc, _ROLLBACK_ERROR_LIMIT))
    if staging_created:
        try:
            remove_tree_anchored(root_fd, staging_rel)
        except Exception as exc:
            errors.append(_bounded_entry("staging cleanup", exc, _ROLLBACK_ERROR_LIMIT))
    return errors


def _publish_link(root_fd: int, staging_rel: str, rel: str, parent_fd: int) -> None:
    """Atomic no-clobber publish: hard-link the staged file to the target name
    (never overwrites an existing target) without following symlinks."""
    os.link(
        f"{staging_rel}/{rel}",
        Path(rel).name,
        src_dir_fd=root_fd,
        dst_dir_fd=parent_fd,
        follow_symlinks=False,
    )


def _verify_published(root_fd: int, rel: str) -> bytes:
    return read_rel_bytes_anchored(root_fd, rel)


def execute_migration(target: Path, planned: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Descriptor-anchored transactional apply.

    The target Vault root is opened once with ``O_RDONLY|O_DIRECTORY|O_NOFOLLOW``
    and every operation (staging, publish, verification, rollback) is anchored to
    that fd with per-component ``O_DIRECTORY|O_NOFOLLOW`` resolution, so no symlink
    can redirect writes outside the Vault (no TOCTOU window).  Publish uses atomic
    no-clobber hard links; any exception during staging, publish, post-publish
    verification, or evidence assembly triggers a full rollback.  Rollback errors
    are reported and never silently swallowed.
    """
    root_fd = os.open(str(target), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    staging_rel = f".sourcenotes-migrate-{secrets.token_hex(8)}"
    staging_created = False
    published: list[str] = []
    created_dirs: list[str] = []
    copied: list[dict[str, Any]] = []
    try:
        # Staging: safe, random, 0700 directory created via the anchored root fd.
        os.mkdir(staging_rel, 0o700, dir_fd=root_fd)
        staging_created = True
        for item in planned:
            staged_rel = f"{staging_rel}/{item['rel']}"
            # ensure_target_parents returns an explicit (fd, owned) pair; the
            # staged path always has the staging directory as a parent, so the
            # returned fd is owned and closed exactly once below.
            staged_parent_fd, owned = ensure_target_parents(root_fd, staged_rel, [])
            try:
                fd = os.open(Path(staged_rel).name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=staged_parent_fd)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(item["bytes"])
                os.chmod(Path(staged_rel).name, item["mode"], dir_fd=staged_parent_fd)
            finally:
                if owned:
                    os.close(staged_parent_fd)
        for item in planned:
            rel = item["rel"]
            # ensure_target_parents returns an explicit (fd, owned) pair: nested
            # targets own the returned parent fd (closed exactly once below, on
            # every success or failure path, including the concurrent/publish/
            # verify OpsError conversions), while top-level targets reuse the
            # borrowed root_fd with owned=False and must never be closed here.
            parent_fd, owned = ensure_target_parents(root_fd, rel, created_dirs)
            try:
                try:
                    _publish_link(root_fd, staging_rel, rel, parent_fd)
                except FileExistsError:
                    raise OpsError(f"Target path was created concurrently: {rel}", EXIT_CONFLICT)
                except OSError as exc:
                    raise OpsError(f"Publish failed for {rel}", EXIT_STORAGE) from exc
                published.append(rel)
                try:
                    data = _verify_published(root_fd, rel)
                except OSError as exc:
                    raise OpsError(f"Post-publish verification failed for {rel}", EXIT_STORAGE) from exc
                if len(data) != len(item["bytes"]) or sha256_bytes(data) != item["sha"]:
                    raise OpsError(f"Hash mismatch after publish for {rel}", EXIT_STORAGE)
                os.unlink(f"{staging_rel}/{rel}", dir_fd=root_fd)
                copied.append(
                    {
                        "source_id": item["source_id"],
                        "src_path": rel,
                        "dst_path": rel,
                        "src_sha256": item["sha"],
                        "dst_sha256": item["sha"],
                        "bytes": len(item["bytes"]),
                        "applied": True,
                    }
                )
            finally:
                if owned:
                    os.close(parent_fd)
        remove_tree_anchored(root_fd, staging_rel)
        return copied
    except BaseException as exc:
        rollback_errors = rollback_transaction(
            root_fd, published, created_dirs, staging_rel, staging_created=staging_created
        )
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            # Control exceptions run the necessary rollback, then propagate
            # unchanged: a cancellation or system exit is never converted into
            # OpsError and never misreported as success.  Any rollback failure
            # is surfaced on stderr so it is not silently swallowed.
            if rollback_errors:
                sys.stderr.write(
                    f"sourcenotes_ops: rollback incomplete after {type(exc).__name__}: {rollback_errors[0]}\n"
                )
            raise
        if rollback_errors:
            raise OpsError(
                "Migration failed and rollback incomplete",
                EXIT_STORAGE,
                original_error=_bounded_message(exc, _ORIGINAL_ERROR_LIMIT),
                rollback_errors=rollback_errors[:5],
            ) from exc
        if isinstance(exc, OpsError):
            raise
        raise OpsError("Migration failed; target restored", EXIT_STORAGE) from exc
    finally:
        os.close(root_fd)


def cmd_migrate(
    manifest_arg: str,
    source_arg: str,
    target_arg: str,
    *,
    apply: bool,
) -> dict[str, Any]:
    source = ensure_git_root(source_arg)
    target = ensure_git_root(target_arg)
    if source == target:
        raise OpsError("Source and target Vaults must differ", EXIT_INPUT)
    _manifest, entries = load_manifest(manifest_arg)
    if apply and any(entry.get("action") == "repair_then_migrate" for entry in entries):
        raise OpsError(
            "repair_then_migrate entries must be converted to migrate before apply",
            EXIT_INPUT,
        )
    validate_manifest(source_arg, manifest_arg)
    # Complete preflight of ALL entries and target state; any failure = zero changes.
    planned, skipped = plan_migration(source, target, entries)
    if apply:
        copied = execute_migration(target, planned)
    else:
        copied = [
            {
                "source_id": item["source_id"],
                "src_path": item["rel"],
                "dst_path": item["rel"],
                "src_sha256": item["sha"],
                "dst_sha256": None,
                "bytes": len(item["bytes"]),
                "applied": False,
            }
            for item in planned
        ]
    return {
        "ok": True,
        "dry_run": not apply,
        "applied": apply,
        "copied": copied,
        "skipped": skipped,
        "copied_count": len(copied),
        "skipped_count": len(skipped),
    }


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------

def cmd_health(vault_arg: str, state_file: str | None) -> dict[str, Any]:
    vault = ensure_git_root(vault_arg)
    report = sourcenotes_agent.cmd_maintenance_report(vault)
    attachments = report["report"]["attachments"]
    gate = attachments.get("gate_2GiB", False)
    if state_file:
        state_path = require_external_dir(state_file, [vault])
        state = {
            "generated_at": dt.datetime.now().astimezone().replace(microsecond=0).isoformat(),
            "vault_head": report["report"]["git"].get("head"),
            "attachment_gate_2GiB": gate,
            "report": report["report"],
        }
        atomic_write(state_path, (json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        return {"ok": True, "gate_2GiB": gate, "state_file": str(state_path), "report": report["report"]}
    return {"ok": True, "gate_2GiB": gate, "report": report["report"]}


# ---------------------------------------------------------------------------
# ledger
# ---------------------------------------------------------------------------

def ledger_file(dir_arg: str) -> Path:
    return Path(dir_arg).expanduser().resolve() / "operations.jsonl"


def cmd_ledger_add(dir_arg: str, record_type: str, data_arg: str, vaults: list[str]) -> dict[str, Any]:
    if record_type not in VALID_LEDGER_TYPES:
        raise OpsError("ledger type must be release or operation", EXIT_INPUT)
    try:
        data = json.loads(data_arg)
    except json.JSONDecodeError as exc:
        raise OpsError("ledger data must be a JSON object", EXIT_INPUT) from exc
    if not isinstance(data, dict):
        raise OpsError("ledger data must be a JSON object", EXIT_INPUT)
    serialized = json.dumps(data, ensure_ascii=False, sort_keys=True)
    hits = scan_secrets(serialized)
    if hits:
        raise OpsError(f"ledger data rejected: secret-like content ({', '.join(hits)})", EXIT_INPUT)
    external = require_external_dir(dir_arg, vaults)
    record = {
        "type": record_type,
        "timestamp": dt.datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "data": data,
    }
    line = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    path = ledger_file(external)
    existing = path.read_bytes() if path.is_file() else b""
    atomic_write(path, existing + line)
    return {"ok": True, "appended": record, "file": str(path)}


def cmd_ledger_list(dir_arg: str, vaults: list[str]) -> dict[str, Any]:
    external = require_external_dir(dir_arg, vaults)
    path = ledger_file(external)
    records: list[dict[str, Any]] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return {"ok": True, "records": records, "count": len(records)}


# ---------------------------------------------------------------------------
# incident
# ---------------------------------------------------------------------------

def safe_artifact_name(index: int, path: Path) -> str:
    suffix = path.suffix.lower()
    safe_suffix = re.sub(r"[^a-z0-9]", "", suffix)[:10]
    return f"diag-{index:04d}" + (f".{safe_suffix}" if safe_suffix else "")


def collect_diagnostics(paths: list[str]) -> list[tuple[str, bytes, str]]:
    """Return [(safe_artifact_name, bytes, sha256)]; fails closed on secrets found in
    the operator path text, the file basename, or the file content.  Order is
    preserved so the generated artifact name is the only source association."""
    collected: list[tuple[str, bytes, str]] = []
    for raw in paths:
        candidate = Path(raw).expanduser().resolve()
        if candidate.is_dir():
            items = [item for item in sorted(candidate.rglob("*")) if item.is_file()]
        elif candidate.is_file():
            items = [candidate]
        else:
            raise OpsError(f"Diagnostic path does not exist: {raw}", EXIT_INPUT)
        for item in items:
            _scan_diagnostic_sources(item)
            collected.append((safe_artifact_name(len(collected) + 1, item), *_read_diagnostic(item)))
    return collected


def _scan_diagnostic_sources(path: Path) -> None:
    """Scan the operator-supplied path text and the file basename for secrets."""
    for label, value in (("source_path", str(path)), ("basename", path.name)):
        hits = scan_filename(value)
        if hits:
            raise OpsError(
                f"Incident bundle rejected: secret-like content detected ({', '.join(hits)})",
                EXIT_INPUT,
            )


def _read_diagnostic(path: Path) -> tuple[bytes, str]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise OpsError("Diagnostic file could not be read", EXIT_STORAGE) from exc
    if size > 128 * 1024 * 1024:
        raise OpsError("Diagnostic file is too large", EXIT_STORAGE)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise OpsError("Diagnostic file could not be read", EXIT_STORAGE) from exc
    hits = scan_bytes_for_secrets(data)
    if hits:
        raise OpsError(
            f"Incident bundle rejected: secret-like content detected ({', '.join(hits)})",
            EXIT_INPUT,
        )
    return data, sha256_bytes(data)


def cmd_incident(vault_arg: str, out_dir_arg: str, metadata_arg: str, diagnostics: list[str]) -> dict[str, Any]:
    vault = ensure_git_root(vault_arg)
    if not diagnostics:
        raise OpsError("incident requires at least one diagnostic file or directory", EXIT_INPUT)
    if metadata_arg.startswith("@"):
        metadata = read_json_file(metadata_arg[1:])
    else:
        try:
            metadata = json.loads(metadata_arg)
        except json.JSONDecodeError as exc:
            raise OpsError("incident metadata must be a JSON object", EXIT_INPUT) from exc
    if not isinstance(metadata, dict):
        raise OpsError("incident metadata must be a JSON object", EXIT_INPUT)
    hits = scan_secrets(json.dumps(metadata, ensure_ascii=False, sort_keys=True))
    if hits:
        raise OpsError(f"Incident bundle rejected: secret-like content detected ({', '.join(hits)})", EXIT_INPUT)
    out_dir = require_external_dir(out_dir_arg, [vault])
    # All scans complete before any bundle path is created; zero bundle on any hit.
    files = collect_diagnostics(diagnostics)
    stamp = dt.datetime.now().astimezone().replace(microsecond=0).strftime("%Y%m%d-%H%M%S")
    bundle_dir = out_dir / f"incident-{stamp}"
    try:
        bundle_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(bundle_dir, 0o700)
        manifest: dict[str, Any] = {
            "created_at": dt.datetime.now().astimezone().replace(microsecond=0).isoformat(),
            "metadata": metadata,
            # Only generated safe artifact names are recorded; original absolute
            # paths and raw basenames are never stored.
            "diagnostics": [
                {"artifact": artifact, "sha256": digest, "bytes": len(data)} for artifact, data, digest in files
            ],
        }
        atomic_write(bundle_dir / "incident.json", (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        for artifact, data, digest in files:
            target = bundle_dir / "diagnostics" / artifact
            target.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(target.parent, 0o700)
            atomic_write(target, data)
            if sha256_bytes(data) != digest:
                raise OpsError("Incident diagnostic copy failed verification", EXIT_STORAGE)
    except Exception:
        shutil.rmtree(bundle_dir, ignore_errors=True)
        raise
    return {"ok": True, "bundle_dir": str(bundle_dir), "diagnostics": len(files), "sha256": sha256_bytes((bundle_dir / "incident.json").read_bytes())}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def dispatch(argv: list[str]) -> int:
    if not argv:
        raise OpsError("A command is required: audit | validate-manifest | migrate | health | ledger | incident", EXIT_INPUT)
    command, args = argv[0], argv[1:]

    if command == "audit":
        vault = _take_flag(args, "--vault")
        if vault is None:
            raise OpsError("audit requires --vault", EXIT_INPUT)
        output = _take_flag(args, "--output")
        if args:
            raise OpsError("Unknown audit arguments", EXIT_INPUT)
        emit(cmd_audit(vault, output))
        return 0

    if command == "validate-manifest":
        manifest = _take_flag(args, "--manifest")
        vault = _take_flag(args, "--source-vault")
        if manifest is None or vault is None:
            raise OpsError("validate-manifest requires --manifest and --source-vault", EXIT_INPUT)
        if args:
            raise OpsError("Unknown validate-manifest arguments", EXIT_INPUT)
        emit(validate_manifest(vault, manifest))
        return 0

    if command == "migrate":
        manifest = _take_flag(args, "--manifest")
        source = _take_flag(args, "--source-vault")
        target = _take_flag(args, "--target-vault")
        if manifest is None or source is None or target is None:
            raise OpsError("migrate requires --manifest, --source-vault and --target-vault", EXIT_INPUT)
        apply = False
        if "--dry-run" in args and "--apply" in args:
            raise OpsError("--dry-run and --apply are mutually exclusive", EXIT_INPUT)
        if "--apply" in args:
            apply = True
        args = [item for item in args if item not in ("--dry-run", "--apply")]
        if args:
            raise OpsError("Unknown migrate arguments", EXIT_INPUT)
        emit(cmd_migrate(manifest, source, target, apply=apply))
        return 0

    if command == "health":
        vault = _take_flag(args, "--vault")
        if vault is None:
            raise OpsError("health requires --vault", EXIT_INPUT)
        state_file = _take_flag(args, "--state-file")
        if args:
            raise OpsError("Unknown health arguments", EXIT_INPUT)
        emit(cmd_health(vault, state_file))
        return 0

    if command == "ledger":
        directory = _take_flag(args, "--dir")
        vault = _take_flag(args, "--vault")
        if directory is None:
            raise OpsError("ledger requires --dir", EXIT_INPUT)
        if vault is None:
            raise OpsError("ledger requires --vault", EXIT_INPUT)
        vault_root = ensure_git_root(vault)
        if not args:
            raise OpsError("ledger requires a subcommand: add | list", EXIT_INPUT)
        sub = args.pop(0)
        if sub == "add":
            record_type = _take_flag(args, "--type")
            data = _take_flag(args, "--data")
            if record_type is None or data is None:
                raise OpsError("ledger add requires --type and --data", EXIT_INPUT)
            if args:
                raise OpsError("Unknown ledger add arguments", EXIT_INPUT)
            emit(cmd_ledger_add(directory, record_type, data, [vault_root]))
            return 0
        if sub == "list":
            if args:
                raise OpsError("Unknown ledger list arguments", EXIT_INPUT)
            emit(cmd_ledger_list(directory, [vault_root]))
            return 0
        raise OpsError("ledger requires a subcommand: add | list", EXIT_INPUT)

    if command == "incident":
        vault = _take_flag(args, "--vault")
        out_dir = _take_flag(args, "--out-dir")
        metadata = _take_flag(args, "--metadata")
        if vault is None or out_dir is None or metadata is None:
            raise OpsError("incident requires --vault, --out-dir and --metadata", EXIT_INPUT)
        diagnostics = _take_all_flags(args, "--diagnostics")
        if not diagnostics:
            raise OpsError("incident requires at least one --diagnostics path", EXIT_INPUT)
        if args:
            raise OpsError("Unknown incident arguments", EXIT_INPUT)
        emit(cmd_incident(vault, out_dir, metadata, diagnostics))
        return 0

    raise OpsError(f"Unknown command: {command}", EXIT_INPUT)


def _take_flag(args: list[str], name: str) -> str | None:
    for index, item in enumerate(args):
        if item == name:
            if index + 1 >= len(args):
                raise OpsError(f"{name} requires a value", EXIT_INPUT)
            value = args[index + 1]
            del args[index : index + 2]
            return value
    return None


def _take_all_flags(args: list[str], name: str) -> list[str]:
    values: list[str] = []
    while True:
        value = _take_flag(args, name)
        if value is None:
            return values
        values.append(value)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    try:
        return dispatch(sys.argv[1:])
    except OpsError as exc:
        return fail(str(exc), exc.code, **exc.details)
    except OSError:
        return fail("Filesystem operation failed", EXIT_STORAGE)


if __name__ == "__main__":
    raise SystemExit(main())
