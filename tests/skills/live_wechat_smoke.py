#!/usr/bin/env python3
"""Disposable live-WeChat smoke tool for vault-capture ingest-web (VAL-06).

Runs the supplied WeChat URL through the repository-owned extractor and the
atomic finalize transaction inside a disposable temporary vault. It never writes
to the real SourceNotes vault, and never prints cookies, profile paths, or raw
HTML.

Exit codes:
  0  -- complete `ready` capture that contains all expected excerpts, OR a
        structured `manual` verification state produced after the browser
        fallback was attempted.
  1  -- unexpected outcome (e.g. a `failed` retryable state, or a `ready`
        capture missing expected excerpts).
  2  -- usage or environment error.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "vault-capture" / "scripts" / "vault_capture.py"

EXPECTED_EXCERPTS = [
    "上半年瑞幸净增5262家门店",
    "在现制茶饮咖啡领域，成为“便利店”一样的存在",
    "对冲过度依赖外卖渠道的风险",
]


def run_cli(vault: Path, command: str, *args: str, payload: dict | None = None) -> dict:
    env = os.environ.copy()
    process = subprocess.run(
        [sys.executable, str(SCRIPT), "--vault", str(vault), command, *args],
        input=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        env=env,
    )
    if process.returncode != 0:
        raise RuntimeError(f"command {command} failed rc={process.returncode}: {process.stderr.strip()}")
    return json.loads(process.stdout)


def init_vault(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for folder in ["sources/web", "sources/transcripts", "sources/documents", "notes/annotations", "notes/ideas"]:
        target = root / folder
        target.mkdir(parents=True, exist_ok=True)
        (target / ".gitkeep").write_text("", encoding="utf-8")
    (root / ".gitignore").write_text(".queue/\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Vault Smoke"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "smoke@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "core.quotepath", "false"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "init"], check=True)
    return root


def _print_diagnostics(status: str, result: dict, vault: Path) -> None:
    """Print safe structured diagnostics for every outcome."""
    reason = result.get("error", "")
    body_length = 0
    image_count = len(result.get("asset_paths", []))
    source_path = result.get("source_path")
    if source_path:
        try:
            body_length = len((Path(vault) / source_path).read_text(encoding="utf-8"))
        except Exception:
            pass
    print(f"state={status}")
    print(f"reason={reason}")
    print(f"body_length={body_length}")
    print(f"image_count={image_count}")
    methods = result.get("methods_attempted") or []
    print(f"methods_attempted={','.join(methods) if methods else '(none)'}")
    for excerpt in EXPECTED_EXCERPTS:
        if source_path:
            try:
                text = (Path(vault) / source_path).read_text(encoding="utf-8")
                print(f"excerpt_present={excerpt in text}")
            except Exception:
                print(f"excerpt_present=False")
        else:
            print(f"excerpt_present=False")


def main() -> int:
    parser = argparse.ArgumentParser(description="Live WeChat smoke test for ingest-web")
    parser.add_argument("--url", required=True, help="WeChat mp.weixin.qq.com article URL")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="vault-capture-smoke-") as tmp:
        vault = init_vault(Path(tmp) / "vault")
        staged = run_cli(
            vault,
            "stage",
            payload={
                "kind": "web",
                "url": args.url,
                "captured_at": "2026-08-07T09:00:00+08:00",
                "annotations": [],
            },
        )
        if not staged.get("job_created"):
            print("job_created=false; aborting smoke")
            return 2
        source_id = staged["id"]
        result = run_cli(vault, "ingest-web", source_id)
        status = result.get("ingest_status")
        print(f"method=ingest-web id={source_id}")

        if status == "ready":
            source_path = Path(vault) / result["source_path"]
            text = source_path.read_text(encoding="utf-8")
            _print_diagnostics(status, result, vault)
            methods = result.get("methods_attempted") or []
            if not methods:
                print("methods_attempted missing; cannot prove extraction ran")
                return 1
            missing = [excerpt for excerpt in EXPECTED_EXCERPTS if excerpt not in text]
            if missing:
                print(f"missing_excerpts={missing}")
                return 1
            if len(result.get("asset_paths", [])) < 1:
                print("image_count=0 but expected body images")
                return 1
            print("outcome=ready_ok")
            return 0

        if status == "manual":
            _print_diagnostics(status, result, vault)
            # A structured manual state is accepted only when WeChat external
            # state requires verification AND browser fallback was actually
            # attempted. methods_attempted must include a browser marker
            # ("browser", "wechat-browser", or "browser-trafilatura") proving
            # static extraction was rejected and Playwright ran before manual.
            methods = result.get("methods_attempted") or []
            browser_methods = {"browser", "wechat-browser", "browser-trafilatura"}
            if not any(m in browser_methods for m in methods):
                print(
                    f"fallback_attempted=False; methods_attempted={methods}; "
                    "browser fallback was not attempted before manual state"
                )
                return 1
            print("fallback_attempted=True")
            print("outcome=manual_ok")
            return 0

        # Unexpected: failed or unknown state
        _print_diagnostics(status, result, vault)
        print("fallback_attempted=unknown")
        print(f"outcome=unexpected")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())