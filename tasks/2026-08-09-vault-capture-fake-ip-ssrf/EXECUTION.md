---
task_id: 2026-08-09-vault-capture-fake-ip-ssrf
status: ready_for_review
execution_round: 3
executor: executor
spec_path: ../SPEC.md
started_at: 2026-08-09T14:45:00+08:00
finished_at: 2026-08-09T15:20:00+08:00
---

# Execution Record

> This file is owned by the executor. Do not change the approved `SPEC.md` or write the review verdict here.

## 1. Preflight

| Repository | Expected baseline | Observed branch and HEAD | Worktree before execution | Result |
|---|---|---|---|---|
| `knowledge-vault-blueprint` | `main @ b7cf1bf63caeb8947120e1c6b3276d81db78bcae` | `main @ b7cf1bf63caeb8947120e1c6b3276d81db78bcae` | clean except untracked `tasks/2026-08-09-vault-capture-fake-ip-ssrf/` (SPEC/EXECUTION/REVIEW) | OK |

Applicable instructions read: `AGENTS.md`, `tasks/.../SPEC.md`, `DECISIONS.md`, `specifications/capture-workflow.md`, `specifications/openclaw-skill-workflow.md`, `skills/vault-capture/SKILL.md`, `references/runtime-contract.md`, `references/web-runtime.md`, `scripts/web_extract.py`, `scripts/vault_capture.py`, `tests/skills/test_web_extract.py`, `tests/skills/test_vault_capture.py`, `tests/opencode-harness/README.md`, `tests/opencode-harness/test_capture_debug.sh`.

Baseline confirmed: no overlapping user changes; only the expected untracked task package is present.

## 2. Implementation summary

- Added a shared, standard-library-only module `skills/vault-capture/scripts/network_security.py` centralizing: domain-only URL syntax validation (rejects IPv4/IPv6 literals and credentials), system-DNS classification, Fake-IP detection (`198.18.0.0/15`), fixed trusted DoH (Cloudflare/Google HTTPS DNS JSON, A+AAAA, all-public, fail closed), environment parsing (`VAULT_CAPTURE_SSRF_FAKE_IP_MODE=clash` + `VAULT_CAPTURE_SSRF_DOH_PROVIDER=cloudflare|google`; partial/unknown => `InvalidNetworkConfig`), and a per-target `validate_url` used before every connection. Resolver/DoH are injectable for tests only.
- Wired the policy into `web_extract.py`: removed `_is_public_host` and the `allow_private_override` production path; `static_fetch`, `_make_navigation_guard`, `playwright_fetch`, `_try_playwright`, `_attempt_browser`, and `extract_article` now accept a `policy` object (default built from the environment). Static and redirect targets are validated before each connection; Playwright validates every HTTP(S) document/subresource/redirect request (non-network schemes use a minimal explicit continue) and re-validates the final URL.
- Wired the policy into `vault_capture.py`: `stage(kind=web)` does domain-only syntax validation before any network; removed `ensure_public_asset_url` and both `VAULT_CAPTURE_ALLOW_PRIVATE_FETCH` / `VAULT_CAPTURE_ALLOW_PRIVATE_ASSETS` bypasses; image downloads now use a no-auto-redirect opener with per-hop policy validation; `cmd_ingest_web` builds one policy and passes it to `extract_article` and `cmd_finalize`; invalid Fake-IP config/DoH/SSRF failures map to short safe `failed` preserving the staged Source.
- Added `tests/skills/test_network_security.py` (32 tests, offline mocks/fakes).
- Reworked `tests/skills/test_web_extract.py` and `tests/skills/test_vault_capture.py` to use scoped injected policies/transports (never a production env switch) and added stage-IP-literal, default-Fake-IP-failed-preserves-Source, and mocked-DoH-ready integration tests.
- Updated `DECISIONS.md` (D-018), `specifications/capture-workflow.md`, `specifications/openclaw-skill-workflow.md`, `skills/vault-capture/SKILL.md`, `references/runtime-contract.md`, `references/web-runtime.md`, and `tests/opencode-harness/README.md` for configuration, trust boundary, errors, no schema migration, and rollback.
- `tests/opencode-harness/test_capture_debug.sh` required no changes (default `ready` semantics preserved; all 19 harness assertions pass).

