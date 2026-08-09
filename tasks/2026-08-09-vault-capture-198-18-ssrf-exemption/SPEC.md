---
task_id: 2026-08-09-vault-capture-198-18-ssrf-exemption
title: Exempt 198.18.0.0/16 from vault-capture address-level SSRF blocking
status: approved
spec_version: 1
planner: primary
executor: executor
created: 2026-08-09
approved_at: 2026-08-09T17:59:04+08:00
approved_by: user
---

# Task Specification

> This file is owned by the planner. After `status: approved`, the executor must not edit it. A material change returns it to `draft`, increments `spec_version`, and requires approval again.

## 1. Context and problem

The accepted D-018 network policy treats every system-DNS answer in `198.18.0.0/15` as a Clash Fake-IP signal. Default mode rejects it, while explicitly configured Clash mode independently verifies the hostname through a fixed trusted DoH provider before allowing the domain-named request.

The user has explicitly requested that address-level SSRF blocking be disabled for `198.18.0.1/16`, interpreted using canonical CIDR semantics as `198.18.0.0/16` (`198.18.0.0` through `198.18.255.255`). This is an intentional security relaxation: a DNS hostname resolving into that half of the benchmarking/Fake-IP range will be trusted without DoH verification.

The immediately preceding Fake-IP-aware SSRF implementation is committed at the clean baseline recorded below, so this task does not overlap uncommitted work.

## 2. Required outcome

For every network boundary using the shared `NetworkPolicy`, a DNS hostname whose complete system-resolver answer set contains only globally routable addresses and/or addresses in `198.18.0.0/16` is allowed. Addresses in the exempt `/16` do not trigger DoH in either default or Clash mode. If any answer is non-global and outside the exempt `/16`, the existing fail-closed behavior remains, except that residual Clash Fake-IP answers in `198.19.0.0/16` retain the current explicit Clash/DoH behavior.

The exemption is address-classification-only. Direct IP URL literals remain forbidden, and every existing syntax, credentials, scheme, redirect, Playwright, image, size, lifecycle, atomic-write, and Git-staging invariant remains in force.

## 3. Non-goals

- Do not allow direct IPv4/IPv6 URL literals, including `http://198.18.0.1/`.
- Do not exempt `198.19.0.0/16` or any other private, loopback, link-local, metadata, multicast, documentation, reserved, or non-global range.
- Do not remove the existing optional Clash/DoH mode; it remains applicable to residual Fake-IP addresses in `198.19.0.0/16`.
- Do not weaken URL syntax, redirect revalidation, Playwright request guards, retained-image validation, response/image limits, extraction quality gates, or safe-error handling.
- Do not change Source/Annotation meaning, metadata fields, capture/read lifecycles, `schema_version`, naming, immutability, or ID-directed staging.
- Do not modify the live `SourceNotes` Vault or production Gateway/agent configuration.
- Do not install dependencies, switch branches, stage, commit, push, merge, tag, deploy, publish, reset, or clean.

## 4. Locked decisions

- `198.18.0.1/16` is normalized to the network `198.18.0.0/16`; no host-specific interpretation is permitted.
- The exemption is unconditional in both default and Clash modes and requires no environment variable.
- A system answer set made only of global and exempt addresses passes. A mixed set containing any other non-global address fails closed, except that `198.19.0.0/16` follows the existing Clash-mode DoH path when Clash mode is validly configured.
- An exempt address must not trigger DoH. If an answer set also contains a residual `198.19.0.0/16` Fake-IP in Clash mode, that residual address still triggers the existing DoH validation for the hostname.
- Direct IP literals remain rejected during network-free syntax validation before DNS or connection.
- Existing Fake-IP/DoH environment parsing remains exact and fail-closed: both unset means default mode; exact `clash` plus a built-in `cloudflare|google` provider enables residual Fake-IP handling; partial/unknown configuration remains invalid.
- `ValidationResult` may report that Fake-IP was observed for the exempt range, but it must not claim a DoH provider was used when no DoH request occurred.
- D-018 remains historical. Add D-019 to explicitly supersede only D-018's no-CIDR-exemption/default-reject rules for `198.18.0.0/16`; preserve all other D-018 protections.
- This changes a security policy, not Vault data meaning. `schema_version` remains `1`; no migration exists.
- The real E2E must prove the exemption without the two Fake-IP/DoH settings. Planner may temporarily remove those settings only from the isolated test agent/Gateway, record and restore prior values, and must stop if test/production isolation cannot be proven.

