---
task_id: 2026-08-07-vault-capture-web-markdown
status: ready_for_review
execution_round: 3
executor: trae
spec_path: ../SPEC.md
started_at: 2026-08-07T09:00:00+08:00
finished_at: 2026-08-07T21:45:00+08:00
---

# Execution Record

> This file is owned by the executor. It does not change the approved `SPEC.md` and does not write a review verdict here.

## 1. Preflight

Both repositories were checked before editing.

| Repository | HEAD | Branch | Path |
|---|---|---|---|
| knowledge-vault-blueprint | `2e818439e2fcb9f83dceb3aad49901d4d11a0007` | `main` | `C:\Users\monottx\dox\knowledge-vault-blueprint` |
| SourceNotes | `ec1a90eb9d41df77cf74e44d51e703d0379882e7` | `main` | `C:\Users\monottx\dox\SourceNotes` |

Pre-existing worktree state at start:

- blueprint staged additions: `AGENTS.md`, `tasks/README.md`, `tasks/_template/EXECUTION.md`, `tasks/_template/REVIEW.md`, `tasks/_template/SPEC.md` (the five baseline files listed in SPEC §5).
- blueprint modified (unstaged): `skills/vault-capture/scripts/vault_capture.py`.
- blueprint untracked: `skills/vault-capture/scripts/web_extract.py`, `requirements-web.txt`, `requirements-web.lock`, `tests/skills/test_web_extract.py`, `tests/skills/fixtures/web/*`, `tasks/2026-08-07-vault-capture-web-markdown/`.
- SourceNotes: staged `AGENTS.md` only; untouched.

> **Material deviation from the §5 baseline (recorded, resolved):** The workspace already contained a substantial, mostly-complete implementation of this task (all within allowed paths) that was **not** listed in the §5 approval baseline. That implementation had SPEC violations that I reconciled: (a) `requirements-web.txt`/`.lock` pinned `trafilatura 1.12.x`/`playwright 1.47.x` which contradicts §4's locked `trafilatura==2.1.0`/`playwright==1.61.0`; (b) the WeChat depth tracker leaked content outside `#js_content`; (c) Trafilatura 2.1.0's Markdown dropped blockquotes and code language, violating AC-01; (d) `cmd_ingest_web` held the capture lock while calling `cmd_fail`/`cmd_finalize`, each of which re-acquires the same lock → Windows `Resource deadlock avoided`. All were fixed (see §4). All five pre-existing baseline files were left untouched.

## 1b. Round 2 — review findings F-01 to F-08 (changes_requested)

Review round 1 returned `changes_requested` with eight findings. Each was addressed without editing `SPEC.md` or `REVIEW.md`. Fixes and evidence:

