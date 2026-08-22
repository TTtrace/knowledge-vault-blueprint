# Work Item 01 Repair Brief — Review round 1 findings

Role: Executor
Effort: `/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-production-switch/`
Work Item: `issues/01-preflight-and-cutover-package.md`（claimed）

## 1. 批准依据

- 第一层 `spec.md` / `plan.md` 已由 Operator 于 2026-08-17 批准；批准原文保持不变。
- 原执行简报：`execution-brief-01.md`。
- Reviewer round 1：`evidence/01/review.md`，Verdict `CHANGES_REQUESTED`，F-01 至 F-08。
- 本修复只关闭允许路径内的文档/Evidence/隔离验证缺陷，不改变目标、迁移边界、Steward 决定、允许路径或 AC；不是 Controlled Action 授权。

## 2. 上下文与已排除方案

- 保留原简报所有不变量与禁止项。
- 仍禁止写活动 OpenClaw 配置、默认 Gateway、两个 Vault、Git index/refs、真实凭据与 last_known_good。
- 允许在**本轮新建且 basename 以 `-test` 结尾的单一 `/tmp/sourcenotes-production-switch-*-test/` 根目录内**建立隔离 OpenClaw state/config/workspace/Vault，并启动唯一 loopback 测试 Gateway；必须使用 `OPENCLAW_STATE_DIR`、`OPENCLAW_CONFIG_PATH`、`OPENCLAW_GATEWAY_PORT` 隔离，channels 全部禁用且不得复制/使用 Telegram token。
- 隔离 E2E 如需模型凭据，只能使用宿主已存在、不会被复制/打印的非 channel 认证机制；如无法在不复制 secret 的情况下运行，返回 BLOCKED，不放宽边界。
- 不再查找或读取任何允许范围外的 vault-starter；只使用仓库内 fixture/测试定义构造临时 Vault。

## 3. 原子修复步骤

### STEP-R1 — 修复 F-01/F-02/F-08 Evidence 边界

- 修改 `evidence/01/execution.md`：一次性路径一律只写 basename 模式，不写绝对路径；删除允许范围外 vault-starter 的绝对路径与“定位”叙述，只保留“仓库内 vault-starter 不存在，使用仓库内测试 fixture 结构”的事实。
- 从 Effort 根运行实际覆盖 `cutover-package.md` 与 `evidence/01/execution.md` 的 secret/path/URL/写命令扫描。
- 对未跟踪 Markdown 使用 `git diff --no-index --check /dev/null <file>`；返回 1 且无 whitespace-error 是“有内容但无 whitespace 错误”，必须逐文件记录。不得把普通 `git diff --check` 当作未跟踪文件证明。
- 扫描规则必须覆盖 token/credential 键值、Bot API token 形态、绝对 SourceNotes 路径、逐项 URL，以及 `cp/mv/install/chmod/mkdir/openclaw config patch/set/unset/gateway` 等写命令是否紧邻 Operator-only 标记。允许文档化命令，但必须分类准确。

### STEP-R2 — 修复 F-03 原子性与权限

- 修改 `cutover-package.md`，把所有配置备份、candidate publish、production cutover、restore 改为同目录临时 regular file → chmod 0600 → flush/fsync → hash/validate → `os.replace`/原子 rename → fsync parent dir 的确定性流程。
- 私有状态目录创建后必须显式 `chmod 0700` 并 `stat` 验证；文件必须 0600 并验证。
- OpenClaw 自有 `config patch` 若用于活动配置，必须引用本机文档“OpenClaw-owned writes replace atomically”，并先 dry-run；若用自有原子 helper，不得用 `cp`/shell redirection 覆盖活动文件。
- 恢复仍是单独 Operator Controlled Action，不执行；只恢复配置，不修改 Vault。

### STEP-R3 — 修复 F-05/F-07 精确候选

- 用一段确定性、secret-safe 的私有候选构造程序/步骤表达：读取活动 regular config；深复制并只改变批准字段；保留所有未知/无关字段；精确替换 `main`/`notesvaulter` agent 条目中的目标字段；删除 notesvaulter Telegram binding 与 account key（不是写 JSON null，除非明确使用 `config patch` merge-patch null 删除语义）；三 skill entries enabled；VAULT_ROOT 从 Operator 私有环境变量读取。
- 所有路径通过已定义并引用的私有变量（例如 `PRODUCTION_VAULT_ROOT`、`STATE_DIR`、`ACTIVE_CONFIG`、`CANDIDATE_CONFIG`），禁止 `<SourceNotes>` 这类 shell 元字符占位符。
- 候选构造不得在命令行参数、stdout/stderr、diff 或 Evidence 输出 token。main 新 token 从 0600 私有文件或 OpenClaw SecretRef 读取；文档只记录 token 字段存在/已轮换布尔值。
- 给出 deterministic secret-free semantic diff 命令：只投影批准字段/布尔值/basename 与 agent/binding/skill names，不读取后输出 secret 值；validate candidate 后才允许进入 controlled gate。

### STEP-R4 — 修复 F-06 凭据轮换语义