## 5. Repository baselines

Baseline observed immediately before approval follow-up on `2026-08-09`.

| Repository | Absolute path | Base branch | Base commit | Existing worktree changes | Working branch |
|---|---|---|---|---|---|
| `knowledge-vault-blueprint` | `/home/monottx/repos/knowledge-vault-blueprint` | `main` | `0018839c121e3a5a7088817ad4a3e363da1230bb` | none; index empty | existing `main`; no branch switch authorized |

`SourceNotes` is outside implementation scope. `/home/monottx/repos/SourceNotes-test` is allowed only for planner-owned E2E validation and ID-directed cleanup.

## 6. Scope by repository

### knowledge-vault-blueprint

Expected changes:

- Add D-019 documenting the explicit `198.18.0.0/16` trust exception, residual protections, risk, and rollback.
- Implement the exemption in the shared policy without changing outbound callers.
- Add deterministic policy, lifecycle, and regression tests.
- Align capture, OpenClaw, skill, runtime, web-runtime, and harness guidance with D-019.
- Complete the task package execution and review records.

Allowed implementation paths:

- `DECISIONS.md`
- `specifications/capture-workflow.md`
- `specifications/openclaw-skill-workflow.md`
- `skills/vault-capture/SKILL.md`
- `skills/vault-capture/references/runtime-contract.md`
- `skills/vault-capture/references/web-runtime.md`
- `skills/vault-capture/scripts/network_security.py`
- `tests/skills/test_network_security.py`
- `tests/skills/test_vault_capture.py`
- `tests/skills/test_web_extract.py`
- `tests/opencode-harness/README.md`
- `tasks/2026-08-09-vault-capture-198-18-ssrf-exemption/EXECUTION.md` (executor only)
- `tasks/2026-08-09-vault-capture-198-18-ssrf-exemption/REVIEW.md` (review record only)

Planner-owned approved record:

- `tasks/2026-08-09-vault-capture-198-18-ssrf-exemption/SPEC.md`

Forbidden paths and behavior:

- Executor must not edit `tasks/2026-08-09-vault-capture-198-18-ssrf-exemption/SPEC.md`.
- `skills/vault-capture/scripts/vault_capture.py`
- `skills/vault-capture/scripts/web_extract.py`
- `skills/vault-capture/requirements-web.txt`
- `skills/vault-capture/requirements-web.lock`
- `specifications/metadata-schema.md`
- `AGENTS.md`
- `tasks/README.md`
- `tasks/_template/**`
- `vault-starter/**`
- Every path not explicitly allowed above.

### SourceNotes and external runtime

Expected implementation changes: none.

Allowed planner-only validation actions:

- Read non-secret test agent/Gateway settings and prove the target Vault basename ends in `-test`.
- Record the prior values of the two SSRF Fake-IP/DoH settings and `VAULT_CAPTURE_PYTHON` without printing secrets.
- Temporarily unset only `VAULT_CAPTURE_SSRF_FAKE_IP_MODE` and `VAULT_CAPTURE_SSRF_DOH_PROVIDER` in the isolated test context if currently present; preserve the existing valid `VAULT_CAPTURE_PYTHON` or point it to the existing test venv as previously approved for E2E.
- Reload/restart only the isolated test Gateway if required.
- Run the README-defined harness with a unique URL/session and `--cleanup`.
- Restore prior settings exactly and reload the test Gateway if it was reloaded.

Forbidden external actions:

- Any write to the live `SourceNotes` Vault.
- Any production Gateway/agent configuration change.
- Persisting host-specific paths, credentials, environment dumps, or secrets in repository content.
- Executor writes outside the blueprint repository.

## 7. Invariants and safety constraints

- Preserve unrelated work and stop if the baseline is no longer clean before executor edits.
- Preserve domain-only absolute HTTP(S), no credentials, literal rejection, pre-connection validation, redirect revalidation, browser scheme restrictions, and image policy coverage.
- Preserve Source body immutability, Source-before-fetch, safe failed-stub retention, lifecycle separation, permanent IDs, and ID-directed Git staging.
- Do not log raw DNS/DoH payloads, cookies, authorization data, environment contents, stack traces, absolute Vault paths, or browser profile paths.
- Do not add a generic private-fetch flag, arbitrary CIDR list, host allowlist, arbitrary DoH endpoint, or user-configurable exemption.
- Do not broaden the exemption beyond canonical `198.18.0.0/16`.
- No schema/Vault migration and no automated data in the live Vault.
- No stage/commit/push/merge/tag/release/deploy/publish is authorized.