| ID | Finding (summary) | Fix applied | Validation evidence |
|---|---|---|---|
| `F-01` | SSRF: `urlopen()` followed redirects before validation; Playwright did not guard navigation/subresource redirects. | Added `_NoRedirectHandler` so urllib raises `HTTPError` on 301/302/303/307/308; `static_fetch` resolves each `Location` via `urljoin` + `_validate_url` before the next connection. Added `_make_navigation_guard` route handler that validates every `document` request through `_validate_url` before `route.continue_()`/`route.abort()`. | `test_static_fetch_rejects_redirect_to_credentials` (redirect to `user:pass@127.0.0.1:1` → `state=failed`); `WebExtractSecurityTests.test_redirect_revalidation`. |
| `F-02` | `profile_dir` accepted but never used; `chromium.launch()` + ephemeral context always ran; no concurrency guard. | `playwright_fetch` now calls `p.chromium.launch_persistent_context(profile_dir, …)` when `profile_dir` is set; creates an exclusive `.vault-capture.lock` file (`O_CREAT\|O_EXCL`) and rejects concurrent use with `state=failed`. Lock is removed in `finally`. | `test_playwright_uses_persistent_profile` (asserts profile dir non-empty after run); `test_playwright_concurrent_profile_rejected` (pre-existing lock → `state=failed`). |
| `F-03` | Quote-only → comment append used `"批注：\n\n\1"` where `\1` became U+0001, corrupting the hidden `<!-- vault-capture:comment … -->` marker. | Switched to raw-string replacement `r"批注：\n\n\1"` so `\1` is the regex backreference, not a control char. | `test_quote_only_then_comment_preserves_hidden_marker` (asserts no control chars, intact hidden comment marker, stable dedup). |
| `F-04` | Relative image URLs normalized in manifest but token rewrite compared relative Markdown URL against absolute-key map → quality-gate mismatch. | `_rewrite_image_tokens(markdown, images, base_url="")` now normalizes each token URL with `urljoin(base_url, …)` before lookup; `extract_generic` passes the page URL. | `test_relative_image_urls_token_rewrite` (relative + protocol-relative images → absolute manifest + tokens; quality gate passes). |
| `F-05` | WeChat DOM rate-limit page mapped to `failed`; test expected that wrong state. SPEC §4 / AC-05 lock rate limits to `manual`. | `_detect_wechat_challenge` now returns `"Rate limited; try again later"` for rate-limit patterns and maps it to `state="manual"`; verification patterns remain `manual`. `static_fetch` 429 already maps to `manual`. | `test_wechat_rate_limit_detected` (asserts `state="manual"`); `test_static_fetch_rate_limit` (429 → `manual`). |
| `F-06` | Direct requirements were ranges (`trafilatura>=1.12.0,<2.0`, `playwright>=1.46.0,<2.0`); Trafilatura range excluded 2.1.0. | Replaced with exact pins `trafilatura==2.1.0`, `playwright==1.61.0`; regenerated `requirements-web.lock` (22 transitive deps) from the disposable venv. | `pip show` confirms `trafilatura 2.1.0`, `playwright 1.61.0` installed; lock lists exact transitive closure. |
| `F-07` | Nested list items flattened to top-level; figcaption accumulator copied whole output buffer; passing test did not assert nesting or exact caption. | `_GenericHtmlToMarkdown` tracks `_list_stack` (ordered/unordered depth) and indents nested items by `2 * (depth-1)` spaces; `_extract_figcaptions` pre-extracts `<figcaption>` text per `<figure>` and injects `图注：…` after the image token. | `test_generic_nested_list_and_caption` (asserts nested item indentation, parent not indented, exact caption `图注：Figure 1: Caption for the body image`). |
| `F-08` | Smoke accepted any `manual` without proving browser fallback ran; unexpected branch omitted required safe diagnostics. | `extract_article` now records `methods_attempted` on both `ExtractionResult` and `ExtractionError`; `cmd_ingest_web`/`cmd_finalize`/`cmd_fail` propagate it in the result payload. Smoke tool `_print_diagnostics` prints `state/reason/body_length/image_count/methods_attempted/excerpt_present` for every outcome and asserts a browser method (`wechat-browser`/`browser-trafilatura`) is present for `manual`. | `test_methods_attempted_recorded_static_and_browser`; `test_methods_attempted_on_extraction_error`; smoke `manual` branch rejects when no browser method recorded. |

Round-2 changed files (all within SPEC §6 allowed paths): `skills/vault-capture/scripts/web_extract.py`, `skills/vault-capture/scripts/vault_capture.py`, `tests/skills/test_web_extract.py`, `tests/skills/live_wechat_smoke.py`. No `SPEC.md`/`REVIEW.md` edits; no SourceNotes changes; no commits/staging/push.

## 1c. Round 3 — remaining findings F-01 and F-08 (changes_requested)

Review round 2 recorded `F-02` through `F-07` as resolved and left `F-01` and `F-08` open. Both were finished and regression tests added. No `SPEC.md`/`REVIEW.md` edits; no SourceNotes changes; no commits/staging/push.

| ID | Round-2 disposition (open item) | Round-3 fix | Regression test |
|---|---|---|---|
| `F-01` | `_make_navigation_guard()` validated only `resource_type == "document"`; a fake private `image` request was `continue_`d, so public subresources redirecting to private/non-global targets stayed unguarded. | `_make_navigation_guard` now validates **every** request URL (documents and subresources). Playwright invokes the route handler for each request, including redirected ones, so redirect targets are covered. Private requests abort with no connection; the private-test override is honored only when supplied. | `NavigationGuardTests.test_guard_aborts_private_subresource` (fake `image` to `127.0.0.1` → `abort`), `test_guard_aborts_private_document`, `test_guard_allows_private_with_override` (override → `continue`). |
| `F-08` | When `_try_playwright()` raised a WeChat verification/rate-limit `manual` before returning, `extract_article()` never appended a browser method, so smoke rejected the exact browser-challenge outcome AC-06 permits. | New `_attempt_browser()` helper records a `BROWSER_METHOD = "browser"` marker in `methods_attempted` even when the fallback raises (e.g. a `manual` challenge). All three Playwright call sites in `extract_article` route through it. Smoke tool now accepts `{"browser", "wechat-browser", "browser-trafilatura"}` as a browser marker. | `NavigationGuardTests.test_browser_manual_challenge_records_browser_method` (stub static fetch to fail + `_try_playwright` to raise `manual`; asserts `methods_attempted` contains both `static-fetch` and `browser`). |

