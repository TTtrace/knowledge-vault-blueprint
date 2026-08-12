---
task_id: 2026-08-12-blueprint-io-evolution
title: Document the blueprint input/output view and evolution candidates
status: approved
spec_version: 1
planner: primary
executor: executor
created: 2026-08-12
approved_at: 2026-08-12T21:42:11+08:00
approved_by: user
---

# Task Specification

> This file is owned by the planner. After `status: approved`, the executor must not edit it. A material change returns it to `draft`, increments `spec_version`, and requires approval again.

## 1. Context and problem

The blueprint already defines nine content types, six Bases, and workflows for capture, reading, literature, journaling, language learning, and Anki. The user now understands the intended system primarily as a personal information repository whose value is realized through its inputs and outputs. That perspective is not yet visible as a unified map in the authoritative blueprint or as an explicit architecture decision.

The discussed input set includes collected articles and audio/video with highlights or annotations; ideas, questions, inspirations, and iterative answers; daily records such as time management, exercise, and sleep; English words and examples; literature and reading notes; AI conversations; and quoted sentences, poems, and aphorisms. Outputs include direct note access, agent answers grounded in the Vault, a reading queue, a personal-life dashboard, Anki cards, and periodic reviews.

Two input gaps need to be durably recorded for later design rather than implemented now:

1. A formed quotation input such as a complete poem with supplied notes is external original material and should evolve as a new Source subtype; the user's own associations remain separate Annotation content.
2. A question-and-answer input should evolve as an Idea variant with exact candidate discriminator `kind: QA`. One question remains one note; current and additional-perspective answers evolve inside that note rather than becoming a fragmentary Idea per answer. A sufficiently mature answer may later be extracted into an independent Idea.

The approved direction also gives the missing read-only knowledge-answering output its own Roadmap stage 5.

## 2. Required outcome

Add an input/output overview to `BLUEPRINT.md`, establish input/output traceability as decision D-021 in `DECISIONS.md`, and update `ROADMAP.md` with the two deferred input requirements, stage-4 life/review outputs, and a distinct stage 5 for knowledge answering and output.

The changes must be documentation-only and additive. They record the conceptual map and future requirements without changing current metadata meaning, declaring candidate schema fields active, implementing templates or automation, or incrementing `schema_version`.

## 3. Non-goals

- Do not implement Source subtypes, `kind: QA`, statuses, templates, Bases, prompts, agents, capture commands, migrations, or automation.
- Do not decide final folder names or metadata fields for quotation/poetry input beyond recording `sources/excerpts/` as a candidate location.
- Do not define the final QA state machine or extraction relation.
- Do not change existing object, lifecycle, Source immutability, Zotero, Yanki, Git, or automation semantics.
- Do not resume, complete, review, or otherwise alter `2026-08-10-vault-capture-wechat-profile-diagnostics`.
- Do not touch the live or test Vaults.
- Do not stage, commit, push, merge, tag, release, or publish.

## 4. Locked decisions

- Input/output is an additional architecture view, not a replacement for the existing content-type, engagement, and lifecycle axes.
- D-021 requires bidirectional traceability: every proposed input must identify the output(s) that consume or surface it; every proposed output must identify its source objects and required fields. This is a design gate against unconsumed collection and unsupported dashboards/answers.
- A complete poem or comparable formed quotation plus supplied textual notes is external original material and a candidate Source subtype. Personal reflection and association remain separate Annotation content, preserving Source body immutability and the existing Source-to-Annotation relationship.
- Question-and-answer input is a future `type: idea` variant with exact candidate value `kind: QA`.
- One QA note owns the question and its evolving answers. Current answer, additional perspectives, and follow-up/reflection may be sections in the same note. Answers are not required to become separate Ideas; only a mature independently useful answer may later be extracted as an Idea.
- Structured life metrics and the personal-life dashboard, plus periodic review output, are assigned to Roadmap stage 4 as future work.
- Read-only grounded knowledge answering and output are assigned to a distinct Roadmap stage 5. Its future contract includes source citation by note ID/path and a read-only allowlist by default.
- The input/output map must label capabilities honestly as supported, partially supported, or planned/gap; it must not describe candidate behavior as currently implemented.
- This task does not change schema meaning or version and has no migration.

