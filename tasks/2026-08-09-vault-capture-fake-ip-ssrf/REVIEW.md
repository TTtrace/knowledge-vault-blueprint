---
task_id: 2026-08-09-vault-capture-fake-ip-ssrf
status: accepted
review_round: 3
reviewer: reviewer
reviewed_at: 2026-08-09T14:55:00+08:00
verdict: accepted
---

# Review Record

> This file is owned by the reviewer. Review the repository and evidence independently; do not accept the executor's summary as proof by itself.

## Round 3 (spec_version 2, final round — verdict: PASS/accepted)

### 1. Review scope and observed state

Independent re-read of `SPEC.md` v2 (unchanged since v2 approval; mtime 13:00:19), `EXECUTION.md` round-3 section (mtime 13:39:11), cumulative `git diff` vs baseline `b7cf1bf63caeb8947120e1c6b3276d81db78bcae`, and the round-3 code. Reviewer re-ran VAL-01..07 and a new F-01 adversarial matrix. Executor summary treated as claims only; every claim below re-derived.

Round-3 delta verified by content + mtime: exactly four files changed this round — `network_security.py` (13:35), `test_network_security.py` (13:36), `openclaw-skill-workflow.md` (13:36), `EXECUTION.md` (13:39); all other files retain round-2 mtimes (13:06–13:14). No undisclosed changes. HEAD == baseline; index empty; nothing committed/pushed.

### 2. Findings — final status (stable IDs across rounds)

- **F-01 [major] — CLOSED (round 3).** `validate_domain_url_syntax` now canonicalizes via `_ascii_host` first, then applies `ipaddress` + `socket.inet_aton` checks to the ASCII host and its single-trailing-dot-stripped candidate (`_reject_literal_host`/`_literal_candidates`, network_security.py:114-152,175-181). Reviewer matrix (all rejected at syntax): canonical IPv4/IPv6, one-part decimal/hex, octal, shorthand, `0xffffffff`, `1.2.3`, case variants, **round-2 residuals** `１２３.0.0.1`, `123。0。0。1`, `123.0.0.１`, `１９８.１８.0.7`, `1.2.3.4.`, `2130706433.`, `0x5db8d822.`, `93.184.` — 27/27 rejected. Full `validate_url` with a permissive fake resolver makes **zero resolver calls** for numeric spellings; real-resolver probe: `http://１２３.0.0.1/` → DENY "IP address literals are not allowed". False-positive matrix (10 hosts: `example.com.`, `例子.测试`, `xn--fsqu00a.xn--0zwm56d`, `foo_bar.com`, `localhost`, numeric-prefix domains, etc.) — none rejected. fix verified; AC-02 fully met.
- **F-02 [minor] — CLOSED (round 2), re-verified round 3** via VAL-03 (`test_direct_finalize_invalid_network_env_no_traceback`: exit 2, no Traceback, no path/value leak).
- **F-03 [minor] — CLOSED (round 2), re-verified round 3** via VAL-01 (`DoHEncodingTests`: punycode query, percent-encoding, invalid-IDN safe reject, transport-error mapping).
- **F-04 [minor] — CLOSED (round 2/3).** DoH dead `ctx` removed round 2; round 3 also removed the now-unused `import ssl`. Static grep: no TLS verification tampering anywhere in `skills/`. (Pre-existing baseline dead `ctx` at `web_extract.py:191` predates this task — baseline :187 — and is out of scope; verification unaffected.)
- **F-05 [minor] — CLOSED (round 2), re-verified round 3** via VAL-02 (file/ftp abort; data/blob/about/chrome continue).
- **F-06 [blocker, round 1] — CLOSED (round 2 plan + planner E2E).** Interpreter contract implemented and proven in the real harness (see AC-10). Round-3 did not touch it; `test_skill_python_commands_use_quoted_interpreter_fallback` passes in VAL-03 rerun.
- **F-07 [minor] — CLOSED (round 3).** `openclaw-skill-workflow.md:137` now uses generic `/path/to/vault-capture/venv/bin/python`. Reviewer grep: no real host path in `specifications/`, `skills/`, `DECISIONS.md`, `tests/skills/`. Remaining `/home/...` occurrences are all pre-existing baseline content (`capture_debug.sh:38` default, README:166 — baseline :160) or untracked ignored harness diagnostics (`tests/opencode-harness/out/*.json`, `git ls-files` count 0 — explicitly permitted by VAL-11). Task-package audit records retain history as allowed.

