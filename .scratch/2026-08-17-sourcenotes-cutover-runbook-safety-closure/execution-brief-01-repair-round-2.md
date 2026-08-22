# Safety Closure Work Item — Final repair round brief

Role: Executor

## 1. 批准依据

- 本 Effort 第一层 approved；Work Item 01 claimed。
- Reviewer round 2 记录于 `evidence/01/review.md`：F-04/F-11/F-13/F-14/F-17/F-18/F-19。
- 本轮是第二个、最后一个自动修复轮，只修复现有范围内缺陷；不改变 AC/路径/设计，不授权 Controlled Action。

## 2. 上下文与排除方案

- 保留已关闭/通过部分，不重写第一层。
- 真实模型 E2E仍 NOT_RUN。
- 禁止 path-following writes、裸重定向、候选归属不明清理、bool-as-int、命令占位符、token rotation 前未锁定 clean baseline。

## 3. 原子步骤

### STEP-F1 — F-04 safe pause assertion

- 修正 Gate A 暂停投影检查为单一完整安全引用 pattern，例如 `grep -Eq '"telegram_enabled"[[:space:]]*:[[:space:]]*false' "$FILE"`，不得把 `false` 解析为文件。
- fixture 实际运行 package 同源 Gate A block，断言 pattern 正例 PASS、true/缺字段/文件缺失均 fail-fast，token rotation sentinel 不执行。

### STEP-F2 — F-11 all private ledgers no-follow transactional create

- `vault_fingerprint.py` ledger 与 provenance marker/ledger 全部复用同一 secure-create primitive：parent fd no-follow；目标预检查 lstat（regular/symlink/dangling 都拒绝）；`O_EXCL|O_NOFOLLOW`；持 fd `fstat` 验证 regular/0600/uid；full write+fsync；parent fsync。
- 一个事务创建多个文件时记录已创建 `(dir_fd,name,dev,inode)`；后续任一步失败，只在 lstat dev/inode 仍等于本事务记录时 reverse-order unlink，并 fsync parent；不得删除既有对象。
- shell target 检查统一 `if [[ -e "$P" || -L "$P" ]]; then die; fi`，dangling symlink 也拒绝，禁止先 chmod。
- fixture 覆盖 fingerprint ledger regular/symlink/dangling、第二文件创建失败、fstat/permission 验证失败，断言外部 target unchanged、已创建 inode 精确回滚、无残留。

### STEP-F3 — F-13 trap original rc + ownership cleanup

- `_safe_cleanup()` 第一条可执行语句必须 `local rc=$?`，之后才 `trap - ERR`；函数最终 `return "$rc"` 或 `exit "$rc"`，cleanup 错误只 stderr 报告、不覆盖原 rc。
- candidate/temp/clone 仅在本轮创建时写 0600 ownership manifest，含 RUN_ID/realpath/dev/inode/role；cleanup 前 no-follow 验证 manifest 与对象 dev/inode/parent/run_id；不匹配则保留并报告。
- `rm/unlink` 失败显式报告；fixture 注入原 rc 7、cleanup 成功/失败/ownership mismatch，断言最终 rc=7、保护文件不变、仅 owned temp 被删除。

### STEP-F4 — F-14 secure outer output + strict integers

- 新增/复用 `secure_capture.py`：在 STATE_DIR 私有 parent 中以 `mkstemp`/`O_EXCL|O_NOFOLLOW` 创建 0600 unique output，fstat 验证，使用 `subprocess.run([...exact approved argv...], stdout=fd, stderr=separate 0600 file, check=False)`；argv 必须精确包含 `openclaw agent --agent main --session-key "$CANARY_SESSION_KEY" --message "$CANARY_PROMPT" --json` 对应值，不新增业务 flags。失败保留私有诊断或按 ownership 安全清理，绝不裸重定向。
- canary_assert 中 failures/query.count 严格 `type(value) is int`（不是 `isinstance`），拒绝 bool；所有 boolean 字段严格 `is True/False`。
- fixture：output regular/symlink/dangling 拒绝；failures false/true、query.count false/true 全拒绝；valid int PASS；outer/inner 既有负例继续 PASS。

### STEP-F5 — F-17 reproducible Evidence

- 删除本 Effort execution Evidence 中所有 `<每个产物>`、`<path>`、`…`/ellipsis 形式；如历史段必须保留，明确标为 superseded 并在 correction 给完整命令，但最终扫描要求实际字符零命中（省略号 Unicode/三个点/尖括号 placeholder）。
- 每个 fixture 保存：完整命令、cwd、exit、关键输出、fixture script SHA-256，以及 package 中同源脚本 section/提取 SHA。Evidence 不需复制全部临时脚本，但必须给可由 package 重新提取的确定性 extraction 命令及 SHA equality。
- 所有扫描命令以完整 literal 记录，不使用自引用无法区分的占位符；可把 regex 存入 Evidence 的 fenced script 并记录 SHA。

### STEP-F6 — F-18 marker exactness

- 全包 marker 统一精确 `sourcenotes-canary-${RUN_ID}`；CANARY_PROMPT、capture fixture、query/assertion、Evidence 全一致。零命中旧 `sourcenotes-canary-marker-`。

### STEP-F7 — F-19 clean baseline before any rotation

- Gate A 在 ingress pause/token rotation 前运行 `git -C "$PRODUCTION_VAULT_ROOT" status --porcelain=v2 -z`，将 bytes 写入 secure 0600 temp/内存；严格断言长度 0，不能只看 exit。
- 同时核验批准 full HEAD 与 pre-clone fingerprint；dirty/untracked/staged 任一存在即 exit，token rotation sentinel 不执行。
- fixture clean PASS；dirty/untracked/staged 三负例均停止在 rotation sentinel 前。

### STEP-F8 — Evidence and regression

- 修改本 Effort `evidence/01/execution.md`，追加 final repair correction；逐 finding closure。
- VAL-F01 pause pattern/rotation sentinel；VAL-F02 transactional secure ledgers；VAL-F03 trap rc/ownership；VAL-F04 secure capture + strict type；VAL-F05 Evidence reproducibility/placeholder zero；VAL-F06 marker exact；VAL-F07 pre-rotation clean；VAL-F08 all prior regression/privacy/whitespace/bash/python/openclaw candidate；VAL-F09 real state unchanged。

## 4. 允许/禁止路径

仅允许修改 parent `cutover-package.md`、本 Effort `evidence/01/execution.md`、本轮 `/tmp/sourcenotes-cutover-safety-*-test/**`（结束删除）。其它全部禁止，尤其 review/第一层/产品代码/活动 config/default Gateway/两个 Vault/Git写/secret/Controlled Action。

## 5. AC/VAL 映射

- AC-S01/F-04/F-19 → VAL-F01 + VAL-F07。
- AC-S03/F-11 → VAL-F02。
- AC-S04/F-13 → VAL-F03。
- AC-S05/F-14/F-18 → VAL-F04 + VAL-F06。
- AC-S07/F-17 → VAL-F05 + VAL-F08。
- AC-S08 → VAL-F09。

## 6. Blocked

- 任何 fixture 不通过、需要越界、无法使用 exact approved agent argv 或无法消除 Evidence placeholders，返回 BLOCKED。
- 本轮后第三次 Review 非 PASS 时停止，不再自动修复。

## 7. 返回契约

沿用固定模板；逐 F/AC/VAL 报告，真实模型 E2E NOT_RUN，FINAL_STATE 含 temp/真实状态/Git/Controlled Action。
