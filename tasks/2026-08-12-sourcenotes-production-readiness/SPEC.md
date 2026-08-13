---
task_id: 2026-08-12-sourcenotes-production-readiness
title: 建立 SourceNotes 简化升级、数据保留与测试库审计基线
status: approved
spec_version: 2
planner: primary
executor: executor
created: 2026-08-12
approved_at: 2026-08-13
approved_by: user
---

# Task Specification

> 本文件由 planner 所有。v1 曾基于含持久微信 profile 的旧 OpenClaw 配置执行，且未纳入 main 已接受的输入输出决策与微信回退，因此其旧 reviewer 结论不得沿用。v2 以重新建立的只读基线取代 v1；executor 不得修改本文件。

## 1. 背景与问题

用户是个人单用户，Telegram 仅本人使用；SourceNotes 在 Windows、macOS、Linux、Android 间通过 Git 同步，Linux 是 OpenClaw 自动捕获的唯一写入者。用户希望以 `main + commit hash + last_known_good + 维护模式 + 临时 *-test Vault` 降低日常心智负担，不强制 RC/正式标签或 staging/production 双蓝图 checkout。

系统必须支持一周或更长的正式环境浸泡，并遵守核心不变量：**回退软件，不回退知识库时间线**。浸泡期间新增捕获、手写内容和附件不得因软件回退丢失。

v1 阶段 0 已建立测试库快照、push 防护、迁移审计和蓝图文档草稿，但把旧 OpenClaw 备份中的 `VAULT_CAPTURE_BROWSER_PROFILE` 当作权威并恢复了该键。并行微信回退任务随后完成并被正式接受，要求删除该键、专用 profile 目录和 helper，且微信验证/验证码/登录要求/限流保持 `manual`，不再技术绕过。另一个已接受任务已将 D-021 用于“输入与输出双向可追溯”。因此 v1 的配置基线、决策编号和验收契约已失效，任务必须重新规划。

## 2. 必需结果

1. 以 main `8882d771356210913054ec31b769e4eb4acceb93` 及微信回退后的活动 OpenClaw 状态作为权威基线。
2. 保留经验证仍一致的测试库完整快照、push 防护和迁移审计，不重新迁移或重新抓取。
3. 将当前阶段 0 文档与 main 已接受的输入输出演进安全组合：D-020 为个人单用户简化发布，保留 main 的 D-021 输入输出双向追溯，D-022 为 Vault 数据单调保留。
4. 建立微信回退后的新 OpenClaw 私有备份和脱敏摘要；旧含 profile 的备份只作为历史证据，不得作为恢复权威。
5. 修正私有恢复说明，使 hash 校验命令与结构化 JSON manifest 一致。
6. 不修改活动 OpenClaw 配置、不恢复捕获、不迁移数据、不修改正式 Vault。

## 3. 非目标

- 不恢复 `vault-capture`，不改变 `VAULT_ROOT`。
- 不增加或恢复 `VAULT_CAPTURE_BROWSER_PROFILE`，不创建微信 profile/helper，不尝试绕过验证、登录或限流。
- 不运行捕获、NotesVaulter E2E、网络重抓取或数据迁移。
- 不删除、修复、重新分类或 unstaged 测试库内容。
- 不修改正式 SourceNotes、skill、tests、schema、模板或自动化实现。
- 不修改 main worktree。
- 不 stage、commit、push、pull、merge、rebase、reset、clean、branch 或 tag。
- 不在本任务执行阶段把工作分支集成进 main；该动作需后续单独授权。

## 4. 锁定决策

1. **个人单用户简化发布**：D-020 使用 `main` commit hash 作为版本身份，外部 `last_known_good` 记录稳定基线；不强制 RC/正式标签或双蓝图 checkout。D-015 保留为历史并由 D-020 取代现行流程。
2. **保留已接受 D-021**：main 的 D-021“输入与输出双向可追溯是架构设计闸门”及其 BLUEPRINT/ROADMAP 内容完整保留，不改号、不覆盖。
3. **数据单调保留编号**：本任务“Vault 数据单调保留，软件回退与数据回退分离”使用 D-022。
4. **微信手动边界**：微信验证、验证码、登录要求和限流保持 `manual`；不配置 persistent profile，不做技术绕过。
5. **测试数据隔离**：合成/自动 E2E 仅允许写入一次性、basename 以 `-test` 结尾的临时 Vault；本阶段不运行 E2E。
6. **长期浸泡保留数据**：浸泡期间正常捕获、手写、commit 和 sync 可以继续；失败时先保护当前 Vault，再以新代码提交回退软件与恢复配置，不倒退 Vault HEAD、不覆盖快照、不删除浸泡期内容。
7. **schema 分级**：纯行为变化只回退代码；向后兼容增量字段由旧代码忽略并保留；breaking schema 在长期浸泡前必须有双读 Adapter 或可逆、幂等、冲突安全的字段级迁移。
8. **旧配置证据只作历史**：`openclaw.json.backup` 及 round-2 browser-profile 证据记录旧现场，不是当前配置恢复源；禁止整文件恢复旧配置。