## 8. Acceptance criteria

- [ ] **AC-01 — Exact default exemption:** In default mode, a DNS hostname resolving solely to one or more `198.18.0.0/16` addresses passes before connection, performs no DoH request, and returns a non-misleading validation result.
- [ ] **AC-02 — Exact Clash exemption:** In valid Clash mode, a hostname resolving solely to global and/or `198.18.0.0/16` addresses passes without DoH. The existing environment activation and invalid-config behavior remain unchanged.
- [ ] **AC-03 — Mixed-answer boundary:** Global plus exempt addresses pass. Any non-global address outside the exemption fails closed, except residual `198.19.0.0/16` answers use the existing configured Clash/DoH flow; a set containing exempt plus residual Fake-IP still requires DoH.
- [ ] **AC-04 — No broader bypass:** `198.19.0.0/16`, RFC1918, loopback, link-local, metadata, reserved, malformed, and all other non-global destinations retain current rejection/DoH semantics. No generic environment-controlled private bypass is introduced.
- [ ] **AC-05 — Domain-only and surface invariants:** Direct IP literals including `198.18.0.0/16`, credentials, and non-HTTP(S) input remain rejected. Initial requests, redirects, Playwright documents/subresources, retained images, and image redirects continue calling the shared policy before connection.
- [ ] **AC-06 — Lifecycle compatibility:** A rejected target preserves its staged Source and reaches a short safe `failed`; an exempt Fake-IP hostname can complete the existing atomic `ready`, naming, image, and ID-directed Git-staging transaction.
- [ ] **AC-07 — Decision and contract consistency:** D-019, D-018 history, specifications, skill references, and harness guidance agree on exact CIDR, unconditional exemption, residual `/16` behavior, remaining safeguards, risk, no migration, and rollback.
- [ ] **AC-08 — Regression and scope:** Policy, web, capture, compile, and harness self-tests pass; task-scoped `git diff --check` passes; only allowed paths change; HEAD remains at the baseline with an empty index.
- [ ] **AC-09 — Real OpenClaw behavior:** In the isolated `*-test` Vault context, the runtime observes at least one system answer inside `198.18.0.0/16`; the two Fake-IP/DoH settings are absent for the test; the configured interpreter imports Trafilatura; and a unique RFC web capture passes the README harness with first observed terminal state exactly `ready`, then ID-directed cleanup restores the test baseline.

## 9. Validation plan

