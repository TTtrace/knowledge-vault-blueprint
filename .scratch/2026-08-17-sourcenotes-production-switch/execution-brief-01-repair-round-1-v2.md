# Work Item 01 Repair Brief v2 — Temporary clone canary amendment

Role: Executor
Effort: `/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-production-switch/`
Work Item: `issues/01-preflight-and-cutover-package.md`（claimed）

## 1. 批准依据

- 第一层 `spec.md` / `plan.md` 已批准；Reviewer round 1 为 `CHANGES_REQUESTED`，F-01 至 F-08 记录于 `evidence/01/review.md`。
- 原修复尝试在隔离 Gateway 模型认证处安全 BLOCKED，未修改工件。
- Operator 后续批准原文：`好的 同意此方案`。批准的修订是：不复制模型密钥、不向正式 SourceNotes 写测试数据；后续 Controlled Action 使用活动 Gateway + 正式库完整一次性 `*-test` 克隆做真实委派 canary，通过后才 production cutover。
- 本简报是 CHANGES_REQUESTED 修复轮 1 的替代简报；不改变目标、迁移边界、单入口、凭据轮换、允许路径或最终 AC，不授权 Controlled Action。

## 2. 上下文与已排除方案

- 保留 `execution-brief-01.md` 的全部不变量与禁止项。
- 排除复制模型 secret 到隔离 Gateway；排除向正式 Vault 写测试数据；排除当前 Work Item 临时修改活动 Gateway。
- 当前 Work Item 已有直接受控入口临时 E2E 证据。真实模型 Steward→NotesVaulter E2E 调整为后续 Operator Controlled Action 的**前置 canary gate**，由 Work Item 02 独立复核实际 Evidence。
- Reviewer F-04 在本轮通过“完整、无占位符、可执行、先 canary 后 production 的精确 runbook + 无模型 schema/clone rehearsal”关闭；不得伪称已执行真实模型 E2E。

## 3. 有序修复步骤

### STEP-V2-01 — 关闭 F-01/F-02/F-08

- 修改 `evidence/01/execution.md`：临时 Vault 只写 basename；删除允许范围外 vault-starter 的绝对路径/定位行为，只保留仓库内 fixture 来源。
- 从 Effort 根对实际两个产物运行 secret/path/URL/写命令扫描；逐个未跟踪 Markdown 用 `git diff --no-index --check /dev/null "$FILE"` 检查，rc=1 且无 whitespace-error 才通过。
- 扫描覆盖 token/credential 键值与 Bot token 形态、绝对 SourceNotes 路径、逐项 URL、以及 `cp/mv/install/chmod/mkdir/openclaw config patch/set/unset/gateway` 等写命令的 Operator-only 分类。

### STEP-V2-02 — 关闭 F-03

- `cutover-package.md` 的 private backup、candidate publish、production cutover、restore 全部使用确定性原子流程：同目录 temporary regular file、0600、flush/fsync、hash/validate、`os.replace`、parent fsync；状态目录强制并验证 0700。
- 可优先使用 OpenClaw 自有 `config patch --dry-run` + atomic write 契约，但必须引用本机文档并证明 deletion/array replacement 语义；禁止 `cp`/shell redirection 直接覆盖活动配置。
- 在本轮 `/tmp/...-test` fixture 上实际演练 atomic backup/publish/restore，绝不针对活动配置。

### STEP-V2-03 — 关闭 F-05/F-07

- 给出 deterministic candidate transformer：读取 regular active config、深复制、保留未知字段；精确修改批准字段；删除 NotesVaulter Telegram binding/account key，而非留下 null（除非明确通过 merge-patch null 删除）；数组按批准列表精确替换。
- 所有路径和 secret 来源使用先定义并全程双引号引用的私有环境变量；禁止 `<SourceNotes>` shell 占位符。
- main 新 token 只能从 0600 私有文件/SecretRef 读取；不得出现在 argv/stdout/stderr/diff/Evidence。
- 给出 secret-free semantic projection/diff，只输出 agent ids/names、allowAgents、skill names、enabled 布尔值、Vault basename、binding/account key 集合和 token-field-present/rotated 布尔值。
- 在无 secret 的 fixture config 上实际运行 transformer 两次，证明 deterministic/idempotent，并用隔离 `OPENCLAW_CONFIG_PATH` validate。

### STEP-V2-04 — 关闭 F-06

- 对现有 main bot 使用 BotFather `/revoke`/reissue，使旧 token 失效；不得用 `/newbot` 代替轮换。
- 对 NotesVaulter bot token revoke，随后从配置移除其 account/binding；删除 bot 本身不在范围。
- Evidence 只允许布尔确认，不含 token、Bot API URL 或命令行 secret。

### STEP-V2-05 — 关闭 F-04：活动 Gateway + 正式库临时克隆 canary runbook

