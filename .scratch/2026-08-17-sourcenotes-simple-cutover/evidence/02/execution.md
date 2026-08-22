# Work Item 02 — Execution Evidence

Effort: `.scratch/2026-08-17-sourcenotes-simple-cutover/`
Work Item: `issues/02-post-cutover-verification.md`
Role: Executor
Date: 2026-08-18
Brief: `execution-brief-02.md` (authoritative)

## Summary

Post-cutover read-only verification completed. Operator already performed the exact
Controlled Action (per brief §1). This Work Item only re-verified the actual runtime
state against AC-06/07/08 and established the soak entry point. All checks are
read-only. No active config, Gateway restart, either Vault, or git index was written.

## Controlled Actions declaration

No commit, push, merge, deploy, publish, active `openclaw.json` write, Gateway
reload/restart, Vault write, credential rotation, or custom-helper creation was
performed or authorized. Only `evidence/02/execution.md` was newly created. No
`stage`/`commit`. No `git push` executed.

## Acceptance coverage

- **AC-06 PASS** — actual config + runtime match production topology:
  `config validate` exit 0; telegram `enabled=true` (production restored); telegram
  accounts only `default`; single binding `main→telegram:default`; `main.name=Steward`;
  `main.subagents.allowAgents=["notesvaulter"]` (no `*`); `agents.list[1].skills` =
  3 Vault skills; `skills.entries.vault-capture.env.VAULT_ROOT` resolved to production
  basename `SourceNotes`; Gateway running/healthy/loopback; skills eligible
  (`vault-capture/vault-maintenance/vault-query` visible, Missing requirements 0);
  tasks 0 queued · 0 running.
- **AC-07 PASS** — production Query/Maintenance read-only canary passed and formal
  Vault unchanged: formal Vault HEAD `ec1a90eb`, porcelain 0 bytes (empty) before and
  after canary; `maintenance report` returns git/sources/attachments read-only fields
  exit 0; `query search "sourcenotes-canary-20260818"` returns `count=0` (marker is
  confined to the canary clone, proving no leak into the formal Vault).
- **AC-08 NOT_RUN** — private ledger `ledger.txt` absent (Operator-created state dir);
  `last_known_good`/soak start not yet recorded. Operator to run `soak` to record.
  Blueprint HEAD remains `017c2ce` (matches candidate `last_known_good` value).

## Verification commands

### VAL-01 — config state (AC-06)

cwd: `/home/monottx/repos/knowledge-vault-blueprint` (openclaw binary on PATH)

| command | exit | key output |
|---|---|---|
| `openclaw config validate` | 0 | `Config valid: ~/.openclaw/openclaw.json` |
| `openclaw config get channels.telegram.enabled` | 0 | `true` |
| `openclaw config get channels.telegram.accounts` | 0 | keys `["default"]` (botToken redacted) |
| `openclaw config get bindings` | 0 | single `{agentId:"main", match:{channel:"telegram", accountId:"default"}}` |
| `openclaw config get 'agents.list.0.name'` | 0 | `Steward` |
| `openclaw config get 'agents.list.0.subagents.allowAgents'` | 0 | `["notesvaulter"]` |
| `openclaw config get 'agents.list.1.skills'` | 0 | `["vault-capture","vault-query","vault-maintenance"]` |
| `openclaw config get 'skills.entries.vault-capture.env.VAULT_ROOT'` | 0 | resolved to production basename `SourceNotes` |

### VAL-02 — runtime state (AC-06)

| command | exit | key output |
|---|---|---|
| `openclaw gateway status` | 0 | `Runtime: running (pid …), state active, sub running, last exit 0`; `bind=loopback (127.0.0.1), port=18789`; `Connectivity probe: ok` |
| `openclaw skills check --agent notesvaulter` | 0 | `Visible to model: 3` (`vault-capture`,`vault-maintenance`,`vault-query`); `Missing requirements: 0` |
| `openclaw tasks list --status running --status queued` | 0 | `0 queued · 0 running · 0 issues` |

### VAL-03 — formal Vault unchanged (AC-07)

cwd: formal Vault `SourceNotes` (basename)
- `git rev-parse HEAD` → `ec1a90eb9d41df77cf74e44d51e703d0379882e7` (matches expected `ec1a90eb…`)
- `git status --porcelain` → empty; porcelain=v2 bytes = `0`

### VAL-04 — read-only Query/Maintenance canary (AC-07)

cwd: `/home/monottx/repos/knowledge-vault-blueprint`, VAULT_ROOT → formal Vault basename `SourceNotes`
- `python3 scripts/sourcenotes_agent.py maintenance report` → exit 0; `{"ok":true,"report":{git{head:ec1a90eb…,dirty_count:0,staged_count:0}, sources{total:0}, attachments{count:3}…}}` (read-only fields)
- `python3 scripts/sourcenotes_agent.py query search "sourcenotes-canary-20260818"` → exit 0; `{"count":0,"ok":true,"results":[]}` (marker absent from formal Vault → no leak)
- Post-run formal Vault porcelain=v2 bytes still `0` (no write occurred)

### VAL-05 — canary clone preserved (AC-07 boundary)

cwd: canary clone `SourceNotes-production-canary-20260818-test` (basename)
- `ls -d …-test` → exists (not deleted)
- `git status --porcelain` → staged additions under `notes/ideas/…sourcenotes-canary-20260818…` (4 files)
- `grep -rl "sourcenotes-canary-20260818" …/notes/` → 4 matches under `notes/ideas/` (capture files retained in clone)

### VAL-06 — last_known_good / soak (AC-08)

- `~/.local/state/sourcenotes-simple-cutover/2026-08-17/ledger.txt` → **absent** (`ls`/`cat` exit 1)
- Reported NOT_RUN per brief: Operator to run `soak` to record `last_known_good` and soak start.

## DEVIATIONS

- none material. VAL-06/AC-08 reported NOT_RUN because the private ledger is
  Operator-created and not yet present; this is the documented expected state (brief §2
  VAL-06 explicitly permits NOT_RUN pending Operator `soak`).

## FINAL_STATE

- Blueprint: `main` @ `017c2ce` (matches candidate `last_known_good` value), index clean
  (untracked `.scratch/` is the effort dir). Not staged/committed.
- SourceNotes (formal Vault): `ec1a90eb`, clean (porcelain 0), untouched.
- SourceNotes-production-canary-20260818-test: exists, contains the 4 canary capture
  files (marker present), retained (not deleted).
- Active config `~/.openclaw/openclaw.json`: read-only via `config get`; not written.
- Gateway: running (pid …), state active, loopback; no reload/restart.
- Queue: 0 queued · 0 running.
- New file created: `evidence/02/execution.md`.
- stage/commit: none. Controlled Action: none.
