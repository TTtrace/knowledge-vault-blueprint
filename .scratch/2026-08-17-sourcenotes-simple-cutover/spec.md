# SourceNotes simple cutover — Specification

Phase: `SPECIFY`
Status: approved
Date: 2026-08-17
Approved by: Operator
Route: `STANDARD`

## 问题

蓝图运行基础已完成，但活动 OpenClaw 仍在测试/维护态。此前两轮 cutover runbook 因自定义安全 helper 反复审查未过；改用 OpenClaw 原生配置操作，用最小 runbook 完成生产切换，canary clone 保留、不自动删除、不维护自定义 helper。

## 预期结果

活动运行拓扑变为「用户 → main(Steward) → notesvaulter(Capture/Query/Maintenance)」，生产 Vault 由宿主 `VAULT_ROOT` 指向 SourceNotes，切换前轮换 Telegram 凭据，失败只恢复配置、不倒退 Vault。

## 范围

### 包含

- 冻结蓝图/两 Vault/活动配置/队列基线。
- 原生 dry-run 验证 canary 与 production 配置 patch。
- canary clone 的完整 clone rehearsal（/tmp 一次性 fixture）。
- 轮换凭据后经 `~/.openclaw/.env` env 替换注入 token 与 Vault 路径。
- canary 与 production 两条 native patch + 精确验证命令。
- production 切换后由 Work Item 02 做只读 Query/Maintenance 验证。

### 明确不包含

- 不迁移、删除 SourceNotes-test 数据；不清理、不自动删除 canary clone。
- 不向正式 Vault 写合成测试数据。
- 不修改产品代码、schema、Source 正文或 Yanki noteId。
- 不 stage/commit/push。
- 不维护自定义 secure helper、ownership manifest、provenance/cleanup 脚本。
- 不自动执行凭据轮换、活动配置写入、Gateway reload/restart 或其它 Controlled Action。

## 产品契约

- 用户只有 Steward 一个公开入口；NotesVaulter 直接 Telegram binding/account 移除，仅经 main 内部委派。
- main 显式 `subagents.allowAgents: ["notesvaulter"]`，禁止 `*`。
- NotesVaulter allowlist 三个 Vault skill 且 eligible。
- `VAULT_ROOT` 与 Telegram token 只经 `~/.openclaw/.env`（0600）env 替换进入配置；仓库/Evidence 只报告 basename 与 token 存在布尔值。
- 配置写入与回滚均由 OpenClaw 原生命令完成；软件回滚不倒退 Vault 数据。

## 验收条件

- **AC-01**：候选 commit 与三仓/配置/队列基线冻结，无未解释漂移。
- **AC-02**：canary 与 production patch 经 `config patch --dry-run` 通过；`config validate` 通过；不触碰活动配置。
- **AC-03**：canary patch 语义正确：telegram disabled、NotesVaulter account/binding 移除、main=Steward、窄 allowAgents、三 skill enabled、VAULT_ROOT 走 env 替换；production patch 仅恢复 telegram。
- **AC-04**：canary clone rehearsal 证明源零写入、push 禁用、clone 结构一致、不自动删除。
- **AC-05**：runbook 不含自定义 helper，全部真实命令标注 Operator-only；仓库/Evidence 无绝对 Vault 路径、secret、正文或逐项 URL。
- **AC-06**：Operator Controlled Action 后 config validate、health、skills eligible、Steward→NotesVaulter 委派通过（Work Item 02 复核）。
- **AC-07**：生产 Query/Maintenance 只读 canary 通过，正式 Vault HEAD/index/既有内容无意外变化（Work Item 02）。
- **AC-08**：last_known_good=017c2ce1… 记录，soak 开始；失败恢复配置不回退数据（Work Item 02）。

## 风险与约束

- 凭据已被早前只读调查触及，生产前必须轮换；未轮换则 BLOCKED。
- `config patch` 对数组默认整体替换；移除 bindings/accounts 需经 native `--replace-path` 或 `null` 删除语义，dry-run 自检为准。
- `.env` 不覆盖进程已存在同名变量；选用全新变量名。
- canary clone 保留意味着后续需单独决定清理；本 Effort 不删除。

## 批准记录

- Approval statement: `批准简化重规划：使用 OpenClaw 原生配置操作，canary clone 暂不自动删除，停止维护自定义安全 helper。`
- Approved by: Operator
- Date: 2026-08-17