## 5. 重新确认的基线

| 主体 | 路径 | 分支 / HEAD | 状态 |
|---|---|---|---|
| 当前任务蓝图 worktree | `/home/monottx/orca/workspaces/knowledge-vault-blueprint/正式运行SourceNotes` | `正式运行SourceNotes` @ `f9810f1ff454aaa4c7d0561a0d4dec1ca5bd5128` | v1 未提交文档和任务包；index 空 |
| main 蓝图 worktree | `/home/monottx/repos/knowledge-vault-blueprint` | `main` @ `8882d771356210913054ec31b769e4eb4acceb93` | clean，与 `origin/main` 一致；含 accepted D-021 与微信回退 |
| 正式 SourceNotes | `/home/monottx/repos/SourceNotes` | `main` @ `ec1a90eb9d41df77cf74e44d51e703d0379882e7` | clean，`main...origin/main` |
| 测试 SourceNotes-test | `/home/monottx/repos/SourceNotes-test` | `main` @ `ec1a90eb9d41df77cf74e44d51e703d0379882e7` | 134 项：124 staged A、1 unstaged M、9 untracked |

测试库冻结指纹：index `286d6c7dd7dcc14f4074e1a033c8705a7c66c33c971d5f5f3dd3d31afeb44487`；porcelain-z `0b42e19a32807b03782c508d1272518464e40a0b408530d101505acc711ea000`；sorted show-ref `d46876208559e7da8c72722adeaf6d95eecc9d32725fe16b720edccf232e2734`。fetch URL 保持原值，push URL 为 `disabled://SourceNotes-test`。

活动 OpenClaw：config valid，SHA-256 `71321f12d664db2c2256663599d71a333321e2050ceebec36c7f56b8abc22f5b`；`vault-capture.enabled=false`；`VAULT_ROOT` basename 为 `SourceNotes-test`；`VAULT_CAPTURE_BROWSER_PROFILE` 缺失；env 键为 `PATH`、`PLAYWRIGHT_BROWSERS_PATH`、`VAULT_CAPTURE_PYTHON`、`VAULT_ROOT`；notesvaulter 下 skill disabled/ineligible；Gateway healthy；running/queued 均为 0；profile 目录与 helper 均不存在。

阶段 0 私有产物目录为 `/home/monottx/.local/state/sourcenotes-production-readiness/2026-08-12/`，根目录 0700、文件 0600。快照 SHA-256 `4ee069e0790d29590ba11ff08114a85887e694735a0ec6f4ad25eaf4ea1a3171`，大小 101693440，840 个成员。审计覆盖 24 Source、2 Annotation、147 附件；测试库冻结指纹仍一致。

## 6. 范围与路径边界

### 6.1 当前任务蓝图 worktree

允许修改：

- `BLUEPRINT.md`
- `DECISIONS.md`
- `ROADMAP.md`
- `specifications/openclaw-skill-workflow.md`
- `specifications/git-workflow.md`
- `specifications/upgrade-workflow.md`
- `tasks/2026-08-12-sourcenotes-production-readiness/SPEC.md`（planner only）
- `tasks/2026-08-12-sourcenotes-production-readiness/EXECUTION.md`（executor only）
- `tasks/2026-08-12-sourcenotes-production-readiness/REVIEW.md`（reviewer only）

禁止：其它仓库路径，特别是 `skills/**`、`tests/**`、`vault-starter/**`、`examples/**`、其它任务包；executor 禁止修改 SPEC/REVIEW。

### 6.2 main 蓝图 worktree