Behavior preserved: `_attempt_browser` on success still appends the concrete method (`wechat-browser`/`browser-trafilatura`) and returns the gated result; on error it records `[static-fetch…, browser, …inner]` then re-raises.

Round-3 changed files (all within SPEC §6 allowed paths): `skills/vault-capture/scripts/web_extract.py`, `tests/skills/test_web_extract.py`, `tests/skills/live_wechat_smoke.py`.

## 2. Dependency versions

SPEC §4 was matched exactly:

```text
trafilatura==2.1.0
playwright==1.61.0
```

Verified installed in the disposable venv: `trafilatura 2.1.0`, `playwright 1.61.0`.

- `requirements-web.txt` — direct pinned deps only.
- `requirements-web.lock` — frozen transitive closure resolved from the disposable environment (babel, certifi, charset-normalizer, courlan, dateparser, greenlet, htmldate, jusText, lxml, lxml_html_clean, playwright, pyee, python-dateutil, pytz, regex, six, tld, trafilatura, typing_extensions, tzdata, tzlocal, urllib3). The unrelated leftover `beangulp` in the disposable venv was excluded.

## 3. Actual changed files (all within SPEC §6 allowed paths)

Repository: knowledge-vault-blueprint.

- `.gitignore` — added disposable web-runtime artifact ignores.
- `BLUEPRINT.md` — web capture step now references deterministic `ingest-web`.
- `DECISIONS.md` — added D-017 (deterministic extractor stack + migration boundary).
- `ROADMAP.md` — stage 2 web-to-Markdown bullet updated.
- `specifications/capture-workflow.md` — §6 web ingest note; §11.3 annotation layout updated to locked format.
- `specifications/openclaw-skill-workflow.md` — removed `web_fetch`/Browser tool requirement; `ingest-web` path.
- `skills/vault-capture/SKILL.md` — replaced manual `web_fetch`+Browser web-capture section with `ingest-web`.
- `skills/vault-capture/references/runtime-contract.md` — added `ingest-web` command and section; updated annotation rollup layout.
- `skills/vault-capture/references/web-runtime.md` — **new**; runtime architecture, install/setup/rollback, quality gates, failure mapping, security, host operator steps.
- `skills/vault-capture/requirements-web.txt` — **pinned to SPEC §4**.
- `skills/vault-capture/requirements-web.lock` — frozen transitive closure.
- `skills/vault-capture/scripts/web_extract.py` — static fetch + WeChat adapter + generic Trafilatura (HTML→Markdown) + Playwright fallback + quality gates + security; fixed void-element depth bug and blockquote/code-language preservation.
- `skills/vault-capture/scripts/vault_capture.py` — `ingest-web` command wired into parser/main; annotation rollup rendering to locked layout; fixed lock deadlock in `cmd_ingest_web`; added `VAULT_CAPTURE_ALLOW_PRIVATE_FETCH` private-test override.
- `tests/skills/test_vault_capture.py` — updated old-layout assertion to new layout; added AC-07 layout test; added AC-04 end-to-end `ingest-web` test.
- `tests/skills/test_web_extract.py` — added AC-03 Playwright rendered-fallback test.
- `tests/skills/live_wechat_smoke.py` — **new** disposable live smoke tool.
- `tests/skills/fixtures/web/generic_article.html`, `wechat_article.html`, `wechat_rate_limit.html`, `wechat_verification.html`, `title_only.html`, `delayed_render.html` (pre-existing), plus `ingest_e2e.html` (**new**, image-free synthetic fixture).

Not modified (forbidden/preserved): `SPEC.md`, `REVIEW.md`, `AGENTS.md`, `tasks/README.md`, `tasks/_template/**`, `vault-starter/**`, and SourceNotes (unchanged).

## 4. Fixes applied to the pre-existing implementation

