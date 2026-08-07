# Repository Agent Instructions

## Repository role

This repository is the source of truth for the knowledge-vault architecture, specifications, decisions, skills, automation, examples, and tests.

The sibling repository `C:\Users\monottx\dox\SourceNotes` is the live Obsidian vault. Do not treat the two repositories as interchangeable. A task that changes both must state the changes, allowed paths, baselines, and validation for each repository separately.

## Plan-execute-review workflow

Canonical task packages live under `tasks/<task-id>/`. Follow [tasks/README.md](tasks/README.md) whenever a task package is named.

- The planner owns `SPEC.md`. It discusses the design with the user, records repository baselines and measurable acceptance criteria, and changes the status to `approved` only after explicit user approval.
- The `trae` executor owns `EXECUTION.md`. It may implement only an approved specification and must not edit `SPEC.md` or `REVIEW.md`.
- The primary agent is the reviewer and owns `REVIEW.md`. It independently checks the diff and validation evidence and returns `accepted`, `changes_requested`, or `blocked`.
- After approval, a material scope or design change returns the specification to `draft`, increments `spec_version`, and requires user approval again.
- Small direct edits may proceed without a task package only when the user explicitly requests direct implementation. Cross-repository work and changes to architecture, schema meaning, lifecycle, automation contracts, or migration behavior require an approved task package.

## Repository constraints

- Before architectural work, read `README.md`, `BLUEPRINT.md`, `DECISIONS.md`, `ROADMAP.md`, and the relevant files under `specifications/`.
- A change to existing data meaning must update `DECISIONS.md`, increment the applicable schema version, include migration and rollback guidance, and be validated on a small sample.
- Preserve Source body immutability, Yanki `noteId`, the split between capture and reading states, and the division of responsibilities among Zotero, Obsidian, Yanki, Git, and automation unless an approved specification explicitly changes them.
- Prefer existing scripts and tests. The current Python test suite is run with `python tests/skills/test_vault_capture.py` from this repository.
- Never write test data into the live `SourceNotes` vault. Use disposable temporary vaults for automated tests.
- Do not commit secrets, credentials, cookies, private keys, large PDFs, video, long audio, or device-specific Obsidian state.

## Change safety

- Preserve unrelated and pre-existing worktree changes. Never clean, reset, or overwrite them.
- Keep changes narrowly within the approved paths and avoid unrelated formatting or generated-file churn.
- Run the validations named by the task and `git diff --check` in every touched repository.
- Do not commit, push, merge, publish, or perform destructive operations unless the user and the approved specification explicitly authorize the action.