| ID | Working directory | Exact command or inspection | Expected result | AC mapping |
|---|---|---|---|---|
| `VAL-01` | `/home/monottx/repos/knowledge-vault-blueprint` | `python tests/skills/test_network_security.py` | Exit 0; exact `/16`, mixed-answer, residual Fake-IP/DoH, literal, and no-broader-bypass tests pass. | AC-01..05,08 |
| `VAL-02` | same | `python tests/skills/test_web_extract.py` | Exit 0; request/redirect/browser surface checks remain intact. | AC-05,08 |
| `VAL-03` | same | `python tests/skills/test_vault_capture.py` | Exit 0; lifecycle, failed-stub, ready transaction, image, and Git-staging regressions pass. | AC-05,06,08 |
| `VAL-04` | same | `python -m compileall -q skills/vault-capture/scripts tests/skills` | Exit 0. | AC-08 |
| `VAL-05` | same | `bash tests/opencode-harness/test_capture_debug.sh` | Exit 0; harness strict-ready, ID recovery, staging, and cleanup contract remains intact. | AC-08 |
| `VAL-06` | same | `rg -n "198\\.18\\.0\\.0/16|198\\.18\\.0\\.0/15|198\\.19\\.0\\.0/16|FAKE_IP_NETWORK|SSRF" DECISIONS.md specifications skills/vault-capture tests/opencode-harness/README.md tests/skills` and inspect all policy statements | D-019 and active docs use exact `/16`; historical D-018 remains identified; no contradictory active default-fail statement or broader bypass. | AC-04,07 |
| `VAL-07` | same | `git diff --check 0018839c121e3a5a7088817ad4a3e363da1230bb -- DECISIONS.md specifications/capture-workflow.md specifications/openclaw-skill-workflow.md skills/vault-capture/SKILL.md skills/vault-capture/references/runtime-contract.md skills/vault-capture/references/web-runtime.md skills/vault-capture/scripts/network_security.py tests/skills/test_network_security.py tests/skills/test_vault_capture.py tests/skills/test_web_extract.py tests/opencode-harness/README.md tasks/2026-08-09-vault-capture-198-18-ssrf-exemption` | Exit 0, no output. | AC-07,08 |
| `VAL-08` | same | Compare `git status --short`, `git diff --name-only 0018839c121e3a5a7088817ad4a3e363da1230bb`, `git diff --cached --name-only`, branch, and HEAD with §5-6 | Only allowed task paths changed; index empty; branch `main`; HEAD unchanged. | AC-08 |
| `VAL-09` | isolated test agent/Gateway context | Prove test Vault basename ends in `-test`; inspect non-secret presence/absence of the three named settings; resolve the selected RFC host in the same context and classify using Python `ipaddress`; run a no-Vault-write agent diagnostic proving the configured interpreter imports Trafilatura | At least one system answer is inside `198.18.0.0/16`; Fake-IP mode/provider are absent; interpreter import succeeds; no secrets or host configuration are emitted. | AC-09 |
| `VAL-10` | `/home/monottx/repos/knowledge-vault-blueprint` | `stamp="$(date +%Y%m%d-%H%M%S)"; ./tests/opencode-harness/capture_debug.sh web "收：https://www.rfc-editor.org/rfc/rfc9110.html?vault_capture_198_18_exempt=$stamp" --wait 180 --expect-status ready --assert --cleanup --session "ssrf-exempt-$stamp"` | Exit 0; valid sync/async envelope, unique Source ID, ID-scoped staging, first terminal state exact `ready`, and cleanup pass. | AC-06,09 |
| `VAL-11` | isolated test Gateway and test Vault | Compare the three relevant settings and test Vault/Gateway state with the pre-E2E record | Prior settings restored exactly; no test artifact remains; live Vault untouched. | AC-09, rollback |

## 10. Deliverables

- Shared policy implementing only the exact `198.18.0.0/16` address exemption.
- D-019 and consistent active documentation with explicit risk and rollback.
- Deterministic regressions proving the positive exception and all negative boundaries.
- Completed executor evidence in `EXECUTION.md`, planner E2E evidence, and independent reviewer verdict in `REVIEW.md`.
- Fixed-format executor return and final Git state report.

## 11. Git and external-action permissions

- Branching: `not authorized`; remain on `main`.
- Staging blueprint files: `not authorized`.
- Committing/pushing/merging/tagging/releasing/deploying/publishing: `not authorized`.
- Test-vault staging: authorized only as normal harness behavior for the unique E2E Source ID, followed by `--cleanup`.
- Read-only network: authorized for the explicit RFC E2E URL and required agent/runtime diagnostics.
- External test configuration: planner only, isolated test context only, limited to temporary removal/restoration of the two Fake-IP/DoH settings and preservation/selection of the existing test `VAULT_CAPTURE_PYTHON`; stop if isolation is uncertain.

## 12. Rollback

- Restore only this task's allowed implementation/document/test paths to baseline `0018839c121e3a5a7088817ad4a3e363da1230bb`; never reset or clean the repository and never overwrite unrelated work.
- Remove D-019 and restore D-018 as the active rule for all `198.18.0.0/15` answers, so default mode rejects and configured Clash mode uses fixed-provider DoH.
- Restore the isolated test agent/Gateway settings to their exact pre-E2E values and reload only that test Gateway if changed.
- No schema or Vault migration exists. E2E cleanup is ID-directed and must stop rather than guess if one unique Source ID cannot be established.

## 13. Open questions

- none. Exact CIDR, direct-literal behavior, residual `/16`, mixed-answer behavior, scope, validation, and rollback are locked.

## 14. Approval record

- Approval statement: `批准第一层计划`
- Approved specification version: `1`
- Approved at: `2026-08-09T17:59:04+08:00`
