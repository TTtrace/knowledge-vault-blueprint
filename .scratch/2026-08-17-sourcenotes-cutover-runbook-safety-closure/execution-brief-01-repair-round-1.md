# Safety Closure Work Item — Repair round 1 brief

Role: Executor

## 1. 批准依据

- 本 Effort `spec.md` / `plan.md` approved；Work Item 01 claimed。
- Reviewer round 1：`evidence/01/review.md`，Verdict CHANGES_REQUESTED，F-11/F-13/F-14/F-16/F-17。
- 本轮仅修复允许路径内普通实现/Evidence 缺陷，不改变第一层意图、路径或 AC；不授权 Controlled Action。

## 2. 上下文与排除方案

- 保留已通过 AC-S01/S02/S06 及 parent closed findings。
- F-16 选择恢复原批准命令：使用 `openclaw agent --agent main --session-key "$CANARY_SESSION_KEY" --message "$CANARY_PROMPT" --json`；删除 `--message-file` 与 `--timeout`，无需重新批准。
- 仍禁止真实 Gateway/config/Vault/secret/Git写入；真实模型 E2E NOT_RUN。

## 3. 原子修复步骤

### STEP-R1 — F-11 safe create/no-follow

- marker/ledger 创建前分别 `lstat`；任何已存在对象（regular、symlink、dangling symlink）均拒绝，禁止 chmod。
- 使用 parent dir fd + `os.open(name, O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0o600, dir_fd=...)` 或等价 no-follow exclusive create；写完整 bytes、fsync、关闭；失败定向清理仅本次成功创建 inode。
- 写后 lstat/fstat 验证 regular、非 symlink、0600、owner uid，再记录 provenance。
- cleanup 的 parent/marker/ledger 继续 no-follow；fixture 新增 existing regular marker、marker symlink、dangling marker、existing ledger、ledger symlink/dangling symlink，均拒绝且外部 target 字节不变。

### STEP-R2 — F-13 fail-fast and cleanup trap

- 每个 Operator Bash block 使用 `set -Eeuo pipefail`，定义 `die()` 与 `run_or_die()`；所有 backup/clone/transform/validate/publish/reload/status/probe/fingerprint/agent/jq 命令必须通过函数或显式 `if !`，不得裸执行。
- trap 只处理当前 RUN_ID 下、已通过 provenance 验证的 candidate temp/canary clone；不得删除正式 Vault/活动 config/未知目录。cleanup 失败只报告并保留现场，不掩盖原 exit。
- 预期非零必须显式 `if command; then die; else expected; fi`。
- 从 package 提取全部 Bash block：bash -n；静态检查每个外部命令分类；fixture 注入 backup/clone/validate/reload/status/jq 等失败，断言后续 sentinel 不执行、trap 不触碰保护文件。

### STEP-R3 — F-14 machine assertions

- CANARY_PROMPT 要求 main 最终可见文本为**无 fence 的单行 JSON**，固定 schema：
  - `ok: true`
  - `marker`
  - `capture: {ok:true, ingest_status:"ready", id, path}`
  - `query: {ok:true, count, ids, paths}`
  - `maintenance: {ok:true}`
- Gate C 使用获批命令把 OpenClaw 外层 JSON 写入 RUN_ID 私有 0600 临时文件（不含 secret）；使用 jq 先断言 outer `.result.meta.aborted != true`、`.result.meta.toolSummary.failures == 0`、visible text 存在，再把 visible text 作为 JSON 解析。
- fail-closed 断言：marker 等于 `sourcenotes-canary-${RUN_ID}`；capture path 是相对路径、无 `..`、以 `.md` 结尾；capture id 非空；query count>=1、ids 含相同 capture id、paths 含同 capture path；maintenance ok；任一失败不得进入 Gate D。
- 测试 fixture：valid outer/result PASS；outer failures、aborted、非 JSON、wrong marker、absolute/non-md/path traversal、id mismatch、query 0、maintenance false 全部拒绝。

### STEP-R4 — F-16 restore exact command

- package 中真实 canary agent 命令必须精确为：`openclaw agent --agent main --session-key "$CANARY_SESSION_KEY" --message "$CANARY_PROMPT" --json`，允许通过已定义 `run_or_die` 包裹及 stdout 安全写 0600 文件，但不得新增 flags。
- 删除所有 `--message-file`、`--timeout 600` 及对应 DEVIATION；扫描确认零命中。

### STEP-R5 — F-17 complete Evidence

- 新 Evidence 追加修复轮原始命令；不得使用 `…`、`<每个产物>`、`<path>`、伪 cwd 或省略 shell。
- 对长 regex 记录完整 literal 命令（可引用本 Effort 内实际保存的 fixture script 文件名，但临时文件删除前须把脚本完整内容或 SHA + package 内同源锚点写入 Evidence）。
- 重新运行隐私/路径/URL/whitespace/write primitive 与三仓/config/Gateway/queue；完整记录 cwd、命令、exit、关键输出。

### STEP-R6 — Evidence update

- 修改本 Effort `evidence/01/execution.md`，追加 round 1 correction，逐项 F-11/F-13/F-14/F-16/F-17 closure 与 VAL-R1-01..05。
- AC-S03/S04/S05/S07/S08 仅实际验证通过后 PASS；真实模型 E2E仍 NOT_RUN。

## 4. 允许/禁止路径

允许修改：
- parent `cutover-package.md`
- 本 Effort `evidence/01/execution.md`
- 本轮 `/tmp/sourcenotes-cutover-safety-*-test/**`，结束删除。

其它全部只读/禁止；不得修改 review/第一层/issue/产品代码/活动 config/default Gateway/两个 Vault，不得 stage/commit/Controlled Action。

## 5. AC/VAL 映射

- F-11/AC-S03 → VAL-R1-01：safe create 正例 + existing/symlink/dangling marker/ledger 负例与外部 target unchanged。
- F-13/AC-S04 → VAL-R1-02：全部 Bash bash-n + 外部命令 fail-fast 分类 + 多阶段失败 sentinel/trap 安全。
- F-14/F-16/AC-S05 → VAL-R1-03：精确 agent 命令静态匹配 + outer/inner JSON parser 正负例。
- F-17/AC-S07 → VAL-R1-04：完整可执行扫描命令与 closed finding regression。
- AC-S08 → VAL-R1-05：三仓/config/Gateway/queue 前后不变。

## 6. Blocked/deviation

- 若 package 无法用获批 `--message` 命令安全获取/解析输出，返回 BLOCKED；不得恢复未批准 flags。
- 需越界或真实运行态写时 BLOCKED/NEEDS_REPLAN。

## 7. 返回契约

沿用固定模板；逐 F/AC/VAL 返回。FINAL_STATE 必须声明 temp 清理、真实状态不变、无 stage/commit/Controlled Action。
