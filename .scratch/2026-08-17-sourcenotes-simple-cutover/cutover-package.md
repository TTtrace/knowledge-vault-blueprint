# SourceNotes Simple Cutover — Runbook & Patch Package

Status: READY_FOR_REVIEW (Executor Work Item 01)
Date: 2026-08-18
Effort: `.scratch/2026-08-17-sourcenotes-simple-cutover/`
Authorization: Operator approved simplified replan — OpenClaw native config ops only; canary clone preserved (not auto-deleted); no custom security helpers.

> **GATE NOTICE**: This document is a runbook prepared by the read-only Work Item 01. Every real write / reload / rotate step below is a **CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED** by the Executor. This Effort does not grant any Controlled Action; the Operator executes them after independent review and explicit approval.

---

## 0. Scope & invariants

- Target topology: `user → main(Steward) → notesvaulter(Capture/Query/Maintenance)`.
- Only OpenClaw native config operations are used: `config patch`, `config set`, `config validate`, `config get`, `skills check`, `gateway status`. **No custom secure/cleanup/ownership helper.**
- Credentials and the production Vault path are injected only via `~/.openclaw/.env` (0600) env variables, referenced in config as `${OPENCLAW_TELEGRAM_BOT_TOKEN}` and `${OPENCLAW_VAULT_ROOT}`. This document contains only those env **references**, never values.
- The canary clone is **preserved and NOT auto-deleted**. Cleanup is a separate future decision.
- This document contains no absolute Vault path, no token/secret value, and no body/entry-specific URL.

## 1. Baseline freeze (verified by Executor, read-only)

- Blueprint: branch `main`, HEAD `017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`, index clean.
- SourceNotes (production Vault): branch `main`, HEAD `ec1a90eb9d41df77cf74e44d51e703d0379882e7`, status clean.
- SourceNotes-test (test Vault): branch `main`, HEAD `ec1a90eb9d41df77cf74e44d51e703d0379882e7`, has pre-existing staged additions (recorded as existing state; not touched).
- Active config `~/.openclaw/openclaw.json`: SHA-256 `de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424`, perms 0600.
- Queue: 0 active / 0 queued / 0 running.
- Gateway: running, pid `1069854`, state active, bind loopback `127.0.0.1:18789`.

## 2. Preconditions before Operator executes

- [ ] Operator has **rotated** the Telegram bot token (credentials were touched by earlier read-only investigation; production must not use the old value).
- [ ] `~/.openclaw/.env` (0600) exists with brand-new variable names (do not reuse pre-existing process env names):
  - `OPENCLAW_TELEGRAM_BOT_TOKEN=<new rotated token>`
  - `OPENCLAW_VAULT_ROOT=<absolute path of the production SourceNotes Vault>`
- [ ] Operator makes a byte-for-byte backup of `~/.openclaw/openclaw.json` and `~/.openclaw/.env`, and records their SHA-256 in the private state dir `~/.local/state/sourcenotes-simple-cutover/2026-08-17/` (0700/0600). Failure rollback restores config only, never Vault data.

## 3. Patch files

Write the two patch files to a private Operator-controlled location (e.g. `~/.local/state/sourcenotes-simple-cutover/2026-08-17/`). Their content follows.

### 3.1 Canary patch — `canary-patch.json5`

```json5
{
  channels: {
    telegram: {
      enabled: false,
      accounts: {
        default: {
          botToken: "${OPENCLAW_TELEGRAM_BOT_TOKEN}"
        },
        notesvaulter: null
      }
    }
  },
  bindings: [
    {
      agentId: "main",
      match: { accountId: "default", channel: "telegram" }
    }
  ],
  skills: {
    entries: {
      "vault-capture": {
        enabled: true,
        env: { VAULT_ROOT: "${OPENCLAW_VAULT_ROOT}" }
      },
      "vault-query": { enabled: true },
      "vault-maintenance": { enabled: true }
    }
  }
}
```

Semantics (field-level; verified by native dry-run on a sanitized fixture):
- `channels.telegram.enabled → false`
- `channels.telegram.accounts.default.botToken → "${OPENCLAW_TELEGRAM_BOT_TOKEN}"` (env reference only)
- `channels.telegram.accounts.notesvaulter → null` (account removed)
- `bindings` replaced via `--replace-path bindings` to only `main → telegram:default`
- `skills.entries.vault-capture`: `enabled=true`, `env.VAULT_ROOT="${OPENCLAW_VAULT_ROOT}"`
- `skills.entries.vault-query`: `enabled=true`
- `skills.entries.vault-maintenance`: `enabled=true`

