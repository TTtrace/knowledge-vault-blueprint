# Work Item 01 Execution Brief — preflight and cutover package

Role: Executor
Effort: `/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-production-switch/`
Work Item: `issues/01-preflight-and-cutover-package.md`

## 1. 批准依据

- 第一层 Specification：`/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-production-switch/spec.md`，`Status: approved`。
- Effort Plan：`/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-production-switch/plan.md`，`Status: approved`。
- Operator 批准原文：`批准上述第一层计划；本次不迁移测试库，main 作为 Steward，切换前轮换 Telegram 凭据。`
- 本简报只实施获批 Work Item 01，不改变第一层目标、非目标、架构、允许路径或 AC；不授权任何 Controlled Action。

## 2. 上下文与已排除方案

### 当前事实

- 蓝图库候选为 `main@017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`；实现含 `scripts/sourcenotes_agent.py`、`vault-capture`、`vault-query`、`vault-maintenance` 与 ops 工具。
- 正式 Vault 为 `/home/monottx/repos/SourceNotes`；测试历史库为 `/home/monottx/repos/SourceNotes-test`。两者在本 Work Item 全部只读。
- 活动 OpenClaw 配置为 `/home/monottx/.openclaw/openclaw.json`。只能读取结构与计算脱敏摘要；禁止打印、复制或记录 token/secret/完整配置。
- 当前运行态已知为 capture disabled、VAULT_ROOT basename `SourceNotes-test`、query/maintenance disabled、NotesVaulter 有独立 Telegram binding、`main` 未显式允许 spawn `notesvaulter`。
- OpenClaw 本机文档：`subagents.allowAgents` 默认只允许同 agent；候选配置必须对 `main` 使用精确 `["notesvaulter"]`，禁止 `*`。

### 不变量

- Source 正文不可变、Yanki `noteId` 保留、抓取/阅读状态分离。
- SourceNotes-test 不清理、不 reset、不迁移；正式 SourceNotes 不写合成测试数据。
- 软件回滚不倒退 Vault 数据。
- Evidence 不包含 secret、绝对 Vault 路径、正文、逐项 URL 或完整主机配置。

### 已排除方案

- 排除直接把当前配置改到 production：尚未完成隔离验证、秘密轮换与独立 Review。
- 排除复用 SourceNotes-test 做 E2E：该库有既有脏状态且批准边界为不迁移、不清理。
- 排除保留 NotesVaulter Telegram bot 作为第二入口：违反 D-023 单入口。
- 排除 `allowAgents: ["*"]`：权限过宽。
- 排除生产合成 capture：正式 Vault 数据单调保留，测试数据不得进入。
- 排除在本 Work Item 轮换凭据、写活动配置、reload/restart Gateway、写 last_known_good：均在后续 Operator Controlled Action gate。

## 3. 有序原子步骤

### STEP-01 — 只读 preflight

- 读取：
  - `/home/monottx/repos/knowledge-vault-blueprint/AGENTS.md`
  - 本 Effort 的 `map.md`、`spec.md`、`plan.md`、Work Item 与本简报
  - `specifications/upgrade-workflow.md`
  - `specifications/openclaw-skill-workflow.md`
  - `specifications/agent-operations.md`
- 只读记录三仓库 branch/HEAD/status/index、蓝图与 origin 关系、OpenClaw config SHA-256、Gateway/queue/skill 摘要。
- OpenClaw 摘要只允许记录：hash、agent ids、skill names、enabled 布尔值、VAULT_ROOT basename、binding 的 agent/account ids、是否存在 token 字段；禁止记录任何 token 值、完整路径值或完整 JSON。
- 若蓝图 HEAD 不是批准 commit、正式 Vault 不 clean、存在运行中/排队 capture、或发现相关配置漂移，停止为 BLOCKED。

### STEP-02 — 仓库回归

- 在 `/home/monottx/repos/knowledge-vault-blueprint` 运行 VAL-02 至 VAL-07。
- 不修改产品代码，不生成库内缓存；Python 使用 `PYTHONDONTWRITEBYTECODE=1 python3 -B`（测试自身必须写临时数据时只可写其既有临时目录）。

### STEP-03 — 一次性受控入口 E2E

- 新增一次性目录：`/tmp/sourcenotes-production-switch-<unique>-test/`；basename 必须以 `-test` 结尾。
- 从 `vault-starter/` 复制 starter 内容，初始化本地 Git baseline，仅在该临时 Vault 内配置测试 Git 身份并 commit baseline。
- 使用 `VAULT_ROOT=<temp>` 调用受控入口：
  1. `capture preflight`
  2. stdin 传入唯一 idea JSON，调用 `capture stage`
  3. `query search` 搜索唯一文本
  4. `maintenance report`
