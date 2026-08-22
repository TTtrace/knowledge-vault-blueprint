# SourceNotes simple cutover — Plan

Phase: `PLAN`
Status: approved
Date: 2026-08-17
Approved by: Operator
Route: `STANDARD`

## 方案摘要

一个只读 Work Item 冻结基线、dry-run 验证 native patch、/tmp clone rehearsal，产出脱敏 cutover runbook 与两个 patch；独立 Review 后停在 Controlled Action gate。Operator 轮换凭据并执行 native patch；随后 Work Item 02 只读复核实际运行态与 soak 起点。

## 技术结构

- Project State / Evidence：`.scratch/2026-08-17-sourcenotes-simple-cutover/**`
- 私有 cutover 状态：`~/.local/state/sourcenotes-simple-cutover/2026-08-17/**`（Operator 创建，0700/0600）
- 凭据/路径注入：`~/.openclaw/.env`（0600）+ 配置内 `${VAR}` env 替换
- 配置：`~/.openclaw/openclaw.json`（OpenClaw 原生原子写，只在 Operator Controlled Action 修改）
- 数据：SourceNotes 正式只读；canary clone 保留不删

## Module 与 Seams

- Steward seam：`agents.list[0]`（main）name + subagents.allowAgents
- NotesVaulter seam：`agents.list[1]`（notesvaulter）skills allowlist；三 skill entries enabled + VAULT_ROOT env 替换
- Channel seam：`channels.telegram` enabled / accounts / bindings
- 验证 seam：`config validate`、`config get --json`、`skills check --agent notesvaulter`、`gateway status`

## Work Item 与 Evidence

- Work Item 01：preflight + native dry-run + /tmp clone rehearsal + cutover runbook；不写活动配置/两 Vault。
- Controlled Action gate：Operator 单独执行凭据轮换与 native patch。
- Work Item 02：切换后只读复核 AC-06/07/08 与 soak 起点。
- Execution Evidence `evidence/<NN>/execution.md`；Reviewer verdict 由 Planner 写 `evidence/<NN>/review.md`。

## 验证策略

- Interface：`config validate`、`config get --json`、patch dry-run。
- Integration：/tmp clone rehearsal、skills eligibility、三 skill env 替换解析。
- Behavior：正式 Vault 零写入、单公开入口、只读 canary、失败只恢复配置。

## Work Item DAG

```text
01-preflight-and-dry-run → Operator exact Controlled Action → 02-post-cutover-verification
```

## 风险控制

- 切换前 Operator 逐字节备份 `openclaw.json` 与 `.env` 并记 SHA；失败只恢复配置。
- 不打印/复制 token；轮换与值只在 Operator 私有通道与 `.env`。
- 不清理 canary clone、不清理 SourceNotes-test、不向正式 Vault 写测试数据。
- 任何基线漂移先停止，不自动覆盖。

## Approval record

- Approval statement: `批准简化重规划：使用 OpenClaw 原生配置操作，canary clone 暂不自动删除，停止维护自定义安全 helper。`
- Approved by: Operator
- Date: 2026-08-17
