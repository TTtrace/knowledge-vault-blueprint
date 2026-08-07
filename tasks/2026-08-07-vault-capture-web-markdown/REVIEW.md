---
task_id: 2026-08-07-vault-capture-web-markdown
status: accepted
review_round: 4
reviewer: primary
reviewed_at: 2026-08-07T22:56:45+08:00
verdict: accepted
---

# Review Record

## 1. Review scope and observed state

| Repository | Spec baseline | Reviewed branch and HEAD | Worktree state |
|---|---|---|---|
| `knowledge-vault-blueprint` | `2e818439e2fcb9f83dceb3aad49901d4d11a0007` | `main` at the same HEAD | Task changes are unstaged/untracked; the five pre-existing staged baseline files remain staged. |
| `SourceNotes` | `ec1a90eb9d41df77cf74e44d51e703d0379882e7` | `main` at the same HEAD | Only the pre-existing staged `AGENTS.md` is present; no task or smoke-test data was written. |

The review used the approved `SPEC.md` v1, inspected the implementation rather than relying on `EXECUTION.md`, reran the two test programs and compilation, exercised targeted edge cases, and independently attempted the supplied live URL. Round 3 independently confirmed that all eight implementation findings were resolved. Round 4 reviews the complete operator-run live evidence recorded in `EXECUTION.md` and accepts the task.

## 2. Findings

| ID | Severity | Repository and path | Finding | Required correction |
|---|---|---|---|---|
| `F-01` | `P1` | `knowledge-vault-blueprint:skills/vault-capture/scripts/web_extract.py:151` and `:921` | The SSRF redirect invariant is not implemented. `urlopen()` follows HTTP redirects before `response.geturl()` is validated, so the validation at lines 152-154 occurs after the redirected connection. Playwright validates only the initial URL and then permits navigation/subresource redirects without validating their targets. A public URL can therefore cause a connection to a private/non-global address before rejection. | Disable automatic redirects and validate each resolved `Location` before the next connection. Add an equivalent pre-request/navigation guard for Playwright, including redirect-to-private tests for both paths. Preserve the explicit private-test override only in tests. |
| `F-02` | `P1` | `knowledge-vault-blueprint:skills/vault-capture/scripts/web_extract.py:899-944` | `profile_dir` is accepted and propagated but never used. The browser always calls `chromium.launch()` plus an ephemeral `new_context()`, so `VAULT_CAPTURE_BROWSER_PROFILE` cannot supply the dedicated persistent session required for WeChat login/verification. | Use the configured directory through a dedicated persistent Playwright context, keep it outside Git and out of output, prevent concurrent use as specified, and add an executable test proving the configured profile is actually passed to Playwright. |
| `F-03` | `P1` | `knowledge-vault-blueprint:skills/vault-capture/scripts/vault_capture.py:822-828` | Normalizing a quote-only entry after a comment is appended uses the ordinary replacement string `"批注：\n\n\1"`. Python interprets `\1` there as U+0001, corrupting/removing the hidden `<!-- vault-capture:comment ... -->` prefix. The independent quote-only → same-quote-with-comment diagnostic produced `control_1=True` and `comment_marker=False`. This breaks hidden metadata, compatibility, and later deduplication. | Use a raw replacement/backreference or a callable replacement, and add a regression test for quote-only followed by a comment on the same entry that asserts no control characters, intact hidden comment metadata, and stable deduplication. |
| `F-04` | `P1` | `knowledge-vault-blueprint:skills/vault-capture/scripts/web_extract.py:765-799` | Relative image URLs are normalized to absolute URLs in the manifest, but token rewriting compares the original relative Markdown URL against the absolute-key map. A fixture containing `![...](/img/photo.jpg)` retained that URL, generated an absolute manifest entry, and then failed the deterministic quality gate with `Markdown image tokens do not match image manifest`. Normal generic articles with relative images cannot finalize. | Normalize the URL in the rewrite step (or retain an explicit raw-to-token mapping) and test relative and protocol-relative body images through extraction, quality gate, and `ingest-web` finalization. |
| `F-05` | `P1` | `knowledge-vault-blueprint:skills/vault-capture/scripts/web_extract.py:488-493` and `:1011-1016`; `tests/skills/test_web_extract.py:166` | A detected WeChat DOM rate-limit page is mapped to `failed`; the test explicitly expects that incorrect state. SPEC §4 and AC-05 lock rate limits to `manual`. | Map rate-limit challenges to `manual` in both static and rendered WeChat paths, keep only a short safe reason, and change the test to assert the approved mapping. |
| `F-06` | `P2` | `knowledge-vault-blueprint:skills/vault-capture/requirements-web.txt:1-2` | The direct requirements are ranges (`trafilatura>=1.12.0,<2.0`, `playwright>=1.46.0,<2.0`), contradicting the approved exact pins and `EXECUTION.md`'s claim that the file contains `trafilatura==2.1.0` and `playwright==1.61.0`. The Trafilatura range actually excludes 2.1.0. | Replace both ranges with the exact approved versions, reconcile the lock artifact from a clean disposable environment, and validate installed versions explicitly. |
| `F-07` | `P1` | `knowledge-vault-blueprint:skills/vault-capture/scripts/web_extract.py:555-704`; `tests/skills/fixtures/web/generic_article.html:24-39` | AC-01's own fixture is not preserved as claimed. Independent extraction flattened nested list items to top-level bullets and dropped `Figure 1: Caption for the body image`. `_list_indents` is never used for `li`, and figcaption accumulation copies the whole output buffer rather than caption text. The passing test does not assert nesting or the actual caption. | Correct nested-list depth/ordered-list rendering and caption capture, then strengthen the fixture test to assert indentation/order and the exact caption text. |
| `F-08` | `P2` | `knowledge-vault-blueprint:tests/skills/live_wechat_smoke.py:93-124`; `tasks/2026-08-07-vault-capture-web-markdown/EXECUTION.md` | AC-06 has not been demonstrated. The independent smoke also exited 1 with `state=failed`; safe diagnosis was `URL resolves to a non-public address`. In addition, the tool accepts any `manual` result without proving that static extraction was rejected and browser fallback was attempted, and its unexpected branch omits the safe reason/body/excerpt/image fields required by VAL-06. | Make fallback attempt/method observable in a safe structured result and assert it in the smoke tool; print the required safe diagnostics for every outcome. After the code findings are fixed, rerun VAL-06 in an environment whose DNS/network reaches the public URL and record either complete `ready` evidence or verified browser-fallback `manual` evidence. |

