---
task_id: 2026-08-07-vault-capture-web-markdown
title: Reliable web and WeChat article capture with concise annotations
status: approved
spec_version: 1
planner: primary
executor: trae
created: 2026-08-07
approved_at: 2026-08-07T08:28:39+08:00
approved_by: user
---

# Task Specification

> This file is owned by the planner. After `status: approved`, the executor must not edit it. A material change returns it to `draft`, increments `spec_version`, and requires approval again.

## 1. Context and problem

`vault-capture` currently delegates webpage extraction to the agent's `web_fetch` tool and only describes Browser as a fallback. That arrangement is not deterministic and failed for the supplied WeChat article `https://mp.weixin.qq.com/s/h-cJeGKmXiZOhtz4QVtPeQ`: the fetch response was truncated around 750 KB, the extraction retained only title/byline metadata, the runtime had no Browser tool, and the task was marked `failed` even though the blocker was an access/rendering capability that should be diagnosable and often recoverable.

The capture transaction and image-localization code are already deterministic, but there is no repository-owned webpage fetch/extract command. The agent therefore has to carry a potentially large Markdown body between tools and `finalize`, and there is no executable quality gate preventing a title-only or challenge page from being treated as article content.

The supplied read-only annotation sample at `D:\tmp\annotated_柯愉乐--3.6万家店的瑞幸,有了新的野心--2026-08-06--20260806-081827-x405.md` also demonstrates three unwanted rendering rules in generated rollups:

- a redundant `## 摘录与批注` heading;
- a repeated Source WikiLink/external URL under every numbered annotation;
- an empty `评论：` section for quote-only entries, and the user-facing term `评论` where the desired term is `批注`.

Research conclusion:

