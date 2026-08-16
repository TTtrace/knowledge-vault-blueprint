from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parents[2]
OPS = REPO / "scripts" / "sourcenotes_ops.py"

OPS_SPEC = importlib.util.spec_from_file_location("sourcenotes_ops", OPS)
assert OPS_SPEC and OPS_SPEC.loader
sourcenotes_ops = importlib.util.module_from_spec(OPS_SPEC)
OPS_SPEC.loader.exec_module(sourcenotes_ops)


def git(vault: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(vault), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=check,
    )


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_vault(base: Path, name: str) -> Path:
    vault = Path(base) / name
    vault.mkdir()
    for folder in [
        "sources/web",
        "sources/transcripts",
        "sources/documents",
        "notes/annotations",
        "notes/ideas",
        "assets/images",
    ]:
        (vault / folder).mkdir(parents=True)
    (vault / ".gitignore").write_text(".queue/\n", encoding="utf-8")
    git(vault, "init", "-q")
    git(vault, "config", "user.name", "Vault Test")
    git(vault, "config", "user.email", "vault-test@example.invalid")
    git(vault, "add", ".")
    git(vault, "commit", "-q", "-m", "init")
    return vault


def write_source(vault: Path, source_id: str, title: str, body_region: str | None) -> Path:
    fields = [
        "schema_version: 1",
        f"id: {source_id}",
        "type: source",
        f"title: {title}",
        "ingest_status: ready",
        "canonical_url: https://example.com/" + source_id,
    ]
    body = f"# {title}\n"
    if body_region is None:
        pass
    else:
        body += "\n<!-- source-content:start -->\n" + body_region + "\n<!-- source-content:end -->\n"
    path = vault / "sources/web" / f"{source_id}.md"
    path.write_text("---\n" + "\n".join(fields) + "\n---\n\n" + body, encoding="utf-8")
    return path


class SourcenotesOpsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_ops(self, *args: str, expected: int = 0) -> dict:
        process = subprocess.run(
            [sys.executable, str(OPS), *args],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        self.assertEqual(process.returncode, expected, process.stderr + process.stdout)
        return json.loads(process.stdout)

    # ---- audit ----

    def test_audit_scaffold_never_counts_as_body(self):
        vault = make_vault(Path(self.temp.name), "Audit-test")
        samples: list[tuple[str, str | None, str]] = [
            ("20260804-100000-aaaa", None, "no_markers"),                                    # 1: no markers
            ("20260804-100001-bbbb", "", "empty"),                                           # 2: empty markers
            ("20260804-100002-cccc", "   \n\t  ", "empty"),                                  # 3: whitespace only
            ("20260804-100003-dddd", "<!-- 模板注释 -->", "empty"),                          # 4: comment only
            ("20260804-100004-eeee", "", "empty"),                                           # 5: scaffold w/ heading outside
            ("20260804-100005-ffff", "审计正文独特内容XYZ", "body"),                          # 6: real body
        ]
        for source_id, region, _expected in samples:
            write_source(vault, source_id, f"样本 {source_id}", region)
        result = self.run_ops("audit", "--vault", str(vault))
        self.assertTrue(result["ok"])
        self.assertEqual(result["report"]["vault"], "redacted")
        by_id = {item["id"]: item for item in result["report"]["sources"]}
        self.assertEqual(len(by_id), len(samples))
        allowed = {"body", "empty", "no_markers"}
        for source_id, _region, expected in samples:
            item = by_id[source_id]
            self.assertEqual(item["disposition"], expected, source_id)
            self.assertIn(item["disposition"], allowed)
            self.assertEqual(item["has_body"], expected == "body")
        # The audit report must not leak body content or absolute vault paths.
        serialized = json.dumps(result)
        self.assertNotIn("审计正文独特内容XYZ", serialized)
        self.assertNotIn(str(vault), serialized)

    def test_audit_output_file_permissions(self):
        vault = make_vault(Path(self.temp.name), "AuditOut-test")
        write_source(vault, "20260804-100000-aaaa", "来源", "正文。")
        out_file = Path(self.temp.name) / "audit.json"
        result = self.run_ops("audit", "--vault", str(vault), "--output", str(out_file))
        self.assertTrue(result["ok"])
        self.assertTrue(out_file.is_file())
        self.assertEqual(stat.S_IMODE(out_file.stat().st_mode), 0o600)

    # ---- manifest validate / migrate ----

    def _seed_migratable_source(self, vault: Path, source_id: str = "20260804-100000-aaaa") -> dict[str, str]:
        source_path = write_source(vault, source_id, "可迁移来源", "可迁移正文内容。")
        annotation_path = vault / "notes/annotations" / f"annotated_{source_id}.md"
        annotation_path.write_text(
            "---\nschema_version: 1\n"
            f"id: 20260804-100001-aaaa\n"
            "type: annotation\n"
            f"source_id: {source_id}\n"
            "---\n\n<!-- vault-capture:annotation-rollup -->\n\n<!-- vault-capture:entries:start -->\n<!-- vault-capture:entries:end -->\n",
            encoding="utf-8",
        )
        asset_dir = vault / "assets/images" / source_id
        asset_dir.mkdir(parents=True)
        asset = asset_dir / "001-deadbeef.png"
        asset.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        return {
            "source": source_path.relative_to(vault).as_posix(),
            "annotation": annotation_path.relative_to(vault).as_posix(),
            "attachment": asset.relative_to(vault).as_posix(),
        }

    def _manifest_file(self, entries: list[dict]) -> Path:
        path = Path(self.temp.name) / "manifest.json"
        path.write_text(
            json.dumps({"manifest_version": 1, "entries": entries}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def _migrate_entry(self, source_id: str, paths: dict[str, str]) -> dict:
        return {
            "source_id": source_id,
            "action": "migrate",
            "reason": "正文已就绪",
            "paths": {"source": paths["source"], "annotation": paths["annotation"], "attachments": [paths["attachment"]]},
        }

    def _seed_top_level_pair(self, vault: Path, source_id: str = "20260804-100000-aaaa") -> dict[str, str]:
        """Seed two TOP-LEVEL files directly at the Vault root (no parent
        directories anywhere): a source and an annotation, both with legal
        frontmatter ids.  Returns their manifest-declared root-relative paths."""
        source_path = vault / "top-source.md"
        source_path.write_text(
            "---\nschema_version: 1\n"
            f"id: {source_id}\n"
            "type: source\n"
            "title: Top-level source\n"
            "ingest_status: ready\n"
            "canonical_url: https://example.com/top\n"
            "---\n\n# Top-level source\n\n"
            "<!-- source-content:start -->\n顶层正文内容。\n<!-- source-content:end -->\n",
            encoding="utf-8",
        )
        annotation_path = vault / "top-annotation.md"
        annotation_path.write_text(
            "---\nschema_version: 1\n"
            "id: 20260804-100001-aaaa\n"
            "type: annotation\n"
            f"source_id: {source_id}\n"
            "---\n\n<!-- vault-capture:annotation-rollup -->\n\n"
            "<!-- vault-capture:entries:start -->\n<!-- vault-capture:entries:end -->\n",
            encoding="utf-8",
        )
        return {"source": source_path.relative_to(vault).as_posix(), "annotation": annotation_path.relative_to(vault).as_posix()}

    def _top_level_entry(self, source_id: str, paths: dict[str, str]) -> dict:
        return {
            "source_id": source_id,
            "action": "migrate",
            "reason": "顶层目标验证",
            "paths": {"source": paths["source"], "annotation": paths["annotation"], "attachments": []},
        }

    def test_migrate_dry_run_and_apply_are_exact_and_safe(self):
        source_vault = make_vault(Path(self.temp.name), "MigrateSrc-test")
        target_vault = make_vault(Path(self.temp.name), "MigrateDst-test")
        paths = self._seed_migratable_source(source_vault)
        manifest = self._manifest_file([self._migrate_entry("20260804-100000-aaaa", paths)])
        source_sha_before = file_sha256(source_vault / paths["source"])
        source_asset_sha_before = file_sha256(source_vault / paths["attachment"])

        validated = self.run_ops("validate-manifest", "--manifest", str(manifest), "--source-vault", str(source_vault))
        self.assertEqual(validated["entries"][0]["status"], "ready")

        dry = self.run_ops(
            "migrate", "--manifest", str(manifest),
            "--source-vault", str(source_vault), "--target-vault", str(target_vault),
            "--dry-run",
        )
        self.assertTrue(dry["dry_run"])
        self.assertEqual(len(dry["copied"]), 3)
        for evidence in dry["copied"]:
            self.assertEqual(len(evidence["src_sha256"]), 64)
            self.assertFalse(evidence["applied"])
        self.assertFalse((target_vault / paths["source"]).exists())

        target_head_before = git(target_vault, "rev-parse", "HEAD").stdout.strip()
        applied = self.run_ops(
            "migrate", "--manifest", str(manifest),
            "--source-vault", str(source_vault), "--target-vault", str(target_vault),
            "--apply",
        )
        self.assertTrue(applied["applied"])
        self.assertEqual(len(applied["copied"]), 3)
        for evidence in applied["copied"]:
            dst = target_vault / evidence["dst_path"]
            self.assertTrue(dst.is_file())
            self.assertEqual(evidence["dst_sha256"], evidence["src_sha256"])
            self.assertEqual(file_sha256(dst), evidence["src_sha256"])
        # Source vault untouched; target received plain file copies only — no
        # stage, no commit, no push, HEAD unchanged (untracked files are expected).
        self.assertEqual(file_sha256(source_vault / paths["source"]), source_sha_before)
        self.assertEqual(file_sha256(source_vault / paths["attachment"]), source_asset_sha_before)
        self.assertEqual(git(target_vault, "diff", "--cached", "--name-only").stdout.strip(), "")
        self.assertEqual(git(target_vault, "rev-parse", "HEAD").stdout.strip(), target_head_before)

        # Second apply must stop on target-path conflict.
        again = self.run_ops(
            "migrate", "--manifest", str(manifest),
            "--source-vault", str(source_vault), "--target-vault", str(target_vault),
            "--apply",
            expected=3,
        )
        self.assertIn("conflict", again["error"])

    def test_migrate_repair_then_migrate_never_applies(self):
        source_vault = make_vault(Path(self.temp.name), "RepairSrc-test")
        target_vault = make_vault(Path(self.temp.name), "RepairDst-test")
        paths = self._seed_migratable_source(source_vault)
        entry = self._migrate_entry("20260804-100000-aaaa", paths)
        entry["action"] = "repair_then_migrate"
        manifest = self._manifest_file([entry])
        result = self.run_ops(
            "migrate", "--manifest", str(manifest),
            "--source-vault", str(source_vault), "--target-vault", str(target_vault),
            "--apply",
            expected=2,
        )
        self.assertIn("repair_then_migrate", result["error"])
        self.assertFalse((target_vault / paths["source"]).exists())

    def test_manifest_rejects_duplicates_escape_and_conflicts(self):
        source_vault = make_vault(Path(self.temp.name), "Manifest-test")
        paths_a = self._seed_migratable_source(source_vault, "20260804-100000-aaaa")
        paths_b = self._seed_migratable_source(source_vault, "20260804-100001-bbbb")
        base_a = self._migrate_entry("20260804-100000-aaaa", paths_a)
        base_b = self._migrate_entry("20260804-100001-bbbb", paths_b)

        duplicate = self._manifest_file([base_a, base_a])
        result = self.run_ops("validate-manifest", "--manifest", str(duplicate), "--source-vault", str(source_vault), expected=2)
        self.assertIn("Duplicate manifest entry", result["error"])

        escaped = self._migrate_entry("20260804-100000-aaaa", paths_a)
        escaped["paths"]["source"] = "../escape.md"
        result = self.run_ops(
            "validate-manifest",
            "--manifest",
            self._manifest_file([escaped]),
            "--source-vault",
            str(source_vault),
            expected=2,
        )
        self.assertIn("escapes the Vault", result["error"])

        missing = self._migrate_entry("20260804-100000-aaaa", paths_a)
        missing["paths"]["source"] = "sources/web/does-not-exist.md"
        result = self.run_ops(
            "validate-manifest",
            "--manifest",
            self._manifest_file([missing]),
            "--source-vault",
            str(source_vault),
            expected=2,
        )
        self.assertIn("missing path", result["error"])

        omitted = self._migrate_entry("20260804-100000-aaaa", paths_a)
        omitted["paths"]["attachments"] = []
        result = self.run_ops(
            "validate-manifest",
            "--manifest",
            self._manifest_file([omitted]),
            "--source-vault",
            str(source_vault),
            expected=2,
        )
        self.assertIn("omits existing attachments", result["error"])

        canonical_conflict = self._migrate_entry("20260804-100000-aaaa", paths_a)
        canonical_conflict_b = self._migrate_entry("20260804-100001-bbbb", paths_b)
        # Rewrite source B to share A's canonical_url.
        source_b = source_vault / paths_b["source"]
        text = source_b.read_text(encoding="utf-8").replace(
            "https://example.com/20260804-100001-bbbb",
            "https://example.com/20260804-100000-aaaa",
        )
        source_b.write_text(text, encoding="utf-8")
        result = self.run_ops(
            "validate-manifest",
            "--manifest",
            self._manifest_file([canonical_conflict, canonical_conflict_b]),
            "--source-vault",
            str(source_vault),
            expected=2,
        )
        self.assertIn("Canonical URL conflict", result["error"])
        # Restore B's canonical_url so later sub-cases are not polluted.
        source_b.write_text(text.replace("https://example.com/20260804-100000-aaaa", "https://example.com/20260804-100001-bbbb"), encoding="utf-8")

        attachment_twice = self._migrate_entry("20260804-100000-aaaa", paths_a)
        attachment_twice_b = self._migrate_entry("20260804-100001-bbbb", paths_b)
        attachment_twice_b["paths"]["attachments"] = [paths_a["attachment"]]
        result = self.run_ops(
            "validate-manifest",
            "--manifest",
            self._manifest_file([attachment_twice, attachment_twice_b]),
            "--source-vault",
            str(source_vault),
            expected=2,
        )
        self.assertIn("Attachment declared twice", result["error"])

    # ---- FIX-F01: transactional migration ----

    def test_migrate_all_or_nothing_on_any_conflict(self):
        # Entry A is fully migratable, entry B conflicts on target.  apply must
        # leave the target with zero changes (A must not be partially migrated).
        source_vault = make_vault(Path(self.temp.name), "AllOrNothingSrc-test")
        target_vault = make_vault(Path(self.temp.name), "AllOrNothingDst-test")
        paths_a = self._seed_migratable_source(source_vault, "20260804-100000-aaaa")
        paths_b = self._seed_migratable_source(source_vault, "20260804-100001-bbbb")
        manifest = self._manifest_file(
            [
                self._migrate_entry("20260804-100000-aaaa", paths_a),
                self._migrate_entry("20260804-100001-bbbb", paths_b),
            ]
        )
        # Pre-existing target file at B's source path -> conflict for B.
        (target_vault / paths_b["source"]).parent.mkdir(parents=True, exist_ok=True)
        (target_vault / paths_b["source"]).write_text("pre-existing", encoding="utf-8")
        source_sha_before = file_sha256(source_vault / paths_a["source"])
        result = self.run_ops(
            "migrate", "--manifest", str(manifest),
            "--source-vault", str(source_vault), "--target-vault", str(target_vault),
            "--apply",
            expected=3,
        )
        self.assertIn("conflict", result["error"])
        for rel in (paths_a["source"], paths_a["annotation"], paths_a["attachment"]):
            self.assertFalse((target_vault / rel).exists(), rel)
        self.assertEqual((target_vault / paths_b["source"]).read_text(encoding="utf-8"), "pre-existing")
        self.assertFalse(any(p.name.startswith(".sourcenotes-migrate-") for p in target_vault.iterdir()))
        self.assertEqual(file_sha256(source_vault / paths_a["source"]), source_sha_before)

    def test_migrate_rolls_back_on_publish_failure(self):
        # FIX-F01: a simulated second publish failure must roll back the first
        # published item; the target ends with zero changes and no staging residue.
        source_vault = make_vault(Path(self.temp.name), "RollbackSrc-test")
        target_vault = make_vault(Path(self.temp.name), "RollbackDst-test")
        paths = self._seed_migratable_source(source_vault)  # source + annotation + attachment
        manifest = self._manifest_file([self._migrate_entry("20260804-100000-aaaa", paths)])
        real_publish_link = sourcenotes_ops._publish_link
        calls = {"n": 0}

        def flaky_publish(root_fd, staging_rel, rel, parent_fd):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("simulated publish failure")
            return real_publish_link(root_fd, staging_rel, rel, parent_fd)

        with mock.patch.object(sourcenotes_ops, "_publish_link", side_effect=flaky_publish):
            with self.assertRaises(sourcenotes_ops.OpsError) as context:
                sourcenotes_ops.cmd_migrate(str(manifest), str(source_vault), str(target_vault), apply=True)
        self.assertIn("Publish failed", str(context.exception))
        for rel in (paths["source"], paths["annotation"], paths["attachment"]):
            self.assertFalse((target_vault / rel).exists(), rel)
        self.assertFalse(any(p.name.startswith(".sourcenotes-migrate-") for p in target_vault.iterdir()))

    def test_migrate_post_publish_verify_failure_rolls_back_zero_residue(self):
        # FIX-F01: a failure while reading the published file for hash/size
        # verification must trigger rollback of every published file, the
        # newly-created parent directory, and the staging tree.
        source_vault = make_vault(Path(self.temp.name), "VerifySrc-test")
        target_vault = make_vault(Path(self.temp.name), "VerifyDst-test")
        paths = self._seed_migratable_source(source_vault)
        manifest = self._manifest_file([self._migrate_entry("20260804-100000-aaaa", paths)])
        # Remove the attachment parent so publish has to create it this round.
        (target_vault / "assets" / "images").rmdir()
        real_verify = sourcenotes_ops._verify_published
        calls = {"n": 0}

        def flaky_verify(root_fd, rel):
            calls["n"] += 1
            if calls["n"] == 3:  # fail while verifying the third publish (attachment)
                raise OSError("simulated verification read failure")
            return real_verify(root_fd, rel)

        with mock.patch.object(sourcenotes_ops, "_verify_published", side_effect=flaky_verify):
            with self.assertRaises(sourcenotes_ops.OpsError) as context:
                sourcenotes_ops.cmd_migrate(str(manifest), str(source_vault), str(target_vault), apply=True)
        self.assertIn("Post-publish verification failed", str(context.exception))
        for rel in (paths["source"], paths["annotation"], paths["attachment"]):
            self.assertFalse((target_vault / rel).exists(), rel)
        # The newly-created parent directory and the staging dir are gone.
        self.assertFalse((target_vault / "assets/images").exists())
        self.assertFalse(any(p.name.startswith(".sourcenotes-migrate-") for p in target_vault.iterdir()))

    def test_migrate_reports_rollback_incomplete(self):
        # FIX-F01: rollback failures must not be silently swallowed; a short
        # safe error explicitly says rollback is incomplete and exits nonzero.
        source_vault = make_vault(Path(self.temp.name), "RbIncompleteSrc-test")
        target_vault = make_vault(Path(self.temp.name), "RbIncompleteDst-test")
        paths = self._seed_migratable_source(source_vault)
        manifest = self._manifest_file([self._migrate_entry("20260804-100000-aaaa", paths)])
        real_publish_link = sourcenotes_ops._publish_link
        publish_calls = {"n": 0}

        def flaky_publish(root_fd, staging_rel, rel, parent_fd):
            publish_calls["n"] += 1
            if publish_calls["n"] == 2:
                raise OSError("simulated publish failure")
            return real_publish_link(root_fd, staging_rel, rel, parent_fd)

        with mock.patch.object(sourcenotes_ops, "_publish_link", side_effect=flaky_publish):
            with mock.patch.object(
                sourcenotes_ops, "_unlink_anchored", side_effect=OSError("simulated rollback failure")
            ):
                with self.assertRaises(sourcenotes_ops.OpsError) as context:
                    sourcenotes_ops.cmd_migrate(str(manifest), str(source_vault), str(target_vault), apply=True)
        self.assertIn("rollback incomplete", str(context.exception))
        self.assertIn("rollback_errors", context.exception.details)

    # ---- FIX-F03: descriptor fd lifecycle + rollback error aggregation ----

    def _fd_count(self) -> int:
        return len(os.listdir("/proc/self/fd"))

    def _open_root(self, path: Path) -> int:
        return os.open(str(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def test_open_rel_dir_symlink_failure_does_not_leak_fds(self):
        # FIX-F03: repeated symlink failures at depth >= 2 must not accumulate
        # the opened intermediate descriptors.
        base = Path(self.temp.name) / "fd-symlink"
        (base / "a").mkdir(parents=True)
        os.symlink("/etc", base / "a" / "b")
        root_fd = self._open_root(base)
        try:
            before = self._fd_count()
            for _ in range(250):
                with self.assertRaises(sourcenotes_ops.OpsError):
                    sourcenotes_ops.open_rel_dir(root_fd, "a/b/c", create=False)
            after = self._fd_count()
        finally:
            os.close(root_fd)
        self.assertLessEqual(abs(after - before), 2)

    def test_open_rel_dir_non_directory_failure_does_not_leak_fds(self):
        # FIX-F03: same stability when a mid-path component is a regular file.
        base = Path(self.temp.name) / "fd-nondir"
        (base / "a").mkdir(parents=True)
        (base / "a" / "regfile").write_text("x", encoding="utf-8")
        root_fd = self._open_root(base)
        try:
            before = self._fd_count()
            for _ in range(250):
                with self.assertRaises(sourcenotes_ops.OpsError):
                    sourcenotes_ops.open_rel_dir(root_fd, "a/regfile/c", create=False)
            after = self._fd_count()
        finally:
            os.close(root_fd)
        self.assertLessEqual(abs(after - before), 2)

    def test_ensure_target_parents_symlink_failure_does_not_leak_fds(self):
        base = Path(self.temp.name) / "fd-parents"
        (base / "a").mkdir(parents=True)
        os.symlink("/etc", base / "a" / "b")
        root_fd = self._open_root(base)
        created: list[str] = []
        try:
            before = self._fd_count()
            for _ in range(250):
                with self.assertRaises(sourcenotes_ops.OpsError):
                    sourcenotes_ops.ensure_target_parents(root_fd, "a/b/c/x.md", created)
            after = self._fd_count()
        finally:
            os.close(root_fd)
        self.assertLessEqual(abs(after - before), 2)
        self.assertEqual(created, [])

    def test_ensure_target_parents_non_directory_failure_does_not_leak_fds(self):
        base = Path(self.temp.name) / "fd-parents-nondir"
        (base / "a").mkdir(parents=True)
        (base / "a" / "regfile").write_text("x", encoding="utf-8")
        root_fd = self._open_root(base)
        created: list[str] = []
        try:
            before = self._fd_count()
            for _ in range(250):
                with self.assertRaises(sourcenotes_ops.OpsError):
                    sourcenotes_ops.ensure_target_parents(root_fd, "a/regfile/c/x.md", created)
            after = self._fd_count()
        finally:
            os.close(root_fd)
        self.assertLessEqual(abs(after - before), 2)
        self.assertEqual(created, [])

    def test_ensure_target_parents_concurrent_creation_fd_stable_and_not_recorded(self):
        # FIX-F03: a directory that "appears" concurrently (mkdir -> FileExistsError)
        # is reopened, never recorded for rollback (we did not create it), and
        # leaks no descriptors across 250 iterations.
        base = Path(self.temp.name) / "fd-concurrent"
        base.mkdir()
        root_fd = self._open_root(base)
        real_mkdir = sourcenotes_ops.os.mkdir

        def concurrent_mkdir(path, mode=0o777, *, dir_fd=None):
            real_mkdir(path, mode, dir_fd=dir_fd)
            raise FileExistsError("simulated concurrent creation")

        created: list[str] = []
        try:
            before = self._fd_count()
            with mock.patch.object(sourcenotes_ops.os, "mkdir", side_effect=concurrent_mkdir):
                for _ in range(250):
                    # Nested target: the returned fd is explicitly owned
                    # (owned=True) and the caller closes it exactly once.
                    parent_fd, owned = sourcenotes_ops.ensure_target_parents(root_fd, "a/b/x.md", created)
                    self.assertTrue(owned)
                    os.close(parent_fd)
            after = self._fd_count()
        finally:
            os.close(root_fd)
        self.assertLessEqual(abs(after - before), 2)
        self.assertEqual(created, [])
        self.assertTrue((base / "a" / "b").is_dir())

    def test_ensure_target_parents_returns_explicit_ownership(self):
        # AC-01: ownership comes from an explicit (fd, owned) tuple, never from
        # fd equality: a top-level rel borrows root_fd with owned=False; a
        # nested rel opens its own fd with owned=True.
        base = Path(self.temp.name) / "fd-ownership"
        (base / "a" / "b").mkdir(parents=True)
        root_fd = self._open_root(base)
        nested_fd = None
        try:
            top_fd, top_owned = sourcenotes_ops.ensure_target_parents(root_fd, "top.md", [])
            self.assertFalse(top_owned)
            self.assertEqual(top_fd, root_fd)
            nested_fd, nested_owned = sourcenotes_ops.ensure_target_parents(root_fd, "a/b/c.md", [])
            self.assertTrue(nested_owned)
            self.assertNotEqual(nested_fd, root_fd)
            # The borrowed root fd stays usable after the top-level borrow —
            # it must never have been closed by the caller.
            os.fstat(root_fd)
        finally:
            if nested_fd is not None:
                os.close(nested_fd)
            os.close(root_fd)

    def test_ensure_target_parents_top_level_borrow_no_fd_growth(self):
        # AC-04: 250 top-level borrows (owned=False, caller must NOT close the
        # returned root fd) must not grow /proc/self/fd linearly; transient
        # delta <= 2.
        base = Path(self.temp.name) / "fd-topborrow"
        base.mkdir()
        root_fd = self._open_root(base)
        try:
            before = self._fd_count()
            for _ in range(250):
                fd, owned = sourcenotes_ops.ensure_target_parents(root_fd, "top.md", [])
                self.assertFalse(owned)
                self.assertEqual(fd, root_fd)
            after = self._fd_count()
        finally:
            os.close(root_fd)
        self.assertLessEqual(abs(after - before), 2)

    def test_migrate_top_level_targets_apply_and_root_fd_survives(self):
        # AC-02: top-level manifest targets migrate successfully with correct
        # content/hash and no staging residue.  The two-file transaction proves
        # root_fd stays alive across every item — a caller closing the borrowed
        # root fd would surface as EBADF on the second item's publish/unlink.
        source_vault = make_vault(Path(self.temp.name), "TopSrc-test")
        target_vault = make_vault(Path(self.temp.name), "TopDst-test")
        paths = self._seed_top_level_pair(source_vault)
        manifest = self._manifest_file([self._top_level_entry("20260804-100000-aaaa", paths)])
        src_sha = {rel: file_sha256(source_vault / rel) for rel in (paths["source"], paths["annotation"])}
        target_head_before = git(target_vault, "rev-parse", "HEAD").stdout.strip()

        applied = self.run_ops(
            "migrate", "--manifest", str(manifest),
            "--source-vault", str(source_vault), "--target-vault", str(target_vault),
            "--apply",
        )
        self.assertTrue(applied["applied"])
        self.assertEqual(len(applied["copied"]), 2)
        for evidence in applied["copied"]:
            dst = target_vault / evidence["dst_path"]
            self.assertTrue(dst.is_file())
            self.assertEqual(evidence["dst_sha256"], evidence["src_sha256"])
            self.assertEqual(file_sha256(dst), evidence["src_sha256"])
        self.assertEqual(file_sha256(target_vault / "top-source.md"), src_sha["top-source.md"])
        self.assertEqual(file_sha256(target_vault / "top-annotation.md"), src_sha["top-annotation.md"])
        # No staging residue; source untouched; no stage/commit.
        self.assertFalse(any(p.name.startswith(".sourcenotes-migrate-") for p in target_vault.iterdir()))
        self.assertEqual(file_sha256(source_vault / "top-source.md"), src_sha["top-source.md"])
        self.assertEqual(git(target_vault, "diff", "--cached", "--name-only").stdout.strip(), "")
        self.assertEqual(git(target_vault, "rev-parse", "HEAD").stdout.strip(), target_head_before)

        # A second apply hits the target-path conflict (proves the first apply
        # left a consistent state and no closed-fd EBADF on the repeat path).
        again = self.run_ops(
            "migrate", "--manifest", str(manifest),
            "--source-vault", str(source_vault), "--target-vault", str(target_vault),
            "--apply",
            expected=3,
        )
        self.assertIn("conflict", again["error"])

    def test_migrate_top_level_publish_failure_rolls_back_zero_residue(self):
        # AC-03: a second top-level publish failure must roll back the first
        # top-level publish, leave zero target/staging residue, keep the source
        # vault byte-identical and exit nonzero.
        source_vault = make_vault(Path(self.temp.name), "TopFailSrc-test")
        target_vault = make_vault(Path(self.temp.name), "TopFailDst-test")
        paths = self._seed_top_level_pair(source_vault)
        manifest = self._manifest_file([self._top_level_entry("20260804-100000-aaaa", paths)])
        src_sha = {rel: file_sha256(source_vault / rel) for rel in (paths["source"], paths["annotation"])}
        real_publish_link = sourcenotes_ops._publish_link
        calls = {"n": 0}

        def flaky_publish(root_fd, staging_rel, rel, parent_fd):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("simulated publish failure")
            return real_publish_link(root_fd, staging_rel, rel, parent_fd)

        with mock.patch.object(sourcenotes_ops, "_publish_link", side_effect=flaky_publish):
            with self.assertRaises(sourcenotes_ops.OpsError) as context:
                sourcenotes_ops.cmd_migrate(str(manifest), str(source_vault), str(target_vault), apply=True)
        self.assertIn("Publish failed", str(context.exception))
        self.assertEqual(context.exception.code, sourcenotes_ops.EXIT_STORAGE)
        for rel in (paths["source"], paths["annotation"]):
            self.assertFalse((target_vault / rel).exists(), rel)
        self.assertFalse(any(p.name.startswith(".sourcenotes-migrate-") for p in target_vault.iterdir()))
        self.assertEqual(file_sha256(source_vault / "top-source.md"), src_sha["top-source.md"])
        self.assertEqual(file_sha256(source_vault / "top-annotation.md"), src_sha["top-annotation.md"])

    def test_rollback_open_rel_dir_ops_error_collected_and_other_actions_attempted(self):
        # FIX-F03: an OpsError raised while rollback resolves a parent directory
        # must be collected (never escape rollback_transaction) and the remaining
        # cleanup actions (later unlinks, rmdirs, staging) must still run.
        base = Path(self.temp.name) / "rollback-ops"
        (base / "a" / "b").mkdir(parents=True)
        (base / "a" / "b" / "f.md").write_text("x", encoding="utf-8")
        (base / "a2" / "b2").mkdir(parents=True)
        (base / "a2" / "b2" / "g.md").write_text("y", encoding="utf-8")
        root_fd = self._open_root(base)
        real_open = sourcenotes_ops.open_rel_dir
        real_unlink = sourcenotes_ops._unlink_anchored
        real_rmdir = sourcenotes_ops._rmdir_anchored
        attempts = {"unlink": 0, "rmdir": 0}

        def flaky_open(root_fd_arg, rel, *, create=False):
            if rel == "a/b":
                raise sourcenotes_ops.OpsError(
                    "simulated rollback open failure", sourcenotes_ops.EXIT_STORAGE
                )
            return real_open(root_fd_arg, rel, create=create)

        def counting_unlink(parent_fd, name):
            attempts["unlink"] += 1
            return real_unlink(parent_fd, name)

        def counting_rmdir(parent_fd, name):
            attempts["rmdir"] += 1
            return real_rmdir(parent_fd, name)

        try:
            with mock.patch.object(sourcenotes_ops, "open_rel_dir", side_effect=flaky_open), \
                 mock.patch.object(sourcenotes_ops, "_unlink_anchored", side_effect=counting_unlink), \
                 mock.patch.object(sourcenotes_ops, "_rmdir_anchored", side_effect=counting_rmdir):
                errors = sourcenotes_ops.rollback_transaction(
                    root_fd,
                    ["a/b/f.md", "a2/b2/g.md"],
                    ["a2/b2"],
                    ".missing-staging",
                )
        finally:
            os.close(root_fd)
        self.assertIsInstance(errors, list)
        self.assertEqual(len(errors), 2)
        self.assertIn("unlink", errors[0])
        self.assertIn("simulated rollback open failure", errors[0])
        self.assertIn("staging cleanup", errors[1])
        # The later unlink and the rmdir were still attempted after the failure.
        self.assertEqual(attempts["unlink"], 1)
        self.assertEqual(attempts["rmdir"], 1)

    def test_rollback_aggregates_mixed_errors_bounded(self):
        # FIX-F03: every cleanup step failing with OSError or OpsError is
        # aggregated into the returned list; messages stay bounded and never
        # carry absolute host paths.
        base = Path(self.temp.name) / "rollback-mixed"
        (base / "x").mkdir(parents=True)
        root_fd = self._open_root(base)
        real_open = sourcenotes_ops.open_rel_dir
        real_unlink = sourcenotes_ops._unlink_anchored
        real_rmdir = sourcenotes_ops._rmdir_anchored

        def flaky_open(root_fd_arg, rel, *, create=False):
            if rel == "a/b":
                raise sourcenotes_ops.OpsError(
                    "simulated OpsError open " + "x" * 500,
                    sourcenotes_ops.EXIT_STORAGE,
                )
            return real_open(root_fd_arg, rel, create=create)

        def failing_unlink(parent_fd, name):
            raise OSError("simulated OSError unlink")

        def failing_rmdir(parent_fd, name):
            raise OSError("simulated OSError rmdir")

        try:
            with mock.patch.object(sourcenotes_ops, "open_rel_dir", side_effect=flaky_open), \
                 mock.patch.object(sourcenotes_ops, "_unlink_anchored", side_effect=failing_unlink), \
                 mock.patch.object(sourcenotes_ops, "_rmdir_anchored", side_effect=failing_rmdir):
                errors = sourcenotes_ops.rollback_transaction(
                    root_fd,
                    ["a/b/f1.md", "x/f2.md"],
                    ["a/b", "x"],
                    ".missing-staging",
                )
        finally:
            os.close(root_fd)
        self.assertIsInstance(errors, list)
        self.assertEqual(len(errors), 5)
        joined = "\n".join(errors)
        self.assertIn("simulated OpsError open", joined)
        self.assertIn("OSError", joined)
        long_entry = next(e for e in errors if "simulated OpsError open" in e)
        self.assertLess(len(long_entry), 250)
        self.assertNotIn(str(base), joined)

    def test_rollback_clean_restores_pre_call_state(self):
        # FIX-F03: a fully successful rollback returns no errors and restores the
        # published file, created parents (reverse creation order) and staging tree.
        base = Path(self.temp.name) / "rollback-clean"
        (base / "a" / "b").mkdir(parents=True)
        (base / "a" / "b" / "f.md").write_text("x", encoding="utf-8")
        (base / ".staging").mkdir()
        (base / ".staging" / "g.md").write_text("y", encoding="utf-8")
        root_fd = self._open_root(base)
        try:
            errors = sourcenotes_ops.rollback_transaction(
                root_fd,
                ["a/b/f.md"],
                ["a", "a/b"],
                ".staging",
            )
        finally:
            os.close(root_fd)
        self.assertEqual(errors, [])
        self.assertFalse((base / "a").exists())
        self.assertFalse((base / ".staging").exists())

    def test_migrate_incomplete_reports_original_error_without_abs_paths(self):
        # FIX-F03: when migration fails and rollback is incomplete, the nonzero
        # result keeps the original failure category together with "rollback
        # incomplete", never leaks absolute paths, and never reports success.
        source_vault = make_vault(Path(self.temp.name), "RbOrigSrc-test")
        target_vault = make_vault(Path(self.temp.name), "RbOrigDst-test")
        paths = self._seed_migratable_source(source_vault)
        manifest = self._manifest_file([self._migrate_entry("20260804-100000-aaaa", paths)])
        real_publish_link = sourcenotes_ops._publish_link
        publish_calls = {"n": 0}

        def flaky_publish(root_fd, staging_rel, rel, parent_fd):
            publish_calls["n"] += 1
            if publish_calls["n"] == 2:
                raise OSError("simulated publish failure")
            return real_publish_link(root_fd, staging_rel, rel, parent_fd)

        with mock.patch.object(sourcenotes_ops, "_publish_link", side_effect=flaky_publish):
            with mock.patch.object(
                sourcenotes_ops, "_unlink_anchored", side_effect=OSError("simulated rollback failure")
            ):
                with self.assertRaises(sourcenotes_ops.OpsError) as context:
                    sourcenotes_ops.cmd_migrate(str(manifest), str(source_vault), str(target_vault), apply=True)
        self.assertIn("rollback incomplete", str(context.exception))
        self.assertEqual(context.exception.code, sourcenotes_ops.EXIT_STORAGE)
        details = context.exception.details
        self.assertIn("original_error", details)
        self.assertIn("Publish failed", details["original_error"])
        self.assertIn("rollback_errors", details)
        serialized = json.dumps(details, ensure_ascii=False)
        self.assertNotIn(str(source_vault), serialized)
        self.assertNotIn(str(target_vault), serialized)

    def test_rollback_entries_sanitize_paths_secrets_newlines_and_bound_total(self):
        # F-01 round 2: malicious absolute paths, secret key-values/tokens and
        # newlines carried by either the rel prefix or the failure message must
        # be redacted into single bounded lines; every aggregated entry respects
        # the strict total-length limit.
        base = Path(self.temp.name) / "rollback-sanitize"
        (base / "x").mkdir(parents=True)
        root_fd = self._open_root(base)
        evil_rel = "/etc/secret/passwd\ncorrupted/../x.md"
        secret = (
            "sk-AAAAAAAAAAAAAAAAAAAAAAAA and "
            "Authorization: Bearer hunter2xyz and "
            "password=hunter2abc"
        )

        def leaking_open(root_fd_arg, rel, *, create=False):
            raise RuntimeError(f"simulated failure leaking {secret}")

        try:
            with mock.patch.object(sourcenotes_ops, "open_rel_dir", side_effect=leaking_open):
                errors = sourcenotes_ops.rollback_transaction(
                    root_fd,
                    [evil_rel, "x/g.md"],
                    ["x"],
                    ".missing-staging",
                    staging_created=True,
                )
        finally:
            os.close(root_fd)
        # unlink x/g.md + unlink evil_rel + staging cleanup (the root-level
        # rmdir of "x" needs no open_rel_dir and succeeds).
        self.assertEqual(len(errors), 3)
        joined = "\n".join(errors)
        self.assertNotIn("/etc/secret/passwd", joined)
        self.assertNotIn("sk-AAAAAAAAAAAAAAAAAAAAAAAA", joined)
        self.assertNotIn("hunter2xyz", joined)
        self.assertNotIn("hunter2abc", joined)
        # Diagnostic categories and action anchors stay useful.
        self.assertIn("RuntimeError", joined)
        self.assertIn("unlink", joined)
        self.assertIn("staging cleanup", joined)
        for entry in errors:
            self.assertNotIn("\n", entry)
            self.assertNotIn("\r", entry)
            self.assertLessEqual(len(entry), sourcenotes_ops._ROLLBACK_ERROR_LIMIT)

    def test_rollback_entries_sanitize_compound_keys_unc_and_preserve_context(self):
        # F-01 round 3: reviewer probes `credential=TOPSECRET`,
        # `client_secret=TOPSECRET` and Windows UNC paths must be fully redacted
        # at the value level; the key name and any following diagnostic text are
        # preserved, and every entry stays single-line and bounded.
        base = Path(self.temp.name) / "rollback-sanitize-r3"
        (base / "x").mkdir(parents=True)
        root_fd = self._open_root(base)
        unc = "\\\\server\\share\\private.txt"
        leak = (
            "failed credential=TOPSECRET; client_secret=TOPSECRET retry=3 "
            f"unc={unc} ending"
        )

        def leaking_open(root_fd_arg, rel, *, create=False):
            raise RuntimeError(f"simulated failure: {leak}")

        try:
            with mock.patch.object(sourcenotes_ops, "open_rel_dir", side_effect=leaking_open):
                errors = sourcenotes_ops.rollback_transaction(
                    root_fd,
                    ["x/a.md"],
                    ["x"],
                    ".missing-staging",
                    staging_created=True,
                )
        finally:
            os.close(root_fd)
        joined = "\n".join(errors)
        # Reviewer probes fully redacted.
        self.assertNotIn("TOPSECRET", joined)
        self.assertNotIn("server\\share", joined)
        self.assertNotIn("private.txt", joined)
        # Key names and surrounding diagnostic text are preserved.
        self.assertIn("credential=<redacted>", joined)
        self.assertIn("client_secret=<redacted>", joined)
        self.assertIn("retry=3", joined)
        self.assertIn("ending", joined)
        self.assertIn("RuntimeError", joined)
        for entry in errors:
            self.assertNotIn("\n", entry)
            self.assertLessEqual(len(entry), sourcenotes_ops._ROLLBACK_ERROR_LIMIT)

    def test_sanitize_keeps_plain_token_secret_descriptions(self):
        # F-01 round 3: error text that merely mentions token/secret/credential
        # as ordinary words (not key=value pairs) must pass through unchanged —
        # never vanish — and words that merely embed a sensitive stem such as
        # "tokenizer" or "author" are not treated as secret keys.
        text = "token not found in manifest; secret scan skipped; credential file missing"
        self.assertEqual(sourcenotes_ops._sanitize_message(text), text)
        text2 = "author=John and tokenizer=abc are not credentials"
        self.assertEqual(sourcenotes_ops._sanitize_message(text2), text2)

    def test_sanitize_quoted_and_delimiter_credential_values(self):
        # AC-05: single/double-quoted credential values redact the value while
        # keeping the key; bare values terminate at every delimiter
        # (| & : , ; ) ] } > ( [ { and whitespace) so the following diagnostic
        # text (retry=3 / ending) is preserved.
        probes = [
            ('failed credential="TOPSECRET" retry=3', "failed credential=<redacted> retry=3"),
            ("failed credential='TOPSECRET' retry=3", "failed credential=<redacted> retry=3"),
            ("credential=TOPSECRET|retry=3|ending", "credential=<redacted>|retry=3|ending"),
            ("credential=TOPSECRET&retry=3&ending", "credential=<redacted>&retry=3&ending"),
            ("credential=TOPSECRET:retry=3:ending", "credential=<redacted>:retry=3:ending"),
            ("credential=TOPSECRET,retry=3,ending", "credential=<redacted>,retry=3,ending"),
            ("credential=TOPSECRET;retry=3;ending", "credential=<redacted>;retry=3;ending"),
            ("credential=TOPSECRET)retry=3)ending", "credential=<redacted>)retry=3)ending"),
            ("credential=TOPSECRET]retry=3]ending", "credential=<redacted>]retry=3]ending"),
            ("credential=TOPSECRET}retry=3}ending", "credential=<redacted>}retry=3}ending"),
            ("credential=TOPSECRET>retry=3>ending", "credential=<redacted>>retry=3>ending"),
            ("credential=TOPSECRET(retry=3(ending", "credential=<redacted>(retry=3(ending"),
            ("credential=TOPSECRET[retry=3[ending", "credential=<redacted>[retry=3[ending"),
            ("credential=TOPSECRET{retry=3{ending", "credential=<redacted>{retry=3{ending"),
            ("credential=TOPSECRET retry=3 ending", "credential=<redacted> retry=3 ending"),
        ]
        sanitized = []
        for raw, expected in probes:
            got = sourcenotes_ops._sanitize_message(raw)
            self.assertEqual(got, expected, raw)
            self.assertNotIn("TOPSECRET", got, raw)
            sanitized.append(got)
        joined = "\n".join(sanitized)
        self.assertNotIn("TOPSECRET", joined)
        self.assertIn("credential=<redacted>", joined)
        self.assertIn("retry=3", joined)
        self.assertIn("ending", joined)

    def test_migrate_rollback_details_sanitize_quoted_values_json_layer(self):
        # AC-05 JSON layer: rollback errors carrying single/double-quoted
        # sensitive values travel through cmd_migrate/rollback into the final
        # details JSON (original_error / rollback_errors) with no secret, the
        # key names and retry=3/ending context preserved, every record bounded.
        source_vault = make_vault(Path(self.temp.name), "RbQuotedSrc-test")
        target_vault = make_vault(Path(self.temp.name), "RbQuotedDst-test")
        paths = self._seed_migratable_source(source_vault)
        manifest = self._manifest_file([self._migrate_entry("20260804-100000-aaaa", paths)])
        real_publish_link = sourcenotes_ops._publish_link
        publish_calls = {"n": 0}
        secret = 'rollback leak credential="TOPQUOTED" client_secret=\'TOPSECRET\' retry=3 ending'

        def flaky_publish(root_fd, staging_rel, rel, parent_fd):
            publish_calls["n"] += 1
            if publish_calls["n"] == 2:
                raise OSError("simulated publish failure")
            return real_publish_link(root_fd, staging_rel, rel, parent_fd)

        with mock.patch.object(sourcenotes_ops, "_publish_link", side_effect=flaky_publish):
            with mock.patch.object(
                sourcenotes_ops, "_unlink_anchored", side_effect=RuntimeError(secret)
            ):
                with self.assertRaises(sourcenotes_ops.OpsError) as context:
                    sourcenotes_ops.cmd_migrate(str(manifest), str(source_vault), str(target_vault), apply=True)
        self.assertIn("rollback incomplete", str(context.exception))
        details = context.exception.details
        serialized = json.dumps(details, ensure_ascii=False)
        self.assertNotIn("TOPQUOTED", serialized)
        self.assertNotIn("TOPSECRET", serialized)
        self.assertIn("credential=<redacted>", serialized)
        self.assertIn("client_secret=<redacted>", serialized)
        self.assertIn("retry=3", serialized)
        self.assertIn("ending", serialized)
        self.assertIn("Publish failed", details["original_error"])
        self.assertLessEqual(len(details["original_error"]), sourcenotes_ops._ORIGINAL_ERROR_LIMIT)
        self.assertTrue(details["rollback_errors"])
        for entry in details["rollback_errors"]:
            self.assertLessEqual(len(entry), sourcenotes_ops._ROLLBACK_ERROR_LIMIT)

    def test_bounded_message_safe_when_exception_str_raises(self):
        # AC-06: an exception whose __str__ itself raises must yield a safe
        # type-only summary — never crash, never leak the payload.
        class BrokenStr(RuntimeError):
            def __str__(self) -> str:
                raise ValueError("simulated __str__ failure")

        exc = BrokenStr("payload that must never leak")
        text = sourcenotes_ops._bounded_message(exc, 200)
        self.assertEqual(text, "BrokenStr: <unprintable>")
        self.assertNotIn("payload", text)
        self.assertNotIn("leak", text)
        # The bounded-entry path (rollback aggregation) stays safe too.
        entry = sourcenotes_ops._bounded_entry("unlink top.md", exc, 200)
        self.assertIn("BrokenStr: <unprintable>", entry)
        self.assertNotIn("payload", entry)

    def test_migrate_rollback_details_sanitized_and_bounded(self):
        # F-01 round 2+3: when a rollback step fails with a message carrying
        # secrets (sk-* token, credential=, client_secret=, Windows UNC path),
        # the final nonzero OpsError details JSON must be scrubbed, keep the
        # original failure category and "rollback incomplete", and stay strictly
        # bounded.
        source_vault = make_vault(Path(self.temp.name), "RbSecretSrc-test")
        target_vault = make_vault(Path(self.temp.name), "RbSecretDst-test")
        paths = self._seed_migratable_source(source_vault)
        manifest = self._manifest_file([self._migrate_entry("20260804-100000-aaaa", paths)])
        real_publish_link = sourcenotes_ops._publish_link
        publish_calls = {"n": 0}

        def flaky_publish(root_fd, staging_rel, rel, parent_fd):
            publish_calls["n"] += 1
            if publish_calls["n"] == 2:
                raise OSError("simulated publish failure")
            return real_publish_link(root_fd, staging_rel, rel, parent_fd)

        with mock.patch.object(sourcenotes_ops, "_publish_link", side_effect=flaky_publish):
            with mock.patch.object(
                sourcenotes_ops,
                "_unlink_anchored",
                side_effect=RuntimeError(
                    "simulated rollback failure with sk-AAAAAAAAAAAAAAAAAAAAAAAA "
                    "credential=TOPSECRET client_secret=TOPSECRET "
                    "\\\\server\\share\\private.txt"
                ),
            ):
                with self.assertRaises(sourcenotes_ops.OpsError) as context:
                    sourcenotes_ops.cmd_migrate(str(manifest), str(source_vault), str(target_vault), apply=True)
        self.assertIn("rollback incomplete", str(context.exception))
        self.assertEqual(context.exception.code, sourcenotes_ops.EXIT_STORAGE)
        details = context.exception.details
        self.assertIn("original_error", details)
        self.assertIn("Publish failed", details["original_error"])
        serialized = json.dumps(details, ensure_ascii=False)
        self.assertNotIn("sk-AAAAAAAAAAAAAAAAAAAAAAAA", serialized)
        self.assertNotIn("TOPSECRET", serialized)
        self.assertNotIn("server\\share", serialized)
        self.assertNotIn(str(source_vault), serialized)
        self.assertNotIn(str(target_vault), serialized)
        # Strict total-length bounds on every record inside the details JSON.
        self.assertLessEqual(len(details["original_error"]), sourcenotes_ops._ORIGINAL_ERROR_LIMIT)
        self.assertTrue(details["rollback_errors"])
        for entry in details["rollback_errors"]:
            self.assertLessEqual(len(entry), sourcenotes_ops._ROLLBACK_ERROR_LIMIT)

    def _assert_rollback_runtime_error_collected_and_actions_continue(self, exc_type, label):
        base = Path(self.temp.name) / f"rollback-{label}"
        (base / "a" / "b").mkdir(parents=True)
        (base / "a" / "b" / "f.md").write_text("x", encoding="utf-8")
        (base / "a2" / "b2").mkdir(parents=True)
        (base / "a2" / "b2" / "g.md").write_text("y", encoding="utf-8")
        (base / ".staging").mkdir()
        root_fd = self._open_root(base)
        real_open = sourcenotes_ops.open_rel_dir
        real_rmdir = sourcenotes_ops._rmdir_anchored
        rmdir_names: list[str] = []
        first = {"done": False}

        def flaky_open(root_fd_arg, rel, *, create=False):
            if rel == "a/b" and not first["done"]:
                first["done"] = True
                raise exc_type(f"simulated {label} during rollback open")
            return real_open(root_fd_arg, rel, create=create)

        def counting_rmdir(parent_fd, name):
            rmdir_names.append(name)
            return real_rmdir(parent_fd, name)

        try:
            with mock.patch.object(sourcenotes_ops, "open_rel_dir", side_effect=flaky_open), \
                 mock.patch.object(sourcenotes_ops, "_rmdir_anchored", side_effect=counting_rmdir):
                errors = sourcenotes_ops.rollback_transaction(
                    root_fd,
                    ["a/b/f.md", "a2/b2/g.md"],
                    ["a2/b2"],
                    ".staging",
                    staging_created=True,
                )
        finally:
            os.close(root_fd)
        self.assertEqual(len(errors), 1)
        self.assertIn(label, errors[0])
        self.assertIn(f"simulated {label} during rollback open", errors[0])
        # The later unlink and the created-dir rmdir still ran after the failure
        # was collected, and the staging tree was removed too.
        self.assertEqual(rmdir_names, ["b2", ".staging"])
        self.assertFalse((base / "a2" / "b2").exists())
        self.assertFalse((base / ".staging").exists())

    def test_rollback_runtime_error_collected_and_actions_continue(self):
        # F-02 round 2: a RuntimeError from one cleanup step must be aggregated
        # (never escape rollback_transaction) and the remaining actions must run.
        self._assert_rollback_runtime_error_collected_and_actions_continue(RuntimeError, "RuntimeError")

    def test_rollback_value_error_collected_and_actions_continue(self):
        # F-02 round 2: a ValueError from one cleanup step must likewise be
        # aggregated and must not stop the remaining cleanup actions.
        self._assert_rollback_runtime_error_collected_and_actions_continue(ValueError, "ValueError")

    def _assert_migrate_control_exception_reraises_after_rollback(self, exc, expected_code=None):
        source_vault = make_vault(Path(self.temp.name), f"Ctrl{type(exc).__name__}Src-test")
        target_vault = make_vault(Path(self.temp.name), f"Ctrl{type(exc).__name__}Dst-test")
        paths = self._seed_migratable_source(source_vault)
        manifest = self._manifest_file([self._migrate_entry("20260804-100000-aaaa", paths)])
        real_publish_link = sourcenotes_ops._publish_link
        real_rollback = sourcenotes_ops.rollback_transaction
        publish_calls = {"n": 0}
        rollback_calls = {"n": 0}

        def control_on_second_publish(root_fd, staging_rel, rel, parent_fd):
            publish_calls["n"] += 1
            if publish_calls["n"] == 2:
                raise exc
            return real_publish_link(root_fd, staging_rel, rel, parent_fd)

        def counting_rollback(*args, **kwargs):
            rollback_calls["n"] += 1
            return real_rollback(*args, **kwargs)

        with mock.patch.object(sourcenotes_ops, "_publish_link", side_effect=control_on_second_publish), \
             mock.patch.object(sourcenotes_ops, "rollback_transaction", side_effect=counting_rollback):
            with self.assertRaises(type(exc)) as context:
                sourcenotes_ops.cmd_migrate(str(manifest), str(source_vault), str(target_vault), apply=True)
        if expected_code is not None:
            self.assertEqual(context.exception.code, expected_code)
        self.assertEqual(rollback_calls["n"], 1)
        # The already-published source was rolled back; zero staging residue.
        for rel in (paths["source"], paths["annotation"], paths["attachment"]):
            self.assertFalse((target_vault / rel).exists(), rel)
        self.assertFalse(any(p.name.startswith(".sourcenotes-migrate-") for p in target_vault.iterdir()))

    def test_migrate_keyboard_interrupt_reraises_after_rollback(self):
        # F-03 round 2: KeyboardInterrupt during publish must run rollback and
        # then propagate unchanged — never wrapped in OpsError, never success.
        self._assert_migrate_control_exception_reraises_after_rollback(KeyboardInterrupt())

    def test_migrate_system_exit_reraises_after_rollback(self):
        # F-03 round 2: SystemExit must likewise run rollback then propagate
        # unchanged (same exit code), never converted to OpsError.
        self._assert_migrate_control_exception_reraises_after_rollback(SystemExit(3), expected_code=3)

    def test_migrate_staging_mkdir_failure_no_rollback_incomplete(self):
        # F-04 round 2: when staging directory creation itself fails before
        # anything was published or created, rollback must not fabricate a
        # remove-tree error for the never-created staging (no "rollback
        # incomplete" misreport, no rollback_errors detail).
        source_vault = make_vault(Path(self.temp.name), "StagingFailSrc-test")
        target_vault = make_vault(Path(self.temp.name), "StagingFailDst-test")
        paths = self._seed_migratable_source(source_vault)
        manifest = self._manifest_file([self._migrate_entry("20260804-100000-aaaa", paths)])
        real_mkdir = sourcenotes_ops.os.mkdir
        first = {"done": False}

        def failing_mkdir(path, mode=0o777, *, dir_fd=None):
            if not first["done"]:
                first["done"] = True
                raise OSError("simulated staging creation failure")
            return real_mkdir(path, mode, dir_fd=dir_fd)

        with mock.patch.object(sourcenotes_ops.os, "mkdir", side_effect=failing_mkdir):
            with self.assertRaises(sourcenotes_ops.OpsError) as context:
                sourcenotes_ops.cmd_migrate(str(manifest), str(source_vault), str(target_vault), apply=True)
        self.assertNotIn("rollback incomplete", str(context.exception))
        self.assertNotIn("rollback_errors", context.exception.details)
        self.assertEqual(context.exception.code, sourcenotes_ops.EXIT_STORAGE)
        for rel in (paths["source"], paths["annotation"], paths["attachment"]):
            self.assertFalse((target_vault / rel).exists(), rel)
        self.assertFalse(any(p.name.startswith(".sourcenotes-migrate-") for p in target_vault.iterdir()))

    def test_migrate_toctou_parent_symlink_fails_closed(self):
        # FIX-F02: replacing a target parent with a symlink to an external dir
        # between preflight and publish must fail; external gets zero writes and
        # the target has no partial migration or staging residue.
        source_vault = make_vault(Path(self.temp.name), "ToctouSrc-test")
        target_vault = make_vault(Path(self.temp.name), "ToctouDst-test")
        paths = self._seed_migratable_source(source_vault)
        manifest = self._manifest_file([self._migrate_entry("20260804-100000-aaaa", paths)])
        external = Path(self.temp.name) / "external-toctou"
        external.mkdir()
        sentinel = external / "sentinel.txt"
        sentinel.write_text("keep", encoding="utf-8")
        real_publish_link = sourcenotes_ops._publish_link
        swapped = {"done": False}

        def swap_then_publish(root_fd, staging_rel, rel, parent_fd):
            if not swapped["done"]:
                # Replace a parent dir needed by a later item with a symlink.
                shutil.rmtree(target_vault / "notes/annotations")
                os.symlink(external, target_vault / "notes/annotations")
                swapped["done"] = True
            return real_publish_link(root_fd, staging_rel, rel, parent_fd)

        with mock.patch.object(sourcenotes_ops, "_publish_link", side_effect=swap_then_publish):
            with self.assertRaises(sourcenotes_ops.OpsError):
                sourcenotes_ops.cmd_migrate(str(manifest), str(source_vault), str(target_vault), apply=True)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
        for rel in (paths["source"], paths["annotation"], paths["attachment"]):
            self.assertFalse((target_vault / rel).exists(), rel)
        self.assertFalse(any(p.name.startswith(".sourcenotes-migrate-") for p in target_vault.iterdir()))

    def test_migrate_concurrent_target_never_overwritten(self):
        # FIX-F02: if a same-name target is created between preflight and publish,
        # the no-clobber link must fail and never overwrite the concurrent file.
        source_vault = make_vault(Path(self.temp.name), "ConcurSrc-test")
        target_vault = make_vault(Path(self.temp.name), "ConcurDst-test")
        paths = self._seed_migratable_source(source_vault)
        manifest = self._manifest_file([self._migrate_entry("20260804-100000-aaaa", paths)])
        real_publish_link = sourcenotes_ops._publish_link
        created = {"done": False}

        def create_then_publish(root_fd, staging_rel, rel, parent_fd):
            if not created["done"]:
                (target_vault / paths["source"]).write_text("concurrent content", encoding="utf-8")
                created["done"] = True
            return real_publish_link(root_fd, staging_rel, rel, parent_fd)

        with mock.patch.object(sourcenotes_ops, "_publish_link", side_effect=create_then_publish):
            with self.assertRaises(sourcenotes_ops.OpsError) as context:
                sourcenotes_ops.cmd_migrate(str(manifest), str(source_vault), str(target_vault), apply=True)
        self.assertIn("concurrently", str(context.exception))
        self.assertEqual((target_vault / paths["source"]).read_text(encoding="utf-8"), "concurrent content")
        self.assertFalse((target_vault / paths["annotation"]).exists())
        self.assertFalse((target_vault / paths["attachment"]).exists())
        self.assertFalse(any(p.name.startswith(".sourcenotes-migrate-") for p in target_vault.iterdir()))

    # ---- FIX-F02: target symlink / path escape ----

    def _assert_migrate_rejected_with_sentinel(self, source_vault, target_vault, manifest, sentinel):
        result = self.run_ops(
            "migrate", "--manifest", str(manifest),
            "--source-vault", str(source_vault), "--target-vault", str(target_vault),
            "--apply",
            expected=3,
        )
        self.assertIn("symlink", result["error"])
        if sentinel and sentinel.is_file():
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
        self.assertFalse(any(p.name.startswith(".sourcenotes-migrate-") for p in target_vault.iterdir()))

    def _symlink_target_pair(self, name: str, vault_rel_dir: str) -> tuple[Path, Path, Path]:
        """Replace <vault_rel_dir> in a fresh target vault with a symlink to an
        external directory holding a sentinel.  Returns (source_vault, target_vault, sentinel)."""
        source_vault = make_vault(Path(self.temp.name), f"{name}Src-test")
        target_vault = make_vault(Path(self.temp.name), f"{name}Dst-test")
        external = Path(self.temp.name) / f"external-{name}"
        external.mkdir()
        sentinel = external / "sentinel.txt"
        sentinel.write_text("keep", encoding="utf-8")
        target_dir = target_vault / Path(vault_rel_dir)
        shutil.rmtree(target_dir)
        os.symlink(external, target_dir)
        return source_vault, target_vault, sentinel

    def test_migrate_rejects_source_symlink_escape(self):
        source_vault, target_vault, sentinel = self._symlink_target_pair("SymSrc", "sources/web")
        paths = self._seed_migratable_source(source_vault)
        manifest = self._manifest_file([self._migrate_entry("20260804-100000-aaaa", paths)])
        self._assert_migrate_rejected_with_sentinel(source_vault, target_vault, manifest, sentinel)

    def test_migrate_rejects_annotation_symlink_escape(self):
        source_vault, target_vault, sentinel = self._symlink_target_pair("SymAnn", "notes/annotations")
        paths = self._seed_migratable_source(source_vault)
        manifest = self._manifest_file([self._migrate_entry("20260804-100000-aaaa", paths)])
        self._assert_migrate_rejected_with_sentinel(source_vault, target_vault, manifest, sentinel)

    def test_migrate_rejects_attachment_symlink_escape(self):
        source_vault, target_vault, sentinel = self._symlink_target_pair("SymAst", "assets")
        paths = self._seed_migratable_source(source_vault)
        manifest = self._manifest_file([self._migrate_entry("20260804-100000-aaaa", paths)])
        self._assert_migrate_rejected_with_sentinel(source_vault, target_vault, manifest, sentinel)

    def test_migrate_rejects_final_target_symlink(self):
        # The final target path itself being a symlink is also rejected.
        source_vault = make_vault(Path(self.temp.name), "SymFinalSrc-test")
        target_vault = make_vault(Path(self.temp.name), "SymFinalDst-test")
        paths = self._seed_migratable_source(source_vault)
        manifest = self._manifest_file([self._migrate_entry("20260804-100000-aaaa", paths)])
        external = Path(self.temp.name) / "external-final"
        external.mkdir()
        (external / "sentinel.txt").write_text("keep", encoding="utf-8")
        (target_vault / paths["source"]).parent.mkdir(parents=True, exist_ok=True)
        os.symlink(external, target_vault / paths["source"])
        self._assert_migrate_rejected_with_sentinel(source_vault, target_vault, manifest, external / "sentinel.txt")

    # ---- FIX-F03: ledger must bind a Vault ----

    def test_ledger_requires_vault(self):
        external = Path(self.temp.name) / "ledger-no-vault"
        result = self.run_ops(
            "ledger", "--dir", str(external), "add",
            "--type", "operation", "--data", json.dumps({"note": "ok"}),
            expected=2,
        )
        self.assertIn("requires --vault", result["error"])
        self.assertFalse(external.exists())

    def test_ledger_rejects_blueprint_dir(self):
        vault = make_vault(Path(self.temp.name), "LedgerBp-test")
        forbidden = REPO / "tasks" / "forbidden-ledger"
        result = self.run_ops(
            "ledger", "--dir", str(forbidden), "add",
            "--vault", str(vault), "--type", "operation", "--data", json.dumps({"note": "ok"}),
            expected=2,
        )
        self.assertIn("blueprint", result["error"])
        self.assertFalse(forbidden.exists())

    # ---- incident ----

    def test_incident_external_full_context_and_permissions(self):
        vault = make_vault(Path(self.temp.name), "Incident-test")
        external = Path(self.temp.name) / "external"
        diagnostic = Path(self.temp.name) / "diagnostic.log"
        diagnostic.write_text(
            "请求 https://example.com/article?a=1 失败：HTTP 500 upstream timeout\n"
            "上下文：静态抓取超时后尝试渲染回退也失败。\n",
            encoding="utf-8",
        )
        result = self.run_ops(
            "incident",
            "--vault", str(vault),
            "--out-dir", str(external),
            "--metadata", json.dumps({"url": "https://example.com/article?a=1", "stage": "ingest"}),
            "--diagnostics", str(diagnostic),
        )
        self.assertTrue(result["ok"])
        bundle = Path(result["bundle_dir"])
        self.assertEqual(stat.S_IMODE(bundle.stat().st_mode), 0o700)
        manifest_file = bundle / "incident.json"
        self.assertEqual(stat.S_IMODE(manifest_file.stat().st_mode), 0o600)
        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        self.assertEqual(manifest_data["metadata"]["url"], "https://example.com/article?a=1")
        artifact = manifest_data["diagnostics"][0]["artifact"]
        self.assertTrue(re.fullmatch(r"diag-\d{4}\.log", artifact))
        copied = bundle / "diagnostics" / artifact
        self.assertTrue(copied.is_file())
        self.assertEqual(manifest_data["diagnostics"][0]["sha256"], file_sha256(copied))
        # The original absolute path and raw basename are never stored.
        self.assertNotIn(str(diagnostic), json.dumps(manifest_data))
        self.assertNotIn("diagnostic.log", json.dumps(manifest_data))

    def test_incident_secret_fails_closed_before_bundle(self):
        vault = make_vault(Path(self.temp.name), "Secret-test")
        external = Path(self.temp.name) / "external-secret"
        diagnostic = Path(self.temp.name) / "secret.log"
        diagnostic.write_text("Authorization: Bearer supersecretvalue\n", encoding="utf-8")
        result = self.run_ops(
            "incident",
            "--vault", str(vault),
            "--out-dir", str(external),
            "--metadata", json.dumps({"stage": "ingest"}),
            "--diagnostics", str(diagnostic),
            expected=2,
        )
        self.assertIn("secret-like content", result["error"])
        self.assertFalse(external.exists())

    def test_incident_secret_filenames_fail_closed_with_zero_bundle(self):
        # FIX-F07: secret-like filenames must fail closed before any bundle path
        # is created; the operator path text and basename are scanned too.
        vault = make_vault(Path(self.temp.name), "FnameSecret-test")
        external = Path(self.temp.name) / "external-fname"
        for bad_name in ("diag-token=abc.log", "diag-password-x.log", "diag-bearer-token.log", "notes-sk-AbcDefGhiJklMnoPqrStUvWx.log"):
            diagnostic = Path(self.temp.name) / bad_name
            diagnostic.write_text("plain context\n", encoding="utf-8")
            result = self.run_ops(
                "incident",
                "--vault", str(vault),
                "--out-dir", str(external),
                "--metadata", json.dumps({"stage": "ingest"}),
                "--diagnostics", str(diagnostic),
                expected=2,
            )
            self.assertIn("secret-like content", result["error"])
            self.assertFalse(external.exists())

    def test_incident_rejects_vault_and_blueprint_output_dirs(self):
        vault = make_vault(Path(self.temp.name), "Outdir-test")
        diagnostic = Path(self.temp.name) / "diag.log"
        diagnostic.write_text("plain context\n", encoding="utf-8")
        inside_vault = vault / "incident-bundle"
        result = self.run_ops(
            "incident",
            "--vault", str(vault),
            "--out-dir", str(inside_vault),
            "--metadata", json.dumps({"stage": "ingest"}),
            "--diagnostics", str(diagnostic),
            expected=2,
        )
        self.assertIn("outside the Vault", result["error"])
        self.assertFalse(inside_vault.exists())
        inside_blueprint = REPO / "tasks" / "forbidden-incident"
        result = self.run_ops(
            "incident",
            "--vault", str(vault),
            "--out-dir", str(inside_blueprint),
            "--metadata", json.dumps({"stage": "ingest"}),
            "--diagnostics", str(diagnostic),
            expected=2,
        )
        self.assertIn("blueprint", result["error"])
        self.assertFalse(inside_blueprint.exists())

    # ---- health ----

    def test_health_2GiB_gate_and_external_state_file(self):
        vault = make_vault(Path(self.temp.name), "Health-test")
        asset_dir = vault / "assets/images/20260804-100000-aaaa"
        asset_dir.mkdir(parents=True)
        big = asset_dir / "big.bin"
        with open(big, "wb") as handle:
            handle.truncate(2 * 1024 * 1024 * 1024 + 4096)  # sparse >2 GiB
        result = self.run_ops("health", "--vault", str(vault))
        self.assertTrue(result["ok"])
        self.assertTrue(result["gate_2GiB"])
        self.assertGreaterEqual(result["report"]["attachments"]["total_bytes"], 2 * 1024 * 1024 * 1024)

        external = Path(self.temp.name) / "health-state"
        state_dir = external / "nested"
        state_file = state_dir / "health.json"
        result = self.run_ops("health", "--vault", str(vault), "--state-file", str(state_file))
        self.assertTrue(result["ok"])
        self.assertEqual(stat.S_IMODE(state_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(state_dir.stat().st_mode), 0o700)
        state = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertTrue(state["attachment_gate_2GiB"])

        inside_vault = vault / "health.json"
        result = self.run_ops("health", "--vault", str(vault), "--state-file", str(inside_vault), expected=2)
        self.assertIn("outside the Vault", result["error"])
        self.assertFalse(inside_vault.exists())

    # ---- ledger ----

    def test_ledger_external_append_and_permissions(self):
        vault = make_vault(Path(self.temp.name), "Ledger-test")
        external = Path(self.temp.name) / "ledger-dir"
        first = self.run_ops(
            "ledger", "--dir", str(external), "add",
            "--vault", str(vault), "--type", "operation",
            "--data", json.dumps({"blueprint_commit": "abc123", "source_id": "20260804-100000-aaaa"}),
        )
        self.assertTrue(first["ok"])
        second = self.run_ops(
            "ledger", "--dir", str(external), "add",
            "--vault", str(vault), "--type", "release",
            "--data", json.dumps({"blueprint_commit": "def456", "vault_head": "012345"}),
        )
        self.assertTrue(second["ok"])
        ledger_path = external / "operations.jsonl"
        self.assertEqual(stat.S_IMODE(ledger_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(external.stat().st_mode), 0o700)
        lines = ledger_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        listed = self.run_ops("ledger", "--dir", str(external), "list", "--vault", str(vault))
        self.assertEqual(listed["count"], 2)
        self.assertEqual(listed["records"][0]["data"]["source_id"], "20260804-100000-aaaa")

    def test_ledger_rejects_secrets_and_vault_dir(self):
        vault = make_vault(Path(self.temp.name), "LedgerSecret-test")
        external = Path(self.temp.name) / "ledger-secret"
        result = self.run_ops(
            "ledger", "--dir", str(external), "add",
            "--vault", str(vault), "--type", "operation",
            "--data", json.dumps({"note": "password=hunter2"}),
            expected=2,
        )
        self.assertIn("secret-like content", result["error"])
        self.assertFalse(external.exists())
        result = self.run_ops(
            "ledger", "--dir", str(vault), "add",
            "--vault", str(vault), "--type", "operation",
            "--data", json.dumps({"note": "ok"}),
            expected=2,
        )
        self.assertIn("outside the Vault", result["error"])


if __name__ == "__main__":
    unittest.main()
