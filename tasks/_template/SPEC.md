---
task_id: YYYY-MM-DD-short-slug
title: Replace with a concise outcome
status: draft
spec_version: 1
planner: primary
executor: trae
created: YYYY-MM-DD
approved_at: null
approved_by: null
---

# Task Specification

> This file is owned by the planner. After `status: approved`, the executor must not edit it. A material change returns it to `draft`, increments `spec_version`, and requires approval again.

## 1. Context and problem

Describe the current behavior, why it matters, and the evidence that motivated the task.

## 2. Required outcome

State the observable result in one or two paragraphs.

## 3. Non-goals

- Explicitly excluded behavior or cleanup.
- Follow-up ideas that must not enter this task.

## 4. Locked decisions

- Decision and rationale.
- Repository ownership or data-flow decision that implementation must preserve.

## 5. Repository baselines

Record these immediately before approval.

| Repository | Absolute path | Base branch | Base commit | Existing worktree changes | Working branch |
|---|---|---|---|---|---|
| `knowledge-vault-blueprint` | `C:\Users\monottx\dox\knowledge-vault-blueprint` | `main` | `<full SHA>` | `none` or exact paths | `none` or exact branch |
| `SourceNotes` | `C:\Users\monottx\dox\SourceNotes` | `main` | `<full SHA>` | `none` or exact paths | `none` or exact branch |

Remove a repository row only when it is explicitly out of scope, then state that fact below.

## 6. Scope by repository

### knowledge-vault-blueprint

Expected changes:

- Describe the required specification, decision, code, test, or example changes.

Allowed paths:

- `<exact path or narrow glob>`

Forbidden paths:

- `<path>`

### SourceNotes

Expected changes:

- Describe the required live-vault, template, dashboard, prompt, or content changes.

Allowed paths:

- `<exact path or narrow glob>`

Forbidden paths:

- `<path>`

## 7. Invariants and safety constraints

- Preserve unrelated and pre-existing changes.
- State data that must not be overwritten, moved, renamed, exposed, or committed.
- State compatibility, migration, privacy, attachment, and rollback constraints.

## 8. Acceptance criteria

- [ ] **AC-01:** Write one independently verifiable outcome.
- [ ] **AC-02:** Write another independently verifiable outcome.
- [ ] **AC-03:** All required validation passes without weakening existing checks.
- [ ] **AC-04:** Each touched repository passes `git diff --check` and contains no out-of-scope changes.

## 9. Validation plan

| ID | Working directory | Exact command or inspection | Expected result |
|---|---|---|---|
| `VAL-01` | `<absolute repository path>` | `<exact command>` | `<exit code and key assertion>` |
| `VAL-02` | `<absolute repository path>` | `git diff --check` | Exit code 0 and no output |

Name manual checks explicitly. Do not describe a manual check as an automated test.

## 10. Deliverables

- Files or artifacts that must exist at handoff.
- Required updates to `EXECUTION.md`.

## 11. Git and external-action permissions

Unless replaced below, the executor must not switch branches, stage, commit, push, merge, publish, deploy, or write to external services.

- Branching: `not authorized`
- Staging: `not authorized`
- Committing: `not authorized`
- Pushing: `not authorized`
- Merging: `not authorized`
- External writes or publication: `not authorized`

## 12. Rollback

Describe how to reverse the implementation without removing unrelated user work.

## 13. Open questions

- `none` before approval, or list every unresolved question.

## 14. Approval record

- Approval statement: `<exact user confirmation>`
- Approved specification version: `<number>`
- Approved at: `<ISO 8601 timestamp with timezone>`