## 3. Changed files

- `DECISIONS.md` — added D-018 decision with rationale, boundary, rollback; schema stays 1. (STEP-07)
- `specifications/capture-workflow.md` — added §6.1 network/SSRF boundary (domain-only, redirects, images, fail-closed, preserve stub). (STEP-07)
- `specifications/openclaw-skill-workflow.md` — added §4.1 optional Fake-IP config, test/production isolation, DoH provider boundary. (STEP-07)
- `skills/vault-capture/SKILL.md` — security invariants; optional config not in `requires.env`. (STEP-07)
- `skills/vault-capture/references/runtime-contract.md` — stage domain-only, ingest SSRF failure mapping, image policy. (STEP-07)
- `skills/vault-capture/references/web-runtime.md` — full security policy, outbound surfaces, deployment config, rollback. (STEP-07)
- `skills/vault-capture/scripts/network_security.py` (new) — shared Fake-IP-aware SSRF policy. (STEP-02)
- `skills/vault-capture/scripts/web_extract.py` — policy integration; removed private override. (STEP-03)
- `skills/vault-capture/scripts/vault_capture.py` — stage/ingest/finalize/image policy integration; removed private bypass. (STEP-04)
- `tests/skills/test_network_security.py` (new) — offline policy tests. (STEP-05)
- `tests/skills/test_web_extract.py` — scoped policy; redirects; navigation guard; kept generic/WeChat/Playwright/quality tests. (STEP-06)
- `tests/skills/test_vault_capture.py` — scoped policy; stage rejection; default-fail-preserve; mocked-DoH ready; images; git staging. (STEP-06)
- `tests/opencode-harness/README.md` — replaced "SSRF另案" note with new config/verification contract. (STEP-07)
- `tasks/2026-08-09-vault-capture-fake-ip-ssrf/EXECUTION.md` — this record. (STEP-01/08)

## 4. Acceptance evidence

- AC-01 (Default fail-closed) — PASS. `test_network_security.DefaultModeTests.test_default_fake_ip_fails`; `test_vault_capture.test_ingest_web_default_fake_ip_fails_preserves_source` (198.18.0.7 system answer fails before connection, Source preserved).
- AC-02 (Domain-only contract) — PASS. `test_network_security.SyntaxTests` (credentials/ftp/IPv4/IPv6/198.18 literals rejected); `test_web_extract.WebExtractSecurityTests`; `test_vault_capture.test_stage_rejects_ip_literal_and_credentials` (exit 2, no web job).
- AC-03 (Explicit activation) — PASS. `test_network_security.EnvironmentModeTests` (unset default; exact valid combos; partial/unknown fail closed).
- AC-04 (Trusted real A/AAAA) — PASS. `test_network_security.ClashDoHTests` + `DoHClientTests` (both A and AAAA; all-global pass; A-only/AAAA-only NODATA pass when other has result; empty fail; any private/link-local/loopback/reserved/Fake-IP/malformed fails; timeout/status/oversize/redirect/content-type fail closed with safe reason).
- AC-05 (Redirect and surface coverage) — PASS. `test_network_security.RevalidationTests` (per-target revalidation, no cache skip); `test_web_extract` static redirect + `NavigationGuardTests` (abort private document/subresource, permissive scoped continue, non-network scheme continue without bypass); `test_vault_capture` image localize + image failure tests (pre-connect policy).
- AC-06 (No broad bypass) — PASS. VAL-06: production `skills/`/`specifications/`/`DECISIONS.md` have no read of `VAULT_CAPTURE_ALLOW_PRIVATE_FETCH`/`VAULT_CAPTURE_ALLOW_PRIVATE_ASSETS`; `vault_capture.py` no longer reads either; references remain only as removal/rollback documentation and in the non-production manual smoke helper `tests/skills/live_wechat_smoke.py` (outside allowed paths, not modified).
- AC-07 (Lifecycle compatibility) — PASS. Rejected web target keeps staged Source and reaches safe `failed` (no 198.18 leak); validated Fake-IP/DoH target completes atomic `ready`, final naming, image localization, and ID-scoped Git staging (`test_vault_capture.test_ingest_web_mocked_doh_fake_ip_reaches_ready`).
- AC-08 (Contract and rollback consistency) — PASS. D-018 and capture/OpenClaw/runtime/web docs agree on config names, trust boundary, errors, no schema migration, rollback; `git diff --check` (VAL-07) clean.
- AC-09 (Regression and scope) — PASS. VAL-01..08 all exit 0; only allowed paths changed; no staging/commit.
- AC-10 (Real OpenClaw E2E) — NOT_RUN by executor. Requires planner-owned VAL-09..11 against `SourceNotes-test` with real Fake-IP system resolution and the two env settings.