- 断言：capture 返回 ok/ready 且只暂存临时 Vault 的本次路径；query 返回 note id/相对路径；maintenance 返回 Git/状态/附件字段；命令输出不含 temp 绝对路径。
- 记录验证摘要后仅删除本次创建的临时目录；删除前确认路径位于 `/tmp/` 且 basename 以 `-test` 结尾。不得调用 SourceNotes 或 SourceNotes-test。

### STEP-04 — 候选配置模型

- 新增：`/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-production-switch/cutover-package.md`。
- 只记录脱敏的“before semantic summary → candidate semantic summary”，不得复制原配置。
- 候选必须精确表达：
  - `main.name = Steward`（或保留 id=`main` 的等价显示名）；
  - `main.subagents.allowAgents = ["notesvaulter"]`；
  - `notesvaulter.skills = ["vault-capture", "vault-query", "vault-maintenance"]`；
  - 三个 skill entries enabled；
  - `vault-capture.env.VAULT_ROOT` 候选只写 `<production SourceNotes path supplied privately>`，正文只声明 basename=`SourceNotes`；
  - 移除 NotesVaulter 的直接 Telegram binding/account；默认 Telegram 只绑定 `main`；
  - main Telegram token 必须轮换，NotesVaulter 旧 token 必须撤销；新值永不出现在 runbook/Evidence；
  - 不改变模型、浏览器、web search、SSRF 及无关 agent/channel 配置。
- 如当前 OpenClaw schema 不支持上述字段或需要修改批准范围外语义，返回 BLOCKED/NEEDS_REPLAN，不猜测。

### STEP-05 — Operator cutover runbook

- 在 `cutover-package.md` 中新增固定小节：
  1. 前置 Gate 与停止条件；
  2. Operator 私下轮换/撤销凭据步骤（不得要求在聊天粘贴 token）；
  3. 创建私有 0700 状态目录、0600 原始配置备份、SHA-256、Vault checkpoint、queue 摘要、ledger 的精确命令；
  4. 对**备份副本或新候选文件**构造配置并 validate 的命令，不直接编辑活动配置；
  5. 独立 `*-test` 真实 NotesVaulter E2E 的命令与期望；若它必须临时替换活动配置，明确这是 Operator Controlled Action，先备份、失败立即恢复；
  6. 最终 production cutover 的唯一精确写入/reload 命令；
  7. post-check：config validate、health、skills list/info/check、agents delegation、新 session、两个 Vault 状态；
  8. 失败恢复：逐字节恢复配置并非破坏性重载，不 reset/clean Vault；
  9. 通过后记录 `last_known_good=017c2ce1...` 与 soak start。
- 所有真实写入命令必须标注 `CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED`。

### STEP-06 — Evidence

- 新增并填写：`/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-production-switch/evidence/01/execution.md`。
- 对 AC-01/02/03/04/09 给出 PASS/FAIL/NOT_RUN；AC-05 必须为 NOT_RUN（等待 Reviewer）；AC-06/07/08 不适用本 Work Item，标为 NOT_RUN。
- 记录所有 VAL 的 cwd、命令、退出码、关键脱敏输出。
- 返回固定模板；不得修改 `map.md`、`spec.md`、`plan.md`、issue 或 review evidence。

## 4. 允许与禁止路径

### 允许新增/修改

- `/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-production-switch/cutover-package.md`
- `/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-production-switch/evidence/01/execution.md`
- `/tmp/sourcenotes-production-switch-*-test/**`（本 Work Item 创建的一次性 E2E Vault，验证后删除）

### 只读

- `/home/monottx/repos/knowledge-vault-blueprint/**`（除上列两个 `.scratch` 文件）
- `/home/monottx/repos/SourceNotes/**` 与 `.git/**`
- `/home/monottx/repos/SourceNotes-test/**` 与 `.git/**`
- `/home/monottx/.openclaw/openclaw.json` 及 OpenClaw runtime 状态
- `/home/monottx/.npm-global/lib/node_modules/openclaw/docs/**`

### 明确禁止