## 5. Repository baseline

| Repository | Absolute path | Base branch | Base commit | Existing worktree changes | Working branch |
|---|---|---|---|---|---|
| `knowledge-vault-blueprint` | `/home/monottx/repos/knowledge-vault-blueprint` | `main` | `f9810f1ff454aaa4c7d0561a0d4dec1ca5bd5128` | Exact pre-existing paths listed below | `main` |

Pre-existing worktree state at approval:

```text
 M DECISIONS.md
 M skills/vault-capture/SKILL.md
 M skills/vault-capture/references/runtime-contract.md
 M skills/vault-capture/references/web-runtime.md
 M skills/vault-capture/scripts/vault_capture.py
 M skills/vault-capture/scripts/web_extract.py
 M specifications/capture-workflow.md
 M specifications/openclaw-skill-workflow.md
 M tests/skills/test_vault_capture.py
 M tests/skills/test_web_extract.py
?? tasks/2026-08-10-vault-capture-wechat-profile-diagnostics/
```

`DECISIONS.md` overlaps this task. Before this task it has `17` added and `1` deleted line relative to HEAD; its pre-task diff SHA-256 is `34bfd6f3d2e6f386407ae5312a4280e71a3b20842828b4ec43b41507e269c833`. Those changes add D-020 and must be preserved exactly. This task may only add D-021 and its summary-table row around that baseline; it must not correct or reorganize D-020 or other pre-existing content.

`SourceNotes`, `SourceNotes-test`, host OpenClaw configuration, and external browser profile state are entirely out of scope.

## 6. Scope by location

### `knowledge-vault-blueprint`

Expected changes:

- Add the input/output overview and closed-loop design guidance to `BLUEPRINT.md`.
- Add D-021 and its decision-table entry to `DECISIONS.md`.
- Add stage-4 output items, stage 5, and a deferred-requirements section to `ROADMAP.md`.
- Create executor/reviewer records under this task package according to ownership.

Allowed paths:

```text
BLUEPRINT.md
DECISIONS.md
ROADMAP.md
tasks/2026-08-12-blueprint-io-evolution/SPEC.md (planner only; executor/reviewer must not edit)
tasks/2026-08-12-blueprint-io-evolution/EXECUTION.md (executor only)
tasks/2026-08-12-blueprint-io-evolution/REVIEW.md (reviewer only)
```

Forbidden paths:

- Every repository path not listed above.
- In particular: `skills/**`, `specifications/**`, `tests/**`, `examples/**`, `vault-starter/**`, other task packages, and all Git metadata/index operations.
- The executor must not edit `SPEC.md` or create/edit `REVIEW.md`.
- The reviewer must not edit implementation files, `SPEC.md`, or `EXECUTION.md`; it owns only `REVIEW.md`.

## 7. Invariants and safety constraints

- Preserve all unrelated and pre-existing worktree/index changes; never reset, clean, restore, checkout over, or broadly unstage them.
- Preserve the pre-existing D-020 documentation exactly while adding D-021.
- Preserve current object meanings and the three existing axes. Candidate Source subtype and `kind: QA` must be clearly marked deferred, not active schema.
- Preserve Source body immutability and the separation of external material from personal Annotation content.
- Use the exact candidate discriminator spelling and case `kind: QA`; do not substitute `question`, `qa`, or a new `type`.
- Do not create a separate Idea for every answer in the described future model.
- Do not claim that the life dashboard, periodic review, or read-only answering agent exists today.
- Do not change `schema_version`; no migration or live-Vault action exists.
- Keep edits narrow and avoid unrelated rewriting, numbering churn, or formatting changes.

## 8. Acceptance criteria

