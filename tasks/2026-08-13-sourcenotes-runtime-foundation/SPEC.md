---
task_id: 2026-08-13-sourcenotes-runtime-foundation
title: 建立 SourceNotes 单入口 Agent 运行基础与运维工具
status: approved
spec_version: 1
planner: primary
executor: executor
created: 2026-08-13
approved_at: 2026-08-13
approved_by: user
---

# Task Specification

## 1. 批准依据

用户已明确批准 SourceNotes 整体正式运行方案，并进一步锁定：

- 用户只与 Steward 对话；Steward 负责规范委派、授权与简洁汇总。
- NotesVaulter 统一承担 Capture、Query 与 Vault Maintenance。
- incident bundle 可保留完整诊断上下文，但不得保存 token、Cookie、密码、私钥等秘密，且不得污染正式 Vault 或公开蓝图库。
- 附件暂用普通 Git；同一 Source 内按内容去重；单附件 5 MiB、单 Source 30 MiB 为软告警；附件总量达到 2 GiB 后再评估 Git LFS。
- “单一入口、清晰结构、渐进披露、最少必要确认”是正式架构原则。
- 个人单用户继续使用 `main + commit hash + last_known_good`，不恢复 RC/正式标签或双 checkout。
- 软件回退不得倒退正式 Vault 数据时间线。

本任务是整体方案的第一阶段，只建立并验证可供后续生产迁移/切换使用的蓝图、技能与通用工具，不迁移正式数据、不修改活动 OpenClaw 配置、不提交或推送。

## 2. 当前基线

| 主体 | 基线 |
|---|---|
| 蓝图库 | `/home/monottx/repos/knowledge-vault-blueprint`, `main@badfd519b85c4d80c7875cbf7cbe23afc340c35f`, 与 `origin/main` 一致；创建本 SPEC 前 clean |
| 正式 Vault | `/home/monottx/repos/SourceNotes`, `main@ec1a90eb9d41df77cf74e44d51e703d0379882e7`, clean，与远端一致 |
| 测试 Vault | `/home/monottx/repos/SourceNotes-test`；既有冻结数据，只读 |
| OpenClaw | config SHA-256 `71321f12d664db2c2256663599d71a333321e2050ceebec36c7f56b8abc22f5b`；`vault-capture.enabled=false`；`VAULT_ROOT` basename=`SourceNotes-test`；Gateway healthy；running/queued=0 |

## 3. 目标

1. 把 Steward→NotesVaulter 的单入口拓扑、结构化委派、简洁用户界面和最少确认原则写入权威蓝图。
2. 为 NotesVaulter 提供 Capture、Query、Maintenance 三类窄接口；Query 默认只读且答案必须引用 note ID/相对路径。
3. 移除 Capture 对嵌套子任务的必要依赖：Steward 委派的 NotesVaulter 子任务在自身运行内调用确定性抓取，避免不必要的 main→orchestrator→worker 层级。
4. 提供受控统一入口，后续可用 exec allowlist 限制 NotesVaulter，而不是授予通用宿主命令和文件编辑能力。
5. 修复测试库审计把模板 scaffold 误判为正文的问题，并提供 manifest 驱动、冲突安全的迁移工具。
6. 对未来捕获实现同 Source 内容寻址去重和 5/30 MiB 软告警；提供 2 GiB 总附件决策闸门。
7. 提供 Vault 外 health、release ledger 与 incident bundle 工具；不保存秘密、不写业务日志到 Vault。

## 4. 非目标

- 不修改 `/home/monottx/repos/SourceNotes/**` 或其 Git 状态。
- 不修改 `/home/monottx/repos/SourceNotes-test/**` 或其 Git 状态。
- executor 不修改 `~/.openclaw/openclaw.json`、agent workspace、exec approvals、systemd 或活动 Gateway。planner 可在实现完成后按 §8 做一次经整体方案已授权的临时 E2E 切换：先逐字节备份配置，仅把 capture 指向全新一次性 `*-test` Vault 并启用，验证后无条件恢复原字节与 hash；不得触碰正式 Vault。
- 不迁移、修复、删除或重新抓取任何真实测试库条目。
- 不 stage、commit、push、pull、merge、rebase、reset、clean、tag 或切换分支。
- 不安装 Git LFS、Docker、Zotero、Yanki 或新系统依赖。
- 不改变 schema 含义或 `schema_version`。

