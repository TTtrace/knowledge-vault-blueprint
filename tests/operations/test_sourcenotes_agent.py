from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parents[2]
AGENT = REPO / "scripts" / "sourcenotes_agent.py"
CAPTURE_SCRIPT = REPO / "skills/vault-capture/scripts/vault_capture.py"

import importlib.util  # noqa: E402

SPEC = importlib.util.spec_from_file_location("vault_capture", CAPTURE_SCRIPT)
assert SPEC and SPEC.loader
vault_capture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vault_capture)

AGENT_SPEC = importlib.util.spec_from_file_location("sourcenotes_agent", AGENT)
assert AGENT_SPEC and AGENT_SPEC.loader
sourcenotes_agent = importlib.util.module_from_spec(AGENT_SPEC)
AGENT_SPEC.loader.exec_module(sourcenotes_agent)

import network_security  # noqa: E402


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


def make_vault(base: Path, name: str = "vault") -> Path:
    vault = Path(base) / name
    vault.mkdir()
    for folder in [
        "sources/web",
        "sources/transcripts",
        "sources/documents",
        "notes/annotations",
        "notes/analyses",
        "notes/ideas",
        "assets/images",
    ]:
        (vault / folder).mkdir(parents=True)
    (vault / ".gitignore").write_text(".queue/\n", encoding="utf-8")
    git(vault, "init", "-q", "-b", "main")
    git(vault, "config", "user.name", "Vault Test")
    git(vault, "config", "user.email", "vault-test@example.invalid")
    git(vault, "config", "core.quotepath", "false")
    git(vault, "add", ".")
    git(vault, "commit", "-q", "-m", "init")
    return vault


def note(vault: Path, folder: str, note_id: str, title: str, body: str, **extra) -> Path:
    fields: dict[str, object] = {"schema_version": 1, "id": note_id, "type": "idea", "title": title}
    fields.update(extra)
    lines = [f"schema_version: 1", f"id: {note_id}", f"type: {fields['type']}", f"title: {title}"]
    for key, value in extra.items():
        if key in {"schema_version", "id", "type", "title"}:
            continue
        lines.append(f"{key}: {value}")
    path = vault / folder / f"{note_id}.md"
    path.write_text("---\n" + "\n".join(lines) + "\n---\n\n" + body, encoding="utf-8")
    return path


class SourcenotesAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.vault = make_vault(Path(self.temp.name))
        self.initial_head = git(self.vault, "rev-parse", "HEAD").stdout.strip()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_agent(self, *args: str, stdin: str | None = None, expected: int = 0) -> dict:
        env = os.environ.copy()
        env["VAULT_ROOT"] = str(self.vault)
        process = subprocess.run(
            [sys.executable, str(AGENT), *args],
            input=stdin,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            env=env,
        )
        self.assertEqual(process.returncode, expected, process.stderr + process.stdout)
        return json.loads(process.stdout)

    def snapshot(self) -> tuple[str, str, str]:
        cached = git(self.vault, "diff", "--cached", "--name-only").stdout
        porcelain = git(self.vault, "status", "--porcelain", "--untracked-files=all").stdout
        hashes = {
            rel: file_sha256(self.vault / rel)
            for rel in sorted((p.relative_to(self.vault).as_posix() for p in self.vault.rglob("*.md")))
        }
        return cached, porcelain, json.dumps(hashes, sort_keys=True)

    # ---- controlled entrypoint / capture family ----

    def test_preflight_and_unknown_commands(self):
        result = self.run_agent("capture", "preflight")
        self.assertTrue(result["ok"])
        self.assertTrue(result["layout"])
        for args in (
            ("frobnicate",),
            ("capture", "nope"),
            ("query", "nope"),
            ("maintenance", "nope"),
            ("capture", "ingest", "not/a-valid-id!"),
        ):
            result = self.run_agent(*args, expected=2)
            self.assertFalse(result["ok"])

    def test_capture_stage_inspect_list_retryable_via_entrypoint(self):
        staged = self.run_agent(
            "capture",
            "stage",
            stdin=json.dumps(
                {
                    "kind": "web",
                    "url": "https://example.com/article?utm_source=x",
                    "captured_at": "2026-08-04T09:30:00+08:00",
                    "annotations": [{"quote": "引文", "comment": "评论"}],
                }
            ),
        )
        self.assertTrue(staged["ok"])
        self.assertTrue(staged["staged"])
        self.assertTrue(staged["job_created"])
        self.assertTrue((self.vault / staged["source_path"]).is_file())
        inspected = self.run_agent("capture", "inspect", staged["id"])
        self.assertEqual(inspected["source_path"], staged["source_path"])
        self.assertEqual(inspected["ingest_status"], "pending")
        retryable = self.run_agent("capture", "list-retryable")
        self.assertEqual(retryable["count"], 0)
        self.assertEqual(git(self.vault, "rev-parse", "HEAD").stdout.strip(), self.initial_head)

    def test_capture_ingest_delegates_to_vault_capture_contract(self):
        # Inline ingest contract: the entrypoint routes to the existing
        # vault_capture.cmd_ingest_web without re-implementing write logic.
        staged = self.run_agent(
            "capture",
            "stage",
            stdin=json.dumps(
                {"kind": "web", "url": "https://ingest.example/a", "captured_at": "2026-08-07T09:00:00+08:00"}
            ),
        )
        with mock.patch.object(
            sourcenotes_agent.vault_capture,
            "cmd_ingest_web",
            return_value={"ok": True, "id": staged["id"], "ingest_status": "ready", "paths_final": True},
        ) as mocked:
            result = sourcenotes_agent.cmd_capture_ingest(self.vault, staged["id"])
        mocked.assert_called_once_with(self.vault, staged["id"])
        self.assertEqual(result["ingest_status"], "ready")
        self.assertTrue(result["paths_final"])
        with self.assertRaises(sourcenotes_agent.OpsError):
            sourcenotes_agent.cmd_capture_ingest(self.vault, "bad/id!")

    # ---- query family ----

    def test_query_search_returns_bounded_results_with_ids(self):
        for index in range(25):
            note(
                self.vault,
                "notes/ideas",
                f"20260804-1000{index:02d}-abc{index:02d}",
                f"检索目标第 {index} 条",
                f"内容包含检索目标标记，编号 {index}。",
            )
        result = self.run_agent("query", "search", "检索目标")
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 20)  # MAX_RESULTS
        for item in result["results"]:
            self.assertTrue(item["id"])
            self.assertTrue(item["path"].endswith(".md"))
            self.assertIn("检索目标", item["excerpt"])
            self.assertTrue(item["path"].startswith("notes/"))

    def test_query_search_requires_query_and_bounds(self):
        too_long = "x" * 501
        result = self.run_agent("query", "search", too_long, expected=2)
        self.assertIn("Query is too long", result["error"])
        result = self.run_agent("query", "search", "   ", expected=2)
        self.assertIn("non-empty query", result["error"])

    def test_query_show_and_related_are_read_only(self):
        source = note(
            self.vault,
            "sources/web",
            "20260804-100000-aaaa",
            "来源文章",
            "# 来源文章\n\n正文段落。",
            type="source",
            ingest_status="ready",
            canonical_url="https://example.com/a",
        )
        note(
            self.vault,
            "notes/ideas",
            "20260804-110000-bbbb",
            "关联想法",
            "引用 [[20260804-100000-aaaa]] 的想法正文。",
            derived_from=[],
        )

        before = self.snapshot()
        shown = self.run_agent("query", "show", "sources/web/20260804-100000-aaaa.md")
        self.assertEqual(shown["id"], "20260804-100000-aaaa")
        self.assertEqual(shown["path"], "sources/web/20260804-100000-aaaa.md")
        self.assertIn("正文段落", shown["excerpt"])
        related = self.run_agent("query", "related", "20260804-100000-aaaa")
        self.assertEqual(related["count"], 1)
        self.assertEqual(related["results"][0]["id"], "20260804-110000-bbbb")
        self.assertIn("20260804-100000-aaaa", related["results"][0]["excerpt"])
        after = self.snapshot()
        self.assertEqual(before, after)
        self.assertEqual(git(self.vault, "rev-parse", "HEAD").stdout.strip(), self.initial_head)

    def test_query_rejects_path_escape_and_non_markdown(self):
        note(self.vault, "notes/ideas", "20260804-100000-aaaa", "标题", "正文")
        outside = Path(self.temp.name) / "outside.md"
        outside.write_text("outside", encoding="utf-8")
        os.symlink(outside, self.vault / "notes/ideas/escape.md")
        for bad in (
            "../notes/ideas/20260804-100000-aaaa.md",
            "/etc/passwd",
            "notes/ideas/missing.md",
            "notes/ideas",
            "notes/ideas/escape.md",
        ):
            result = self.run_agent("query", "show", bad, expected=2)
            self.assertFalse(result["ok"])
            self.assertNotIn("/home", result["error"])
            self.assertNotIn(str(self.temp), result["error"])

    def test_query_show_rejects_non_markdown_file(self):
        target = self.vault / "notes/ideas/plain.txt"
        target.write_text("not markdown", encoding="utf-8")
        result = self.run_agent("query", "show", "notes/ideas/plain.txt", expected=2)
        self.assertIn("Markdown", result["error"])

    def test_query_does_not_modify_index_or_worktree(self):
        note(self.vault, "notes/ideas", "20260804-100000-aaaa", "只读标题", "只读正文")
        before = self.snapshot()
        self.run_agent("query", "search", "只读")
        self.run_agent("query", "show", "notes/ideas/20260804-100000-aaaa.md")
        self.run_agent("query", "related", "20260804-100000-aaaa")
        after = self.snapshot()
        self.assertEqual(before, after)
        self.assertEqual(git(self.vault, "rev-parse", "HEAD").stdout.strip(), self.initial_head)

    # ---- maintenance family ----

    def test_maintenance_report_metrics(self):
        note(
            self.vault,
            "sources/web",
            "20260804-100000-aaaa",
            "失败来源",
            "# 失败\n\n正文。",
            type="source",
            ingest_status="failed",
        )
        note(
            self.vault,
            "sources/web",
            "20260804-100001-bbbb",
            "手动来源",
            "# 手动\n\n正文。",
            type="source",
            ingest_status="manual",
        )
        note(
            self.vault,
            "notes/annotations",
            "20260804-100002-cccc",
            "悬空批注",
            "批注正文。",
            type="annotation",
            source_id="20260804-999999-zzzz",
        )
        asset_dir = self.vault / "assets/images/20260804-100000-aaaa"
        asset_dir.mkdir(parents=True)
        (asset_dir / "small.png").write_bytes(b"small")
        large = asset_dir / "large.bin"
        with open(large, "wb") as handle:
            handle.truncate(6 * 1024 * 1024)  # >5 MiB sparse
        result = self.run_agent("maintenance", "report")
        report = result["report"]
        self.assertTrue(result["ok"])
        self.assertEqual(report["git"]["branch"], "main")
        self.assertEqual(report["git"]["head"], git(self.vault, "rev-parse", "HEAD").stdout.strip())
        self.assertEqual(report["git"]["staged_count"], 0)
        self.assertEqual(report["sources"]["failed_count"], 1)
        self.assertEqual(report["sources"]["manual_count"], 1)
        self.assertEqual(report["sources"]["failed_paths"][0]["id"], "20260804-100000-aaaa")
        self.assertEqual(report["missing_source_references"][0]["missing_id"], "20260804-999999-zzzz")
        attachments = report["attachments"]
        self.assertEqual(attachments["count"], 2)
        self.assertEqual(attachments["over_5MiB_count"], 1)
        self.assertFalse(attachments["gate_2GiB"])
        self.assertEqual(git(self.vault, "rev-parse", "HEAD").stdout.strip(), self.initial_head)

    def test_maintenance_requires_vault_root(self):
        env = os.environ.copy()
        env.pop("VAULT_ROOT", None)
        process = subprocess.run(
            [sys.executable, str(AGENT), "maintenance", "report"],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            env=env,
        )
        self.assertEqual(process.returncode, 2)
        self.assertIn("VAULT_ROOT is not configured", json.loads(process.stdout)["error"])

    # ---- FIX-F04: query symlink fail-closed ----

    def test_query_fails_closed_on_symlinked_note_file(self):
        external = Path(self.temp.name) / "external-secret-notes"
        external.mkdir()
        secret_note = external / "secret.md"
        secret_note.write_text("外部机密内容SECRETXYZ", encoding="utf-8")
        os.symlink(secret_note, self.vault / "notes/ideas/link-secret.md")
        for args in (
            ("query", "search", "外部机密"),
            ("query", "related", "20260804-100000-aaaa"),
            ("query", "show", "notes/ideas/link-secret.md"),
        ):
            result = self.run_agent(*args, expected=2)
            self.assertIn("symlink", result["error"])
            self.assertNotIn("SECRETXYZ", json.dumps(result))

    def test_query_fails_closed_on_symlinked_directory(self):
        # FIX-F04: a symlinked directory inside the queryable note tree must
        # fail closed with a stable nonzero error instead of silently skipping.
        external = Path(self.temp.name) / "external-secret-dir"
        external.mkdir()
        (external / "leak.md").write_text("外部目录机密内容LEAKXYZ", encoding="utf-8")
        os.symlink(external, self.vault / "notes/ideas/external-dir")
        for args in (
            ("query", "search", "外部目录机密"),
            ("query", "related", "20260804-100000-aaaa"),
        ):
            result = self.run_agent(*args, expected=2)
            self.assertIn("symlink", result["error"])
            self.assertNotIn("LEAKXYZ", json.dumps(result))

    def test_query_ignores_symlinks_inside_excluded_dirs(self):
        # FIX-F04: symlinks inside fully-excluded system dirs never enter the
        # query scope and must not fail the command.
        external = Path(self.temp.name) / "external-ignored"
        external.mkdir()
        (external / "x.md").write_text("被忽略内容IGNORED", encoding="utf-8")
        (self.vault / ".obsidian").mkdir()
        os.symlink(external, self.vault / ".obsidian" / "plugins")
        os.symlink(external, self.vault / "assets" / "images-link")
        note(self.vault, "notes/ideas", "20260804-100000-aaaa", "正常标题", "正常正文内容")
        result = self.run_agent("query", "search", "正常正文")
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertNotIn("IGNORED", json.dumps(result))

    # ---- FIX-F05: global output caps ----

    def test_query_caps_oversized_frontmatter_fields(self):
        giant_id = "20260804-100000-" + "x" * 5000
        giant_title = "超长标题" + "长" * 5000
        path = self.vault / "notes/ideas" / "20260804-100000-aaaa.md"
        path.write_text(
            "---\nschema_version: 1\n"
            f"id: {giant_id}\ntype: idea\n"
            f"title: \"{giant_title}\"\n"
            "---\n\n# 标题\n\n包含检索词的内容。\n",
            encoding="utf-8",
        )
        result = self.run_agent("query", "search", "检索词")
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        item = result["results"][0]
        self.assertLessEqual(len(item["id"]), 129)  # 128 + ellipsis
        self.assertLessEqual(len(item["title"]), 301)  # 300 + ellipsis
        self.assertLess(len(json.dumps(result).encode("utf-8")), 256 * 1024)
        shown = self.run_agent("query", "show", "notes/ideas/20260804-100000-aaaa.md")
        self.assertLessEqual(len(shown["id"]), 129)
        self.assertLess(len(json.dumps(shown).encode("utf-8")), 256 * 1024)

    def test_query_related_bounded(self):
        note(self.vault, "notes/ideas", "20260804-100000-aaaa", "目标", "目标正文")
        for index in range(25):
            note(
                self.vault,
                "notes/ideas",
                f"20260804-1000{index:02d}-b{index:02d}",
                f"关联{index}",
                f"链接 [[20260804-100000-aaaa]] 的内容{index}",
            )
        result = self.run_agent("query", "related", "20260804-100000-aaaa")
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 20)  # MAX_RESULTS
        self.assertLess(len(json.dumps(result).encode("utf-8")), 256 * 1024)

    def test_emit_global_output_cap_returns_short_safe_error(self):
        # FIX-F05: every envelope (success or error) obeys the byte cap at emit;
        # stdout is always a single valid JSON object <= 256 KiB.
        import contextlib
        import io

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = sourcenotes_agent.emit({"big": "x" * (300 * 1024)})
        text = buffer.getvalue()
        parsed = json.loads(text)
        self.assertNotEqual(code, 0)
        self.assertFalse(parsed["ok"])
        self.assertEqual(parsed["error"], "Output limit exceeded")
        self.assertLess(len(text.encode("utf-8")), 256 * 1024)

    # ---- FIX-F06: per-Source 30 MiB aggregation ----

    def test_maintenance_per_source_30MiB_and_unassigned(self):
        for source_id in ("20260804-100000-aaaa", "20260804-100001-bbbb"):
            asset_dir = self.vault / "assets/images" / source_id
            asset_dir.mkdir(parents=True)
            with open(asset_dir / "file.bin", "wb") as handle:
                handle.truncate(20 * 1024 * 1024)  # two Sources x 20 MiB
        result = self.run_agent("maintenance", "report")
        attachments = result["report"]["attachments"]
        self.assertEqual(attachments["sources_over_30MiB_count"], 0)  # no single Source >30 MiB
        self.assertFalse(attachments["gate_2GiB"])

        single = self.vault / "assets/images/20260804-100002-cccc"
        single.mkdir(parents=True)
        with open(single / "big.bin", "wb") as handle:
            handle.truncate(31 * 1024 * 1024)  # one Source >30 MiB
        result = self.run_agent("maintenance", "report")
        attachments = result["report"]["attachments"]
        self.assertEqual(attachments["sources_over_30MiB_count"], 1)
        self.assertEqual(
            attachments["sources_over_30MiB_paths"][0]["source_dir"],
            "assets/images/20260804-100002-cccc",
        )

        # A root-scattered file is unassigned and never mixed into a Source.
        (self.vault / "assets" / "root.bin").write_bytes(b"x")
        result = self.run_agent("maintenance", "report")
        attachments = result["report"]["attachments"]
        self.assertEqual(attachments["unassigned_count"], 1)
        self.assertEqual(attachments["unassigned_paths"][0]["path"], "assets/root.bin")
        self.assertNotIn("root.bin", json.dumps(attachments["sources_over_30MiB_paths"]))


if __name__ == "__main__":
    unittest.main()