- [ ] **AC-01 — Input/output overview:** `BLUEPRINT.md` contains a coherent input/output overview mapping every approved input and output to the current object/directory or future destination, with honest supported/partial/planned status and a closed-loop explanation. It remains consistent with the existing nine types, six Bases, and three-axis model.
- [ ] **AC-02 — Traceability decision:** `DECISIONS.md` contains exactly one D-021 summary row and one D-021 section, formatted consistently with existing decisions. It establishes both traceability directions, explains the collection-graveyard/unsupported-output risk, and states the documentation-only/no-schema boundary.
- [ ] **AC-03 — Deferred quotation requirement:** `ROADMAP.md` records the complete-poem/formed-quotation requirement as a candidate Source subtype (candidate `sources/excerpts/`), keeps supplied textual notes with the immutable Source, keeps personal thought/association in Annotation, and names unresolved origin/mobile-input/metadata questions without activating a schema.
- [ ] **AC-04 — Deferred QA requirement:** `ROADMAP.md` records exact candidate `type: idea` plus `kind: QA`, one question per file, in-note iterative current/additional-perspective answers, optional later extraction of mature answers, and unresolved template/state-machine questions. It does not require one Idea per answer.
- [ ] **AC-05 — Output evolution:** `ROADMAP.md` adds structured personal-life dashboard and periodic review work to stage 4 and a separate stage 5 for read-only, source-cited knowledge answering/output with a meaningful exit condition. It does not claim implementation.
- [ ] **AC-06 — Scope and preservation:** Only allowed files are newly changed by this task; D-020 and every pre-existing change are preserved; current task `2026-08-10-vault-capture-wechat-profile-diagnostics` is untouched; no Vault/config/external state is read or written.
- [ ] **AC-07 — Documentation quality:** Headings, numbering, links, terminology, status labels, and Markdown tables are internally consistent; the additions avoid duplicate authority or contradictions with README/BLUEPRINT principles.
- [ ] **AC-08 — Validation:** Named documentation checks and `git diff --check` pass. No stage/commit/push occurs.

## 9. Validation plan

| ID | Working directory | Exact command or inspection | Expected result |
|---|---|---|---|
| `VAL-01` | `/home/monottx/repos/knowledge-vault-blueprint` | `git diff --check -- BLUEPRINT.md DECISIONS.md ROADMAP.md tasks/2026-08-12-blueprint-io-evolution` | Exit 0 and no output. |
| `VAL-02` | same | `python3 - <<'PY'` content assertions over the three documents for one D-021 row/section, exact `kind: QA`, the input/output overview, stage 5, and the two requirement candidates | Exit 0; each required marker occurs in the intended document and D-021 occurs once as a row and once as a section. Record the complete assertion script in `EXECUTION.md`. |
| `VAL-03` | same | Review `git diff -- BLUEPRINT.md DECISIONS.md ROADMAP.md` against §4 and AC-01..07 | Only approved additive documentation appears; D-020 remains intact; no candidate is misrepresented as active schema. |
| `VAL-04` | same | `git status --short` and `git diff --stat` compared with §5 baseline | Newly changed paths are limited to `BLUEPRINT.md`, `ROADMAP.md`, additive D-021 changes in already-modified `DECISIONS.md`, and this task package's role-owned files. Pre-existing paths remain present and unstaged. |
| `VAL-05` | same | `git diff --name-only --diff-filter=ACDMRTUXB` plus untracked-path inspection limited to task-package names | No tracked path outside the three approved blueprint documents is changed by this task; no other task package is edited. |

## 10. Deliverables

- Updated `BLUEPRINT.md`, `DECISIONS.md`, and `ROADMAP.md` satisfying AC-01..07.
- Executor-owned `EXECUTION.md` with exact preflight, change summary, and VAL evidence.
- Reviewer-owned `REVIEW.md` after independent review.

## 11. Git and external-action permissions

- Branching: `not authorized`
- Staging: `not authorized`
- Committing: `not authorized`
- Pushing: `not authorized`
- Merging/tagging/releasing/publishing: `not authorized`
- Vault, host-config, browser-profile, or other external writes: `not authorized`

## 12. Rollback

Remove only this task's input/output overview, D-021 row/section, Roadmap stage-4 additions, stage 5, and deferred-requirement section. Preserve D-020 and all other pre-existing worktree changes byte-for-byte. Do not use reset, clean, restore, or broad checkout. No schema/Vault migration or external rollback exists.

## 13. Open questions

- None. Final Source subtype name/fields and QA template/state machine are deliberately deferred requirements, not unresolved decisions needed for this documentation task.

## 14. Approval record

- Approval statement: `问题-回答输入：type：idea 的 kind：QA变体。阶段 5「知识问答与输出」单列，我同意。`
- Approved specification version: `1`
- Approved at: `2026-08-12T21:42:11+08:00`
