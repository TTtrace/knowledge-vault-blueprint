---
task_id: 2026-08-09-vault-capture-fake-ip-ssrf
title: Fake-IP-aware SSRF validation for vault-capture
status: approved
spec_version: 2
planner: primary
executor: executor
created: 2026-08-09
approved_at: 2026-08-09T13:00:08+08:00
approved_by: user
---

# Task Specification

> This file is owned by the planner. After `status: approved`, the executor must not edit it. A material change returns it to `draft`, increments `spec_version`, and requires approval again.

## 1. Context and problem

`vault-capture` rejects every non-global result returned by system DNS. Clash/FlClash TUN Fake-IP mode intentionally resolves public domains into `198.18.0.0/15`, so a legitimate public article currently ends in `failed` with `URL resolves to a non-public address`. The previous web-ingestion task worked around this only by disabling the proxy; that does not validate the real production network shape.

The repository also exposes `VAULT_CAPTURE_ALLOW_PRIVATE_FETCH=1` to the runtime and uses separate SSRF implementations for article fetch, Playwright requests, and image downloads. The image downloader permits automatic redirects and validates only the final URL, so the security contract is not uniformly enforced before every connection.

This task adds a single fail-closed network policy that recognizes Fake-IP only as a proxy-environment signal, independently resolves the domain through a trusted DoH provider, and permits the request only when every real A/AAAA result is globally routable. It does not authorize private-network fetching.

Planning baseline was recorded after approval because planner Bash use required approval. The worktree was clean, so no overlap or scope exception was introduced.

Review round 1 returned `NEEDS_REPLAN`. Independent review found that non-canonical numeric IPv4 forms were not rejected as literals, direct `finalize` could expose an uncaught invalid-network-config traceback, and DoH query parameters were not safely encoded. The real harness also proved that the test agent ignored the skill-entry `PATH` override and used `/usr/bin/python3` without Trafilatura on its first attempt; a later concurrent attempt reached `ready`, but the harness correctly failed on the first terminal `failed`. Version 2 adds a narrow explicit interpreter-path contract for the test/runtime skill entry and authorizes that external test setting. Exact-`ready` semantics remain unchanged.

## 2. Required outcome

By default, current fail-closed behavior remains: a hostname resolving to `198.18.0.0/15` is rejected. Operators may explicitly enable Clash Fake-IP awareness with `VAULT_CAPTURE_SSRF_FAKE_IP_MODE=clash` and select a built-in trusted provider using `VAULT_CAPTURE_SSRF_DOH_PROVIDER=cloudflare|google`. In that mode, Fake-IP system answers are accepted only as a signal to resolve A and AAAA independently over trusted HTTPS; at least one address must exist and every returned address must be public.

All user/redirect/asset targets must use DNS hostnames. IPv4 and IPv6 literals, including public literals and direct Fake-IP URLs, remain forbidden. Initial pages, static redirects, Playwright document/subresource redirects, retained body images, and image redirects must apply the same policy before connection. `VAULT_CAPTURE_ALLOW_PRIVATE_FETCH` must be removed from production behavior with no equivalent broad bypass.

The completed behavior must be demonstrated through the real NotesVaulter agent and `tests/opencode-harness/capture_debug.sh`, in a strict `*-test` Vault, while the runtime observes a Fake-IP system answer and the web capture reaches exact terminal state `ready`.

Every skill command must use one optional operator-supplied executable path, `VAULT_CAPTURE_PYTHON`, falling back to `python3` when unset. This is host configuration, not a repository path or dependency installer. The E2E test agent will point it at the existing dedicated vault-capture virtual environment so the first ingestion attempt uses the validated runtime.

## 3. Non-goals

- Do not permit localhost, RFC1918, link-local, reserved, documentation, multicast, cloud-metadata, or arbitrary private destinations.
- Do not add private host/CIDR allowlists, arbitrary DoH endpoint URLs, system-DNS discovery, proxy configuration, or Clash rule management.
- Do not accept direct IPv4/IPv6 URL literals, even when the literal is globally routable.
- Do not change Source/Annotation meaning, capture/read lifecycles, extraction quality gates, naming, image limits, or atomic Git staging.
- Do not change `schema_version`, bulk-migrate Vault files, or write automated data to the live `SourceNotes` Vault.
- Do not add Python dependencies, modify global Python/browser installations, commit, push, merge, tag, release, deploy, or publish.
- Do not change the harness to wait through or accept a transient `failed`, and do not treat later failed→ready retry recovery as success.