- 禁止修改活动 OpenClaw 配置、Gateway、systemd、agent workspace、bindings、tokens、SecretRef 或环境。
- 禁止读取后打印/复制 token 值；禁止把完整配置复制到 `/tmp`、仓库或 Evidence。
- 禁止 stage/commit/push/pull/fetch/merge/rebase/reset/clean/tag/branch switch。
- 禁止写两个 Vault、迁移、capture/retry 正式数据、删除测试库内容。
- 禁止安装依赖、网络抓取、真实 production capture、计划外重构。
- 默认不得覆盖已有改动；若目标 Evidence 文件已存在非空内容，停止上报。

## 5. 验收契约与 VAL 映射

- **AC-01 → VAL-01**：
  - cwd：各仓库/宿主；命令：只读 `git branch --show-current`、`git rev-parse HEAD`、`git status --short --branch`、`git diff --cached --name-status`、`git remote -v`（URL 只报告是否一致，不记录值），以及 secret-free config/runtime 摘要。
  - 期望：蓝图 `main@017c2ce1...` 且与 origin 一致；正式 SourceNotes clean；测试库只记录既有状态；无 running/queued capture。
- **AC-02 → VAL-02..VAL-08**：
  - **VAL-02** cwd blueprint：`PYTHONDONTWRITEBYTECODE=1 python3 -B tests/skills/test_vault_capture.py`；期望 exit 0。
  - **VAL-03** cwd blueprint：`PYTHONDONTWRITEBYTECODE=1 python3 -B tests/skills/test_web_extract.py`；期望 exit 0。
  - **VAL-04** cwd blueprint：`PYTHONDONTWRITEBYTECODE=1 python3 -B tests/skills/test_network_security.py`；期望 exit 0。
  - **VAL-05** cwd blueprint：`PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests/operations -p 'test_*.py'`；期望 exit 0。
  - **VAL-06** cwd blueprint：`bash tests/opencode-harness/test_capture_debug.sh`；期望 exit 0、失败 0。
  - **VAL-07** cwd blueprint：`PYTHONDONTWRITEBYTECODE=1 python3 -B -m py_compile scripts/sourcenotes_agent.py scripts/sourcenotes_ops.py`；期望 exit 0；若 `py_compile` 仍生成缓存，删除仅本命令新建的 `__pycache__` 并记录。
  - **VAL-08** cwd temp `*-test`：按 STEP-03 调用受控入口；期望 capture/query/maintenance 全部满足断言，temp 删除后不存在。
- **AC-03/04/09 → VAL-09**：
  - cwd blueprint；人工 + 确定性扫描 `cutover-package.md` 与 `execution.md`。
  - 期望：所需语义齐全；无 token 模式、原始 token、绝对 SourceNotes 路径、正文/逐项 URL；所有写命令标明 Operator-only；`git diff --check -- .scratch/2026-08-17-sourcenotes-production-switch` exit 0。
- **AC-05**：本 Work Item 不自证；等待独立 Reviewer。

## 6. blocked / deviation 规则

立即停止并返回 `STATUS: BLOCKED`：

- 蓝图 HEAD/branch、正式 Vault clean 状态或活动配置在 preflight 与收尾间发生相关漂移；
- running/queued capture 非零；
- 任一验证失败且不能在允许的两个 Evidence 文件内解释；
- 需要修改活动配置、两个 Vault、产品代码或其它允许路径外文件；
- 需要显示、复制、提交或在命令行传递真实 secret；
- OpenClaw schema 不支持候选配置，或单入口需要新增代码/skill；
- 临时 E2E 无法证明只写新建 `*-test` Vault；
- 需改变批准目标、迁移边界、Steward 决定、允许路径或 AC（报告 `NEEDS_REPLAN` 建议，不自行变化）。

上报必须包含：停在哪个 STEP、原始命令（secret-free）与错误、退出码、当前已写文件、两 Vault/配置是否保持不变、建议的最小下一决策。

## 7. 返回契约

必须逐字段返回，不得省略：

```text
STATUS: READY_FOR_REVIEW | BLOCKED
CHANGED_FILES: 每个文件绝对路径、变更内容、原因、对应 STEP
ACCEPTANCE_EVIDENCE: 每条 AC 的 PASS/FAIL/NOT_RUN 与证据
VALIDATION_LOG: 每条 VAL 的工作目录、命令、退出码、关键输出
DEVIATIONS: 与简报的任何偏差及原因（无则写 none）
BLOCKERS: 阻塞项（无则写 none）
FINAL_STATE: 三仓库 branch/HEAD/status、活动配置 hash 是否不变、Gateway/queue 摘要、临时目录是否清理、是否 stage/commit、是否执行 Controlled Action
```
