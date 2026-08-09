---
task_id: 2026-08-09-vault-capture-198-18-ssrf-exemption
status: accepted
review_round: 2
reviewer: reviewer
reviewed_at: 2026-08-09T18:36:42+08:00
verdict: accepted
---

# Review Record

> This file records independent review. The reviewer verified actual files, diff, and validation evidence rather than trusting the executor summary.

## 1. Review scope and observed state

- Approved specification: `SPEC.md` v1, approval signal `批准第一层计划`.
- Baseline: `main @ 0018839c121e3a5a7088817ad4a3e363da1230bb`.
- Reviewed state: HEAD unchanged, index empty, nothing staged or committed.
- Changed implementation set: exactly the eleven approved code/test/document paths plus this untracked task package; no forbidden or unrelated path changed.
- Planner E2E evidence for VAL-09..11 was assessed separately from the executor's repository validations.

## 2. Findings

- `F-01` (`major`, closed in round 2): `EXECUTION.md` originally used non-protocol value `status: implemented`. Executor changed only that token to `status: ready_for_review`; reviewer verified the other 90 lines were unchanged and the task now satisfies `tasks/README.md` completion protocol.

## 3. Scope compliance

- Allowed-path compliance: `pass`.
- Forbidden-path compliance: `pass`.
- Unrelated-change check: `pass`.
- Specification integrity: `pass`; the approved status, version, baseline, scope, AC/VAL contract, and approval record match the user-approved input.
- Git state: `main`, baseline HEAD unchanged, index empty, no commit/push.

## 4. Independent acceptance check

| Criterion | Verdict | Independent evidence |
|---|---|---|
| `AC-01` | pass | Default mode accepts the first and last addresses of `198.18.0.0/16`, performs no DoH, reports `fake_ip_observed=true` and no provider. |
| `AC-02` | pass | Clash mode accepts exempt-only and global+exempt answers without DoH; environment parsing remains unchanged and fail-closed. |
| `AC-03` | pass | Global+exempt passes; exempt+RFC1918 fails; exempt+residual `198.19/16` fails in default mode and invokes DoH in Clash mode. Address-classification order was independently checked. |
| `AC-04` | pass | `198.19/16`, RFC1918, loopback, link-local, malformed, and other non-global destinations retain their prior semantics; no generic bypass exists. |
| `AC-05` | pass | Direct IP literals including both exempt-range boundaries remain rejected before resolver access; credentials, schemes, redirects, browser, and image surfaces remain guarded by untouched shared-policy callers. |
| `AC-06` | pass | Residual Fake-IP rejection preserves a safe failed Source; exempt-default and residual-Clash/DoH paths complete the existing atomic ready/naming/image/staging transaction. |
| `AC-07` | pass | D-019 and all active specifications, skill references, and harness guidance agree; D-018 remains clearly historical. |
| `AC-08` | pass | All repository validations pass; scope, HEAD, branch, and index satisfy the contract. |
| `AC-09` | pass | Planner E2E observed `198.18.0.71`, absent Fake-IP/DoH settings, valid Trafilatura runtime, first terminal state exactly `ready`, all harness assertions passing, ID-directed cleanup, exact test-Vault fingerprint restoration, and no live-Vault write. |

## 5. Reviewer validation

All commands ran from `/home/monottx/repos/knowledge-vault-blueprint` unless stated otherwise.

| Validation | Result | Evidence summary |
|---|---|---|
| `VAL-01` | exit 0 | 54 network-policy tests passed. |
| `VAL-02` | exit 0 | 34 web extraction/security tests passed. |
| `VAL-03` | exit 0 | 23 capture/lifecycle tests passed. |
| `VAL-04` | exit 0 | Python compileall passed. |
| `VAL-05` | exit 0 | Harness self-test: 19 passed, 0 failed. |
| `VAL-06` | pass | `rg` was unavailable; equivalent `grep -rn -E` audit found no active contradiction or broader bypass. |
| `VAL-07` | exit 0 | Task-scoped `git diff --check` produced no output. |
| `VAL-08` | pass | Only allowed paths changed; branch `main`, HEAD unchanged, index empty. |
| `VAL-09` | pass, planner evidence | Test runtime resolved the RFC host to `198.18.0.71`; SSRF Fake-IP/DoH settings absent; no-write agent diagnostic imported Trafilatura 2.1.0 with zero tool failures. |
| `VAL-10` | exit 0, planner evidence | Async envelope valid; unique Source ID `20260809-182304-0iui`; first terminal state exactly `ready`; six assertions passed; cleanup removed one new staged path and two new files. |
| `VAL-11` | pass, planner evidence | Temporary interpreter setting removed; Gateway healthy; pre/post test-Vault status/index fingerprints and HEAD identical; no E2E ID residue. |

## 6. Cross-repository and rollback check

- The live `SourceNotes` Vault was not touched.
- The pre-existing dirty state in `SourceNotes-test` was preserved byte-for-byte at the Git status/index fingerprint level.
- Temporary test Gateway configuration was restored.
- `schema_version` remains `1`; no migration exists.
- Rollback to D-018 is explicit and requires reverting only this task's delta.

## 7. Verdict

- Verdict: `accepted` (`PASS`) in review round 2.
- Required follow-up: none; F-01 is closed.
- Remaining accepted risk: D-019 intentionally trusts system answers in `198.18.0.0/16` without DoH; this user-approved security relaxation is documented with rollback. `fake_ip_observed` now also denotes an exempt observation while `provider` remains null when DoH was not used.
- Reviewed at: `2026-08-09T18:36:42+08:00`.

Acceptance does not authorize stage, commit, push, merge, deployment, or publication.