## 5. Validation log

All commands run in `/home/monottx/repos/knowledge-vault-blueprint` unless noted. Web tests require `trafilatura`/`playwright`; these were installed into a disposable venv `/tmp/vc-venv` (browser at `/tmp/vc-browsers`) per the repo's one-time validation path — no global Python/browser change.

- VAL-01: `python tests/skills/test_network_security.py` — exit 0, 32 tests OK.
- VAL-02: `PLAYWRIGHT_BROWSERS_PATH=/tmp/vc-browsers python tests/skills/test_web_extract.py` — exit 0, 31 tests OK.
- VAL-03: `python tests/skills/test_vault_capture.py` — exit 0, 20 tests OK.
- VAL-04: `python -m compileall -q skills/vault-capture/scripts tests/skills` — exit 0.
- VAL-05: `bash tests/opencode-harness/test_capture_debug.sh` — exit 0, 19 PASS / 0 FAIL.
- VAL-06: repo search for `VAULT_CAPTURE_ALLOW_PRIVATE_FETCH`/`VAULT_CAPTURE_ALLOW_PRIVATE_ASSETS` in production scripts/docs — no production read; only removal/rollback docs and non-production `tests/skills/live_wechat_smoke.py` hit (not in allowed paths, left untouched).
- VAL-07: `git diff --check b7cf1bf63caeb8947120e1c6b3276d81db78bcae -- DECISIONS.md specifications/capture-workflow.md specifications/openclaw-skill-workflow.md skills/vault-capture tests/skills tests/opencode-harness tasks/2026-08-09-vault-capture-fake-ip-ssrf` — exit 0, no output.
- VAL-08: `git status --short` / diff inspection — only allowed paths changed; nothing staged or committed.

VAL-09..11 were not run (planner-owned real Gateway/Fake-IP/harness E2E).

## 6. Assumptions

- Disposable venv/browser install in `/tmp` is the sanctioned one-time validation path and does not modify global Python or browser installations.
- `tests/skills/live_wechat_smoke.py` is a non-production manual smoke helper outside allowed paths; leaving it unmodified does not create a production bypass (its env var is no longer read by `vault_capture.py`).

## 7. Deviations from specification

- Test injection approach: because `cmd_ingest_web`/`cmd_finalize` build the policy from the environment and a subprocess CLI cannot receive a scoped policy without an env switch (forbidden), the network-dependent vault tests (`finalize` with images, E2E ingest) run in-process with an explicitly injected scoped fake policy via `mock.patch` on `NetworkPolicy.from_environment`. This is a test-only injection, unreachable by runtime environment configuration.
- E2E ready test uses `http://localhost:<port>/article` (a DNS name) so `stage`'s domain-only check passes; the injected resolver handles policy validation while the actual TCP connection resolves `localhost` to the loopback test server.
- `web_extract.py` gained a guarded `sys.path` insert to import the sibling `network_security` module when loaded via a module spec (test load path); no production behavioral change.
- `tests/skills/live_wechat_smoke.py` still sets `VAULT_CAPTURE_ALLOW_PRIVATE_ASSETS`; outside allowed paths so not modified — noted for transparency; it is not production code and the variable is now inert.

## 8. Unresolved risks and blockers

- none. AC-10 remains NOT_RUN (planner-owned real E2E). No blockers.

## 9. Git state at handoff