### 3.2 Production patch — `production-patch.json5`

```json5
{
  channels: {
    telegram: {
      enabled: true
    }
  }
}
```

Semantics: only re-enables Telegram. `VAULT_ROOT` stays as the env reference; the Operator switches the value to production simply by setting `OPENCLAW_VAULT_ROOT` in `~/.openclaw/.env` (no config change).

### 3.3 Agent-level changes (native `config set`, avoids whole-array copy)

```bash
openclaw config set agents.list[0].name 'Steward'
openclaw config set 'agents.list[0].subagents.allowAgents' '["notesvaulter"]' --strict-json
openclaw config set 'agents.list[1].skills' '["vault-capture","vault-query","vault-maintenance"]' --strict-json --replace
```

## 4. Operator execution sequence (CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED)

> Each of the following is a real write/reload and must be performed **only** by the Operator after explicit approval. The Executor neither executes nor authorizes them.

1. `CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED`
   ```bash
   openclaw config patch --file ./canary-patch.json5 --replace-path bindings
   ```
2. `CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED`
   ```bash
   openclaw config set agents.list[0].name 'Steward'
   openclaw config set 'agents.list[0].subagents.allowAgents' '["notesvaulter"]' --strict-json
   openclaw config set 'agents.list[1].skills' '["vault-capture","vault-query","vault-maintenance"]' --strict-json --replace
   ```
3. `CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED` — restart/reload the Gateway to apply config:
   ```bash
   systemctl --user restart openclaw-gateway
   ```
   (Or an equivalent native reload. Confirm `openclaw gateway status` reports running and healthy.)
4. Verify (read-only):
   ```bash
   openclaw config validate
   openclaw config get channels.telegram.enabled
   openclaw config get channels.telegram.accounts
   openclaw config get bindings
   openclaw config get 'skills.entries.vault-capture.env.VAULT_ROOT'
   openclaw skills check --agent notesvaulter
   openclaw gateway status
   ```
   Expected after canary: telegram disabled; only `default` account; single binding `main → telegram:default`; three Vault skills enabled for `notesvaulter`; `VAULT_ROOT` reads `${OPENCLAW_VAULT_ROOT}`.
5. Real-model canary E2E (STEERING / OPERATOR or approved agent, read-only against the canary clone) — **NOT_RUN in this Work Item**.
6. Production switch (only after canary verified) — `CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED`:
   ```bash
   openclaw config patch --file ./production-patch.json5
   ```
   Set `OPENCLAW_VAULT_ROOT` in `~/.openclaw/.env` to the production Vault before the first production capture.
7. Post-cutover verification (Work Item 02, read-only): validate config/health/skills eligibility/Steward→NotesVaulter delegation; confirm production Vault HEAD/index/untracked unchanged; record `last_known_good=017c2ce1fb2ef00f4fdc4e6f872a9877c49890da` and start soak.

## 5. Rollback (failure path)

- On failure, **restore config only**; never roll back Vault data.
- `CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED`: restore the byte-for-byte backup of `~/.openclaw/openclaw.json` (and `~/.openclaw/.env`), then restart the Gateway. Re-`openclaw config validate`.
- The canary clone is preserved; no cleanup is performed by this Effort.

## 6. Clone rehearsal result (read-only fixture, /tmp)

Performed on a disposable fixture Git Vault (not the production Vault):
- `git clone --no-hardlinks <source> <clone-*-test>`: exit 0.
- `git -C <clone> remote remove origin`: exit 0; `git remote -v` empty → no remote → push disabled.
- Clone HEAD and tree identical to source; clone status clean; file set identical.
- Source HEAD/tree/status unchanged after clone (source zero-write).
- Clone preserved — **not auto-deleted**.

## 7. Dry-run validation summary (read-only fixture)

- Canary patch: `openclaw config patch --file canary-patch.json5 --dry-run --json --replace-path bindings` → `ok:true`, schema `true`, resolvability `true`, exit 0 (with `OPENCLAW_TELEGRAM_BOT_TOKEN` / `OPENCLAW_VAULT_ROOT` present as dummy fixtures).
- Production patch: dry-run → `ok:true`, exit 0.
- `openclaw config validate` on resulting projections: exit 0 (2 expected env-var warnings when env refs not supplied to the validator).
- No active config was written. No real secrets were copied.