### Round 2 disposition

| ID | Status | Independent round-2 evidence |
|---|---|---|
| `F-01` | `open` | Static auto-redirect was fixed. However, `_make_navigation_guard()` validates only requests whose `resource_type == "document"`; a fake private `image` request produced `private_subresource_action=continue`. Public subresources that redirect to private/non-global targets therefore remain unguarded. The cited `test_redirect_revalidation` only calls `_validate_url()` on an initial loopback URL and does not exercise a redirect or Playwright. |
| `F-02` | `resolved` | `profile_dir` now uses `launch_persistent_context`, an exclusive profile lock is created/removed, and the persistent/concurrent-profile tests pass. |
| `F-03` | `resolved` | The replacement is now a raw backreference; the quote-only → comment regression verifies no U+0001, an intact hidden marker, and stable deduplication. |
| `F-04` | `resolved` | Relative/protocol-relative fixtures now produce two absolute manifest URLs and two Markdown tokens; `quality_gate()` passes. |
| `F-05` | `resolved` | Both DOM and HTTP rate-limit tests now assert and return `manual`. |
| `F-06` | `resolved` | Direct requirements are exactly `trafilatura==2.1.0` and `playwright==1.61.0`; the disposable environment reports those versions. |
| `F-07` | `resolved` | Independent fixture output shows the two nested items indented beneath their parent and one exact caption line; the strengthened test passes. |
| `F-08` | `open` | Diagnostics are now printed and the smoke checks for a browser method. But when `_try_playwright()` raises a WeChat verification/rate-limit `manual` before returning a result, `extract_article()` never appends a browser method. An independent stubbed flow produced `manual_state=manual` with `manual_methods=['static-fetch']`, so the smoke rejects the exact browser-challenge outcome AC-06 permits. Add a regression for this error path. The independent live smoke still exits 1 because DNS resolves the URL to a non-public address. |