- 在 `cutover-package.md` 写完整精确流程，所有真实动作标为 `CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED`：
  1. 确认 queue 0/0，暂停 Telegram/自动捕获入口并进入维护模式；记录正式 SourceNotes branch/HEAD/index/status/remote 与附件基线。
  2. 定义并引用变量：`PRODUCTION_VAULT_ROOT`、`CANARY_VAULT_ROOT`（basename 必须 `SourceNotes-production-canary-<id>-test`）、`STATE_DIR`、`ACTIVE_CONFIG`、`BACKUP_CONFIG`、`CANDIDATE_CONFIG`；不得使用尖括号占位符。
  3. 从正式 SourceNotes 创建本地完整克隆/等价完整副本到全新 canary `*-test`；不得修改正式仓 `.git/config` 或 refs；验证 canary HEAD/结构与正式基线一致、canary remote push 被禁用或无 remote。
  4. 在私有 candidate config 中先保持单入口/三技能候选，但 `VAULT_ROOT` 指向 canary；轮换后的 main 凭据仅在私有 config/SecretRef；NotesVaulter direct channel 已移除。
  5. 原子 publish canary config，并按 OpenClaw 提示执行唯一必要 reload/restart；新 session 从 main 发起，要求显式 `sessions_spawn(agentId="notesvaulter")` 完成：真实 idea capture（只写 canary）、query 命中、maintenance report；检查三个 skills eligible、envelope/ID/相对路径/暂存与失败数。
  6. canary PASS 后，在私有 candidate 把 VAULT_ROOT 单字段改为 production，重新 validate/semantic diff，原子 publish 并新 session 做 Query/Maintenance 只读 canary；不在正式 Vault执行合成 Capture。
  7. 任一步失败：立即原子恢复 BACKUP_CONFIG、按提示重载、验证 default Gateway/Telegram 恢复；不 reset/clean 正式 Vault。canary 克隆只在保存必要脱敏诊断后删除。
  8. PASS 后记录 last_known_good 与 soak start；真实首次 production Capture 等待用户下一条真实输入。
- 当前 Work Item 只在 `/tmp/...-test` 上演练“从一个干净 fixture Git Vault 完整 clone 到 basename `*-test`、禁用 push、写入只发生于 clone、源 HEAD/index/status/hash 不变、删除 clone”的无模型 rehearsal。
- Evidence 必须明确：真实模型委派 canary `NOT_RUN — OPERATOR CONTROLLED ACTION GATE`，不报 PASS。

### STEP-V2-06 — Evidence 修正

- 在 `evidence/01/execution.md` 追加 round 1 correction；保留历史，逐项 F-01 至 F-08 closure。
- AC-03/04/09/10 可在文档与 rehearsal 通过后报 PASS；AC-05 仍 NOT_RUN；AC-06/07/08 与真实模型 E2E 仍 NOT_RUN。
- 记录所有新 VAL 的 cwd、精确命令、退出码、关键脱敏输出。

## 4. 允许/禁止路径

允许修改：
- `.scratch/2026-08-17-sourcenotes-production-switch/cutover-package.md`
- `.scratch/2026-08-17-sourcenotes-production-switch/evidence/01/execution.md`
- 本轮新建 `/tmp/sourcenotes-production-switch-*-test/**`，结束删除。

其余沿用原简报：第一层/Reviewer/issue/产品代码/活动配置/默认 Gateway/两个 Vault全部禁止写；禁止 secret 输出、stage/commit/Controlled Action。

## 5. AC 与 VAL 映射

- **VAL-V2-01 / AC-03**：fixture transformer 两次 deterministic/idempotent；隔离 config validate exit 0；secret-free semantic projection 精确匹配批准字段。
- **VAL-V2-02 / AC-04**：临时 fixture 上 atomic backup/publish/restore，0700/0600/hash/bytes/regular file 全断言通过。
- **VAL-V2-03 / AC-03/10**：干净 fixture source → 完整 `*-test` clone rehearsal；只 clone 产生写入，source HEAD/index/status/hash 不变；push disabled/no remote；clone 删除无残留。
- **VAL-V2-04 / AC-09**：从 Effort 根扫描实际工件 + 逐文件 no-index whitespace；期望无 secret/绝对 Vault/逐项 URL，所有真实写命令分类 Operator-only。
- **VAL-V2-05 / AC-01**：只读复核三仓库/config hash/default Gateway/queue 前后不变。
- **真实模型 E2E**：NOT_RUN，明确列入 Operator Controlled Action 与后续 Work Item 02 Evidence，不得在本轮自证。

## 6. Blocked/deviation

- 如修复 runbook 仍需在命令行传 secret、需要当前 Work Item 写活动配置/正式 Vault、无法用明确变量消除 shell 占位符、或 transformer 不能保留未知字段，返回 BLOCKED。
- 临时 clone rehearsal 不需要模型 secret；不得再因真实模型 E2E 未执行而擅自复制 secret。

## 7. 返回契约

沿用固定模板，逐项报告 F-01 至 F-08 closure、VAL-V2-01..05、真实模型 E2E NOT_RUN。FINAL_STATE 必须声明 temp 无残留、活动 config hash/default Gateway/两个 Vault不变、无 stage/commit/Controlled Action。