- Branch `main` @ `b7cf1bf63caeb8947120e1c6b3276d81db78bcae` (unchanged; no branch switch).
- Worktree: 11 modified allowed files + 3 untracked (`skills/vault-capture/scripts/network_security.py`, `tests/skills/test_network_security.py`, `tasks/2026-08-09-vault-capture-fake-ip-ssrf/`).
- Nothing staged; nothing committed; nothing pushed.

## 10. Handoff

- Status: `ready_for_review`
- Recommended reviewer action: independently check the diff (especially `network_security.py` DoH/provider fixedness, removal of private-fetch bypass, and test-only injection paths), then verify VAL-01..08 evidence and note AC-10 requires the planner-run real E2E (VAL-09..11).

---

# Round 2 (spec_version 2)

> Round 1 returned `NEEDS_REPLAN`. v2 absorbed the necessary scope changes (legacy numeric IPv4 rejection, safe CLI error handling, DoH/IDN encoding hardening, Playwright scheme allowlist, and the `VAULT_CAPTURE_PYTHON` interpreter contract). This round closes findings F-01..F-06 from `REVIEW.md` and implements the v2 increments.

## Round 2 Preflight

Baseline unchanged: `main @ b7cf1bf63caeb8947120e1c6b3276d81db78bcae`. Worktree before this round: round-1 modified files (11) + untracked `network_security.py`, `test_network_security.py`, task package. No overlapping user changes; SPEC/REVIEW untouched (reviewer-owned). Reviewed approved `SPEC.md` (v2, status approved) and round-1 `REVIEW.md`.

## Round 1 finding closure (F-01..F-06)

| Finding | Severity | Closure in this round | Evidence |
|---|---|---|---|
| F-01 non-canonical numeric IPv4 bypass | major | `validate_domain_url_syntax` now also rejects any hostname parseable by `socket.inet_aton` (one-part decimal/hex, octal, shorthand) via `host.isascii()`-guarded `inet_aton`; canonical IPv6/IPv4 already rejected. `validate_url` uses the same syntax gate so globally-routable numeric forms are rejected. | `LegacyNumericSyntaxTests` + `test_stage_rejects_ip_literal_and_credentials` legacy forms; reviewer matrix verified rejected. |
| F-02 direct finalize uncaught InvalidNetworkConfig | minor | `_policy_for(None)` translates `NetworkPolicyError`→`CaptureError(EXIT_INPUT)`; `main()` added a defensive `NetworkPolicyError`→short safe `EXIT_INPUT` JSON catch. No traceback on any path. | `test_direct_finalize_invalid_network_env_no_traceback`. |
| F-03 DoH host not encoded / IDN UnicodeEncodeError | minor | `_doh_query` converts host via `_ascii_host` (IDNA) and builds the query with `urllib.parse.urlencode`; transport/encoding errors (`UnicodeError`,`ValueError`,URLError,OSError,timeout) map to `NetworkPolicyError("DoH provider request failed")`. | `DoHEncodingTests` (punycode, percent-encoding, invalid-IDN safe reject, transport-error mapping). |
| F-04 dead `ssl.create_default_context()` | minor | Removed the unused `ctx` variable; urllib's default HTTPS handler still verifies certificates; no-redirect preserved. | compile + existing DoH tests. |
| F-05 Playwright non-HTTP(S) continue-all | minor | `_make_navigation_guard` now allowlists `{data, blob, about, chrome}`; all other non-HTTP(S) schemes (including `file`) abort; HTTP(S) still validated by policy. | `NavigationGuardTests` (file abort, data/blob/about/chrome continue, ftp abort). |
| F-06 AC-10 real E2E first-run interpreter | blocker | Repository-side contract implemented: `VAULT_CAPTURE_PYTHON` (quoted `"${VAULT_CAPTURE_PYTHON:-python3}"`) used by every Python command in `SKILL.md`, not in `requires.env`, no host path persisted; docs describe dedicated-venv usage and import verification. External setting/rerun of VAL-09..11 is planner-owned. | `test_skill_python_commands_use_quoted_interpreter_fallback`; VAL-01..08 pass; AC-10 remains NOT_RUN (planner). |

## Round 2 Implementation summary

