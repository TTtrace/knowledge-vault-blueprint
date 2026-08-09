---
task_id: 2026-08-09-vault-capture-198-18-ssrf-exemption
status: ready_for_review
execution_round: 1
executor: executor
spec_path: ./SPEC.md
started_at: 2026-08-09T18:02:00+08:00
finished_at: 2026-08-09T18:30:00+08:00
---

# Execution Record

> This file is owned by the executor. Do not change the approved `SPEC.md` or write the review verdict here.

## 1. Preflight

- Repository: `knowledge-vault-blueprint`, working directory `/home/monottx/repos/knowledge-vault-blueprint`.
- Branch `main`, HEAD exactly `0018839c121e3a5a7088817ad4a3e363da1230bb` (verified via `git rev-parse HEAD`).
- Index empty; only worktree change was the planner-created untracked task package `tasks/2026-08-09-vault-capture-198-18-ssrf-exemption/` (`SPEC.md`, `EXECUTION.md`, `REVIEW.md`). No unexpected overlap; preflight passed.
- Read `AGENTS.md` and the approved `SPEC.md` (status `approved`, `spec_version: 1`).
- Web tests require `trafilatura`/`playwright`; the sanctioned disposable venv `/tmp/vc-venv` (browser at `/tmp/vc-browsers`) was used, matching the immediately preceding Fake-IP task's one-time validation path. No global Python/browser change.

## 2. Implementation summary

Implemented the exact `198.18.0.0/16` trust exemption in the shared `NetworkPolicy`:

- Added code-owned constant `EXEMPT_NETWORK = 198.18.0.0/16` while retaining `FAKE_IP_NETWORK = 198.18.0.0/15` to represent the full Fake-IP range and its residual `198.19.0.0/16` half.
- Reclassified addresses as `global / exempt / residual_fake / non_global`:
  - Default mode: every system answer must be global or exempt `/16`; any `non_global` or residual `198.19.0.0/16` fails closed; exempt passes with no DoH.
  - Clash mode: `non_global` fails; residual `198.19.0.0/16` Fake-IP triggers the existing fixed-provider DoH (all DoH answers must be global); global+exempt (with no residual) passes with no DoH; exempt+residual still triggers DoH.
- `ValidationResult` names a provider only when a DoH request actually occurred; it may set `fake_ip_observed=True` for exempt answers.
- Direct IP-literal rejection (canonical, legacy/IDNA/trailing-dot) is unchanged and happens before any resolver/DoH.
- No runtime-configurable bypass, no new env flag, no caller changes, no schema migration.

## 3. Changed files (all within allowed paths)

| File | Change | Reason | STEP |
|---|---|---|---|
| `skills/vault-capture/scripts/network_security.py` | Added `EXEMPT_NETWORK` constant, reworked `_classify`/`_classify_all` and `NetworkPolicy.validate_url`, updated module docstring | Implement exact `/16` exemption + residual `/16` semantics | STEP-02 |
| `tests/skills/test_network_security.py` | Added exempt/residual constants and boundary tests in `DefaultModeTests` and `ClashDoHTests`; retargeted DoH-triggering tests to residual `198.19.0.0/16` | Deterministic policy matrix (AC-01..04) | STEP-03 |
| `tests/skills/test_vault_capture.py` | Residual `198.19.0.0/7` default-fail preserves Source; refactored ready transaction helper; Clash residual-DoH ready test; new default-mode exempt ready test | Lifecycle/regression (AC-05, AC-06) | STEP-04 |
| `tests/skills/test_web_extract.py` | Extended `test_ip_literal_rejected_without_network` with `198.18.0.0` and `198.18.255.255` literals | Prove exempt-range literals still denied (AC-05) | STEP-04 |
| `DECISIONS.md` | Added D-019 (table row + section) before historical D-018; added supersession note to D-018 | Document trust exception, residual behavior, risk, rollback | STEP-05 |
| `specifications/capture-workflow.md` | Updated §6.1 for exact `/16` exemption and residual `/16` | Align active contract | STEP-06 |
| `specifications/openclaw-skill-workflow.md` | Updated §4.1 for exact `/16` exemption; clarified DoH now only for residual `198.19` | Align active contract | STEP-06 |
| `skills/vault-capture/SKILL.md` | Updated `不变量` web-security bullet | Align active contract | STEP-06 |
| `skills/vault-capture/references/runtime-contract.md` | Updated SSRF paragraph | Align active contract | STEP-06 |
| `skills/vault-capture/references/web-runtime.md` | Updated §5 and host-deployment §6 | Align active contract | STEP-06 |
| `tests/opencode-harness/README.md` | Updated Fake-IP warning/E2E guidance: exemption proven without the two env vars; residual `198.19` still needs them | Align harness guidance | STEP-06 |
| `tasks/2026-08-09-vault-capture-198-18-ssrf-exemption/EXECUTION.md` | This record | Handoff record | STEP-08 |

## 4. Acceptance evidence (AC-01..09)