- 把 main 凭据步骤改为针对**现有 main bot**的 BotFather `/revoke`/reissue 流程，明确旧 token 立即失效；禁止 `/newbot` 作为轮换。
- NotesVaulter 旧 bot token 同样 revoke，随后配置移除其 account/binding；是否删除 bot 本身不在范围。
- 验证只记录 Operator/BotFather 的旧凭据失效确认，不把旧/新值用于命令行、URL、日志或 Evidence。

### STEP-R5 — 修复 F-04 并实际隔离验证

- 在本轮新建的单一 `/tmp/...-test/` 根内创建：isolated state、config、workspace、临时 Vault；channels 全部 disabled/omitted，无 Telegram token；选择空闲 loopback port，并导出 `OPENCLAW_STATE_DIR`、`OPENCLAW_CONFIG_PATH`、`OPENCLAW_GATEWAY_PORT` 给**每条**测试 CLI。
- 候选测试配置必须包含 main=Steward、main allowAgents=[notesvaulter]、NotesVaulter 三技能、三个 skill entries enabled、VAULT_ROOT 指向该临时 Vault、skills extraDirs 指向蓝图库 skill 目录；不得把活动完整 config 复制进测试根。
- 若可在不复制 secret 的条件下启动：以前台/后台唯一测试 Gateway 启动，捕获 PID，立即安装 trap；health/probe 后运行带唯一 session key 的 main 新 session，要求 main 显式 spawn `notesvaulter` 完成：query search（命中临时 fixture note）和 maintenance report；另外验证三技能 list/info/check 对 notesvaulter eligible。记录 secret-free envelope/assertions。最后终止并 wait 测试 PID、删除本轮 temp root，证明无残留。
- 禁止测试 production Capture；如需验证 Capture skill eligibility，只做 info/check，不调用 capture。
- 如果 OpenClaw agent 命令无法明确指向隔离 Gateway/state/port，或现有模型认证不能在不复制 secret 下使用，立即 BLOCKED，并保留已完成的文档修复，不伪称 E2E PASS。
- 将完整、无未定义占位符的隔离流程写回 `cutover-package.md`；每条 CLI 显式带隔离 env。

### STEP-R6 — 更新 Evidence

- 在 `evidence/01/execution.md` 追加/修订 round 1 correction，逐项关闭 F-01 至 F-08，保留原历史但纠正错误完成声明；不得删除 Reviewer finding。
- AC-03/04/09 仅在相应修复与新验证通过后报 PASS；AC-05 仍 NOT_RUN；AC-06/07/08 仍 NOT_RUN。
- 重报全部修复 VAL 的 cwd、精确命令、退出码、关键脱敏输出和 final state。

## 4. 允许/禁止路径

允许修改：
- `/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-production-switch/cutover-package.md`
- `/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-production-switch/evidence/01/execution.md`
- 本轮新建 `/tmp/sourcenotes-production-switch-*-test/**`，完成后删除。

其余全部只读/禁止，沿用原简报。特别禁止修改 `evidence/01/review.md`、第一层工件、issues、产品代码、活动配置、默认 Gateway、两个 Vault；禁止 stage/commit、secret 输出和 Controlled Action。

## 5. AC/VAL 映射

- AC-03 → **VAL-R1-01**：确定性 candidate transform 在脱敏 fixture 上运行两次结果一致；candidate config 使用隔离 `OPENCLAW_CONFIG_PATH` 执行 `openclaw config validate` exit 0；semantic projection 精确匹配批准字段且无 `*`/second binding/secret value。
- AC-04 → **VAL-R1-02**：对临时同目录 fixture 实际执行原子 backup/publish/restore helper，断言 regular file、0700/0600、hash、fsync/replace 后字节恢复；绝不针对活动配置。
- AC-02/03 → **VAL-R1-03**：按 STEP-R5 隔离 Gateway E2E；期望 test health/probe、notesvaulter 三 skill eligible、main 新 session 委派 query+maintenance 成功，PID 终止、temp 无残留。无法安全执行则 BLOCKED。
- AC-09 → **VAL-R1-04**：从 Effort 根扫描两个实际产物；期望无 secret/绝对 Vault/逐项 URL；写命令均有 Operator-only 分类；逐文件 no-index whitespace 无错误。
- AC-01 → **VAL-R1-05**：只读复核三仓库/config hash/Gateway/queue 前后不变；期望与 round 0 baseline 一致，无 active write。

## 6. blocked/deviation 规则

沿用原简报。尤其：隔离 Gateway 若要求复制活动 config/Telegram token、修改默认 state、使用 production Vault、或无法通过显式 env/port 定向，则 `STATUS: BLOCKED`；不得把缺失 Evidence 改写为 PASS。

## 7. 返回契约

按原固定模板逐字段返回，并在 ACCEPTANCE_EVIDENCE/VALIDATION_LOG 中逐项列出 F-01 至 F-08 closure 与 VAL-R1-01..05。DEVIATIONS 无则 `none`。FINAL_STATE 必须声明测试 Gateway PID 已终止、temp root 已删除、活动 config hash/默认 Gateway/两个 Vault未变、未 stage/commit/Controlled Action。