- `network_security.py`: legacy numeric IPv4 (inet_aton) rejection in syntax; `_ascii_host` IDNA helper; DoH query built with `urlencode`; removed dead TLS context; `NetworkPolicy.validate_url` uses ASCII host for resolver/DoH; encoding/transport exceptions mapped to `NetworkPolicyError`.
- `vault_capture.py`: `_policy_for` converts env-policy build errors to `CaptureError`; `main()` defensive `NetworkPolicyError` catch.
- `web_extract.py`: Playwright guard explicit local-scheme allowlist `{data, blob, about, chrome}`; others (incl. `file`) abort.
- `SKILL.md` + specs/refs/harness README: `VAULT_CAPTURE_PYTHON` interpreter contract (quoted fallback, optional, not in requires.env); narrow D-018/capture-workflow notes.
- `tests/skills/live_wechat_smoke.py`: removed the now-inert `VAULT_CAPTURE_ALLOW_PRIVATE_ASSETS` assignment (acceptance semantics unchanged).
- Tests: `test_network_security.py` (41), `test_web_extract.py` (34), `test_vault_capture.py` (22) — added legacy-numeric matrix, IDN/DoH encoding, scheme-guard, direct-finalize safe-env, and interpreter-command contract.

## Round 2 Changed files

- `skills/vault-capture/scripts/network_security.py` — numeric/IPv4 + IDNA/DoH hardening (STEP-22).
- `skills/vault-capture/scripts/vault_capture.py` — safe env-policy error on direct finalize + main safety net (STEP-23).
- `skills/vault-capture/scripts/web_extract.py` — Playwright scheme allowlist (STEP-23).
- `skills/vault-capture/SKILL.md` — quoted interpreter fallback for every command (STEP-24).
- `specifications/openclaw-skill-workflow.md` — §4.2 interpreter contract (STEP-24).
- `skills/vault-capture/references/runtime-contract.md` — interpreter note (STEP-24).
- `skills/vault-capture/references/web-runtime.md` — interpreter + operating guide (STEP-24).
- `tests/opencode-harness/README.md` — interpreter + exact-first-ready verification note (STEP-24).
- `DECISIONS.md` — D-018 boundary interpreter note (STEP-24).
- `specifications/capture-workflow.md` — interpreter note (STEP-24).
- `tests/skills/live_wechat_smoke.py` — removed inert private-assets env assignment (STEP-25).
- `tests/skills/test_network_security.py` — legacy numeric + DoH/IDN tests (STEP-25).
- `tests/skills/test_web_extract.py` — scheme-guard tests (STEP-25).
- `tests/skills/test_vault_capture.py` — stage legacy forms, direct-finalize safe env, interpreter contract (STEP-25).

## Round 2 Acceptance evidence (v2)

- AC-01..AC-09: PASS — re-verified via VAL-01..08 (see below); all prior evidence retained.
- AC-02 (now includes legacy numeric IPv4, incl. global forms): PASS — `LegacyNumericSyntaxTests`, `test_legacy_numeric_rejected_at_validate_url`, and stage legacy-form rejection.
- AC-03/04: PASS — unchanged, re-run in VAL-01.
- AC-05/06: PASS — scheme-guard tests + VAL-06 (no production/helper read of the two private env vars; only DECISIONS.md removal/rollback documentation remains).
- AC-07: PASS — lifecycle tests unchanged, re-run in VAL-03.
- AC-08: PASS — D-018 and all docs consistent (interpreter contract + Fake-IP config); VAL-07 clean.
- AC-09: PASS — VAL-01..08 all exit 0; only allowed paths changed (now including `tests/skills/live_wechat_smoke.py`).
- AC-10: NOT_RUN — planner-owned real E2E (VAL-09..11). Repository-side interpreter contract is complete; external setting of `VAULT_CAPTURE_PYTHON`/Fake-IP env and rerun are the planner's responsibility.
- AC-11 (safe edge handling): PASS — invalid network config on direct finalize (no traceback, short safe error), IDN/encoded DoH names, unexpected DoH encoding/transport failures → `NetworkPolicyError`; Playwright aborts unapproved non-HTTP(S) schemes (incl. `file`).

