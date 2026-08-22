# SourceNotes production switch — Specification

Phase: `SPECIFY`
Status: approved
Date: 2026-08-17
Approved by: Operator
Route: `STANDARD`

## 问题

蓝图库 `main@017c2ce1fb2ef00f4fdc4e6f872a9877c49890da` 已包含受控入口、Capture / Query / Maintenance 与安全修复，但活动 OpenClaw 仍处于测试/维护态，且 NotesVaulter 仍有独立 Telegram 入口。需要把已验证的基础转成单入口生产运行态，而不迁移测试库或污染正式 Vault。

## 预期结果

活动运行拓扑成为「用户 → `main`（Steward 唯一入口）→ `notesvaulter`（Capture / Query / Maintenance）」；生产 Vault 由宿主 `VAULT_ROOT` 指向 SourceNotes；切换前凭据完成轮换；失败可恢复配置而不倒退 Vault 数据。

## 第一版范围

### 包含

- 固定当前 commit、两 Vault、活动配置与任务队列的切换前基线。
- 在隔离环境验证当前代码、skill 发现、受控入口与临时 `*-test` Vault。
- 生成脱敏、精确、可回滚的 OpenClaw 配置 cutover package。
- `main` 作为 Steward；显式允许其委派 `notesvaulter`。
- NotesVaulter 只通过内部委派服务，并 allowlist/启用三个 Vault skills。
- 生产切换后做只读 Query / Maintenance canary；首次 Capture 等待用户下一条真实输入，不写合成生产数据。
- 建立外部私有配置备份、checkpoint、operation ledger 与 `last_known_good` 记录。
- 真实模型委派 E2E 使用正式 SourceNotes 当前干净基线的完整一次性克隆，克隆 basename 必须以 `-test` 结尾；测试期间活动 Gateway 进入维护模式、暂停真实入口并暂时指向克隆，成功后才切换正式 Vault。

### 明确不包含

- 不迁移、删除、修复或重新抓取 SourceNotes-test 数据。
- 不把合成 E2E 数据写入正式 SourceNotes。
- 不修改蓝图产品代码、schema、Source 正文或 Yanki `noteId`。
- 不 stage/commit/push/merge。
- 不自动执行凭据轮换、活动配置写入、Gateway reload/restart 或其它 Controlled Action。

## 产品契约

- 用户只有 Steward 一个公开入口；NotesVaulter 的直接 Telegram binding/account 从活动拓扑移除。
- Steward 通过显式 `subagents.allowAgents: ["notesvaulter"]`（或当前 OpenClaw 版本的等价精确配置）委派，不能使用宽泛 `*`。
- NotesVaulter 只 allowlist `vault-capture`、`vault-query`、`vault-maintenance`；三个 skill 必须 eligible。
- `VAULT_ROOT` 只存在于宿主私有配置，Evidence 只报告 basename；任何新凭据不得进入仓库、Project State、命令日志或 Evidence。
- 软件回滚只恢复 OpenClaw 配置；正式 Vault 数据时间线不倒退。
- Planner/Executor/Reviewer 不执行或授权 Controlled Action；Operator 必须在看到精确命令、目标和配置 diff 后单独执行/授权。

## 可观察验收条件

- **AC-01**：候选 commit 为 `017c2ce1...`，蓝图库与正式 SourceNotes 无未解释漂移；SourceNotes-test 仅只读记录既有状态。
- **AC-02**：仓库全套既有验证及临时 `*-test` 受控入口验证通过，不触碰正式 Vault。
- **AC-03**：cutover package 给出唯一公开入口、窄 `allowAgents`、NotesVaulter 三技能、生产 VAULT_ROOT、凭据轮换与回滚的精确脱敏 diff/runbook。
- **AC-04**：切换前配置备份/checkpoint/ledger 方案满足 0700/0600、原子写和秘密不进入 Evidence。
- **AC-05**：Operator Controlled Action 前，独立 Reviewer 对实际工件、测试证据和配置候选给出 PASS。
- **AC-06**：Operator 执行精确 Controlled Action 后，配置 validate、Gateway health、skill eligible、Steward→NotesVaulter 委派全部通过。
- **AC-07**：生产 Query / Maintenance canary 只读通过；正式 SourceNotes HEAD/index/既有内容无意外变化。
- **AC-08**：`last_known_good` 精确记录 `017c2ce1...`，soak 开始；失败时恢复配置但不回退 Vault 数据。
- **AC-09**：无 secret、绝对 Vault 路径、正文或逐项 URL 泄露到仓库/Project State/Evidence。
- **AC-10**：真实委派 canary 不写正式 SourceNotes；测试目标是正式库的完整一次性 `*-test` 克隆，失败恢复活动配置，克隆仅在确认无需要保留的诊断后删除。

## 风险与约束

- 凭据已被工具输出触及，生产前必须轮换；未轮换则 BLOCKED。
- OpenClaw 默认只允许 subagent 委派自身；未显式配置窄 allowAgents 时 Steward 委派必失败。
- 直接保留 NotesVaulter Telegram binding 会违反单入口架构。
- SourceNotes-test 有既有脏状态，不得清理、reset 或当作全新 E2E Vault。
- 任何需改变迁移边界、公开入口、允许路径或 AC 的情况为 NEEDS_REPLAN。

## 批准记录

- Approval statement: `批准上述第一层计划；本次不迁移测试库，main 作为 Steward，切换前轮换 Telegram 凭据。`
- Approved by: Operator
- Date: 2026-08-17
- Approved amendment: Operator 于 2026-08-17 回复 `好的 同意此方案`，批准使用正式库完整临时克隆而非复制模型密钥或向正式 Vault 写测试数据。