### Round 3 disposition

| ID | Status | Independent round-3 evidence |
|---|---|---|
| `F-01` | `resolved` | `_make_navigation_guard(False)` now aborts the same fake private `image` request that round 2 showed was continued. The handler validates every request URL, and all three new document/subresource/override regression tests pass. |
| `F-08` | `resolved` | The same stubbed static-failure → browser-`manual` diagnostic now returns `manual_methods=['static-fetch', 'browser']`. The new regression passes, and the smoke accepts `browser` as proof of fallback. |

No implementation finding remained open after round 3; external validation of AC-06/VAL-06 was the sole item carried into round 4.

### Round 4 final disposition

The external-network VAL-06 run recorded in `EXECUTION.md` is complete and internally consistent:

- exit `0`, `state=ready`, `outcome=ready_ok`;
- `methods_attempted=static-fetch,wechat-static`;
- body length `9135` and `15` localized body images;
- all three required excerpts report `excerpt_present=True`.

The reviewer sandbox retried the same command and remained subject to synthetic `198.18.0.x` DNS, so it could not reproduce the public fetch locally. That constrained retry does not contradict the successful proxy-disabled operator run. SPEC AC-06 requires the exact observed live outcome to be recorded and independently reviewed; it does not require the reviewer and operator to share the same network. The recorded output satisfies the successful `ready` branch, and the implementation producing it has already been independently checked in rounds 1-3.

## 3. Scope compliance

- Allowed-path compliance: `pass`
- Forbidden-path compliance: `pass`
- Unrelated change check: `pass`
- Specification remained unchanged after approval: `not_verifiable`

Evidence:

- All implementation paths reported by `git status --short` are within the approved blueprint path list; `SourceNotes` has no task changes.
- `git diff -- AGENTS.md tasks/README.md tasks/_template/EXECUTION.md tasks/_template/REVIEW.md tasks/_template/SPEC.md` is empty, so the five pre-existing staged files were not modified after the recorded baseline.
- The current specification is approved v1 and contains the recorded approval statement. Because the whole task package remains untracked, Git cannot independently prove its byte-for-byte immutability between approval and execution.

## 4. Independent acceptance check

| Criterion | Verdict | Independent evidence |
|---|---|---|
| `AC-01` | `pass` | Nested-list/caption and relative-image diagnostics now pass; generic structure and token manifest are preserved. |
| `AC-02` | `pass` | The offline WeChat fixture test passed and inspection confirms article-scoped metadata/body and lazy-image handling; no separate defect was found in this criterion. |
| `AC-03` | `pass` | The delayed-render Playwright test passed and the orchestration invokes it only after static content is insufficient. |
| `AC-04` | `pass` | The end-to-end `ingest-web` transaction and existing atomic/finalize regression tests pass; relative-image token/manifest reconciliation also passes independently. |
| `AC-05` | `pass` | Rate limits now map to `manual`; the specified quality/failure fixtures pass. The remaining browser-request SSRF defect is recorded separately as the failed §7 safety invariant (`F-01`). |
| `AC-06` | `pass` | The proxy-disabled operator run exits 0 with `ready_ok`, all three required excerpts, 15 images, and the static WeChat method. The reviewer independently checked the exact output and the responsible implementation; its own sandbox retry remains DNS-constrained. |
| `AC-07` | `pass` | Annotation layout tests pass, including quote-only → comment append with intact hidden metadata. |
| `AC-08` | `pass` | Compatibility regressions pass, schema remains version 1, and SourceNotes is unchanged. |
| `AC-09` | `pass` | Exact dependency pins and persistent external-profile behavior are implemented and independently verified. |
| `AC-10` | `pass` | The 18-test and 29-test programs plus compileall pass, scoped/unstaged diff-check exits 0, only the four recorded pre-existing cached EOF warnings remain, and no forbidden-path task change was found. |