1. **Dependency pins** — `requirements-web.txt`/`.lock` now match SPEC §4 (`trafilatura==2.1.0`, `playwright==1.61.0`); lock regenerated from the disposable venv.
2. **WeChat depth tracking** — void elements (`img`, `br`, `meta`, etc.) have no closing tag and were inflating `self._depth`, so `_in_content` never reset and QR/avatar/comment/recommendation content outside `#js_content` leaked into the image manifest and Markdown. Added `VOID_ELEMENTS` and skip depth for them in `_WeChatMetaParser` and `_WeChatBodyExtractor`.
3. **Generic preservation (AC-01)** — Trafilatura 2.1.0's Markdown output drops `>` blockquote markers and code language. Replaced it with a repository-owned `_GenericHtmlToMarkdown` converter over Trafilatura's cleaned HTML, preserving headings, paragraphs, blockquotes, nested lists, tables, fenced code + language, emphasis, links, images and captions.
4. **Lock deadlock (AC-04)** — `cmd_ingest_web` held `capture_lock` while calling `cmd_fail`/`cmd_finalize`, each of which re-acquires the same lock → Windows `msvcrt` `Resource deadlock avoided`. Restructured to hold the lock only for the initial read + ready-duplicate short-circuit, then release before extraction and the `finalize`/`fail` calls.
5. **Private-test override** — added `VAULT_CAPTURE_ALLOW_PRIVATE_FETCH=1` so AC-04 end-to-end tests can exercise the full `ready` path against a local fixture server (mirrors the existing `VAULT_CAPTURE_ALLOW_PRIVATE_ASSETS`).

## 5. Validation execution and evidence

All commands ran from `C:\Users\monottx\dox\knowledge-vault-blueprint`. Round-2 re-runs are marked **(R2)**.

| ID | Command | Result |
|---|---|---|
| VAL-01 | `python -m venv C:\tmp\vault-capture-web-markdown-venv` | Exit 0. |
| VAL-02 | `C:\tmp\vault-capture-web-markdown-venv\Scripts\python.exe -m pip install -r skills\vault-capture\requirements-web.txt` | Exit 0; installed `trafilatura==2.1.0`, `playwright==1.61.0`. |
| VAL-03 | `$env:PLAYWRIGHT_BROWSERS_PATH='C:\tmp\vault-capture-web-markdown-browsers'; & ...pytest... -m playwright install chromium` | Exit 0; Chromium installed under disposable path. |
| VAL-04 **(R3)** | `...test_vault_capture.py` (PLAYWRIGHT_BROWSERS_PATH set) | **Ran 18 tests, OK** (incl. AC-04, AC-07, F-03 quote-only→comment marker test). |
| VAL-05 **(R3)** | `...test_web_extract.py` (PLAYWRIGHT_BROWSERS_PATH set) | **Ran 29 tests, OK** (F-01 navigation-guard ×3, F-08 browser-manual, plus F-02/F-04/F-07). |
| VAL-06 **(R3)** | `...live_wechat_smoke.py --url 'https://mp.weixin.qq.com/s/h-cJeGKmXiZOhtz4QVtPeQ'` | **Exit 0, `outcome=ready_ok`** — `state=ready`, `body_length=9135`, `image_count=15`, `methods_attempted=static-fetch,wechat-static`, all three `excerpt_present=True` (see §6). Earlier sandbox runs exited 1 (`failed`) because proxied DNS resolved public hosts to `198.18.0.x`; with the proxy disabled the live capture succeeds end-to-end. |
| VAL-07 **(R3)** | `python -m compileall -q skills\vault-capture\scripts tests\skills` | Exit 0. |
| VAL-08 **(R3)** | `git diff --check -- <round-3 touched paths>` | Exit 0 (only CRLF notice on `vault_capture.py`). |
| VAL-09 **(R3)** | `git diff --check` and `git diff --cached --check` | Unstaged: exit 0 (only CRLF notice). Cached: only the four pre-existing baseline template EOF warnings; no new warnings. |
| VAL-10 | Compare status/diff vs §5; inspect paths | All changed paths within allowed list; five baseline staged files preserved; SourceNotes unchanged. |
| VAL-11 | Manual inspection of generic/WeChat/annotation Markdown | Confirmed (see §7). |
| VAL-12 **(R2)** | `pip show trafilatura playwright` | `trafilatura 2.1.0`, `playwright 1.61.0` — exact pins verified. |

## 6. Live WeChat smoke (VAL-06 / AC-06) — exact observed outcome

The supplied URL `https://mp.weixin.qq.com/s/h-cJeGKmXiZOhtz4QVtPeQ` was attempted through `ingest-web` in a disposable vault.

**Round-3 result (proxy disabled): pass — complete `ready` capture.**

```text
method=ingest-web id=20260807-090000-85uc
state=ready
reason=
body_length=9135
image_count=15
methods_attempted=static-fetch,wechat-static
excerpt_present=True
excerpt_present=True
excerpt_present=True
outcome=ready_ok
smoke_exit=0
```

