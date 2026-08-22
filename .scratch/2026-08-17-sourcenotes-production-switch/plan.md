# SourceNotes production switch — Effort Plan

Phase: `PLAN`
Status: approved
Date: 2026-08-17
Approved by: Operator
Specification: `.scratch/2026-08-17-sourcenotes-production-switch/spec.md`（approved）
Route: `STANDARD`

## 方案摘要

先用一个无生产写入的纵向 Work Item 固定基线、运行隔离验证并产出精确 cutover package；独立 Review PASS 后停在 Controlled Action gate。Operator 轮换凭据并执行精确配置切换。随后第二个只读 Work Item 独立验证实际运行态、canary、last_known_good 与 soak 起点。

## 技术结构

- Project State / Evidence：`.scratch/2026-08-17-sourcenotes-production-switch/**`
- 无模型受控入口 E2E：一次性 `/tmp/**-test` Vault，不复用 SourceNotes-test。
- 真实模型委派 canary：后续 Operator Controlled Action 中，把干净正式 SourceNotes 只读完整克隆为一次性 `SourceNotes-production-canary-<id>-test`，暂停真实入口后让活动 Gateway 暂时指向该克隆；不得把模型密钥复制到另一 Gateway。
- 私有 cutover 状态：`~/.local/state/sourcenotes-production-switch/2026-08-17/**`，由 Operator Controlled Action 创建，0700/0600。
- 活动配置：`~/.openclaw/openclaw.json`，只在独立 Controlled Action 中修改。

## Module 与 Seams

- Steward seam：`main` 的 subagent allowlist 与结构化委派提示/配置。
- NotesVaulter seam：agent skill allowlist、skill entries、`VAULT_ROOT` 与受控 `sourcenotes_agent.py`。
- Runtime seam：OpenClaw config validate、Gateway、新 session 与 skills eligibility。
- Data seam：SourceNotes 在切换阶段只读；实际 capture 只接受后续真实用户输入。

## Work Item 与 Evidence 规则

- Work Item 01：preflight + isolated validation + cutover package；不得写活动配置或两个 Vault。
- Controlled Action gate：Operator 单独执行凭据轮换与精确 cutover；不属于 Technical Loop。
- Work Item 02：切换后只读复核 actual state、Query/Maintenance canary、last_known_good 与 soak 起点。
- Execution Evidence 写 `evidence/<NN>/execution.md`；Reviewer verdict 由 Planner 写 `evidence/<NN>/review.md`。
- CHANGES_REQUESTED 最多两轮范围内修复；NEEDS_REPLAN/BLOCKED 立即停止。

## 验证策略

- Interface：config schema、skills info/check、受控 CLI 子命令与 secret-free output。
- Integration：全新 `*-test` Vault、Steward 候选委派配置、NotesVaulter 三技能。
- Behavior：正式 Vault 零意外写、单公开入口、只读 canary、配置回滚与数据单调保留。

## Work Item DAG

```text
01-preflight-and-cutover-package
  → Operator exact Controlled Action
    → 02-post-cutover-verification
```

## 风险控制

- 切换前逐字节备份配置并记录 SHA；配置失败只恢复配置。
- 真实 canary 先克隆正式库再写测试数据；正式库全程不承载测试写入。canary 失败恢复配置，临时克隆只在保存必要脱敏诊断后删除。
- 不打印、复制或记录 token；轮换由 Operator 在私有通道完成。
- 不清理 SourceNotes-test；不在正式 Vault 写测试数据。
- 任何状态漂移先停止，不自动覆盖。

## 来源事实

- `specifications/upgrade-workflow.md`
- `specifications/openclaw-skill-workflow.md`
- `specifications/agent-operations.md`
- OpenClaw 本机文档：`subagents.allowAgents` 默认仅允许同 agent，需显式窄配置。

## Approval record

- Approval statement: `批准上述第一层计划；本次不迁移测试库，main 作为 Steward，切换前轮换 Telegram 凭据。`
- Approved by: Operator
- Date: 2026-08-17
- Approved amendment: Operator 于 2026-08-17 同意正式库完整临时克隆 canary 方案。