## Round 2 Validation log

All commands in `/home/monottx/repos/knowledge-vault-blueprint` (web tests use disposable venv `/tmp/vc-venv`, browser `/tmp/vc-browsers`):

- VAL-01 `python tests/skills/test_network_security.py` — exit 0, 41 tests OK.
- VAL-02 `PLAYWRIGHT_BROWSERS_PATH=/tmp/vc-browsers python tests/skills/test_web_extract.py` — exit 0, 34 tests OK.
- VAL-03 `python tests/skills/test_vault_capture.py` — exit 0, 22 tests OK.
- VAL-04 `python -m compileall -q skills/vault-capture/scripts tests/skills` — exit 0.
- VAL-05 `bash tests/opencode-harness/test_capture_debug.sh` — exit 0, 19 PASS / 0 FAIL.
- VAL-06 repo search for the two private env vars — only DECISIONS.md removal/rollback documentation hits; `live_wechat_smoke.py` no longer sets the var.
- VAL-07 task-scoped `git diff --check b7cf1bf...` — exit 0, no output.
- VAL-08 `git status`/diff — only allowed paths changed; nothing staged/committed.
- VAL-09..11 — NOT_RUN (planner-owned real Gateway/Fake-IP/harness E2E).

## Round 2 Git state at handoff

- Branch `main` @ `b7cf1bf63caeb8947120e1c6b3276d81db78bcae` (unchanged).
- Worktree: 12 modified allowed files (adds `tests/skills/live_wechat_smoke.py`) + 3 untracked (`network_security.py`, `test_network_security.py`, task package).
- Nothing staged; nothing committed; nothing pushed.

---

# Round 3 (spec_version 2, minimal fixes)

> Round 2 returned `CHANGES_REQUESTED` with two open findings: F-01 residual (IDNA-mapped/trailing-dot numeric IP literals pass syntax) and F-07 (real host path persisted in a specification). This round closes both within the existing v2 allowed paths. No target/scope/path/AC change; no replan.

## Round 3 Preflight

Baseline unchanged: `main @ b7cf1bf63caeb8947120e1c6b3276d81db78bcae`. Worktree before this round: round-2 state (12 modified allowed files + 3 untracked). No overlapping user changes; `SPEC.md`/`REVIEW.md` untouched (reviewer-owned). Read approved `SPEC.md` v2 and round-2 `REVIEW.md` (verdict `changes_requested`).

## Round 3 finding closure (F-01 residual, F-07; optional nit)

| Finding | Severity | Closure |
|---|---|---|
| F-01 residual — IDNA-mapped numeric spellings (`１２３.0.0.1`, `123。0。0。1`, `123.0.0.１`), trailing-dot numeric (`1.2.3.4.`, `2130706433.`) pass syntax | major | `validate_domain_url_syntax` now obtains the canonical ASCII IDNA host via `_ascii_host(host)` and runs canonical `ipaddress.ip_address` + legacy `socket.inet_aton` literal checks on that ASCII host and on its single-trailing-dot-stripped form (`_literal_candidates`). All numeric/IDNA/trailing-dot forms are rejected at syntax before any resolver/DoH call; normal FQDN trailing dot (`example.com.`) and valid IDN (`例子.测试`, `xn--fsqu00a.xn--0zwm56d`) remain allowed. `validate_url` reuses the same syntax gate, so the resolver/DoH are never consulted for numeric spellings (asserted). Also removed the now-unused `import ssl` (reviewer nit). |
| F-07 — real test-machine path `/home/monottx/.local/share/vault-capture/venv/bin/python` in `openclaw-skill-workflow.md` | minor | Replaced with generic placeholder `/path/to/vault-capture/venv/bin/python`. Verified no non-task file in `skills/`, `specifications/`, `DECISIONS.md`, `tests/skills/` persists the real path. |
| F-02..F-06 (closed round 2) | — | Not regressed; all prior closures re-verified by full VAL-01..08 rerun. |

## Round 3 Changed files