- **AC-01 — Exact default exemption: PASS.** `test_network_security.DefaultModeTests.test_default_exempt_passes` (198.18.0.0 and 198.18.255.255 pass, no DoH, `fake_ip_observed=True`, `provider is None`); `test_default_global_and_exempt_passes`; `test_vault_capture.test_ingest_web_default_exempt_reaches_ready`.
- **AC-02 — Exact Clash exemption: PASS.** `test_network_security.ClashDoHTests.test_clash_exempt_no_doh` and `test_clash_global_and_exempt_pass_no_doh` (pass without DoH, provider `None`); environment activation/invalid-config behavior unchanged (`EnvironmentModeTests`, `ProviderFixednessTests` still pass).
- **AC-03 — Mixed-answer boundary: PASS.** `test_network_security.test_clash_exempt_plus_residual_invokes_doh` (exempt+residual requires DoH), `test_clash_exempt_plus_rfc1918_fails`, `test_clash_exempt_no_doh`, `test_default_exempt_plus_rfc1918_fails`; residual Clash DoH public pass / private fail covered by `test_residual_fake_ip_triggers_doh_and_all_public_passes` and `test_any_doh_private_answer_fails`.
- **AC-04 — No broader bypass: PASS.** `198.19.0.0/16` residual default rejects (`test_default_residual_fake_ip_fails`), RFC1918/loopback/link-local/reserved/malformed all fail (`test_any_non_global_fails`, `test_default_malformed_fails`, `ClashDoHTests`). Only `EXEMPT_NETWORK=198.18.0.0/16` is exempt; no env-controlled generic bypass added.
- **AC-05 — Domain-only and surface invariants: PASS.** Direct literals including `198.18.0.0`, `198.18.255.255` rejected at syntax without resolver (`test_network_security.SyntaxTests`, `LegacyNumericSyntaxTests`, `test_web_extract.test_ip_literal_rejected_without_network`). Credentials/non-HTTP rejected. Redirect/browser surface policy unchanged (VAL-02 passes).
- **AC-06 — Lifecycle compatibility: PASS.** Residual default-fail preserves Source and reaches safe `failed` (`test_ingest_web_default_residual_fake_ip_fails_preserves_source`); exempt host completes atomic `ready`/naming/image/Git-staging (`test_ingest_web_default_exempt_reaches_ready`); Clash residual+DoH ready (`test_ingest_web_mocked_doh_residual_fake_ip_reaches_ready`).
- **AC-07 — Decision and contract consistency: PASS.** D-019 added, D-018 historical with supersession note; capture/OpenClaw/SKILL/runtime/web/harness docs all use exact `/16` for exemption, residual `/16` for Clash/DoH, literal prohibition, risk, no migration, rollback. VAL-06 grep inspection found no contradictory active default-fail statement or broader bypass; VAL-07 `git diff --check` clean.
- **AC-08 — Regression and scope: PASS.** VAL-01..08 all pass (see log); only allowed paths changed; branch `main`; HEAD unchanged; index empty.
- **AC-09 — Real OpenClaw behavior: NOT_RUN** (planner-owned VAL-09..11). Not a blocker for READY_FOR_REVIEW per brief.

## 5. Validation log (VAL-01..11)

All commands run in `/home/monottx/repos/knowledge-vault-blueprint`. `rg` is unavailable in this environment; VAL-06 used the equivalent `grep -rn -E` with identical patterns. `python` is not on PATH; the sanctioned venv `/tmp/vc-venv` interpreter was used.

- **VAL-01** `python tests/skills/test_network_security.py` → via `/tmp/vc-venv/bin/python`, exit 0, 54 tests OK.
- **VAL-02** `PLAYWRIGHT_BROWSERS_PATH=/tmp/vc-browsers python tests/skills/test_web_extract.py` → via `/tmp/vc-venv/bin/python`, exit 0, 34 tests OK.
- **VAL-03** `python tests/skills/test_vault_capture.py` → via `/tmp/vc-venv/bin/python`, exit 0, 23 tests OK.
- **VAL-04** `python -m compileall -q skills/vault-capture/scripts tests/skills` → via `/tmp/vc-venv/bin/python`, exit 0.
- **VAL-05** `bash tests/opencode-harness/test_capture_debug.sh` → exit 0, 19 PASS / 0 FAIL.
- **VAL-06** `grep -rn -E "198\.18\.0\.0/16|198\.18\.0\.0/15|198\.19\.0\.0/16|FAKE_IP_NETWORK|SSRF" ...` → exit 0; inspected: D-019 and all active docs use exact `/16`; D-018 clearly historical/superseded; no contradictory active default-fail statement; no broader bypass in code (`EXEMPT_NETWORK` is the only exempt range).
- **VAL-07** `git diff --check 0018839... -- <allowed paths>` → exit 0, no output.
- **VAL-08** `git status --short` (11 modified allowed files + untracked task package), `git diff --name-only 0018839...` (11 allowed files only), `git diff --cached --name-only` (empty), branch `main`, HEAD `0018839...` unchanged → PASS.
- **VAL-09..11** NOT_RUN — planner-owned real OpenClaw E2E. AC-09 accordingly NOT_RUN.

## 6. Deviations

- `rg` unavailable → used `grep -rn -E` with identical patterns for VAL-06 (equivalent output and contract).
- `python` not on PATH → used sanctioned disposable venv `/tmp/vc-venv/bin/python` for VAL-01..04 (identical code path; web tests already require this venv per repo one-time validation path).
- Otherwise none. All semantics, CIDR, literal policy, residual `/16` behavior, allowed paths, and acceptance contract match the approved SPEC and brief.

## 7. Blockers

none.

## 8. Final Git state

- Branch: `main`; HEAD: `0018839c121e3a5a7088817ad4a3e363da1230bb` (unchanged).
- Index: empty (`git diff --cached --name-only` empty). Nothing staged or committed. Task package files remain untracked.
