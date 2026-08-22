# Execution Brief 01 — close final runbook findings

Role: Executor

## 1. 批准依据

- 本 Effort `spec.md` / `plan.md` 均 approved。
- Operator 授权原文：`批准新建窄范围安全闭环 Work Item 并继续。`
- Parent approved baseline：`../2026-08-17-sourcenotes-production-switch/spec.md`、`plan.md` 及临时完整 clone amendment。
- Parent final Reviewer Evidence：`../2026-08-17-sourcenotes-production-switch/evidence/01/review.md` round 3。
- 本简报不改变父第一层计划，不授权 Controlled Action。

## 2. 上下文与已排除方案

- Parent package 当前已关闭 F-01/F-02/F-03/F-05/F-06/F-08/F-09/F-10/F-12，但仍有 F-04/F-07/F-11/F-13/F-14/F-15。
- 排除向正式 Vault 写测试数据、复制模型 secret、使用隔离 Gateway、裸 `rm -rf`、恢复旧 token、重复 production publish。
- 真实模型 E2E仍在 Operator gate，当前只做 fixture rehearsal。

## 3. 有序原子步骤

### STEP-01 — F-04 ingress pause first

- 修改 parent `cutover-package.md` 的 DAG：在读取/轮换任何 bot token 前，先构造并 dry-run **INGRESS_PAUSED_BASELINE**，其唯一语义变化是 `channels.telegram.enabled=false`、capture disabled/无新任务；原子发布后按 OpenClaw 当前版本提示执行必要 reload/restart，验证 config/health、queue 0/0、Telegram ingress disabled。
- 只有上述验证 PASS 才允许 Operator 进入 main token `/revoke`；此后 POST_MAIN_ROTATION_BASELINE 必须基于 INGRESS_PAUSED_BASELINE 且保持 ingress paused。
- canary 仅由 Operator 本地 `openclaw agent --agent main --session-key "$CANARY_SESSION_KEY" --message "$CANARY_PROMPT" --json` 触发；production candidate 最终发布时才恢复 default main Telegram ingress。

### STEP-02 — F-07 fail-closed variables

- 在任何 Operator command 前提供可直接 source 的 preamble，至少使用 `: "${VAR:?}"` 验证 `PRODUCTION_VAULT_ROOT`、`STATE_DIR`、`ACTIVE_CONFIG`、`MAIN_BOT_TOKEN_FILE`、`RUN_ID`、`CANARY_SESSION_KEY`。
- 派生 `CANARY_VAULT_ROOT` 只能由已验证 `STATE_DIR` + RUN_ID 计算；验证 absolute/real parent/basename `SourceNotes-production-canary-${RUN_ID}-test`，目标初始不存在。
- 不在 package/Evidence 给变量伪值、真实路径或尖括号占位符。

### STEP-03 — F-11 provenance hardening

- parent canary directory 在创建/删除时均以 `lstat`/no-follow 验证不是 symlink；realpath parent 必须精确为 `STATE_DIR/canary`。
- ledger/marker 必须 `lstat` regular、非 symlink、0600、owner=current uid；内容 schema 仅 run_id、source fingerprints、clone realpath/dev/inode；ledger 与 marker 两边完全匹配。
- cleanup 前验证无相关 PID/process、clone root 本身非 symlink、parent/marker/ledger/provenance 全匹配；通过 fd/realpath 定向删除。任何失败只报告，不删除。
- fixture 包含 parent symlink、ledger symlink、ledger 0644、ledger mismatch 等拒绝例。

### STEP-04 — F-13 fail-fast shell

- 每个完整 Operator shell block 首行 `set -Eeuo pipefail`，安装只针对本次临时 candidate/clone 的 cleanup trap；trap 不触碰正式 Vault或未知路径。
- 每个 `test`/clone/backup/transform/validate/publish/reload/probe 由 `if ! ...; then ...; exit 1; fi` 或 `&&` 明确串联；不得失败后继续。
- 预期失败（例如无 remote 的 `git push`）写成 `if git ...; then echo unexpected >&2; exit 1; else echo expected; fi`，不得依赖裸非零。
- package 中所有 shell 片段通过 `bash -n`；fixture 注入前置失败，断言后续 sentinel 不执行。

### STEP-05 — F-14 queryable canary marker