## 4. Locked decisions

- Explicit activation requires both exact values: `VAULT_CAPTURE_SSRF_FAKE_IP_MODE=clash` and `VAULT_CAPTURE_SSRF_DOH_PROVIDER=cloudflare|google`. Missing, partial, or invalid configuration does not enable Fake-IP handling.
- Provider IDs map to fixed, code-owned HTTPS DNS JSON endpoints. Arbitrary endpoint configuration and insecure HTTP are forbidden. Calls use normal certificate verification, bounded timeout/response size, no credentials, and no unsafe redirect.
- URL syntax validation is network-free and requires absolute HTTP(S), no credentials, a DNS hostname, and no IPv4/IPv6 literal. It is applied during `stage` and again at every network boundary.
- “IP literal” includes canonical IPv4/IPv6 and legacy numeric IPv4 spellings accepted by the host resolver (`inet_aton`-style one-part, shorthand, octal, and hexadecimal forms). All are rejected during syntax validation, including globally routable numeric forms.
- DoH query parameters use standard URL encoding. IDN hostnames are converted consistently or rejected with a short policy error, and unexpected encoding/transport exceptions are translated into `NetworkPolicyError` rather than escaping as tracebacks.
- Default mode requires every system resolver address to be globally routable. Clash mode still rejects every non-global system answer outside `198.18.0.0/15`.
- When any system answer is in `198.18.0.0/15`, Clash mode must query both A and AAAA through the selected trusted provider. At least one real IP must be returned and every returned A/AAAA value must satisfy `ipaddress.ip_address(...).is_global`.
- DoH timeout, TLS/HTTP error, DNS non-success, malformed/oversized data, no A/AAAA, or any non-global real answer fails closed. Safe error text must not contain raw DNS payloads, host configuration, stack traces, or absolute paths.
- Fake-IP is never considered a real destination and can never be supplied directly as a URL. It only indicates that the local proxy will carry a domain-named request whose real DNS identity was independently validated.
- Redirect clients must not connect before validation. Automatic redirects are disabled where needed; every resolved `Location` is syntax/address validated before the next request. Browser route checks cover documents and subresources, including redirected requests. Retained image downloads use equivalent manual redirect handling.
- A bounded resolver cache may be used only if it does not skip URL validation or redirect-target validation. Static and image redirect targets must force policy validation before each next connection.
- Production code must not read `VAULT_CAPTURE_ALLOW_PRIVATE_FETCH` and must not add an equivalent broad override. Local fixture tests may use scoped injected validators/transports that cannot be enabled by runtime environment configuration.
- Direct `finalize`, `ingest-web`, and image paths translate invalid/partial Fake-IP configuration into short safe command/failure semantics; no `NetworkPolicyError`, `UnicodeEncodeError`, or traceback may escape the CLI.
- Playwright continues only explicitly required local browser schemes (`data`, `blob`, `about`, and `chrome` where applicable); other non-HTTP(S) schemes, including `file`, are aborted.
- `VAULT_CAPTURE_PYTHON` is an optional, quoted executable-path setting used by every command example in `SKILL.md`. It is not added to `requires.env`, has no default host path in the repository, does not install dependencies, and grants no network-policy bypass. Test configuration points it to the existing dedicated vault-capture venv interpreter.
- Use the Python standard library for DNS JSON HTTPS calls; do not change web dependency files.
- No metadata meaning changes: `schema_version` stays `1`. Record a new architecture/security decision and explicit rollback rather than a schema migration.

## 5. Repository baselines

Approval/baseline observation: `2026-08-09T08:34:07+08:00`.

| Repository | Absolute path | Base branch | Base commit | Existing worktree changes | Working branch |
|---|---|---|---|---|---|
| `knowledge-vault-blueprint` | `/home/monottx/repos/knowledge-vault-blueprint` | `main` | `b7cf1bf63caeb8947120e1c6b3276d81db78bcae` | clean; task package is the expected planner-created post-baseline addition | existing `main`, one commit ahead of `origin/main`; no branch switch authorized |