`/home/monottx/repos/knowledge-vault-blueprint/**` 全部只读。作为 D-021、输入输出文档和微信回退语义的权威来源；不得修改 index、refs 或工作树。

### 6.3 正式 SourceNotes

`/home/monottx/repos/SourceNotes/**` 与 `.git/**` 全部只读。

### 6.4 SourceNotes-test

`/home/monottx/repos/SourceNotes-test/**` 与 `.git/**` 全部只读。现有 push 防护仅验证，不再次写入。

### 6.5 OpenClaw 与运行态

`~/.openclaw/openclaw.json`、Gateway、tasks、sessions、audit、workspace 全部只读；不得 reload/restart，不得调用 agent 产生捕获。

### 6.6 外部私有目录

允许修改/新增仅限：

- 修正既有 `RECOVERY.md` 中结构化 JSON manifest 的只读校验方法；保留灾难恢复边界。
- 新增 post-WeChat-rollback 活动配置备份、脱敏摘要和再验证 manifest；文件名必须清楚表明是当前权威基线。

禁止覆盖或删除旧历史证据；禁止输出秘密、完整配置、真实正文或逐项 URL；权限保持目录 0700、文件 0600。

## 7. 验收标准

- [ ] **AC-01 — 权威基线：** main 为 `8882d77...` 且 clean；微信回退和输入输出任务的 REVIEW 均为 accepted；执行前无相关共享状态漂移。
- [ ] **AC-02 — 决策编号与语义：** 最终文档恰有 D-020 简化发布、main 已接受的 D-021 输入输出追溯、D-022 数据单调保留；无重复编号、覆盖或错误交叉引用。
- [ ] **AC-03 — main 文档保留：** main 已接受的输入输出全景、阶段 4 生活/复习输出、阶段 5 知识问答和延后 QA/引文需求完整保留。
- [ ] **AC-04 — 简化发布一致性：** 当前规范使用 `main + commit hash + last_known_good + 维护模式 + 临时 *-test Vault`；不强制 RC/正式标签/双 checkout；D-015 保留历史并被 D-020 显式取代。
- [ ] **AC-05 — 微信 manual 边界：** 当前规范不引入 `VAULT_CAPTURE_BROWSER_PROFILE` 或 profile 绕过；验证、验证码、登录要求或限流继续安全结束为 `manual`。
- [ ] **AC-06 — 数据单调与一周浸泡：** D-022 与升级/Git 规范完整定义浸泡期间正常写入、失败先保护当前 Vault、只回退软件/配置、不得倒退 HEAD/覆盖快照/删除浸泡期数据，并通过 operation ledger 定向修复。
- [ ] **AC-07 — schema 分级：** 三类策略明确；breaking schema 无双读或可逆幂等冲突安全迁移时不得进入长期浸泡；逆向迁移不得覆盖后续编辑、Source 正文、未知属性或 Yanki `noteId`。
- [ ] **AC-08 — 正式 Vault 未触碰：** HEAD、branch/upstream、remote、index 和 clean 状态保持基线。
- [ ] **AC-09 — 测试库冻结未触碰：** HEAD、134 项状态、三项冻结指纹、fetch/push URL 全部保持基线。
- [ ] **AC-10 — 快照与恢复说明：** 四项 manifest hash、840 成员、tar 可读性、0700/0600 权限通过；RECOVERY 的 hash 校验命令适配 JSON manifest；不执行恢复。
- [ ] **AC-11 — 审计仍有效：** 冻结指纹不变时复用审计，确认 24 Source、2 Annotation、147 附件及处置唯一性；不重新读取正文或重写审计。
- [ ] **AC-12 — OpenClaw 只读维护态：** 活动配置前后 hash 不变，始终 enabled=false、VAULT_ROOT=SourceNotes-test、profile 键缺失、skill disabled/ineligible、Gateway healthy、running/queued=0、外部 profile/helper 缺失。
- [ ] **AC-13 — 当前配置私有证据：** 新备份与活动配置逐字节一致并有 hash；脱敏摘要不含值/秘密；旧含 profile 备份明确标记为历史且禁止整文件恢复。
- [ ] **AC-14 — 隐私与范围：** 蓝图库和新私有产物不含正文、逐项标题/URL、trajectory、secret 或完整配置副本之外的泄露；只修改允许路径。
- [ ] **AC-15 — 无未授权动作：** 无 Git 写操作、OpenClaw 配置写入/reload/restart、捕获、迁移或网络重抓取。
- [ ] **AC-16 — 基础质量：** Markdown 相对链接、决策引用和当前规范一致；当前任务蓝图 diff 与 main accepted 内容组合正确；`git diff --check` 通过。