## 5. 锁定设计

### 5.1 用户可见拓扑

`用户 → Steward（唯一入口） → NotesVaulter（Capture / Query / Maintenance）`。opencode 只在代码级调试或升级时介入。Steward 不直接写 Vault，不复制 NotesVaulter 的知识职责。

### 5.2 接口与权限

- 新增一个可直接执行的受控 Python entrypoint，暴露固定子命令，不接受任意 shell、任意 Python、任意目标根目录或路径穿越。
- Capture 复用现有 `vault_capture.py` 的事务，不复制写入逻辑。
- Query 只读，提供有界 search/show/related（或功能等价的最小命令），只读取 Vault 内 Markdown；结果包含 ID、相对路径和有界摘录。
- Maintenance 本阶段只读，输出健康、重复/缺失引用、状态与附件预算；任何修复由后续显式批准。
- Capture 的网页完成在当前 NotesVaulter 运行内执行确定性 `ingest-web`；不再要求它继续 spawn worker。

### 5.3 附件

- 未来抓取中，同一 Source 事务内内容 SHA-256 相同的附件只落一份，正文多个位置可引用同一路径。
- 5 MiB（单文件）和 30 MiB（单 Source）只产生稳定 JSON warning，不降低 `ready`、不丢内容。
- 2 GiB 是 Vault 总附件决策闸门，只由 health/maintenance 报告，不自动迁移或删除。

### 5.4 Incident 与日志

- 输出位置必须显式位于 Vault/蓝图库之外；工具拒绝把 bundle 写入两仓。
- 可保留完整 URL、错误、必要上下文和显式提供的诊断文件。
- 明确禁止并扫描常见 token/Cookie/password/private-key；命中时失败关闭，不写 bundle。
- bundle/ledger/health 默认创建为目录 0700、文件 0600。

### 5.5 迁移工具

- 审计正文只计算 `<!-- source-content:start -->` 与 `<!-- source-content:end -->` 之间的实际内容；模板标题、callout、空 marker 不算正文。
- manifest 明确每个 Source/Annotation 的 `migrate`、`repair_then_migrate`、`exclude`，并记录理由；工具不自行猜测价值。
- apply 前检查目标 ID、canonical URL、相对路径、附件、未暂存/未跟踪冲突；冲突即停止。
- 支持 dry-run；apply 只复制 manifest 指定内容并输出 hash/路径证据，不 commit/push、不触碰源库。

## 6. 允许路径

允许修改/新增：

- `BLUEPRINT.md`
- `DECISIONS.md`
- `ROADMAP.md`
- `specifications/capture-workflow.md`
- `specifications/git-workflow.md`
- `specifications/openclaw-skill-workflow.md`
- `specifications/upgrade-workflow.md`
- `specifications/agent-operations.md`（新增）
- `skills/vault-capture/SKILL.md`
- `skills/vault-capture/references/runtime-contract.md`
- `skills/vault-capture/references/web-runtime.md`（仅附件 warning/去重契约需要时）
- `skills/vault-capture/scripts/vault_capture.py`
- `skills/vault-query/**`（新增）
- `skills/vault-maintenance/**`（新增）
- `scripts/sourcenotes_agent.py`（新增）
- `scripts/sourcenotes_ops.py`（新增）
- `tests/skills/test_vault_capture.py`
- `tests/operations/**`（新增）
- `tests/opencode-harness/README.md`（仅新拓扑/命令说明需要时）
- `tests/opencode-harness/test_capture_debug.sh`（仅契约确需时，不得弱化断言）
- `tasks/2026-08-13-sourcenotes-runtime-foundation/EXECUTION.md`（executor only）
- `tasks/2026-08-13-sourcenotes-runtime-foundation/REVIEW.md`（reviewer only）

禁止其它所有路径；executor 不得修改本 `SPEC.md` 或 `REVIEW.md`。

Planner-only 验证允许：`/tmp/opencode/**-test/**` 一次性 Vault、临时修改并逐字节恢复 `~/.openclaw/openclaw.json`、以及 Vault/蓝图库之外的私有验证证据。该权限不授予 executor。

## 7. 验收标准