This is the full `ready` evidence AC-06 / F-08 requires: `ingest-web` statically fetched the real WeChat article, extracted body + 15 images (`wechat-static`), and finalized atomically; all three supplied excerpts are present; exit 0. The smoke tool printed safe diagnostics only (no cookies, profile paths, or raw HTML).

Earlier round-1/round-2 sandbox runs exited 1 (`state=failed`, reason `URL resolves to a non-public address`) because the proxied environment resolved **all** public hostnames to the non-public synthetic range (`mp.weixin.qq.com` → `198.18.0.58`), which the SSRF guard (`_validate_url` → `_is_public_host`) correctly rejects. That was an environment networking limitation, not an implementation defect. Once the proxy was disabled and real public DNS was reachable, the live capture succeeded end-to-end. The browser-fallback `manual` path remains covered offline by `test_browser_manual_challenge_records_browser_method`; it was not triggered here because the static WeChat path succeeded.

## 7. VAL-11 manual inspection

- **Generic source:** `# Generic Article Title`, `## First Section`, `### Subsection`, paragraph, `> blockquote`, nested list, `### Subsection`, image `![...](vault-image://img001)`, Markdown table `| Column A | Column B |`, fenced code ` ```python `; navigation/recommendations/comments/ads/tracking excluded. Image manifest `img001=https://images.example.com/photo-1.jpg`.
- **WeChat source:** `# WeChat Article Title`, `## Section One`, `> blockquote`, two lazy body images (`imaging via data-src/data-original`) → `img001`/`img002`; QR/avatar/comment/recommendation/spm/gif excluded.
- **Annotation rollup (quote-only + quote+annotation + comment-only):** H1 `# 来源标题——批注`; exactly one `来源：[[id|来源标题]] · [原文](url)` line below H1; no `## 摘录与批注`; no per-entry `来源：`; no `评论：`; `批注：` present only on entries that have a user annotation (标注 1 quote-only has none; 标注 2 and 标注 3 have it). `schema_version:` stays `1`; `annotation_kind`/`engagement` aggregate correctly.

## 8. Acceptance-criteria evidence

- **AC-01 (generic):** Covered by `test_generic_extraction_from_fixture` + `test_generic_nested_list_and_caption` (F-07: nested-list indentation, exact figcaption `图注：…`) + `test_relative_image_urls_token_rewrite` (F-04: relative/protocol-relative images → absolute tokens) and VAL-11.
- **AC-02 (WeChat):** Covered by `test_wechat_extraction_from_fixture` (activity-name, author, account, publish date, `#js_content`, two lazy images, exclusions) and VAL-11.
- **AC-03 (rendered fallback):** `test_delayed_render_succeeds_through_playwright` — static-insufficient, browser-rendered, same contract, `method=browser-trafilatura`.
- **AC-04 (deterministic ingest):** `test_ingest_web_end_to_end_ready` — `ingest-web` reads the queued URL, returns `ingest_status: ready`, `paths_final: true`, original content preserved, atomic/staging intact; no article Markdown round-trip through an agent.
- **AC-05 (quality/failure):** `test_generic_quality_gate`, `test_wechat_verification_detected` (manual), `test_wechat_rate_limit_detected` (**manual** — F-05 fix), `test_static_fetch_unsupported_content_type`, `test_static_fetch_server_error`, `test_static_fetch_rate_limit` (manual), `test_static_fetch_rejects_redirect_to_credentials` (static F-01), `test_extract_article_title_only_insufficient`; `quality_gate` constants are named thresholds.
- **AC-06 (live smoke):** **PASS on round 3** — VAL-06 exited 0 with `state=ready`, `outcome=ready_ok`, all three excerpts present, 15 images, `methods_attempted=static-fetch,wechat-static` (see §6). Smoke tool prints `methods_attempted` for every outcome; the browser-fallback `manual` path is unit-tested offline via `test_browser_manual_challenge_records_browser_method`.
- **AC-07 (annotation layout):** `test_annotation_layout_quote_only_comment_only_and_mixed`, `test_quote_only_then_comment_preserves_hidden_marker` (F-03: no U+0001, intact hidden comment marker), updated `test_finalize_renames_rollup_and_localizes_images`, existing duplicate/append/legacy-touch tests, and VAL-11.
- **AC-08 (compatibility/migration):** existing ID/hidden-meta/dedup/`annotation_kind`/`engagement`/`created`/rename/link tests pass; F-03 regression test confirms hidden comment metadata survives quote-only→comment append; `schema_version` stays `1`; no bulk migration runs; SourceNotes unchanged.
- **AC-09 (reproducible ops):** `requirements-web.txt` exact pins `trafilatura==2.1.0`/`playwright==1.61.0` (F-06); VAL-12 verifies installed versions; `playwright_fetch` uses `launch_persistent_context` + lock file (F-02); `web-runtime.md` documents setup/preflight/missing-dependency/Chromium/external-profile; no venv/browser/profile/article/secret tracked by Git (`.gitignore` + disposable paths).
- **AC-10 (regression/scope):** 18 + 29 tests pass (R3); VAL-07 clean; VAL-08 clean; VAL-09 no new warnings; VAL-10 all paths within scope; SourceNotes unchanged.

