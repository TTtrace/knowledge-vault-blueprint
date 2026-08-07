---
task_id: YYYY-MM-DD-short-slug
status: pending
review_round: 1
reviewer: primary
reviewed_at: null
verdict: pending
---

# Review Record

> This file is owned by the reviewer. Review the repositories and evidence independently; do not accept the executor's summary as proof by itself.

## 1. Review scope and observed state

| Repository | Spec baseline | Reviewed branch and HEAD | Worktree state |
|---|---|---|---|
| `knowledge-vault-blueprint` | `<full SHA>` | `<observed>` | `<git status --short>` |
| `SourceNotes` | `<full SHA>` | `<observed>` | `<git status --short>` |

## 2. Findings

List actionable findings in severity order. Use stable IDs so the executor can respond without rewriting this file.

| ID | Severity | Repository and path | Finding | Required correction |
|---|---|---|---|---|
| `F-01` | `P0/P1/P2/P3` | `<repo:path>` | `<observable problem>` | `<specific outcome>` |

If there are no findings, write `No actionable findings.`

## 3. Scope compliance

- Allowed-path compliance: `pass/fail`
- Forbidden-path compliance: `pass/fail`
- Unrelated change check: `pass/fail`
- Specification remained unchanged after approval: `pass/fail`

Evidence:

- `<diff or repository evidence>`

## 4. Independent acceptance check

| Criterion | Verdict | Independent evidence |
|---|---|---|
| `AC-01` | `pass/fail/not_applicable` | `<evidence>` |
| `AC-02` | `pass/fail/not_applicable` | `<evidence>` |

## 5. Reviewer validation

| Validation | Exact command or inspection | Exit/result | Evidence summary |
|---|---|---|---|
| `VAL-01` | `<command>` | `<exit code>` | `<key output>` |

## 6. Cross-repository consistency

- Blueprint and live-vault responsibilities remain consistent: `pass/fail/not_applicable`
- Schema, templates, examples, and tests agree where applicable: `pass/fail/not_applicable`
- Migration and rollback are adequate where applicable: `pass/fail/not_applicable`

## 7. Verdict

- Verdict: `accepted`, `changes_requested`, or `blocked`
- Required follow-up: `none` or finding IDs and next action
- Remaining risks: `none` or explicit residual risks accepted by the user
- Reviewed at: `<ISO 8601 timestamp with timezone>`

An `accepted` verdict confirms the implementation against the approved specification. It does not authorize commit, push, merge, deployment, publication, or other external action.