- `skills/vault-capture/scripts/network_security.py` — `validate_domain_url_syntax` runs literal checks on the IDNA-canonical host and its single-trailing-dot-stripped form (`_reject_literal_host`/`_literal_candidates`); removed unused `import ssl`. (STEP-32)
- `tests/skills/test_network_security.py` — added fullwidth/ideographic-dot/trailing-dot numeric rejection matrix, FQDN/IDN allow matrix, and resolver-zero assertions. (STEP-33)
- `specifications/openclaw-skill-workflow.md` — genericized the `VAULT_CAPTURE_PYTHON` venv interpreter example (removed real host path). (STEP-34)
- `tasks/2026-08-09-vault-capture-fake-ip-ssrf/EXECUTION.md` — round-3 record. (STEP-31/35)

## Round 3 Acceptance evidence (v2)

- AC-01..AC-09: PASS — re-verified via VAL-01..08 (below); all prior evidence retained.
- AC-02 (now includes IDNA-mapped and trailing-dot numeric forms incl. global mappings): PASS — `LegacyNumericSyntaxTests.test_idna_mapped_numeric_spellings_rejected`, `test_trailing_dot_numeric_spellings_rejected`, `test_idna_mapped_numeric_rejected_at_validate_url`, `test_numeric_spellings_do_not_call_resolver`; normal FQDN trailing dot and valid IDN pass (`test_trailing_dot_and_idn_domains_allowed`).
- AC-10: PASS (planner evidence, not rerun) — reviewer round-2 §4 AC-10: planner VAL-09 (system resolver `www.rfc-editor.org`→`198.18.0.71`, fake_ip=True; agent reported dedicated venv + `trafilatura 2.1.0`), VAL-10 (fresh capture `20260809-132214-20zb`, first observed terminal exactly `ready`, all assertions PASS, ID-directed cleanup), VAL-11 (settings restored, live vault untouched). Executor/planner do not rerun VAL-09..11.
- AC-11: PASS — unchanged and re-verified via VAL-01/02/03 (direct-finalize safe env, IDN/encoded DoH, transport-error mapping, Playwright scheme guard).

## Round 3 Validation log

All in `/home/monottx/repos/knowledge-vault-blueprint` (web tests use disposable venv `/tmp/vc-venv`, browser `/tmp/vc-browsers`):

- VAL-01 `python tests/skills/test_network_security.py` — exit 0, 46 tests OK.
- VAL-02 `PLAYWRIGHT_BROWSERS_PATH=/tmp/vc-browsers python tests/skills/test_web_extract.py` — exit 0, 34 tests OK.
- VAL-03 `python tests/skills/test_vault_capture.py` — exit 0, 22 tests OK.
- VAL-04 `python -m compileall -q skills/vault-capture/scripts tests/skills` — exit 0.
- VAL-05 `bash tests/opencode-harness/test_capture_debug.sh` — exit 0, 19 PASS / 0 FAIL.
- VAL-06 narrow search for the two private env vars — only `DECISIONS.md` removal/rollback documentation; no production/helper read; smoke helper no longer sets the var.
- Extra manual probe: reviewer F-01 matrix (fullwidth digits, ideographic dots, mixed, canonical/legacy/trailing-dot, global/private) all REJECTED at syntax; `example.com`, `example.com.`, `例子.测试`, `xn--fsqu00a.xn--0zwm56d`, `foo_bar.com`, `localhost` all PASS; resolver zero-call confirmed for numeric spellings.
- F-07 host-path check: no `/home/monottx/.local/share/vault-capture` in `skills/`, `specifications/`, `DECISIONS.md`, `tests/skills/`.
- VAL-07 task-scoped `git diff --check b7cf1bf...` — exit 0, no output.
- VAL-08 `git status`/diff — only allowed paths changed; nothing staged/committed.
- VAL-09..11 — not rerun; existing planner evidence (round-2 reviewer §4, AC-10 PASS) referenced as-is.

## Round 3 Git state at handoff

- Branch `main` @ `b7cf1bf63caeb8947120e1c6b3276d81db78bcae` (unchanged).
- Worktree: 12 modified allowed files + 3 untracked (`network_security.py`, `test_network_security.py`, task package). The four round-3 files are subsets of the allowed paths.
- Nothing staged; nothing committed; nothing pushed.


