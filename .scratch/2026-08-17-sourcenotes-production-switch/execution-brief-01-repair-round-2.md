# Work Item 01 Repair Brief — final automatic repair round

Role: Executor
Effort: `/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-production-switch/`
Work Item: `issues/01-preflight-and-cutover-package.md`（claimed）

## 1. 批准依据

- 第一层 `spec.md` / `plan.md` 及临时克隆 amendment 均已由 Operator 批准。
- 原简报与 v2 repair brief 继续作为背景；Reviewer round 2 记录于 `evidence/01/review.md`。
- 本轮是该 Work Item 的第二个、最后一个自动修复轮，只修复 F-01 至 F-07、F-09 至 F-12；F-08 已关闭。不得改变第一层目标、范围、设计决定、允许路径或 AC；不授权 Controlled Action。

## 2. 上下文与排除方案

- 活动配置、默认 Gateway、两个 Vault、secret、Git index/refs 继续严格只读。
- 真实模型 canary 继续 NOT_RUN，留在 Operator Controlled Action；本轮只把 runbook 和 fixture Evidence 做到精确可复核。
- 排除恢复已撤销旧 token；回滚必须使用“轮换后可用”的私有 rollback candidate。
- 排除 stdout 生成完整候选、固定 temp 名、文本模式复制配置、宽泛 rm、重复 production publish。

## 3. 有序原子步骤

### STEP-R2-01 — F-01/F-02/F-07：隐私扫描与无 stdout secret

- 删除 package/Evidence 中任何绝对 Vault 路径示例，包括伪路径；正文只允许角色变量名与 basename。
- transformer/token injector/atomic helper 均直接写 0600 私有文件；stdout 只输出固定布尔/哈希/semantic projection，绝不 `print(json.dumps(full_config))`。
- 从 Effort 根扫描实际 package/execution：
  - Unix 绝对路径（允许 Project State 自身已知路径需按明确 allowlist 分类；任何 SourceNotes 角色路径一律禁止）；
  - token/credential 键值和 Bot token 形态；
  - URL；
  - 所有 shell/Python 写 primitive：`rm`、`unlink`、`rmdir`、`git clone`、`git remote remove/set-url`、`cp`、`mv`、`install`、`chmod`、`mkdir`、`open/write/os.replace/tempfile`、OpenClaw config/gateway 写命令。
- 生成一张逐命令分类表：行号、动作、目标角色、Operator-only 标记、是否在 fixture 实际执行。不得用“11 处标记”总数代替逐项证明。
- no-index whitespace 逐文件执行并记录。

### STEP-R2-02 — F-03：binary-safe atomic helper

- helper 必须：`open(...,'rb')`/bytes；目标同目录 `tempfile.mkstemp` 唯一 temp；fchmod 0600；完整 write loop；flush/fsync；可选 expected SHA；`os.replace`；parent dir fsync；`finally` 对尚存在的唯一 temp 定向 unlink。
- 不允许固定 `.tmp`、文本 decode/encode、shell redirection 或 `cp` 覆盖。
- fixture 验证：包含非 UTF-8 bytes/尾随换行的逐字节 backup→publish→restore；并注入 write/fsync/replace 失败，断言 active 原字节保留或恢复、temp 零残留、权限 0700/0600。

### STEP-R2-03 — F-05/F-09/F-10：可执行 fail-closed transformer/projection