No open findings. Deviation audit: the single round-3 deviation (unused-`ssl` removal) verified; no undisclosed deviations.

### 3. Scope compliance (final)

- Cumulative change set = SPEC v2 §6 allowed set exactly: 12 modified (`DECISIONS.md`, 2 specifications, `SKILL.md`, 2 references, 2 scripts, 3 tests, smoke helper, harness README) + 2 allowed new files + task package. Forbidden paths untouched (`requirements-web.*`, `metadata-schema.md`, `AGENTS.md`, `tasks/README.md`, `_template/**`, `vault-starter/**`, `capture_debug.sh`). `SPEC.md` untouched by executor in all rounds (mtimes: SPEC 13:00:19 planner < EXECUTION 13:39:11).
- Git: HEAD == baseline `b7cf1bf`; index empty; no commit/push; baseline was clean — no user changes existed or were harmed.
- External: planner's v2-authorized temporary settings (Fake-IP pair + `VAULT_CAPTURE_PYTHON`) restored per VAL-11 evidence; live `SourceNotes` untouched; test vault fully cleaned (ID-directed).

### 4. Independent acceptance check (final)

- AC-01: PASS — default-mode fake-ip fail-closed + stub preservation (VAL-01/03).
- AC-02: PASS — canonical, legacy numeric, IDNA-mapped numeric, and trailing-dot numeric forms (incl. global mappings) all rejected at stage and network boundaries, zero resolver calls; domains/IDN/FQDN unaffected (reviewer matrix + `LegacyNumericSyntaxTests`).
- AC-03: PASS — exact-pair activation only; partial/unknown fail closed.
- AC-04: PASS — fixed-provider DoH A+AAAA, all-global enforcement, full failure matrix (timeout/status/malformed/oversize/redirect/content-type/NODATA/private).
- AC-05: PASS — static per-hop redirect validation, Playwright document/subresource/redirect guard with scheme allowlist, final-URL revalidation, image manual per-hop validation (VAL-02/03).
- AC-06: PASS — no production/helper read of either private-fetch env var; only D-018 removal/rollback text (reviewer grep).
- AC-07: PASS — safe `failed` preserves stub; validated Fake-IP/DoH target completes atomic ready/final-name/image/Git-staging transaction.
- AC-08: PASS — D-018 + capture/OpenClaw/SKILL/runtime/web/harness docs mutually consistent (config names, trust boundary, safe errors, interpreter contract, schema 1, rollback); VAL-07 clean.
- AC-09: PASS — VAL-01..08 all reproduced exit 0 by reviewer (46/34/22 tests OK; compile 0; harness 19 PASS/0 FAIL; scope exact).
- AC-10: PASS (planner evidence, round-2 evaluated, stands) — VAL-09: `198.18.0.71` fake-ip observed + agent diagnostic proved configured `VAULT_CAPTURE_PYTHON` imports `trafilatura 2.1.0` (clean envelope); VAL-10: fresh unique capture `20260809-132214-20zb`, exact SPEC command, **first observed terminal exactly `ready`**, all harness assertions PASS, ID-directed cleanup; VAL-11: three temp settings restored, config validate OK, no residue, live vault untouched. Debug-history failures were disclosed, ID-directed-cleaned, and never counted.
- AC-11: PASS — direct finalize invalid env → short safe exit-2 error, no traceback; IDN/encoded DoH + transport failures → `NetworkPolicyError`; Playwright aborts unapproved non-HTTP(S) schemes.