`SourceNotes` is out of implementation scope. `/home/monottx/repos/SourceNotes-test` is permitted only for planner-owned OpenClaw harness execution and ID-directed cleanup; it is not an implementation repository.

## 6. Scope by repository

### knowledge-vault-blueprint

Expected changes:

- Centralize domain-only URL, system DNS, Fake-IP, trusted DoH, and redirect validation.
- Apply that policy to stage input, static fetch, Playwright requests, retained image fetches, and redirects.
- Remove the production private-fetch override.
- Update the architecture decision, capture/security/runtime/OpenClaw contracts, tests, harness guidance, execution evidence, and review record.

Allowed paths:

- `DECISIONS.md`
- `specifications/capture-workflow.md`
- `specifications/openclaw-skill-workflow.md`
- `skills/vault-capture/SKILL.md`
- `skills/vault-capture/references/runtime-contract.md`
- `skills/vault-capture/references/web-runtime.md`
- `skills/vault-capture/scripts/network_security.py` (new)
- `skills/vault-capture/scripts/web_extract.py`
- `skills/vault-capture/scripts/vault_capture.py`
- `tests/skills/test_network_security.py` (new)
- `tests/skills/test_web_extract.py`
- `tests/skills/test_vault_capture.py`
- `tests/skills/live_wechat_smoke.py` only to remove the now-inert historical private-assets environment assignment and align the helper with the shared policy; its acceptance semantics must not expand
- `tests/opencode-harness/README.md`
- `tests/opencode-harness/test_capture_debug.sh` only if a regression assertion must change; default `ready` semantics must not be weakened
- `tasks/2026-08-09-vault-capture-fake-ip-ssrf/EXECUTION.md` (executor)
- `tasks/2026-08-09-vault-capture-fake-ip-ssrf/REVIEW.md` (reviewer only)

Forbidden paths:

- `tasks/2026-08-09-vault-capture-fake-ip-ssrf/SPEC.md` after approval
- `skills/vault-capture/requirements-web.txt`
- `skills/vault-capture/requirements-web.lock`
- `specifications/metadata-schema.md`
- `AGENTS.md`
- `tasks/README.md`
- `tasks/_template/**`
- `vault-starter/**`
- every path not explicitly allowed above

### SourceNotes and external runtime

Expected implementation changes: none.

Allowed runtime actions, planner only:

- Read the current NotesVaulter test-agent/Gateway configuration without printing secrets.
- For E2E only, inject the two approved Fake-IP settings plus `VAULT_CAPTURE_PYTHON` pointing to the existing dedicated test runtime into the test `vault-capture` skill entry, and reload/restart only the test Gateway if required.
- Record prior values and restore them after validation.
- Run the harness only against a Git Vault whose basename ends in `-test`; use `--cleanup`.

Forbidden:

- Any write to the live `SourceNotes` Vault.
- Persisting secrets or host paths in this repository.
- Changing production Gateway/agent configuration when test/production isolation cannot be proven.
- Executor changes outside the blueprint repository.

## 7. Invariants and safety constraints

- Preserve unrelated and pre-existing worktree/index changes; stop rather than overwrite them.
- Preserve Source body immutability, one capture-managed Annotation per Source, permanent IDs, capture/read lifecycle separation, and ID-directed Git staging.
- The Source stub must still land before web ingestion. SSRF rejection must result in a short safe `failed` record without losing the captured URL.
- Do not log raw DoH responses, cookies, authorization data, environment contents, browser-profile paths, stack traces, or absolute Vault paths.
- Do not weaken browser request validation, content quality gates, image completeness, response/image size limits, or redirect limits.
- DoH validates real destination identity but does not authorize direct connection to Fake-IP input or private real addresses.
- Test-only private fixture access must not be reachable through production environment configuration.
- The interpreter override is quoted, operator-controlled, and limited to selecting an existing Python executable; it must not be evaluated as shell text or persisted in repository content.
- No stage/commit/push/merge/tag/release/deploy/publish is authorized in the blueprint repository.

## 8. Acceptance criteria