- 提供可直接保存并运行的完整 Python 脚本，不使用省略号或无效表达式。
- fail-closed 断言：`agents.list` 存在且 main/notesvaulter 各恰一；`skills.entries` 存在；三个 skill entry 可建立但必须是 dict；bindings 为 list；telegram accounts 为 dict；生产/测试 Vault 变量为 absolute、basename 符合角色；任何结构冲突非零退出且不写 candidate。
- 三个 skill entries 均设置相同 `env.VAULT_ROOT`，保留各自其它 env/未知键；三个 enabled=true。
- NotesVaulter skills 精确为三个批准项；main allowAgents 精确为 notesvaulter；删除直接 binding/account。
- token 从 0600 file/SecretRef 私下读取并写 candidate；脚本 stdout 只给固定 `CANDIDATE_WRITTEN=true` 与 candidate SHA，不输出 config。
- projection 是独立完整可执行脚本，只输出批准字段、basename、键集合、token_present/rotated 布尔，绝不读取后输出 token 值。修复所有 Python 语法。
- fixture 两次运行 deterministic/idempotent；缺 main、重复 notesvaulter、skill entry 非 dict、bindings 非 list、token file mode 非 0600 等负例全部 fail-closed 且无 candidate。
- 使用隔离 `OPENCLAW_CONFIG_PATH` validate candidate；分别 `skills info/check --agent notesvaulter` 或当前 CLI 等价命令证明三个 skill 对 fixture candidate eligible，不能只看 enabled。

### STEP-R2-04 — F-06：轮换后可恢复顺序

runbook 必须锁定单一顺序，并给每个可恢复点命名：

1. **PRE_ROTATION_BACKUP**：只作审计，不作为 token revoke 后回滚目标。
2. Operator 对现有 main bot `/revoke`/reissue，立即用新 token 构造并原子发布 **POST_MAIN_ROTATION_BASELINE**：保持切换前运行语义/VAULT_ROOT/capture enabled 状态，仅 main token 更新；validate、Gateway/Telegram health 成功后才继续。该文件成为后续可用 rollback target。
3. 构造 **CANARY_CANDIDATE**：基于 POST_MAIN_ROTATION_BASELINE，单入口候选 + 三技能 + canary Vault；NotesVaulter token 在 canary 前尚未 revoke，因此 CANARY 失败可恢复 POST_MAIN_ROTATION_BASELINE。
4. CANARY PASS 后，对 NotesVaulter bot revoke；立即构造并 validate **POST_ROTATION_SAFE_ROLLBACK**：新 main token、移除 NotesVaulter binding/account、保持 maintenance-safe（capture disabled、原测试 VAULT_ROOT 或明确安全值）。从此禁止恢复 PRE_ROTATION_BACKUP/含旧 token 文件。
5. 构造 **PRODUCTION_CANDIDATE**：基于 POST_ROTATION_SAFE_ROLLBACK，只增加生产三技能/production VAULT_ROOT 等最终字段。唯一 final publish 失败时恢复 POST_ROTATION_SAFE_ROLLBACK，保证 main Telegram 仍可用。

所有候选/rollback 文件 0600、状态目录 0700、原子发布；Evidence 只记录 hash/role/布尔。

### STEP-R2-05 — F-04/F-12：精确单一 cutover DAG

- 用明确 DAG/编号命令消除 §2.5/§2.6 重复：
  - Gate A maintenance + POST_MAIN_ROTATION_BASELINE
  - Gate B create exact canary clone + CANARY_CANDIDATE single publish/reload
  - Gate C local Operator `openclaw agent --agent main --session-key <nonsecret>`（使用当前活动 Gateway）发出**明确提示**，要求 `sessions_spawn` 到 notesvaulter 并返回 query/maintenance/capture 结果；提示文本给出但不含 secret/绝对路径；Telegram 不用于 canary。
  - Gate D canary PASS → revoke NotesVaulter → POST_ROTATION_SAFE_ROLLBACK
  - Gate E construct/validate PRODUCTION_CANDIDATE；**唯一 production publish/reload 只在一个小节一次**
  - Gate F Work Item 02 production Query/Maintenance read-only verification；不重复 publish。
- “暂停入口”必须给精确可执行策略：不依赖 Telegram 发 canary；在 maintenance window 内先用配置 patch/candidate 禁用 channel ingress 或停止 default Telegram polling 的当前版本支持方式。若 OpenClaw 无单独 pause 命令，明确以 CANARY_CANDIDATE `channels.telegram.enabled=false` 实现，并通过 local `openclaw agent`；production candidate 才恢复 default main Telegram。不得在 canary 复制/使用 channel token。
- 每个失败边明确恢复哪个轮换后 baseline，并给 post-restore validate/health 命令。