### 5. Reviewer validation (round 3)

All in `/home/monottx/repos/knowledge-vault-blueprint`, `PATH=/tmp/vc-venv/bin:$PATH`:

- VAL-01 `python tests/skills/test_network_security.py` — exit 0, 46 OK. VAL-02 (PLAYWRIGHT_BROWSERS_PATH=/tmp/vc-browsers) — exit 0, 34 OK. VAL-03 — exit 0, 22 OK. VAL-04 compileall — exit 0. VAL-05 harness self-test — exit 0, 19 PASS/0 FAIL. VAL-06 grep — clean. VAL-07 task-scoped `git diff --check` — exit 0, no output. VAL-08 status/diff/mtime audit — allowed paths only, index empty, round-3 delta = exactly the 4 claimed files.
- Reviewer F-01 matrix (27 reject forms incl. IDNA-mapped/trailing-dot, zero-resolver-call proof, 10-host false-positive matrix, real-resolver deny) — all as required.
- Reviewer F-07 grep — formal docs free of real host paths; remaining hits are baseline content or ignored diagnostics.
- VAL-09..11 not rerun (planner-owned; existing evidence referenced per round-3 brief).

### 6. Cross-repository consistency (final)

Live `SourceNotes` never written. `SourceNotes-test` clean (final E2E ID auto-cleaned; stale diagnostic ID manually ID-directed-removed). Test-agent configuration restored to pre-E2E baseline. `schema_version` remains 1; no migration; rollback guidance intact in D-018/SPEC §12.

### 7. Round 3 verdict

- Verdict: `accepted` (PASS) — all AC-01..AC-11 satisfied; no open blocker/major/minor findings.
- Required follow-up: none. (Post-acceptance housekeeping, not review scope: committing/publishing remains unauthorized unless the user explicitly instructs.)
- Remaining risks: none identified. Note only: the pre-existing dead `ctx` at `web_extract.py:191` (baseline code, harmless) may be cleaned in some future unrelated task.
- Reviewed at: 2026-08-09T14:55:00+08:00

---

## Round 2 history (spec_version 2, verdict CHANGES_REQUESTED)

Round 2 (reviewed 2026-08-09T14:40:00+08:00) verified closure of F-02..F-06 and planner AC-10 evidence (first-exact-ready E2E PASS), but returned `changes_requested` on: F-01 residual [major] — literal checks ran on the pre-IDNA host, so IDNA-mapped numeric spellings (`１２３.0.0.1`, `123。0。0。1`) passed syntax and reached POLICY-ALLOW, and trailing-dot numeric spellings passed syntax; and F-07 [minor] — a real test-machine host path persisted in `openclaw-skill-workflow.md`. Both closed in round 3 (see above). VAL-01(41)/02(34)/03(22)/04/05/06/07/08 were reproduced exit 0 in round 2.

## Round 1 history (spec_version 1, verdict NEEDS_REPLAN)

Round 1 (reviewed 2026-08-09T10:20:00+08:00) returned `needs_replan` on F-06: the real harness twice observed first terminal `failed` because the test agent's exec used `/usr/bin/python3` without Trafilatura despite the skill-entry PATH, with an async retry later reaching `ready` — unfixable within v1-authorized actions. Round-1 findings: F-01 major (non-canonical numeric IPv4 literals allowed), F-02 minor (uncaught `InvalidNetworkConfig` traceback on direct finalize), F-03 minor (unencoded DoH host / IDN `UnicodeEncodeError`), F-04 minor (dead ssl context), F-05 minor (guard continue-all non-HTTP(S)), F-06 blocker (AC-10 environment/authorization). v2 absorbed F-06 as an approved plan change (`VAULT_CAPTURE_PYTHON` + first-exact-ready contract) and mandated the F-01..F-05 fixes.