- Use [Trafilatura](https://github.com/adbar/trafilatura) as the maintained Python-native generic article extractor. It supports metadata extraction and Markdown output with formatting, links, tables, and images, and fits the skill's existing Python runtime.
- Use [Playwright for Python](https://playwright.dev/python/) as the repository-owned rendered-page fallback, with a dedicated persistent profile path outside Git for sites such as WeChat that may require a real browser session.
- Keep a dedicated WeChat adapter for `#js_content`, `#activity-name`, `#js_name`, `#publish_time`, lazy `data-src` images, challenge/rate-limit detection, and WeChat image CDN behavior. Generic extraction alone is not sufficient for that DOM and access model.
- Mozilla Readability and Defuddle were evaluated but are not selected for this task: Readability needs a separate DOM and Markdown layer, while Defuddle would add a second Node runtime to a Python skill and currently labels itself a work in progress. Crawl4AI was also evaluated but is unnecessarily broad and heavy for one-article capture.

Planning baseline evidence on 2026-08-07:

- `python tests/skills/test_vault_capture.py`: 15 tests passed.
- The supplied article/annotation ID is not present in `SourceNotes`.
- Full repository `git diff --check` already reports trailing blank-line warnings in five pre-existing staged files listed in §5; implementation must not modify those files or add new warnings.

## 2. Required outcome

Add a deterministic, repository-owned web ingestion path. A new `ingest-web <id>` command must inspect the queued Source, fetch the complete response without the agent tool's response truncation, extract main content and metadata, render stable Markdown, enumerate every retained body image as a `vault-image://` token, and call the existing atomic `finalize`/`fail` behavior directly. Article bodies must not be round-tripped through an LLM or chat payload.

The extractor must use a static fetch first and Playwright only when required. WeChat URLs receive site-specific DOM and metadata handling before generic extraction. A title-only response, challenge page, incomplete body, or incomplete body-image manifest must never become `ready`. Captcha, login, rate-limit, or user-verification requirements become `manual`; transient network/extractor failures remain `failed` and retryable.

Generated capture-managed Annotation rollups must show the Source WikiLink and external original URL exactly once immediately below the H1 title, omit `## 摘录与批注`, omit all per-entry source lines, use `批注：` only for entries that actually contain one or more user annotations, and never emit the user-facing label `评论：`.

## 3. Non-goals

- Do not change the meaning or allowed values of existing metadata fields and do not increment `schema_version`.
- Do not bulk-migrate existing Annotation files or write any test/article data into the live `SourceNotes` vault.
- Do not copy the supplied article body or personal annotations into repository fixtures; fixtures must be synthetic and minimal.
- Do not implement account-history crawling,公众号 search, read/comment metrics, paywall bypass, captcha bypass, credential capture, proxy interception, or WeChat desktop automation.
- Do not add PDF, transcript, OCR, refresh, or multi-page crawling support.
- Do not add an LLM cleanup, rewriting, summarization, or quality-scoring stage.
- Do not replace the existing Source/Annotation transaction, naming, Git staging, image size, or Source immutability contracts.
- Do not install or configure dependencies in the live production host as part of repository implementation; document the exact operator step and validate in disposable paths only.

## 4. Locked decisions

- The generic extractor is `trafilatura==2.1.0`; the browser renderer is `playwright==1.61.0`. Pin both direct dependencies in a dedicated web-runtime requirements file. Resolve and lock their transitive dependencies in a reproducible lock artifact if the chosen standard Python tooling supports it without adding a second package manager.
- Static HTTP is attempted first. It must use bounded time/size limits, full-body reads (no silent truncation), redirect revalidation, explicit content-type/charset handling, a normal browser User-Agent, and SSRF protection for the initial URL and every redirect.
- Playwright is the fallback for empty/low-quality static extraction and for browser-required WeChat states. Browser automation is read-only: navigate, wait for the article container, scroll only to materialize lazy body assets, and read DOM. It must never type credentials, submit forms, solve captchas, or alter an account.
- Browser profile/cookie state is optional and external to both repositories. The path is supplied by configuration, is never printed in user-facing output, and is never staged. If verification is needed, return `manual` with a short safe reason.
- The WeChat adapter owns selectors and normalization for article metadata, `#js_content`, `data-src`/`data-original` images, relative/protocol-relative URLs, SVG/1×1/tracking exclusions, and explicit challenge/rate-limit detection. It must not depend on `web_fetch` or an agent Browser tool.
- Trafilatura performs generic main-content selection and Markdown conversion. Post-processing may be added only to satisfy the repository's existing preservation contract (heading order, paragraphs, blockquotes, lists, tables, fenced code, emphasis, links, body images, and captions) and to generate the exact image-token manifest expected by `finalize`.
- `ingest-web <id>` is the only new state-changing entry point. It uses the queue job URL returned by `inspect`, never an untrusted caller-supplied replacement URL, and delegates final file/image/Git mutation to the existing transaction code.
- Quality gates are deterministic and fixture-tested. They must detect at least: missing article container, title-only/metadata-only extraction, known WeChat captcha/verification/rate-limit pages, unsupported content type, response over the configured maximum, and Markdown/image-manifest mismatch. Thresholds must be constants with named tests, not prompt judgment.
- Failure mapping is locked: authentication/captcha/verification/rate limit/browser-profile need → `manual`; timeout/DNS/HTTP 5xx/temporary browser or extraction error → `failed`; invalid job or contract input retains the existing command error semantics.
- Annotation body format is locked as follows:

  ```markdown
  # <来源标题>——批注

  来源：[[<source-id>|<来源标题>]] · [原文](<source-url>)

  <!-- vault-capture:annotation-rollup -->
  <!-- vault-capture:entries:start -->
  ...
  ## 标注 1

  > 引文

  批注：

  - 用户批注
  ...
  <!-- vault-capture:entries:end -->
  ```

  `批注：` and its following list are absent when that entry has no user annotation. A comment-only entry still uses `批注：`. Locator and deduplication data remain in hidden managed metadata; no per-entry Source link is rendered.
- Newly created managed rollups use the new format. Existing managed rollups are normalized only when an explicit capture append/finalize already touches them. There is no repository-wide or live-vault migration.
- No metadata field meaning changes, so `schema_version` remains `1`; add an architecture decision for the deterministic extractor stack and migration boundary rather than a schema decision.

## 5. Repository baselines

Approval baseline refreshed immediately before approval at `2026-08-07T08:28:39+08:00`:

| Repository | Absolute path | Base branch | Base commit | Existing worktree changes | Working branch |
|---|---|---|---|---|---|
| `knowledge-vault-blueprint` | `C:\Users\monottx\dox\knowledge-vault-blueprint` | `main` | `2e818439e2fcb9f83dceb3aad49901d4d11a0007` | Pre-existing staged additions: `AGENTS.md`, `tasks/README.md`, `tasks/_template/EXECUTION.md`, `tasks/_template/REVIEW.md`, `tasks/_template/SPEC.md`. Planner-created task package under `tasks/2026-08-07-vault-capture-web-markdown/` is also expected. | existing `main`; no branch switch authorized |

`SourceNotes` is explicitly out of scope. It was observed at `main` / `ec1a90eb9d41df77cf74e44d51e703d0379882e7` with a pre-existing staged `AGENTS.md`; the executor and tests must not write there.

## 6. Scope by repository

### knowledge-vault-blueprint

Expected changes:

- Document the deterministic generic + WeChat + browser fallback architecture and operational dependency setup.
- Add the web extractor and `ingest-web` orchestration while preserving the existing transaction and safety boundaries.
- Change capture-managed Annotation rendering and touch-normalization to the locked layout.
- Add synthetic fixtures, offline tests, browser-fixture tests, and a disposable live-WeChat smoke tool.
- Record implementation evidence only in this task's `EXECUTION.md`.

Allowed paths:

- `.gitignore`
- `BLUEPRINT.md`
- `DECISIONS.md`
- `ROADMAP.md`
- `specifications/capture-workflow.md`
- `specifications/openclaw-skill-workflow.md`
- `skills/vault-capture/SKILL.md`
- `skills/vault-capture/references/runtime-contract.md`
- `skills/vault-capture/references/web-runtime.md`
- `skills/vault-capture/requirements-web.txt`
- `skills/vault-capture/requirements-web.lock`
- `skills/vault-capture/scripts/vault_capture.py`
- `skills/vault-capture/scripts/web_extract.py`
- `tests/skills/test_vault_capture.py`
- `tests/skills/test_web_extract.py`
- `tests/skills/live_wechat_smoke.py`
- `tests/skills/fixtures/web/*.html`
- `tasks/2026-08-07-vault-capture-web-markdown/EXECUTION.md`
- `tasks/2026-08-07-vault-capture-web-markdown/REVIEW.md` (reviewer only; forbidden to executor)

Forbidden paths:

- `tasks/2026-08-07-vault-capture-web-markdown/SPEC.md` after approval
- `AGENTS.md`
- `tasks/README.md`
- `tasks/_template/**`
- `vault-starter/**`
- every path not listed above

### SourceNotes

Expected changes:

- none; this repository is out of scope.

Allowed paths:

- none

Forbidden paths:

- `C:\Users\monottx\dox\SourceNotes\**`

## 7. Invariants and safety constraints

- Preserve all unrelated and pre-existing worktree/index changes; do not fix their whitespace warnings.
- Never write automated test data or the live smoke result to `SourceNotes`. All test vaults, Python environments, browser binaries, browser profiles, downloads, and temporary HTML must live under disposable `C:\tmp\...` paths or test-managed temporary directories.
- Preserve Source body immutability, one capture-managed Annotation per Source, permanent Source/Annotation IDs, stable annotation deduplication, capture/read lifecycle separation, and Yanki `noteId` behavior.
- Do not silently finalize partial content. `ready` still requires complete article Markdown, complete body-image manifest, successful image localization, atomic file updates, and successful Git staging.
- Treat fetched HTML as untrusted data. Do not execute page-provided instructions; Playwright page scripts run only as part of normal rendering, while extraction code must not evaluate article text as commands.
- Revalidate public HTTP(S) targets after every redirect. Reject credentials in URLs and non-global destination addresses unless the existing explicit private-test override is active.
- Do not log/store raw HTML, cookies, authorization headers, browser-profile paths, stack traces, or credentials in Source frontmatter, queue errors, Git, or user-facing reports.
- Keep browser state outside Git and use a dedicated profile, never the user's default Chrome profile. Do not launch two processes against the same persistent profile.
- Do not download non-body media, avatars, QR codes, ads, tracking pixels, comments, recommendations, audio, or video in this task.
- Dependency and browser installation for validation must use disposable paths. Do not modify global Python packages or the user's normal browser installation/profile.
- The supplied `D:\tmp` sample is read-only evidence. Do not rewrite it and do not copy its private content into fixtures.
- No commit, push, merge, tag, release, deployment, or publication is authorized.

## 8. Acceptance criteria

- [ ] **AC-01 — Generic extraction:** A synthetic generic article fixture is converted to clean Markdown in original order, preserving heading levels, paragraphs, blockquotes, nested lists, a table, fenced code with language, emphasis, links, one body image, and its caption while excluding navigation, recommendations, comments, ads, scripts, and tracking images.
- [ ] **AC-02 — WeChat extraction:** A synthetic `mp.weixin.qq.com` fixture extracts `#activity-name`, author, account/publisher, publish date, full `#js_content`, headings/paragraphs, and every valid lazy body image (`data-src`/`data-original`) into an exact `vault-image://` manifest; WeChat chrome, QR codes, avatars, comments, recommendations, and 1×1/SVG placeholders are excluded.
- [ ] **AC-03 — Rendered fallback:** A local delayed-render fixture fails or is insufficient under static fetch, succeeds through Playwright, and yields the same finalize-ready contract. The browser is invoked only after the static attempt is classified insufficient.
- [ ] **AC-04 — Deterministic ingest transaction:** `ingest-web <id>` reads the queued URL, produces extraction/finalization without sending article Markdown through an agent, and on success returns the existing final paths/status with `ingest_status: ready`. Existing atomic file, image, rename, conflict, and Git-staging behavior remains intact.
- [ ] **AC-05 — Quality and failure states:** Offline fixtures/tests prove that title-only, empty, truncated/over-limit, unsupported-content, Markdown/image mismatch, WeChat captcha/verification, and rate-limit pages never reach `ready`. Manual states and retryable failures map exactly as locked in §4 and expose only short safe reason codes/messages.
- [ ] **AC-06 — Supplied live URL smoke:** In a disposable vault, the supplied WeChat URL is attempted through the new command. A successful capture must contain all three user-supplied highlighted excerpts and complete body images. If current WeChat external state requires verification, the smoke must demonstrate that the static attempt was rejected, the browser fallback was attempted, and the result is a structured `manual` state rather than the previous title-only `failed` result. The exact observed outcome is recorded in `EXECUTION.md` and independently reviewed.
- [ ] **AC-07 — Annotation layout:** Fresh quote-only, quote+annotation, comment-only, duplicate/append, locator, finalize/rename, and explicitly touched legacy managed-rollup tests show exactly one Source WikiLink/original URL line below H1, no `## 摘录与批注`, no per-entry `来源：`, no `评论：`, and `批注：` only when that numbered entry has user annotation text.
- [ ] **AC-08 — Compatibility and migration:** Existing IDs, hidden entry/comment metadata, deduplication, `annotation_kind`, `engagement`, `created`, source renaming, and links remain correct. No bulk migration runs, `schema_version` remains `1`, and `SourceNotes` is unchanged.
- [ ] **AC-09 — Reproducible operations:** Web runtime dependencies and Chromium setup are pinned/documented; setup, preflight, missing-dependency, missing-browser, and external profile behavior have executable checks. No dependency cache, virtual environment, browser binary, cookie/profile, captured article, or secret is tracked by Git.
- [ ] **AC-10 — Regression and scope:** All existing and new tests pass without weakening existing assertions. Task-scoped `git diff --check` has no output; full-repository output contains no warnings beyond the five pre-existing baseline files. No forbidden path changes in either repository.

## 9. Validation plan

| ID | Working directory | Exact command or inspection | Expected result |
|---|---|---|---|
| `VAL-01` | `C:\Users\monottx\dox\knowledge-vault-blueprint` | `python -m venv C:\tmp\vault-capture-web-markdown-venv` | Exit 0; disposable virtual environment created outside both repositories. |
| `VAL-02` | same | `C:\tmp\vault-capture-web-markdown-venv\Scripts\python.exe -m pip install -r skills\vault-capture\requirements-web.txt` | Exit 0; only pinned web runtime dependencies are installed into the disposable environment. |
| `VAL-03` | same | PowerShell: `$env:PLAYWRIGHT_BROWSERS_PATH='C:\tmp\vault-capture-web-markdown-browsers'; & 'C:\tmp\vault-capture-web-markdown-venv\Scripts\python.exe' -m playwright install chromium` | Exit 0; Chromium is installed only under the disposable path. |
| `VAL-04` | same | `C:\tmp\vault-capture-web-markdown-venv\Scripts\python.exe tests\skills\test_vault_capture.py` | Exit 0; all existing plus Annotation/ingest integration tests pass. |
| `VAL-05` | same | PowerShell: `$env:PLAYWRIGHT_BROWSERS_PATH='C:\tmp\vault-capture-web-markdown-browsers'; & 'C:\tmp\vault-capture-web-markdown-venv\Scripts\python.exe' tests\skills\test_web_extract.py` | Exit 0; static, WeChat, rendered fallback, security, quality-gate, and failure-state fixture tests pass. |
| `VAL-06` | same | PowerShell: `$env:PLAYWRIGHT_BROWSERS_PATH='C:\tmp\vault-capture-web-markdown-browsers'; & 'C:\tmp\vault-capture-web-markdown-venv\Scripts\python.exe' tests\skills\live_wechat_smoke.py --url 'https://mp.weixin.qq.com/s/h-cJeGKmXiZOhtz4QVtPeQ'` | Runs only against a disposable vault. Exit 0 for a complete `ready` capture containing all expected excerpts, or for an explicitly asserted structured `manual` verification state after browser fallback. Output records method, safe state/reason, body length, excerpt checks, and image count; it never prints cookies/profile paths/raw HTML. |
| `VAL-07` | same | `python -m compileall -q skills\vault-capture\scripts tests\skills` | Exit 0. |
| `VAL-08` | same | `git diff --check 2e818439e2fcb9f83dceb3aad49901d4d11a0007 -- .gitignore BLUEPRINT.md DECISIONS.md ROADMAP.md specifications/capture-workflow.md specifications/openclaw-skill-workflow.md skills/vault-capture tests/skills tasks/2026-08-07-vault-capture-web-markdown` | Exit 0 and no output from task-scoped changes. |
| `VAL-09` | same | `git diff --check` and `git diff --cached --check` | No new warning beyond the planning-baseline warnings in `AGENTS.md`, `tasks/README.md`, and the three `tasks/_template/*.md` files. Record exact output; do not edit those files. |
| `VAL-10` | both repositories | Compare `git status --short`, `git diff`, and `git diff --cached` with §5; inspect every changed path against §6. | Only allowed blueprint paths changed; all pre-existing changes preserved; `SourceNotes` unchanged. |
| `VAL-11` | disposable test output | Manual visual inspection of one generic Source, one WeChat Source, and the quote-only/mixed Annotation fixtures. | Markdown order and image/caption placement are readable in Obsidian-compatible Markdown; exactly one top Source line and conditional `批注：` layout are confirmed. This is a manual check, not an automated test. |

If dependency or browser download requires sandbox/network approval, request it only for the exact disposable install commands. Do not substitute global installation.

## 10. Deliverables

- Updated architecture/specification/skill/runtime documentation within allowed paths.
- Pinned Python web-runtime dependency files and documented Linux/OpenClaw setup and rollback.
- `web_extract.py` and `ingest-web` command integrated with the existing capture transaction.
- Synthetic generic, WeChat, delayed-render, and failure fixtures; no copied private article content.
- Updated Annotation rendering/normalization tests and web extraction/integration tests.
- A disposable live smoke tool for the supplied URL.
- `EXECUTION.md` completed by trae with preflight state, dependency versions, exact changed files, acceptance evidence, full validation outputs, live-smoke outcome, assumptions/deviations, and final Git state.

## 11. Git and external-action permissions

- Branching: `not authorized`; remain on the existing branch.
- Staging: `not authorized`; repository implementation files must not be added to the index. Existing application tests may stage only files inside disposable temporary test vaults.
- Committing: `not authorized`.
- Pushing: `not authorized`.
- Merging: `not authorized`.
- Tagging/releasing/deploying/publishing: `not authorized`.
- External service writes: `not authorized`.
- Read-only network access: authorized only for installing the pinned dependencies/Chromium into disposable validation paths and for the explicit live URL smoke.
- Local writes outside repositories: authorized only under task-specific disposable `C:\tmp\vault-capture-web-markdown-*` paths and Playwright's explicitly redirected disposable browser path. No default browser profile or global Python environment may be changed.

## 12. Rollback

- Revert only the task's allowed implementation paths to the baseline versions; do not reset or clean either worktree and do not alter the five pre-existing staged files.
- Remove the new extractor, dependency/runtime files, fixtures/tests, command wiring, and documentation changes as one coherent rollback. Restore the former Annotation renderer and runtime contract together so implementation and docs do not diverge.
- Delete disposable virtualenv/browser/profile/test-vault paths under `C:\tmp\vault-capture-web-markdown-*`; they contain no authoritative data.
- No live-vault migration is run, so rollback requires no SourceNotes rewrite. Managed Annotation files created or explicitly touched later by a deployed version are ordinary Git-visible vault changes and must be reverted individually by their owner if desired; automation must not mass-rewrite them.
- The schema remains at version 1, so there is no schema down-migration.

## 13. Open questions

- none. The dependency stack, fallback policy, annotation rendering, migration boundary, repository scope, and permissions are locked for approval.

## 14. Approval record

- Approval statement: `批准 SPEC v1，交给 trae executor 执行`
- Approved specification version: `1`
- Approved at: `2026-08-07T08:28:39+08:00`