## 8. 验证计划

| ID | 工作目录 | 命令/检查 | 期望 | AC |
|---|---|---|---|---|
| VAL-01 | 两个蓝图 worktree | `git branch --show-current`、`git rev-parse HEAD`、`git status --short --branch`、diff/name-status | main 仍为 clean 8882d77；当前 worktree 仅允许路径变化、index 空 | 01,14,15 |
| VAL-02 | 当前任务 worktree | 人工及 Python 内容断言：D-020/D-021/D-022 各一行一节，D-021 内容与 main 一致，D-015 supersession，输入输出/阶段 4/5/延后需求保留 | 全部通过 | 02–07,16 |
| VAL-03 | 当前任务 worktree | 相对链接检查、敏感模式扫描、`git diff --check` | exit 0；无隐私泄露或无效链接 | 14,16 |
| VAL-04 | 正式 Vault | branch/HEAD/status/remote/diff/cached diff/index hash | 与基线一致、clean | 08,15 |
| VAL-05 | 测试 Vault | HEAD、sorted show-ref/index/porcelain-z hash、134 分类、remote fetch/push | 全部与基线一致 | 09,11,15 |
| VAL-06 | OpenClaw | config validate；结构化只读摘要/hash；skills info；health/status；tasks running/queued；profile/helper existence | 活动配置与维护态前后不变 | 05,12,15 |
| VAL-07 | 私有目录 | 结构化验证 `sha256-manifest.json`、tar 成员数/可读性、权限、RECOVERY 命令审查 | 全部通过，不恢复 | 10 |
| VAL-08 | 私有目录 | 解析 migration-audit JSON 并断言 24/2/147、每项唯一处置、关键运行残留字段齐全 | 全部通过；不重写审计 | 11 |
| VAL-09 | 私有目录 | 比较新配置备份与活动配置 hash；检查脱敏摘要、历史标记和权限 | 当前证据权威、旧证据仅历史 | 13,14 |

人工检查必须标为人工；未运行不得写 PASS。

## 9. 一周浸泡期数据保留契约

未来启用候选前必须记录正式 Vault HEAD/index/status/附件基线和“立即升级前”的活动配置，建立外部 operation ledger。浸泡期间允许正常捕获、手写、commit 与跨设备同步。失败时进入维护模式、保护当前 Vault、通过新的修复/revert commit 回退蓝图并恢复当次升级前配置；不得 reset Vault、检出旧 Vault commit、用旧快照覆盖或删除浸泡期文件。用 Source ID、相对路径和附件集合的包含性检查证明数据仍存在；质量可疑数据只定向修复或标记。

## 10. 风险与回滚

- 若 main、活动配置、两个 Vault 或冻结指纹在 executor 开工前发生相关漂移，立即 BLOCKED；如需改变目标/路径/AC，则 NEEDS_REPLAN。
- main 文档组合必须逐段保留，禁止用整文件旧版本覆盖 main accepted 内容。
- 蓝图回滚只精确撤销本任务允许文件中的 v2 变化，不使用 reset/clean。
- 新私有证据若需回滚，只删除新 manifest 精确列出的文件；保留旧快照、审计和历史证据。
- RECOVERY 修改可精确恢复原文字节，但不得执行其中任何恢复步骤。
- 正式 Vault 和活动 OpenClaw 配置无预期变化，因此不存在正常数据/配置回滚动作。

## 11. 权限

- 当前任务允许路径文档编辑：authorized
- 外部私有目录 §6.6 窄范围写入：authorized
- main worktree、两个 Vault、活动 OpenClaw 配置/运行态写入：not authorized
- Git stage/commit/push/pull/merge/rebase/reset/clean/branch/tag：not authorized
- 捕获、E2E、迁移、网络重抓取：not authorized

## 12. 批准记录

- v1 approval retained as historical record in prior execution materials.
- v2 replan presented after read-only baseline reconstruction on 2026-08-13.
- Approval statement: `批准。`
- Approved specification version: `2`
- Approved at: `2026-08-13`
