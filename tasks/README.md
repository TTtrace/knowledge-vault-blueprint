# Plan-Execute-Review Task Protocol

This directory is the durable control plane for work that benefits from separating planning, implementation, and review. It is especially useful for changes spanning both `knowledge-vault-blueprint` and `SourceNotes`.

## Task package

Create one directory per task:

```text
tasks/YYYY-MM-DD-short-slug/
  SPEC.md
  EXECUTION.md
  REVIEW.md
```

Copy the three files from `tasks/_template/` and replace every placeholder before approval. The task ID must be stable and the same in all three files.

## Document ownership

| File | Owner | Purpose | Executor may edit? |
|---|---|---|---|
| `SPEC.md` | Planner / primary agent | Frozen intent, scope, baselines, acceptance criteria, and validation | No |
| `EXECUTION.md` | `trae` executor | Implementation record and evidence | Yes |
| `REVIEW.md` | Reviewer / primary agent | Independent findings, validation, and verdict | No |

Chat is used for discussion and coordination. These files are the durable handoff record. If chat and an approved specification differ, stop and have the planner revise the specification rather than guessing.

## Status lifecycle

```text
SPEC:       draft -> approved
                         |
EXECUTION:  not_started -> in_progress -> ready_for_review
                                 |          |       |
                                 +-> blocked|       +-> incomplete
                                            v
REVIEW:                             pending -> accepted
                                         |
                                         +-> changes_requested -> executor revision -> pending
                                         +-> blocked
```

Only the user can authorize the planner to change `SPEC.md` from `draft` to `approved`. Only the reviewer can mark the review `accepted`.

If implementation reveals a material design or scope change:

1. The executor records the issue and stops the affected work.
2. The planner changes `SPEC.md` back to `draft` and increments `spec_version`.
3. Repository baselines, scope, acceptance criteria, and validation are updated.
4. The user approves the revised specification.
5. Execution resumes and the review round is incremented.

## Planning checklist

Before approval, the planner must:

1. Confirm both Git worktrees and record `git rev-parse HEAD` for every repository in scope.
2. Record existing uncommitted changes and decide whether they overlap the task.
3. Define goals and non-goals.
4. List allowed and forbidden paths separately for each repository.
5. Record locked design decisions and repository responsibilities.
6. Write acceptance criteria that can be independently checked.
7. Give exact validation commands, working directories, and expected results.
8. State branching, staging, commit, push, and merge permissions.
9. Record the user's explicit approval and approval date.

## Executor handoff

Use the registered `trae` role with a narrow message such as:

```text
Read the approved specification at:
C:\Users\monottx\dox\knowledge-vault-blueprint\tasks\<task-id>\SPEC.md

Implement it exactly. Update only the corresponding EXECUTION.md task record.
Do not edit SPEC.md or REVIEW.md. Return when ready_for_review or blocked.
```

The executor must perform preflight checks before editing, preserve user changes, stay within allowed paths, run the named validations, and record exact evidence. It does not decide final acceptance.

## Review loop

The primary agent reviews from the baselines recorded in `SPEC.md`, not merely from the executor's summary.

1. Inspect each repository's status and diff from its recorded baseline.
2. Check scope and forbidden paths.
3. Evaluate every acceptance criterion independently.
4. Rerun risk-appropriate validation.
5. Check cross-repository consistency.
6. Record findings and the verdict in `REVIEW.md`.

For `changes_requested`, send the same executor the finding IDs and the `REVIEW.md` path. The executor updates the implementation and `EXECUTION.md`; it must not edit the findings or verdict.

## Completion

A task is complete only when:

- `SPEC.md` is approved.
- `EXECUTION.md` is `ready_for_review` and contains evidence.
- `REVIEW.md` is `accepted` with all applicable acceptance criteria passing.
- Git state and any remaining user actions are explicitly reported.

Acceptance does not authorize commit, push, merge, deployment, or publication. Those actions require the permissions recorded in `SPEC.md` or a new explicit user instruction.