- [ ] **AC-01 — Default fail-closed:** With no Fake-IP settings, a domain whose system answer is in `198.18.0.0/15` fails before target connection, with a short non-sensitive error.
- [ ] **AC-02 — Domain-only contract:** Domain HTTP(S) input is accepted syntactically; credentials, non-HTTP schemes, canonical IPv4/IPv6, direct Fake-IP, and legacy numeric IPv4 forms (one-part decimal/hex, octal, and shorthand) are rejected at stage and network boundaries, including numeric forms representing global addresses.
- [ ] **AC-03 — Explicit activation:** Only the exact approved mode plus a built-in provider enables Fake-IP handling. Missing/partial/unknown values fail closed and do not silently fall back to private access.
- [ ] **AC-04 — Trusted real A/AAAA:** When Fake-IP is observed, both A and AAAA are queried through the selected fixed provider. At least one address exists and all answers are global. Timeout, bad status/data, no addresses, or one non-global result rejects the target.
- [ ] **AC-05 — Redirect and surface coverage:** Initial static fetch, every static redirect, Playwright documents/subresources including redirects, retained images, and every image redirect run the shared policy before connection. Tests prove redirect-to-private/direct-IP targets are never connected.
- [ ] **AC-06 — No broad bypass:** Production code no longer reads `VAULT_CAPTURE_ALLOW_PRIVATE_FETCH`, and repository search plus tests find no equivalent environment-controlled private-fetch bypass.
- [ ] **AC-07 — Lifecycle compatibility:** A rejected web target keeps its staged Source and reaches safe `failed`; a validated Fake-IP/DoH web target still completes the existing atomic `ready`, image, final-name, and Git-staging transaction.
- [ ] **AC-08 — Contract and rollback consistency:** D-018 and all capture/OpenClaw/runtime/security documents agree on configuration, trust boundary, errors, no schema migration, and rollback.
- [ ] **AC-09 — Regression and scope:** New security tests and all existing web/capture/harness tests pass; compile check and task-scoped `git diff --check` pass; only allowed paths change.
- [ ] **AC-10 — Real OpenClaw E2E:** In `SourceNotes-test`, the runtime is proven to observe a `198.18.0.0/15` answer for the chosen domain, explicit Clash/DoH settings and the existing dedicated-venv `VAULT_CAPTURE_PYTHON` are active, and planner first verifies through the agent that the configured interpreter imports Trafilatura. Planner then runs `capture_debug.sh web ... --wait 180 --assert --cleanup` with a unique RFC URL. The harness meets its README envelope/ID/staging checks and the first observed terminal state is exactly `ready`, not transient `failed`, later retry recovery, `manual`, `terminal`, or timeout.
- [ ] **AC-11 — Safe edge handling:** Invalid network configuration on direct `finalize`, IDN/encoded DoH names, and unexpected DoH encoding/transport failures produce short fail-closed errors without raw traceback; Playwright aborts unapproved non-HTTP(S) schemes.

## 9. Validation plan