- CANARY_PROMPT 必须要求 NotesVaulter：先 Capture 一个唯一 idea，idea 文本/标题含 `RUN_ID` 派生的非秘密 marker；再 Query 同一 marker，并做 Maintenance。Capture 应生成 Markdown；Query 命中刚生成 note id/相对路径。
- 断言顺序：capture ok/ready、staged path 为 canary 内 `.md`、query count>=1 且结果含相同 marker/note id、maintenance ok、tool failures=0。
- 删除 `.marker.txt` 作为 Query 证据的设计；provenance marker 可继续存在但不得作为 query target。
- fixture 使用仓库受控入口在临时 clone 演练 idea capture→query 命中→maintenance，不调用模型。

### STEP-06 — F-15 pre-clone fingerprint

- clone 前只读记录并锁定正式 Vault：branch、full HEAD、`HEAD^{tree}`、index file SHA-256、`git status --porcelain=v2 -z` SHA-256/line-state、`git ls-files -s -z` SHA-256；要求 clean 且与批准 HEAD 一致。
- 将该 fingerprint 写入 0600 私有 ledger；clone 完成后、canary 前、canary 后、cleanup 前、production publish 前、收尾各重算并逐项等值；任一漂移立即停止并恢复配置，不清理/修改正式 Vault。
- clone provenance 使用**clone 前** fingerprint，不允许 clone 后首次读取 source HEAD。
- fixture 在干净 source 上证明一致；注入 source 修改后拒绝继续。

### STEP-07 — regression and Evidence

- 从 parent package 提取/构造相关 shell/Python fixture，运行：
  - VAL-S01 ingress-pause/rotation state machine；
  - VAL-S02 variable preamble 正负例 + bash -n/fail-fast sentinel；
  - VAL-S03 provenance cleanup parent/ledger 正负例；
  - VAL-S04 Markdown idea capture→query→maintenance；
  - VAL-S05 pre-clone fingerprint/drift refusal；
  - VAL-S06 parent closed findings regression：secret/path/URL/write classification、binary atomic、transform/projection/three skill eligibility、唯一 production publish、whitespace；
  - VAL-S07 三仓/config/default Gateway/queue 前后只读一致。
- 新增本 Effort `evidence/01/execution.md`，逐 AC/finding 与 VAL 写证据。

## 4. 允许/禁止路径

允许：
- 修改 `/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-production-switch/cutover-package.md`
- 新增 `/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-cutover-runbook-safety-closure/evidence/01/execution.md`
- 本轮新建 `/tmp/sourcenotes-cutover-safety-*-test/**`，完成删除。

其余全部只读/禁止；尤其禁止修改 parent execution/review、两 Effort 第一层/issue、产品代码、活动 config、default Gateway、两个 Vault；禁止 secret 输出、stage/commit/Controlled Action。

## 5. 验收契约映射

- AC-S01/F-04 → VAL-S01：state machine 必须先 ingress paused 再 rotate；本地 CLI 唯一 canary；production 才恢复 Telegram。
- AC-S02/F-07 + AC-S04/F-13 → VAL-S02：unset/invalid vars 非零且无 sentinel；所有 shell `bash -n`；失败不继续。
- AC-S03/F-11 → VAL-S03：正常 cleanup PASS；parent/ledger symlink、0644、mismatch/inode/process 全拒绝。
- AC-S05/F-14 → VAL-S04：临时 Git Vault 中 idea capture 生成 `.md`，query 同 marker 命中，maintenance PASS。
- AC-S06/F-15 → VAL-S05：pre-clone fingerprint 全阶段一致；drift 注入拒绝。
- AC-S07 → VAL-S06：已关闭 finding 全回归。
- AC-S08 → VAL-S07：真实状态前后不变。

## 6. blocked/deviation

- 需修改允许路径外、产品代码、真实运行态、使用 secret 或改变父第一层 AC 时立即 BLOCKED/NEEDS_REPLAN。
- 任何 fixture 失败不得通过文档声明替代。

## 7. 返回契约

```text
STATUS: READY_FOR_REVIEW | BLOCKED
CHANGED_FILES: 绝对路径、内容、原因、STEP
ACCEPTANCE_EVIDENCE: AC-S01..S08 与 F-04/F-07/F-11/F-13/F-14/F-15
VALIDATION_LOG: VAL-S01..S07 cwd/command/exit/key output
DEVIATIONS: none 或逐项
BLOCKERS: none 或逐项
FINAL_STATE: parent package、新 Effort、三仓/config/Gateway/queue/temp/stage/commit/Controlled Action
```
