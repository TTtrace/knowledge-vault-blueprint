# SourceNotes production switch — SHAPE checkpoint

Phase: `EXECUTE`
Status: in progress
Date: 2026-08-17
Current phase: EXECUTE
Active Work Item: `01-preflight-and-cutover-package`
Next gate: Operator 决定第三次 Review 仍未通过的处置；Controlled Action gate 保持关闭

## Objective

以蓝图库 `main@017c2ce1fb2ef00f4fdc4e6f872a9877c49890da` 为候选，在不覆盖正式 Vault 数据的前提下，把活动 OpenClaw 从测试/维护态切换为「Steward 唯一入口 → NotesVaulter（Capture / Query / Maintenance）」生产运行态。

## Route and role

- Route: `STANDARD`，生产配置写入与启用属于独立 Controlled Action，不能由 Phase Advance、VERIFIED 或 ACCEPTED 隐式授权。
- Host Role: Planner。
- 本 checkpoint 是新请求的 Project State，不续接或接管旧任务。

## Decisions so far

- Operator 于 2026-08-17 明确发起正式生产切换。
- Operator 于 2026-08-17 明确批准第一层计划：本次不迁移测试库、`main` 作为 Steward、切换前轮换 Telegram 凭据。
- 候选蓝图 commit 为当前 `main/origin/main@017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`；当前蓝图与正式 SourceNotes 工作树只读检查为 clean。
- 正式切换不得以旧快照覆盖 SourceNotes，不得删除 SourceNotes-test 数据，不得改写 Source 正文或 Yanki `noteId`。
- 先完成隔离验证与精确配置 diff，再由 Operator 对精确 Controlled Action 单独授权；Planner/Executor/Reviewer 均不执行或授权 Controlled Action。

## Open top-level decisions

- none；第一层范围已锁定。任何目标、允许路径、架构决定或 AC 变化必须回到第一层重新批准。

## Known implementation facts

- 蓝图库当前实现含受控入口 `scripts/sourcenotes_agent.py`、三个 Vault skills 及运维工具；后继 final-safety-fixes 已关闭 fd ownership 与脱敏边界缺陷。
- 活动配置仍为维护/测试态：capture disabled、VAULT_ROOT 指向 basename `SourceNotes-test`、query/maintenance disabled。
- NotesVaulter 当前仅 allowlist `vault-capture`；当前配置仍有 NotesVaulter 的独立 Telegram binding。
- OpenClaw 文档说明 `subagents.allowAgents` 默认只能委派同一 agent；要让 Steward 委派 NotesVaulter，必须显式允许 `notesvaulter`。
- 仓库未提供独立 Steward skill；推荐复用现有 `main` agent 作为 Steward，而不是新增第二个用户入口。

## Deferred design details

- 精确 OpenClaw JSON patch、备份目录、验证命令与 operator-run cutover runbook 在第一层批准后写入 plan.md 与 execution brief。
- 首次 production capture 使用真实用户输入，不写合成测试数据；切换前 capture E2E 只在全新 basename 以 `-test` 结尾的一次性 Vault 中执行。

## Approval record

- Approval statement: `批准上述第一层计划；本次不迁移测试库，main 作为 Steward，切换前轮换 Telegram 凭据。`
- Approved by: Operator
- Approval date: 2026-08-17
- Controlled Action boundary: 本批准锁定第一层计划并授权 Work Item 01 Technical Loop；不授权生产配置写入、凭据轮换、Gateway reload/restart 或其它 Controlled Action。

## Current blocker

- Work Item 01 的 CHANGES_REQUESTED 修复轮 1 停在 `STEP-R5 / VAL-R1-03`。
- 原因：真实 Steward→NotesVaulter 隔离 E2E 需要模型认证；模型凭据只存在于活动 OpenClaw 私有配置/auth profile，不在环境或独立 SecretRef 中。按获批边界，Executor 不得读取后复制 secret 到一次性 state，因此不能启动可真实推理的完全隔离 Gateway。
- 当前状态保持安全：蓝图与两个 Vault未写，活动配置 hash 不变，默认 Gateway 未 reload/restart，queue 0/0，无临时目录、stage/commit 或 Controlled Action。
- Operator 已选择不复制模型密钥：真实委派 E2E 在后续 Controlled Action 中使用活动 Gateway，但先暂停真实入口、把干净正式 SourceNotes 完整克隆为一次性 basename 以 `-test` 结尾的 canary Vault，并暂时指向该克隆；通过后才切换正式 Vault，失败恢复配置并删除临时克隆。
- 该决定不授权当前 Agent 执行活动配置写入/reload/restart；当前 Work Item 只修复 cutover package、Evidence 与无生产写入验证。

## Approved amendment

- Operator statement: `好的 同意此方案`
- Date: 2026-08-17
- Locked design: 不把测试数据写进正式 SourceNotes；以正式库的只读完整克隆 `*-test` 做高保真 canary；真实模型委派 E2E 属后续 Operator Controlled Action 的前半段，成功才继续 production cutover。

## Executor failure after review round 2

- Reviewer round 2 仍为 `CHANGES_REQUESTED`，要求在第二个、最后一个自动修复轮关闭 F-01 至 F-07、F-09 至 F-12；F-08 已关闭。
- 同一 Executor 会话在接受 `execution-brief-01-repair-round-2.md` 后连续返回损坏、非结构化输出，无法提供 STATUS/Evidence；Planner 只读检查确认 `cutover-package.md` 与 `evidence/01/execution.md` 未出现 round 2 修复内容。
- 因无法确认执行状态，按 BLOCKED 处理；未委派 Reviewer。当前活动配置、默认 Gateway、两个 Vault与 Git 保持未写状态。
- 待 Operator 决定是否以全新 Executor 会话重试同一个最终修复轮；该重试不扩大第一层范围，也不执行 Controlled Action。
- Operator 于 2026-08-17 明确回复：`同意更换 Executor 并重试最终修复轮。` 已授权用全新 Executor 会话重试同一 Work Item 的第二个、最后一个修复轮；不增加修复轮次、不扩大范围、不授权 Controlled Action。

## Final review outcome

- 全新 Executor 完成最终修复轮并返回 READY_FOR_REVIEW；Reviewer round 3 仍给出 `CHANGES_REQUESTED`。
- 未关闭 major：F-04、F-07、F-11，以及新发现 F-13、F-14、F-15；详见 `evidence/01/review.md`。
- 由于这是第三次 Review，按 lifecycle 停止自动修复；Work Item 01 保持 `claimed`，Effort 未 VERIFIED，生产 Controlled Action 未授权也未执行。