| ID | Working directory | Exact command or inspection | Expected result | AC mapping |
|---|---|---|---|---|
| `VAL-01` | `/home/monottx/repos/knowledge-vault-blueprint` | `python tests/skills/test_network_security.py` | Exit 0; canonical/legacy numeric literals, domain, mode/provider, Fake-IP, encoded DoH A/AAAA, all-public, safe-error and redirect-policy tests pass. | AC-01..06,11 |
| `VAL-02` | same | `python tests/skills/test_web_extract.py` | Exit 0; static, browser, redirects, quality gates, and extraction tests pass. | AC-04,05,09 |
| `VAL-03` | same | `python tests/skills/test_vault_capture.py` | Exit 0; stage rejection including legacy numeric forms, failed preservation, safe direct-finalize config handling, ready transaction, images, Git staging, interpreter-command contract, and regressions pass. | AC-02,05,07,09,11 |
| `VAL-04` | same | `python -m compileall -q skills/vault-capture/scripts tests/skills` | Exit 0. | AC-09 |
| `VAL-05` | same | `bash tests/opencode-harness/test_capture_debug.sh` | Exit 0; harness guard/assert/cleanup contract unchanged. | AC-09 |
| `VAL-06` | same | Repository search for `VAULT_CAPTURE_ALLOW_PRIVATE_FETCH`, `VAULT_CAPTURE_ALLOW_PRIVATE_ASSETS`, and equivalent runtime bypasses in production scripts/docs/helpers | No production/helper read or documented bypass; historical task records may retain history. | AC-06 |
| `VAL-07` | same | `git diff --check b7cf1bf63caeb8947120e1c6b3276d81db78bcae -- DECISIONS.md specifications/capture-workflow.md specifications/openclaw-skill-workflow.md skills/vault-capture tests/skills tests/opencode-harness tasks/2026-08-09-vault-capture-fake-ip-ssrf` | Exit 0, no output. | AC-08,09 |
| `VAL-08` | same | Compare `git status --short`, diff, and changed paths to §5-6 | Baseline clean state is preserved except allowed task files; no staging/commit. | AC-09 |
| `VAL-09` | test Gateway host/context | Resolve the selected RFC host using the same system resolver context used by NotesVaulter and classify with Python `ipaddress`; then invoke a no-Vault-write agent diagnostic using configured `VAULT_CAPTURE_PYTHON` to report `sys.executable` and import Trafilatura | At least one observed system answer is within `198.18.0.0/15`; agent reports the existing dedicated venv executable and successful import. Output contains no secrets. | AC-10 |
| `VAL-10` | `/home/monottx/repos/knowledge-vault-blueprint` | `stamp="$(date +%Y%m%d-%H%M%S)"; ./tests/opencode-harness/capture_debug.sh web "收：https://www.rfc-editor.org/rfc/rfc9110.html?vault_capture_fake_ip_test=$stamp" --wait 180 --assert --cleanup --session "fake-ip-ssrf-$stamp"` | Exit 0; README contract passes; unique Source ID and new ID-scoped staging observed; first observed terminal state is exact `ready`; cleanup is ID-directed. | AC-10 |
| `VAL-11` | test Gateway configuration | Compare the three relevant env settings and Gateway/test Vault state with the recorded pre-E2E baseline | Prior values restored; no live Vault touched; no test artifact left except harness diagnostics under its ignored output path. | AC-10, rollback |

## 10. Deliverables

- Approved task package with completed `EXECUTION.md` and independently accepted `REVIEW.md`.
- Shared Fake-IP-aware SSRF policy and integration across all approved outbound surfaces.
- Security decision/contracts and explicit rollback/configuration guidance.
- Deterministic unit/integration regressions and recorded real OpenClaw `ready` evidence.
- Executor fixed-format structured return and final Git state.

## 11. Git and external-action permissions

- Branching: `not authorized`; remain on `main`.
- Staging blueprint files: `not authorized`.
- Committing/pushing/merging/tagging/releasing/deploying/publishing: `not authorized`.
- Test-vault staging: authorized only as normal harness behavior for the unique E2E Source ID, followed by `--cleanup`.
- Read-only network: authorized for fixed DoH resolution and the explicit RFC E2E URL.
- External configuration: planner-only, test agent/Gateway only, limited to the two approved SSRF env settings, `VAULT_CAPTURE_PYTHON` pointing to the existing dedicated venv, and required reload; record and restore prior state. If isolation cannot be proven, stop `BLOCKED`.

## 12. Rollback

- Remove/restore the two test-agent Fake-IP settings and `VAULT_CAPTURE_PYTHON` to their exact prior values; reload only the test Gateway if it was reloaded for validation.
- Revert only this task's allowed implementation/document/test paths to baseline; never reset or clean the repository and never overwrite unrelated user work.
- Remove the shared policy and restore the previous callers coherently, but do not reintroduce `VAULT_CAPTURE_ALLOW_PRIVATE_FETCH` as an operational workaround. If a full historical rollback necessarily restores that old source line, leave the environment variable unset and document that the rolled-back version remains unsafe for Fake-IP use.
- No schema or Vault migration exists. Existing Source files created by ordinary capture remain normal Git-visible data and are not bulk rewritten.
- E2E uses `--cleanup`; if it cannot identify one unique Source ID, cleanup must stop rather than guess. Any manual cleanup must be ID-directed.

## 13. Open questions

- none. Configuration names, trusted providers, address policy, interpreter selection, redirect scope, repository paths, validation, and rollback are locked.

## 14. Approval record

- Version 1 approval statement: `“批准第一层计划”`
- Version 1 approved at: `2026-08-09T08:34:07+08:00`
- Version 2 approval statement: `批准 spec v2`
- Version 2 approved at: `2026-08-09T13:00:08+08:00`