Safety invariant SPEC §7 (public-target validation for browser requests/redirects): `pass`.

## 5. Reviewer validation

| Validation | Exact command or inspection | Exit/result | Evidence summary |
|---|---|---|---|
| Existing capture suite | `C:\tmp\vault-capture-web-markdown-venv\Scripts\python.exe tests\skills\test_vault_capture.py` | `0` | 18 tests passed in round 2. |
| Compilation | `python -m compileall -q skills\vault-capture\scripts tests\skills` | `0` | No compilation errors. |
| Generic fixture inspection (round 2) | Run `extract_generic()` on `tests/skills/fixtures/web/generic_article.html` and inspect Markdown | `pass` | Nested bullets are indented and the exact figcaption appears once. |
| Relative-image diagnostic (round 2) | Run `extract_generic()`/`quality_gate()` on `relative_images.html` | `pass` | Two absolute manifest entries and two image tokens; quality gate passes. |
| Annotation append regression (round 2) | `test_quote_only_then_comment_preserves_hidden_marker` | `pass` | No U+0001; hidden marker and repeat-merge dedup are intact. |
| Web extraction suite (round 3) | With disposable `PLAYWRIGHT_BROWSERS_PATH`, run `...\python.exe tests\skills\test_web_extract.py` | `0` | 29 tests passed; one non-failing Python `ResourceWarning` about a closed socket was emitted. |
| Browser subresource guard diagnostic | Invoke `_make_navigation_guard(False)` with a fake `image` request to `http://127.0.0.1/private.png` | defect reproduced | Handler called `continue_()` rather than `abort()` (`F-01`). |
| Browser-manual methods diagnostic | Stub static fetch to fail and `_try_playwright` to raise `ExtractionError(state='manual')` | defect reproduced | Result methods were only `['static-fetch']`; no browser attempt was recorded (`F-08`). |
| F-01 repeat diagnostic (round 3) | Invoke `_make_navigation_guard(False)` with the same fake private `image` request | `pass` | Handler now calls `abort()` rather than `continue_()`. |
| F-08 repeat diagnostic (round 3) | Stub static fetch to fail and `_try_playwright` to raise `ExtractionError(state='manual')` | `pass` | Error methods are `['static-fetch', 'browser']`. |
| Live URL (round 3) | `...\python.exe tests\skills\live_wechat_smoke.py --url 'https://mp.weixin.qq.com/s/h-cJeGKmXiZOhtz4QVtPeQ'` | `1` | Structured output reports `failed`, safe reason `URL resolves to a non-public address`, zero images/excerpts, and no attempted method because initial validation rejected the synthetic DNS result. |
| Live URL operator run (round 4 evidence) | Same VAL-06 command with proxy disabled | `0` | `state=ready`, `body_length=9135`, `image_count=15`, `methods_attempted=static-fetch,wechat-static`, three `excerpt_present=True`, `outcome=ready_ok`. |
| Reviewer constrained retry (round 4) | Same VAL-06 command in reviewer sandbox | `1` | Still resolved to a synthetic non-public address; recorded as an environment limitation, not contradictory application evidence. |
| Diff checks | Approved scoped `git diff --check`; full unstaged and cached checks | scoped `0`; unstaged `0`; cached `2` | Cached output is limited to the four pre-existing task-template EOF warnings; CRLF notices are non-failing Git notices. |

## 6. Cross-repository consistency

- Blueprint and live-vault responsibilities remain consistent: `pass`
- Schema, templates, examples, and tests agree where applicable: `pass`
- Migration and rollback are adequate where applicable: `pass`

## 7. Verdict

- Verdict: `accepted`
- Required follow-up: `none` for this approved specification.
- Remaining risks: WeChat may change its DOM or access controls in the future; the deterministic quality gates and structured `manual` fallback remain the operational safeguards. The reviewer sandbox's synthetic DNS prevented a second public fetch, but the successful proxy-disabled evidence fulfills AC-06.
- Reviewed at: `2026-08-07T22:56:45+08:00`

This verdict does not authorize commit, push, merge, deployment, publication, staging, or any other external action.
