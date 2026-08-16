# 升级与回退规范

> 本规范定义个人单用户环境下的升级前检查、一次性 E2E、长期浸泡、外部操作账本、三类 schema 回退，以及软件回退与数据保留边界。适用对象为蓝图代码与 OpenClaw 运行配置；正式 Vault 数据时间线保持单调保留（受 [D-022](../DECISIONS.md#d-022vault-数据单调保留软件回退与数据回退分离) 约束）。

## 1. 术语

- **blueprint commit**：蓝图库 `main` 上的一个 commit；是版本身份，可精确复现。
- **last-known-good**：最近一次通过 Linux 验证、可安全作为 production 基线的 blueprint commit；保存在 Vault 与蓝图库之外。
- **Vault checkpoint**：升级前对正式 Vault 的 HEAD、工作树与状态的只读记录（非内容快照覆盖）。
- **maintenance mode**：升级期间暂停自动捕获/写入的运行状态，使同一 checkout 安全更新与验证。
- **soak period**：候选功能在正式环境运行的一周或更长测试期。
- **operation ledger**：不含正文的版本操作账本，记录 blueprint commit、Vault HEAD、Source ID、run/task/session 与受影响路径的关联。
- **incident bundle**：供调试使用的脱敏故障包，位于 Vault 与蓝图库之外。

## 2. 升级前检查

1. 确认没有运行中/排队中的 Vault capture 任务（`openclaw tasks list --status running|queued`）。
2. 检查工作树与远端：目标 Vault 工作树干净或明确已知；跨设备默认 `pull --ff-only`。
3. 记录 Vault checkpoint（HEAD、branch、工作树/暂存状态）。
4. 记录配置与队列摘要（脱敏）：`skills.entries.<name>.enabled`、`VAULT_ROOT` 哈希/basename、queue/archive 计数。
5. 建立外部私有备份：当前 OpenClaw 配置原样备份 + 非敏感配置摘要 + 必要快照（详见本任务阶段产物）。
6. 若任一基线不符或存在运行中任务，停止并人工处理，不自动继续。

**「立即升级前」记录（启用候选前强制）**：在任何候选启用/升级步骤执行前一刻，必须记录正式 Vault 的 HEAD、index、工作树状态与附件基线，并逐字节备份当时活动 OpenClaw 配置、记录其 SHA-256 与 `enabled` 值等脱敏摘要，写入外部 operation ledger。若启用前与记录时刻之间发生状态漂移，先冻结并人工处理，不得在未记录状态下直接启用。

## 3. 更新与验证

- 同一 checkout 更新，**不得同时为测试和 production 加载不同版本**。
- 更新时先进入维护模式（暂停自动捕获），验证通过后再恢复 production。
- 验证步骤：
  1. `openclaw config validate`。
  2. 单元测试 `python tests/skills/test_vault_capture.py`。
  3. 一次性、basename 以 `-test` 结尾的临时 Vault 中执行真实 NotesVaulter E2E。
  4. `openclaw skills list/info/check` 确认来源与 eligible 状态。
- 验证失败：恢复配置并停止；在 `main` 上创建新的修复 commit 或 `git revert`，记录新的 last-known-good，不得改写已验证 commit。

## 4. Production canary 与长期浸泡

- 候选功能可先做 production canary，再进入一周或更长的 soak。
- 浸泡期间正常捕获、手写、commit 与 sync 继续，不做内容取舍。
- 浸泡期产生但质量可疑的数据通过外部 operation ledger 定位，定向修复或标记，不随软件回退删除。

## 5. 外部操作账本

- operation ledger 与 incident bundle 位于 Vault 与蓝图库之外（蓝图库只保存格式、工具与 runbook）。工具为 `scripts/sourcenotes_ops.py` 的 `ledger`/`incident`/`health` 子命令：目录 0700、文件 0600、原子写入；incident 允许完整 URL/错误/上下文与显式诊断文件，但递归扫描 token/Cookie/password/private-key 模式，命中即失败关闭不写 bundle。
- ledger 最小字段（不含正文）：
  - `blueprint_commit`
  - `vault_head`
  - `source_id`
  - `run_id` / `task_id` / `session_id`
  - `affected_path`（路径角色或脱敏相对路径）
  - 时间戳与处置状态
- 蓝图库文档不写入真实正文、逐篇标题/URL、trajectory、secret 或完整主机配置。

### 5.1 单入口与附件预算

- 运行拓扑为「用户 → Steward（唯一入口）→ NotesVaulter（Capture / Query / Maintenance）」，Steward 不直接写 Vault；NotesVaulter 通过受控 entrypoint `scripts/sourcenotes_agent.py` 操作 Vault（见 [D-023](../DECISIONS.md#d-023单入口运行拓扑steward-唯一入口--notesvaulter-三能力--附件预算) 与 [agent-operations.md](agent-operations.md)）。升级/维护写操作一律经 Steward 批准。
- 附件预算：同 Source 事务内内容去重；5 MiB/30 MiB（单 Source **物理落盘唯一附件字节**，重复 token 不重复计入）为软告警（不降 `ready`、不丢附件）；20 MiB 单下载图片、100 MiB 单篇**下载字节**硬限制不变；总量 2 GiB 为决策闸门（仅报告，不自动迁移）。

## 6. 回退

1. 先冻结并保护当前正式 Vault；不倒退 HEAD、不用旧快照覆盖、不删除浸泡期数据。
2. 以 `git revert` 或新的修复 commit 回退蓝图代码到 last-known-good。
3. 恢复 OpenClaw 运行配置（按外部备份/记录的原值），验证配置并非破坏性重载。
4. 协调队列与 archive，清理终态任务或按账本定向修复。
5. 验证浸泡期新增捕获、手写内容与附件仍存在：用 Source ID、相对路径和附件集合的**包含性检查**证明数据仍在（新增捕获可经 Source ID/相对路径定位，附件集合可核对其成员包含关系）；质量可疑数据只定向修复或标记，不随软件回退删除。
- **禁止**：普通回退使用 `reset`/`clean`、旧 Vault 快照覆盖或回退整周数据 commit。破坏性 `reset`/`clean` 仅限明确授权的灾难恢复，且需用户单独批准。

## 7. 三类 schema 策略

| 变更类型 | 处理 |
|---|---|
| 纯行为变化 | 只回退代码；数据不受影响 |
| 向后兼容增量字段 | 旧代码忽略并保留该字段 |
| breaking（改字段含义/结构） | 进入长期正式测试前必须提供双读兼容 Adapter，或可逆、幂等、冲突安全的字段级迁移 |

- breaking schema 需要 migration 与 rollback 指导。
- 逆向迁移遇到用户后续编辑时停止，不静默覆盖。
- 保护不变量：Source 正文、Yanki `noteId`、抓取/阅读状态分离、未知属性。

## 8. 灾难恢复与普通回退的区分

- **普通回退**：只作用于蓝图代码与运行配置，保留 Vault 数据时间线（见 §6）。
- **灾难恢复**：仅当 Vault/仓库发生不可逆损坏或误删时，使用外部私有快照重建现场；恢复前必须保护任何新数据，且需用户单独明确授权；不得以灾难恢复名义覆盖当前正式 Vault 的浸泡期数据。
