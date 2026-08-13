---
task_id: 2026-08-10-vault-capture-wechat-profile-diagnostics
title: Roll back persistent WeChat profile and retain manual verification boundary
status: approved
spec_version: 3
planner: primary
executor: executor
created: 2026-08-10
approved_at: 2026-08-13T01:26:58+08:00
approved_by: user
---

# Task Specification

> This file is owned by the planner. Version 1 was approved for persistent-profile diagnostics, but live validation reached WeChat rate limiting. Version 2 was approved for rollback, then execution discovered that its `f9810f1` test-file baseline already contained seven version-1 tests without their implementation. Version 3 resolves that acceptance conflict and requires fresh approval.

## 1. Context and problem

Version 1 added uncommitted diagnostics code/tests/docs, an OpenClaw `VAULT_CAPTURE_BROWSER_PROFILE` entry, a dedicated profile directory, and a temporary graphical helper. Human validation reached WeChat's “操作过于频繁，请稍后重试” response. The user no longer wants a technical attempt to pass verification and requests rollback. Existing pre-task behavior already maps WeChat verification/rate-limit pages to `ingest_status: manual` and does not finalize partial content.

The repository HEAD is now `f9810f1` because the previously accepted 198.18/16 SSRF task was committed externally during execution. That commit remains authoritative for implementation, documentation, network policy, and all non-v1 tests. However, inspection during version-2 rollback proved that the commit accidentally captured seven version-1 test methods while omitting their corresponding `attempt_diagnostics` implementation. Those orphan tests make the committed suite fail and are not a valid rollback target.

Version-2 execution already removed the version-1 implementation/documentation/config/profile changes and stopped before changing the conflicting test files. The remaining work is to remove exactly those seven orphan version-1 test methods, preserve all pre-v1 and 198.18/16 tests, and finish the deferred read-only Source/scope validation.

## 2. Required outcome

Remove all implementation, test, documentation, and host-runtime changes introduced by version 1, while preserving this task package as an audit record. Restore active behavior to the `f9810f1` implementation, with one explicit correction to its polluted test baseline: remove the seven orphan version-1 test methods from `tests/skills/test_web_extract.py` and `tests/skills/test_vault_capture.py`. When static/Playwright access encounters WeChat verification, captcha, login requirement, or rate limiting, ingestion ends safely as `manual`; no profile-based attempt to bypass that boundary is configured.

Keep Source ID `20260809-214018-ooaa` as an existing staged test-vault `manual` record. Do not automatically retry it during rollback. A later retry must be an explicit operator action against that existing Source ID (for example `ingest-web 20260809-214018-ooaa`), or the user may manually collect the article content outside this automation.

## 3. Non-goals

- No new WeChat extraction behavior, retry command, scheduler, provider, or third-party service.
- No changes to canonical URL/deduplication, network policy, schema, Source body, or production Vault.
- No automatic retry of the target URL and no attempt to solve/pass verification.
- No deletion or unstaging of the existing test-vault Source record.
- No commit, push, merge, tag, release, deployment, or unrelated cleanup.

## 4. Locked decisions

- `manual` is the final automation boundary for verification/captcha/login/rate-limit responses; partial or challenge content never reaches `ready`.
- Automated retry does not occur. Explicit future operator retry uses the existing Source ID; no duplicate Source is intentionally created.
- Remove the dedicated persistent-profile configuration and runtime artifacts created by version 1.
- Roll back version-1 `attempt_diagnostics` implementation/tests/docs entirely; retain the pre-existing `methods_attempted` behavior and final safe `manual` reason.
- Preserve the externally committed `f9810f1` 198.18/16 implementation and its tests. The only intentional divergence from tracked `f9810f1` is deletion of the seven identified orphan version-1 tests from the two allowed test files, plus this task package and unrelated pre-existing work.
- Preserve `SPEC.md`, update executor-owned `EXECUTION.md` with rollback evidence, and have reviewer create `REVIEW.md`; the task package itself remains as history.

## 5. Baselines

- Blueprint: `/home/monottx/repos/knowledge-vault-blueprint`, branch `main`, HEAD `f9810f1`.
- Version-2 has already rolled back the version-1 implementation/docs/config/profile artifacts. Its executor return and `EXECUTION.md` are the immediate pre-v3 baseline.
- Polluted test baseline: `f9810f1` contains four version-1 methods in `tests/skills/test_web_extract.py` (ordered diagnostics, unknown sentinel, no-profile context, persistent-profile context) and three in `tests/skills/test_vault_capture.py` (queue/inspect diagnostics, profile-path sentinel, unknown-secret sentinel). All seven must be removed; all other tests remain.
- SourceNotes-test: `/home/monottx/repos/SourceNotes-test`, branch `main`, HEAD `ec1a90e`; `sources/web/20260809-214018-ooaa.md` remains staged `A` and its queue job remains `manual`.
- Active OpenClaw config contains the version-1 profile entry; pre-version-1 config hash was `bfa7de62dce7a15a836e47dd14ebeb3af6b7eab94bd86aea421f7d1e14215a28` before unrelated later changes. Rollback must remove the exact entry structurally, not overwrite the whole file.
- Version-1 external artifacts: `/home/monottx/.local/share/vault-capture/wechat-browser-profile/` and `/tmp/opencode/vault-capture-wechat-init.py`.

## 6. Allowed and forbidden paths