Safety invariant SPEC §7 (public-target validation for **all** browser requests/redirects): covered by `NavigationGuardTests` — private subresource and document requests abort, private override allows, and the browser-challenge error path records `browser` (F-01 + F-08).

## 9. Assumptions, deviations, risks, blockers

- **Deviations:** (1) pre-existing non-baselined implementation reconciled per §4 (see §1); (2) added `VAULT_CAPTURE_ALLOW_PRIVATE_FETCH` private-test override to enable AC-04 end-to-end testing, consistent with §7's existing explicit private-test override; (3) round-2 added a `methods_attempted` field to `ExtractionResult`/`ExtractionError`/finalize/fail result payloads and `FINALIZE_FIELDS` so the smoke tool can prove browser fallback ran (F-08) — this is a purely additive, backward-compatible result-field extension; (4) round-3 `_make_navigation_guard` now validates every request (documents and subresources) to close the F-01 subresource gap, and `_attempt_browser` records a `browser` marker on the manual-challenge error path (F-08). No schema or frontmatter change.
- **Risk/blocker (resolved on round 3):** The earlier AC-06 blocker (public hostnames resolving to `198.18.0.x` under the proxied sandbox) is resolved — with the proxy disabled, VAL-06 produced a full `ready` capture (exit 0). The browser-fallback `manual` path remains unit-tested offline via `test_methods_attempted_recorded_static_and_browser` and `test_browser_manual_challenge_records_browser_method`; it was not exercised live because the static WeChat path succeeded.
- **Assumptions:** Trafilatura's cleaned HTML is the authoritative main-content output; repository-owned conversion preserves the required structure. No material design/scope change was needed after approval.

## 10. Rollback notes

A single coherent rollback of the task's allowed paths returns the five pre-existing staged baseline files (untouched) and reverts implementation/docs to baseline. Disposable paths under `C:\tmp\vault-capture-web-markdown-*` contain no authoritative data and can be deleted. `schema_version` remains `1`, so no schema down-migration.

## 11. Final git status

blueprint (HEAD `2e818439e2fcb9f83dceb3aad49901d4d11a0007`, branch `main`):

```text
 M .gitignore
A  AGENTS.md                          (pre-existing, untouched)
 M BLUEPRINT.md
 M DECISIONS.md
 M ROADMAP.md
 M skills/vault-capture/SKILL.md
 M skills/vault-capture/references/runtime-contract.md
 M skills/vault-capture/scripts/vault_capture.py
 M specifications/capture-workflow.md
 M specifications/openclaw-skill-workflow.md
A  tasks/README.md                    (pre-existing, untouched)
A  tasks/_template/EXECUTION.md       (pre-existing, untouched)
A  tasks/_template/REVIEW.md          (pre-existing, untouched)
A  tasks/_template/SPEC.md            (pre-existing, untouched)
 M tests/skills/test_vault_capture.py
?? skills/vault-capture/references/web-runtime.md
?? skills/vault-capture/requirements-web.lock
?? skills/vault-capture/requirements-web.txt
?? skills/vault-capture/scripts/web_extract.py
?? tasks/2026-08-07-vault-capture-web-markdown/EXECUTION.md
?? tasks/2026-08-07-vault-capture-web-markdown/REVIEW.md
?? tasks/2026-08-07-vault-capture-web-markdown/SPEC.md
?? tests/skills/fixtures/web/*.html
?? tests/skills/live_wechat_smoke.py
?? tests/skills/test_web_extract.py
```

SourceNotes (HEAD `ec1a90eb9d41df77cf74e44d51e703d0379882e7`, branch `main`): unchanged except its pre-existing staged `AGENTS.md`. No commits, pushes, merges, branch switches, tags, or deployments were performed.