### STEP-R2-06 — F-11：clone provenance-safe cleanup

- CANARY_VAULT_ROOT 必须是 `STATE_DIR/canary/<exact generated basename>-test` 的 realpath，父目录精确匹配 0700 canary parent。
- 创建前父目录为空、目标不存在；clone 后写一个不入 Git 的私有 marker（0600），内容只含 run_id、source HEAD、clone realpath/inode/dev；同时在私有 ledger 记同一 dev/inode。
- 删除前重新验证：目标 realpath 的父目录、精确 basename/run_id、marker regular no-follow 0600、marker 值、目标 dev/inode 与 ledger、目标不是 symlink、没有运行中 canary process、SourceNotes 正式路径不相等；任一不符停止人工处理。
- 删除只允许通过一个 fail-closed helper 按已验证 fd/realpath 定向删除；不得裸 `rm -rf "$CANARY_VAULT_ROOT"`。在 fixture 验证正确 clone 可删，伪 marker/换 inode/symlink/错误父目录均拒绝且源不变。

### STEP-R2-07 — Evidence

- 在 execution.md 追加 round 2 correction，逐项 F-01..F-07、F-09..F-12 closure，F-08 保持 CLOSED。
- 记录 VAL-R2-01（扫描分类）、R2-02（binary atomic + failures）、R2-03（transform/projection + negative + three eligible）、R2-04（rotation/cutover state-machine fixture assertions）、R2-05（clone provenance cleanup positive/negative）、R2-06（只读 baseline）。
- AC-05 仍 NOT_RUN；真实模型 E2E/AC-06/07/08/10 仍 NOT_RUN，不得提前 PASS。

## 4. 允许/禁止路径

仅允许修改：
- `.scratch/2026-08-17-sourcenotes-production-switch/cutover-package.md`
- `.scratch/2026-08-17-sourcenotes-production-switch/evidence/01/execution.md`
- 本轮新建 `/tmp/sourcenotes-production-switch-*-test/**`，完成后删除。

其余全部只读/禁止，沿用前序简报。不得修改 review/第一层/issue/产品代码/活动配置/default Gateway/两个 Vault，不得输出 secret、stage/commit 或执行 Controlled Action。

## 5. AC/VAL 映射

- AC-09 → VAL-R2-01：完整扫描 + 每个写 primitive 分类 + no-index whitespace。
- AC-04 → VAL-R2-02：binary atomic success/failure/collision/cleanup + 0700/0600。
- AC-03 → VAL-R2-03：valid transformer/projection、fail-closed negatives、candidate validate、三 skill eligible。
- AC-03/04 → VAL-R2-04：凭据轮换后可恢复状态机与唯一 cutover DAG fixture 断言。
- AC-10 → VAL-R2-05：clone provenance-safe cleanup 正负例；真实模型 E2E仍 NOT_RUN。
- AC-01 → VAL-R2-06：三仓/config/default Gateway/queue 前后不变。

## 6. Blocked/deviation

- 任何修复需要真实 secret、活动配置写、default Gateway 变更、正式/测试 Vault 写、产品代码改动即 BLOCKED。
- 当前 OpenClaw CLI 若没有可证明的三技能 eligibility 子命令，可用隔离 candidate 的 `skills list/info/check --agent notesvaulter` 等实际支持组合；必须记录真实命令，不能编造。
- 本轮后 Reviewer 第三次仍非 PASS 时，停止请求 Operator，不得再自动修复。

## 7. 返回契约

沿用固定模板；逐 finding 与 VAL-R2-01..06 报告。FINAL_STATE 必须含 temp 零残留、活动 config hash/default Gateway/两个 Vault未变、无 stage/commit/Controlled Action。