### Blueprint allowed rollback paths

```text
DECISIONS.md
specifications/capture-workflow.md
specifications/openclaw-skill-workflow.md
skills/vault-capture/SKILL.md
skills/vault-capture/references/runtime-contract.md
skills/vault-capture/references/web-runtime.md
skills/vault-capture/scripts/web_extract.py
skills/vault-capture/scripts/vault_capture.py
tests/skills/test_web_extract.py
tests/skills/test_vault_capture.py
tasks/2026-08-10-vault-capture-wechat-profile-diagnostics/EXECUTION.md
tasks/2026-08-10-vault-capture-wechat-profile-diagnostics/REVIEW.md (reviewer only)
```

Only version-1 additions may be removed. For the two test files, deletion is limited to the seven methods identified in §5; surrounding imports/helpers/assertions may be removed only if proven introduced solely for those methods and unused afterward. `SPEC.md` is planner-owned and forbidden to executor.

### Host/runtime allowed rollback paths

```text
/home/monottx/.openclaw/openclaw.json
/home/monottx/.local/share/vault-capture/wechat-browser-profile/**
/tmp/opencode/vault-capture-wechat-init.py
```

In OpenClaw config, only remove `skills.entries.vault-capture.env.VAULT_CAPTURE_BROWSER_PROFILE`; preserve every other setting. Delete the dedicated profile directory without inspecting or printing its contents, and delete the temporary helper.

### Explicitly forbidden

```text
/home/monottx/repos/SourceNotes/**
/home/monottx/repos/SourceNotes-test/** (read-only status/inspect only)
skills/vault-capture/scripts/network_security.py
tests/skills/test_network_security.py
tests/opencode-harness/**
tasks/2026-08-09-vault-capture-198-18-ssrf-exemption/**
default browser profiles
OpenClaw credentials/auth/session files
all unrelated paths
```

## 7. Acceptance criteria

- **AC-01:** All version-1 implementation/test/documentation additions are removed. Allowed implementation/docs match HEAD `f9810f1`; the two allowed test files differ only by deletion of the seven identified orphan version-1 methods and any now-unused v1-only test scaffolding.
- **AC-02:** Active OpenClaw config is valid JSON, lacks `VAULT_CAPTURE_BROWSER_PROFILE`, and all other settings are preserved.
- **AC-03:** The dedicated profile directory and temporary helper no longer exist; contents are never inspected or printed.
- **AC-04:** Existing tests pass and confirm WeChat verification/rate-limit maps to `manual`, with no partial `ready`.
- **AC-05:** Source ID `20260809-214018-ooaa` remains staged and `manual`; rollback triggers no network request and makes no test-vault content change.
- **AC-06:** The committed 198.18/16 task, production Vault, default browser profiles, credentials, Git index, and unrelated files remain unchanged.
- **AC-07:** No stage/commit/push/reset/clean/broad restore is performed; `git diff --check` passes.

## 8. Validation plan

- `VAL-01` from blueprint: verify allowed implementation/docs have no diff from `f9810f1`; verify the two test-file diffs contain only deletion of the seven identified orphan methods and now-unused v1-only scaffolding; task package and unrelated pre-existing differences are expected.
- `VAL-02`: run the dedicated runtime Python against `tests/skills/test_web_extract.py`; exit 0, verification/rate-limit tests assert `manual`.
- `VAL-03`: run `tests/skills/test_vault_capture.py`; exit 0.
- `VAL-04`: run `tests/skills/test_network_security.py`; exit 0 and accepted 198.18 behavior preserved.
- `VAL-05`: run `python3 -m compileall -q skills/vault-capture/scripts tests/skills`; exit 0.
- `VAL-06`: run `git diff --check`; exit 0.
- `VAL-07`: structurally parse OpenClaw config and prove only the profile entry was removed relative to the immediate pre-rollback state.
- `VAL-08`: existence/metadata-only checks prove both runtime artifacts are absent; never list/read former profile contents.
- `VAL-09`: `inspect 20260809-214018-ooaa` and ID-directed Git status only; state stays `manual`, target stays staged, no `ingest-web` call.
- `VAL-10`: inspect status/diff/HEAD in both repositories and forbidden paths; no unauthorized change or Git action.

## 9. Risks and rollback of this rollback

- Removing the profile deletes its WeChat session state. This is intended by the requested rollback.
- If the user later wants persistent-profile automation again, it requires a new approved plan; do not recreate it implicitly.
- If rollback encounters unrelated edits in an allowed file, stop instead of overwriting them.

## 10. Permissions

- Authorized: surgical removal of version-1 repository changes, the exact OpenClaw env entry, the dedicated profile directory, and temporary helper.
- Not authorized: branch switch, repository staging, commit, push, merge, reset, clean, broad restore, production-Vault write, network capture/retry, or any other external action.

## 11. Approval record

- Requested change: `进行回退。对触发微信验证这种情况，不做技术绕过了，置为manul，之后由我手动再次调用抓取，或者我手动自己抓取。`
- Approval for SPEC v2: `批准 SPEC v2 回退` at `2026-08-13T00:56:23+08:00`.
- Version-2 blocker: `f9810f1` accidentally contains seven v1 tests without their implementation, making AC-01 and AC-04 mutually incompatible.
- Approval for SPEC v3: `批准 SPEC v3`.
- Approved at: `2026-08-13T01:26:58+08:00`.