- **AC-01 架构清晰：** 权威文档以一张简洁拓扑呈现用户→Steward→NotesVaulter，定义三类能力、最少确认和渐进披露；D-020/D-022 保持有效，新决策编号唯一且 schema 仍为 1。
- **AC-02 Capture 兼容：** 现有捕获、网页、SSRF、Annotation、Git 暂存测试全部通过；不自动 commit/push；失败仍先保留 stub。
- **AC-03 单层委派：** `vault-capture` 不再要求 NotesVaulter spawn 网页 worker；同一受委派运行可完成 stage→ingest-web，并保持同步/异步外层行为可由 Steward 管理。
- **AC-04 受控入口：** 统一 entrypoint 仅暴露固定 capture/query/maintenance 子命令，拒绝路径穿越、任意 Vault、非 Markdown show、超限输出和未知操作。
- **AC-05 Query：** search/show 能只读返回有界结果，并携带 note ID/相对路径；普通查询不改工作树/index。
- **AC-06 Maintenance：** 能报告 Git 状态、failed/manual、缺失引用、附件总量/增长输入与 2 GiB 闸门，不自动修复。
- **AC-07 审计正确：** 空 marker scaffold 的六类样例不再计为正文；真实 marker 正文可识别；审计输出每项唯一 disposition。
- **AC-08 迁移安全：** dry-run/apply 在临时仓库测试中证明 manifest 定向复制、hash/链接/附件保持、冲突停止、源库不变且不 commit/push。
- **AC-09 附件策略：** 同 Source 重复附件只落一份；5/30 MiB 只产生 warning；2 GiB health 闸门可测试；图片引用仍完整。
- **AC-10 Incident/ledger：** 外部路径、0700/0600、允许完整诊断上下文、秘密扫描失败关闭、拒绝写入 Vault/蓝图库均有测试。
- **AC-11 范围与质量：** 仅允许路径变化，`git diff --check` 通过；正式 Vault、测试 Vault、OpenClaw 配置与运行态未变。

## 8. 验证命令

均在 `/home/monottx/repos/knowledge-vault-blueprint`：

1. `python3 tests/skills/test_vault_capture.py`
2. `python3 tests/skills/test_web_extract.py`
3. `python3 tests/skills/test_network_security.py`
4. `python3 -m unittest discover -s tests/operations -p 'test_*.py'`
5. `bash tests/opencode-harness/test_capture_debug.sh`
6. `python3 -m py_compile scripts/sourcenotes_agent.py scripts/sourcenotes_ops.py`
7. `git diff --check`
8. `git status --short --branch` 与 `git diff --name-status`

期望全部 exit 0；harness 默认 exact-ready 语义不得弱化。真实 OpenClaw E2E 由 planner 在 executor 返回后、reviewer 审查前按 harness README 在一次性 `*-test` Vault 执行，并把证据传给 reviewer。

Planner E2E 至少包括：配置备份/hash、临时 Vault 初始化、idea `--assert --cleanup`、唯一 RFC URL 的 web `--wait 180 --expect-status ready --assert --cleanup`、正式 Vault 前后 HEAD/index/status/hash 不变、临时 Vault无测试残留、原配置逐字节恢复且 config validate/Gateway health 通过。任何失败均先恢复配置，再按 BLOCKED 上报，不进入生产切换。

## 9. Blocked / deviation

遇到以下任一情况立即停止并返回 BLOCKED：

- 基线出现与本任务重叠的用户改动；
- 需要修改允许路径外文件；
- 需要改变上述拓扑、附件阈值、incident 边界、schema 或验收契约；
- 需要覆盖用户改动或触碰两个 Vault/活动配置；
- 测试依赖或权限失败且无法在允许路径内安全解决。

返回必须写明 STEP、原始命令/错误、已产生变化和建议。

## 10. 权限

- 允许路径内实现和测试：authorized。
- 正式/测试 Vault、OpenClaw、systemd、agent workspace、exec approvals 写入：not authorized in this phase。
- stage/commit/push/pull/merge/rebase/reset/clean/tag：not authorized in this phase。

## 11. 批准记录

- 用户批准整体方案：`批准修订后的整体方案并执行`
- 用户批准附件策略：`同意`
- Approved at: 2026-08-13
