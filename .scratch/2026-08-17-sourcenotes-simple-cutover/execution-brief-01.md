# Execution Brief 01 — preflight and dry-run

Role: Executor
Effort: `/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-simple-cutover/`
Work Item: `issues/01-preflight-and-dry-run.md`

## 1. 批准依据

- 第一层 `spec.md` / `plan.md` approved。
- Operator 授权原文：`批准简化重规划：使用 OpenClaw 原生配置操作，canary clone 暂不自动删除，停止维护自定义安全 helper。`
- 本简报只实施获批 Work Item 01 只读技术循环，不改变第一层，不授权任何 Controlled Action。

## 2. 上下文与已排除方案

- 采用 OpenClaw 原生 `config patch --dry-run` / `config validate` / `config get --json` / `skills check`，不再引入自定义 secure/cleanup/ownership helper。
- canary clone 保留、不自动删除；清理由后续单独决定。
- 凭据与 Vault 路径经 `~/.openclaw/.env`（0600）env 替换注入，仓库/Evidence 只含 `${VAR}` 引用与 basename。
- 排除：自定义 helper、向正式 Vault 写测试数据、复制模型 secret、复用旧 runbook。

## 3. 有序原子步骤

### STEP-01 — 只读基线

- 只读记录：蓝图 branch/HEAD/status/index、正式 SourceNotes branch/HEAD/status、SourceNotes-test 既有状态、活动 config SHA-256、queue running/queued、Gateway pid/health、当前语义摘要（agent ids、skills、bindings、accounts、skill enabled 布尔、VAULT_ROOT basename）。
- 不记录任何 token 值、完整配置、绝对 Vault 路径。
- 若蓝图 HEAD 非 `017c2ce1…`、正式 Vault 非 clean、queue 非 0、或相关漂移，返回 BLOCKED。

### STEP-02 — 候选 patch 构造与 native dry-run

- 新增 `cutover-package.md`，含两条 patch（canary / production）与精确 Operator 命令。
- canary patch 语义（字段级，使用 env 替换，无 secret/路径）：
  - `channels.telegram.enabled: false`
  - `channels.telegram.accounts.default.botToken: "${OPENCLAW_TELEGRAM_BOT_TOKEN}"`
  - `channels.telegram.accounts.notesvaulter: null`（删除 account）
  - `bindings` 替换为仅 `main → telegram:default`（需 native `--replace-path bindings`）
  - `skills.entries`：vault-capture enabled=true 且 `env.VAULT_ROOT="${OPENCLAW_VAULT_ROOT}"`；vault-query / vault-maintenance enabled=true
- agent 级改动走 native `config set`（避免整数组复制泄露 workspace 路径）：
  - `openclaw config set agents.list[0].name "Steward"`
  - `openclaw config set 'agents.list[0].subagents.allowAgents' '["notesvaulter"]' --strict-json`
  - `openclaw config set 'agents.list[1].skills' '["vault-capture","vault-query","vault-maintenance"]' --strict-json --replace`
- production patch 仅 `channels.telegram.enabled: true`（VAULT_ROOT 由 `.env` 变量从 canary 值切换到正式值，无需改 config）。
- 使用一次性 fixture config（/tmp `*-test`）运行 `openclaw config patch --file <patch> --dry-run` 与 `config validate`，记录 native 输出与所需 `--replace-path` 结果；不得对活动配置执行任何写操作。

### STEP-03 — clone rehearsal

- 在 /tmp 用干净 fixture Git Vault 演练：`git clone --no-hardlinks <source> <clone-*-test>`，`git -C <clone> remote remove origin`；断言 source HEAD/tree/status 不变、clone 无 remote（push 失败）、clone 结构一致。
- 明确 runbook 中 clone 保留、不自动删除。

### STEP-04 — 隐私与可执行性

- runbook 不含自定义 helper；所有真实写命令标注 `CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED`。
- 扫描 runbook：无绝对 Vault 路径、无 token/secret、无正文/逐项 URL；env 替换 `${OPENCLAW_TELEGRAM_BOT_TOKEN}`、`${OPENCLAW_VAULT_ROOT}` 仅作引用。
- 对未跟踪 Markdown 用 `git diff --no-index --check /dev/null <file>` 检查 whitespace。

### STEP-05 — Evidence

- 新增 `evidence/01/execution.md`，记录 AC-01..05 与 VAL 全量日志、DEVIATIONS、FINAL_STATE。
- AC-06/07/08 标 NOT_RUN（Work Item 02）。真实模型 E2E NOT_RUN — OPERATOR GATE。

## 4. 允许/禁止路径

允许新增/修改：
- `.scratch/2026-08-17-sourcenotes-simple-cutover/cutover-package.md`
- `.scratch/2026-08-17-sourcenotes-simple-cutover/evidence/01/execution.md`
- 本轮 `/tmp/sourcenotes-simple-cutover-*-test/**`（结束删除）

只读：蓝图库其余路径、正式/测试 Vault、`~/.openclaw/openclaw.json` 与 runtime、OpenClaw 文档。

禁止：活动配置写入、Gateway reload/restart、两个 Vault 写、secret 输出/复制、stage/commit、Controlled Action、自定义 helper。

## 5. AC 与 VAL 映射

- AC-01 → VAL-01：三仓/config/queue/Gateway 只读基线。
- AC-02 → VAL-02：fixture `config patch --dry-run` 两条 patch + `config validate` exit 0。
- AC-03 → VAL-03：semantic projection 断言（enabled/bindings/accounts/skills/VAULT_ROOT env 引用）符合 AC-03。
- AC-04 → VAL-04：clone rehearsal 源零写、无 remote、不删除。
- AC-05 → VAL-05：隐私/路径/URL 扫描 + no-index whitespace + 写命令 Operator-only 分类。

## 6. Blocked / deviation

- 需要活动配置写、真实 secret、正式/测试 Vault 写、产品代码改、或 native patch 无法表达批准语义 → BLOCKED/NEEDS_REPLAN。
- 任一 fixture 不通过不得以文档声明替代。

## 7. 返回契约

```text
STATUS: READY_FOR_REVIEW | BLOCKED
CHANGED_FILES: 绝对路径、内容、原因、STEP
ACCEPTANCE_EVIDENCE: AC-01..08 逐项
VALIDATION_LOG: VAL-01..05 cwd/command/exit/key output
DEVIATIONS: none 或逐项
BLOCKERS: none 或逐项
FINAL_STATE: 三仓/config/Gateway/queue/temp/stage/commit/Controlled Action
```
