---
task_id: 2026-08-14-sourcenotes-migration-fd-cleanup
status: ready_for_review
execution_round: 3
executor: executor
spec_path: ../SPEC.md
started_at: 2026-08-14
finished_at: 2026-08-14
---

# Execution Record

> This file is owned by the executor. Do not change the approved `SPEC.md` or write the review verdict here.

## 1. Preflight (round 2)

| Repository | Expected baseline | Observed branch and HEAD | Worktree before execution | Result |
|---|---|---|---|---|
| `knowledge-vault-blueprint` | `main @ badfd519b85c4d80c7875cbf7cbe23afc340c35f`，包含前序任务未提交改动 + 本任务 SPEC | `main @ badfd519b85c4d80c7875cbf7cbe23afc340c35f`；`## main...origin/main`；12 M + 7 ??（均前序任务 + 本任务文件；`scripts/`、`tests/operations/`、`tasks/2026-08-14-.../` 为 untracked） | 前序任务未提交/未暂存允许路径改动 + 本任务 SPEC/EXECUTION；index 无 cached | pass |
| `SourceNotes`（正式 Vault） | `main @ ec1a90eb9d41df77cf74e44d51e703d0379882e7`，clean | `main @ ec1a90eb9d41df77cf74e44d51e703d0379882e7`；porcelain 计数 0 | clean | pass |
| `SourceNotes-test`（测试 Vault） | 冻结既有状态，只读 | `main @ ec1a90eb9d41df77cf74e44d51e703d0379882e7`；porcelain=164 / cached=154 | 既有 staged 资产文件（pre-existing，未触碰） | pass |
| OpenClaw 活动配置 | SHA-256 `71321f12d664db2c2256663599d71a333321e2050ceebec36c7f56b8abc22f5b` | `sha256sum ~/.openclaw/openclaw.json` = `71321f12d664db2c2256663599d71a333321e2050ceebec36c7f56b8abc22f5b` | 未修改（只读核对） | pass |

Applicable instructions read (round 2):

- `/home/monottx/repos/knowledge-vault-blueprint/AGENTS.md`
- `/home/monottx/repos/knowledge-vault-blueprint/tasks/README.md`
- `/home/monottx/repos/knowledge-vault-blueprint/tasks/2026-08-14-sourcenotes-migration-fd-cleanup/SPEC.md`
- 本任务 round 1 `EXECUTION.md`（执行记录基线；round 2 修正其中夸大/错误的测试计数）
- `/home/monottx/repos/knowledge-vault-blueprint/tasks/2026-08-13-sourcenotes-runtime-foundation/EXECUTION.md`（前序任务记录）

Round-2 基线核对结论：与 round 1 完全一致，除允许路径改动与任务文件外无其它漂移；正式/测试 Vault 与 OpenClaw 配置基线不变；三个允许文件均为 untracked（属前序任务目录）。STEP-R2-01 通过。

Round-3 基线核对结论（STEP-R3-01）：与 round 2 handoff 完全一致 —— `main @ badfd519b85c4d80c7875cbf7cbe23afc340c35f`、`## main...origin/main`、12 M + 7 ??（同一路径集合）、`git diff --cached --name-status` 为空；无重叠用户改动；仅执行 reviewer round 2 剩余 F-01（F-02..F-05 已 resolved，未触碰）。

## 2. Round-1 reviewer findings and round-2 disposition

| Finding | Severity | Disposition (round 2) | Implemented fix | STEP |
|---|---|---|---|---|
| F-01 `_bounded_message` 仅截断，未清理绝对路径、秘密或换行；rel 前缀不受整体长度限制 | major | fixed | 新增 `_sanitize_message`（绝对路径 POSIX/Windows 双形式 → `<path>`；`SECRET_PATTERNS` 键值/已知 token 格式 → `<category>`；控制字符与 `\n`/`\r` 转义为单行）；`_bounded_message` 先脱敏再截断；新增 `_bounded_entry` 对「action/rel 前缀 + 摘要」的**整体**总长设限（≤ `_ROLLBACK_ERROR_LIMIT`）。`authorization_header` 模式扩展为 `\s*(?:bearer\s+)?\S+` 使 `Authorization: Bearer <token>` 整段可被脱敏（扫描命中语义不变，仅扩大替换跨度）。诊断类别（`OSError`/`OpsError`/`RuntimeError`…）保留 | STEP-R2-02 |
| F-02 rollback 仅捕获 OSError/OpsError，其它普通运行时异常逃逸 | major | fixed | `rollback_transaction` 三个清理边界（unlink / rmdir / staging）改捕获 `Exception`（绝不捕获 `BaseException`）；错误经 `_bounded_entry` 有界汇总；单 action 失败不阻止后续清理 | STEP-R2-03 |
| F-03 KeyboardInterrupt/SystemExit 被 except BaseException 转为 OpsError | major | fixed | `execute_migration` 外层：rollback 后若 `exc` 为 `KeyboardInterrupt`/`SystemExit`，先执行必要 rollback，再**原样重抛**（不转 OpsError、不误报成功）；rollback 不完整时以单行有界 stderr 提示，不吞掉信号。普通 `Exception` 仍遵循既有 original_error / rollback incomplete 契约 | STEP-R2-04 |
| F-04 staging 创建失败仍 remove-tree，缺失 staging 被误记 rollback incomplete | major | fixed | `execute_migration` 新增 `staging_created` 显式跟踪：`os.mkdir(staging_rel)` 成功才置 True；`rollback_transaction` 新增 `staging_created: bool = True` 参数（默认 True 保持既有直接调用方语义），为 False 时跳过 staging remove-tree。staging 创建失败且无已发布/已创建路径 → 不产生 rollback error / 不误报 incomplete | STEP-R2-05 |
| F-05 执行记录称新增 10 测试但实际 9；`git diff --check` 不覆盖 untracked 文件 | minor | fixed（round 2） | 实测并修正计数：round 1 实际新增 **9** 项（本文件 §3 修正），round 2 新增 7 项，round 3 新增 2 项，总计 42 项；对三个允许文件补 `git diff --no-index --check /dev/null <file>` 只读 whitespace 检查（退出语义见 §7 VAL-08b） | STEP-R2-06 / R3-04 |
| F-01（round 3 剩余）`credential=TOPSECRET`、`client_secret=TOPSECRET` 复合键与 Windows UNC 路径仍泄漏 | major | fixed（round 3） | `_ABSOLUTE_PATH_RE` 扩为三选一（POSIX、Windows drive-letter、Windows UNC `\\\\server\\share\\...`）；新增 `_COMPOUND_SECRET_KEY_RE`：对由字母/数字/下划线/连字符组成且**以敏感词为后缀**（credential/secret/password/token/api-key/auth/bearer，可复数或带数字后缀）的键，**保留键名、仅替换值**为 `<redacted>`，值在空白/引号/逗号/分号/右括号处截止（不吞后续诊断文本）；敏感词必须是键的后缀（可选复数/数字），普通词如 `tokenizer`/`author` 不会被误判。`_sanitize_message` 在 SECRET_PATTERNS 之后追加复合键 pass | STEP-R3-02 |

## 3. Test count correction (F-05)

Round 1 执行记录错误声称「新增 10 个测试」「既有 23 + 新增 10 = 33」。逐项清点后：

- 前序/既有测试：**24** 项。
- Round 1 实际新增：**9** 项（`test_open_rel_dir_symlink_failure_does_not_leak_fds`、`test_open_rel_dir_non_directory_failure_does_not_leak_fds`、`test_ensure_target_parents_symlink_failure_does_not_leak_fds`、`test_ensure_target_parents_non_directory_failure_does_not_leak_fds`、`test_ensure_target_parents_concurrent_creation_fd_stable_and_not_recorded`、`test_rollback_open_rel_dir_ops_error_collected_and_other_actions_attempted`、`test_rollback_aggregates_mixed_errors_bounded`、`test_rollback_clean_restores_pre_call_state`、`test_migrate_incomplete_reports_original_error_without_abs_paths`）。
- Round 1 总数：24 + 9 = **33**（与 VAL-01 输出一致）。
- Round 2 新增：**7** 项（见 §4 测试清单）。
- Round 2 总数：33 + 7 = **40**（VAL-01 实测 `Ran 40 tests`）。
- Round 3 新增：**2** 项 —— `test_rollback_entries_sanitize_compound_keys_unc_and_preserve_context`（`credential=TOPSECRET` / `client_secret=TOPSECRET` / UNC `\\server\share\private.txt` 探针：值级脱敏、键名保留、后续诊断文本 `retry=3`/`ending` 保留、单行且有界）与 `test_sanitize_keeps_plain_token_secret_descriptions`（非键值词句 `token not found…` / `author=John` / `tokenizer=abc` 原样保留，不整体消失）。另扩展 `test_migrate_rollback_details_sanitized_and_bounded` 的 rollback 异常消息加入 `credential=` / `client_secret=` / UNC，并在最终 details JSON 层断言 `TOPSECRET`、`server\share` 不出现。
- Round 3 总数：40 + 2 = **42**（VAL-01 实测 `Ran 42 tests`）。

## 4. Changed files (round 2)

| File | Change and reason | STEP |
|---|---|---|
| `/home/monottx/repos/knowledge-vault-blueprint/scripts/sourcenotes_ops.py` | F-01：新增 `_ABSOLUTE_PATH_RE`、`_sanitize_message`、`_bounded_entry`；`_bounded_message` 改为先脱敏再截断；`authorization_header` 模式扩为含 `Bearer <token>` 整段。F-02：`rollback_transaction` 三处清理边界改捕获 `Exception`。F-04：`rollback_transaction` 增 `staging_created` 参数，False 时跳过 staging 清理；`execute_migration` 显式跟踪 `staging_created`。F-03：`execute_migration` 对 `KeyboardInterrupt`/`SystemExit` 在必要 rollback 后原样重抛（stderr 有界提示 rollback 不完整） | STEP-R2-02/03/04/05 |
| `/home/monottx/repos/knowledge-vault-blueprint/tests/operations/test_sourcenotes_ops.py` | 新增 7 个测试方法（+2 个测试辅助方法，不计入测试数）：`test_rollback_entries_sanitize_paths_secrets_newlines_and_bound_total`（恶意绝对路径 + token/secret 键值 + 换行 + 超长条目 → 条目单行、脱敏、每条 ≤ `_ROLLBACK_ERROR_LIMIT`）；`test_migrate_rollback_details_sanitized_and_bounded`（rollback 异常带秘密 → 最终 OpsError details JSON 无秘密/无绝对路径、original_error 类别保留、`rollback incomplete`、original_error ≤ `_ORIGINAL_ERROR_LIMIT`、每条 rollback_errors ≤ `_ROLLBACK_ERROR_LIMIT`）；`test_rollback_runtime_error_collected_and_actions_continue` / `test_rollback_value_error_collected_and_actions_continue`（RuntimeError/ValueError 被汇总不逃逸，后续 unlink/rmdir/staging 继续）；`test_migrate_keyboard_interrupt_reraises_after_rollback` / `test_migrate_system_exit_reraises_after_rollback`（控制异常执行 rollback 后原样重抛、exit code 保留、零残留）；`test_migrate_staging_mkdir_failure_no_rollback_incomplete`（staging mkdir 失败 → 无 `rollback incomplete`、无 `rollback_errors`、零残留） | STEP-R2-02/03/04/05 |
| `/home/monottx/repos/knowledge-vault-blueprint/tasks/2026-08-14-sourcenotes-migration-fd-cleanup/EXECUTION.md` | 本执行记录更新至 execution_round=2：逐 finding 处置、计数修正、AC/VAL 证据 | STEP-R2-08 |

### Round-3 additions

| File | Change and reason | STEP |
|---|---|---|
| `/home/monottx/repos/knowledge-vault-blueprint/scripts/sourcenotes_ops.py` | `_ABSOLUTE_PATH_RE` 扩为 POSIX / Windows drive-letter / Windows UNC（`\\\\server\\share\\...`）三选一，均替换为 `<path>`；新增 `_COMPOUND_SECRET_KEY_RE`（敏感词后缀键，保留键名、仅值替换为 `<redacted>`，值截止于空白/引号/逗号/分号/右括号）；`_sanitize_message` 在 SECRET_PATTERNS 后追加复合键 pass。F-02..F-05 代码未触碰 | STEP-R3-02 |
| `/home/monottx/repos/knowledge-vault-blueprint/tests/operations/test_sourcenotes_ops.py` | 新增 2 个测试方法（见 §3）；扩展 `test_migrate_rollback_details_sanitized_and_bounded` 覆盖 round-3 探针的 JSON 层断言 | STEP-R3-03 |
| `/home/monottx/repos/knowledge-vault-blueprint/tasks/2026-08-14-sourcenotes-migration-fd-cleanup/EXECUTION.md` | 本执行记录更新至 execution_round=3 | STEP-R3-05 |

未修改：`SPEC.md`、`REVIEW.md`、前序任务记录、两个 Vault、`~/.openclaw/**`、`scripts/sourcenotes_agent.py`、`skills/*`、`specifications/*`、`tests/skills/*`、`tests/operations/test_sourcenotes_agent.py`。

## 5. Acceptance evidence (round 3)

| Criterion | Result | Evidence |
|---|---|---|
| AC-01 rollback 汇总 | pass | `rollback_transaction` 每个 unlink/rmdir/open/remove-tree 步骤捕获 `Exception`（含 OSError/OpsError/RuntimeError/ValueError），返回有界错误记录、不直接逃出；`test_rollback_runtime_error_collected_and_actions_continue`、`test_rollback_value_error_collected_and_actions_continue`（rmdir_names == ["b2", ".staging"] 证明后续 action 继续）与 `test_rollback_open_rel_dir_ops_error_collected_and_other_actions_attempted`、`test_rollback_aggregates_mixed_errors_bounded` 通过；`_bounded_entry` 保证每条记录总长 ≤ 200（round 3 重跑 VAL-01/VAL-05 通过，不退化） |
| AC-02 原始错误保留 | pass | 迁移失败且 rollback 不完整 → 非 0 `OpsError`（code=EXIT_STORAGE）同时带 `original_error`（有界、脱敏、保留 `Publish failed` 类别）与 `rollback_errors`，消息含 `rollback incomplete`。round 3 覆盖 reviewer 三个具体探针：`test_rollback_entries_sanitize_compound_keys_unc_and_preserve_context`（`credential=TOPSECRET` / `client_secret=TOPSECRET` / UNC `\\server\share\private.txt` 均不泄漏；键名 `credential=<redacted>`/`client_secret=<redacted>` 保留；`retry=3`/`ending` 等后续诊断文本保留；单行且每条 ≤200）与 `test_sanitize_keeps_plain_token_secret_descriptions`（非键值词句原样保留）；扩展 `test_migrate_rollback_details_sanitized_and_bounded` 在最终 details JSON 层断言 `TOPSECRET`/`server\share`/`sk-*`/绝对路径均不出现，original_error ≤ `_ORIGINAL_ERROR_LIMIT`、每条 rollback_errors ≤ `_ROLLBACK_ERROR_LIMIT`；F-04 不误报（见 AC-03） |
| AC-03 rollback 完整成功 | pass | 无错误时仍恢复发布文件、新建父目录与 staging，errors==[] 不误报 incomplete（`test_rollback_clean_restores_pre_call_state`、`test_migrate_post_publish_verify_failure_rolls_back_zero_residue` 保持）；staging 创建失败不再误报：`test_migrate_staging_mkdir_failure_no_rollback_incomplete`（无 `rollback incomplete`、无 `rollback_errors`、零残留）；成功路径的 `remove_tree_anchored(staging)` 与既有完整 rollback 行为保持（round 3 重跑不退化） |
| AC-04 fd 生命周期 | pass | ownership 规则（round 1 写入 3 个 helper docstring）未变；round 2/3 未触碰 descriptor helper；5 个 fd 测试（`open_rel_dir` symlink/非目录、`ensure_target_parents` symlink/非目录/并发）全部保持通过 |
| AC-05 压力证据 | pass | symlink/非目录失败路径各 250 次、并发创建 250 次：`/proc/self/fd` diff ≤ 2 不随次数线性增长（round 1 的 5 个测试 round 3 重跑通过，VAL-01） |
| AC-06 安全不退化 | pass | no-follow（symlink 逃逸四件套）、no-clobber（`test_migrate_concurrent_target_never_overwritten`）、TOCTOU（`test_migrate_toctou_parent_symlink_fails_closed`）、post-publish 验证失败全 rollback 全部通过（round 3 重跑 VAL-01） |
| AC-07 全套回归 | pass | VAL-01..08 全部 exit 0（详见 §6/§7）；untracked 文件 whitespace 证据（VAL-08b + 对照测试）round 3 重跑 |
| AC-08 范围与外部状态 | pass | 仅三个允许路径变化；`git diff --cached --name-status` 为空（index 无 cached，未 stage/commit）；正式 Vault clean@ec1a90e、测试 Vault 冻结状态（porcelain=164/cached=154）、OpenClaw config SHA-256=`71321f12…` 全部不变（VAL-09，round 3 复核） |

## 6. Targeted test evidence (rounds 2+3, subset of VAL-01)

- `test_rollback_entries_sanitize_paths_secrets_newlines_and_bound_total`：`/etc/secret/passwd\ncorrupted/../x.md` 恶意 rel；`sk-AAAAAAAA…`、`Authorization: Bearer hunter2xyz`、`password=hunter2abc` → joined 无绝对路径/无任何秘密值、无裸 `\n`/`\r`、每条 ≤ 200，`RuntimeError`/`unlink`/`staging cleanup` 类别保留。
- `test_rollback_entries_sanitize_compound_keys_unc_and_preserve_context`（round 3）：`credential=TOPSECRET; client_secret=TOPSECRET retry=3 unc=\\server\share\private.txt ending` → joined 无 `TOPSECRET`/`server\share`/`private.txt`；`credential=<redacted>`、`client_secret=<redacted>`、`retry=3`、`ending`、`RuntimeError` 保留；每条单行且 ≤ 200。
- `test_sanitize_keeps_plain_token_secret_descriptions`（round 3）：`token not found in manifest; secret scan skipped; credential file missing` 与 `author=John and tokenizer=abc are not credentials` 原样通过（`_sanitize_message` 恒等），普通词句不整体消失。
- `test_migrate_rollback_details_sanitized_and_bounded`（round 2+3）：rollback `_unlink_anchored` 抛带 `sk-*` + `credential=TOPSECRET` + `client_secret=TOPSECRET` + UNC 路径的 RuntimeError → 最终 details JSON 无 `sk-*`/`TOPSECRET`/`server\share`/绝对路径；`original_error` 含 `Publish failed`；`rollback incomplete` 呈现；original_error ≤ `_ORIGINAL_ERROR_LIMIT`、每条 rollback_errors ≤ `_ROLLBACK_ERROR_LIMIT`。
- `test_migrate_keyboard_interrupt_reraises_after_rollback` / `test_migrate_system_exit_reraises_after_rollback`：`rollback_transaction` 恰好调用 1 次；`KeyboardInterrupt` 原样重抛、`SystemExit(3)` 原样重抛且 code==3；已发布文件回滚、无 staging 残留。
- `test_migrate_staging_mkdir_failure_no_rollback_incomplete`：staging `mkdir` 首调用抛 OSError → OpsError(code=EXIT_STORAGE)，无 `rollback incomplete`、无 `rollback_errors`，目标零变化、无 staging 残留。

## 7. Validation log (round 3)

工作目录：`/home/monottx/repos/knowledge-vault-blueprint`（VAL-09 中 Vault/OpenClaw 检查在对应目录）

| Validation | Exact command | Exit | Evidence summary |
|---|---|---|---|
| VAL-01 | `python3 -m unittest tests.operations.test_sourcenotes_ops` | 0 | `Ran 42 tests ... OK`（24 既有 + 9 round1 + 7 round2 + 2 round3；含 rollback 异常汇总、fd 压力、脱敏/有界、复合键/UNC 脱敏、控制异常重抛、staging 失败测试） |
| VAL-02 | `python3 tests/skills/test_vault_capture.py` | 0 | `Ran 29 tests ... OK` |
| VAL-03 | `python3 tests/skills/test_web_extract.py` | 0 | `Ran 34 tests ... OK` |
| VAL-04 | `python3 tests/skills/test_network_security.py` | 0 | `Ran 54 tests ... OK` |
| VAL-05 | `python3 -m unittest discover -s tests/operations -p 'test_*.py'` | 0 | `Ran 60 tests ... OK`（agent 18 + ops 42） |
| VAL-06 | `bash tests/opencode-harness/test_capture_debug.sh` | 0 | `通过 19 项，失败 0 项` |
| VAL-07 | `python3 -m py_compile scripts/sourcenotes_ops.py` | 0 | `PYCOMPILE_EXIT=0` |
| VAL-08a | `git diff --check` | 0 | 无输出（`DIFFCHECK_EXIT=0`） |
| VAL-08b | `git diff --no-index --check /dev/null scripts/sourcenotes_ops.py`；同法 `tests/operations/test_sourcenotes_ops.py`、`tasks/2026-08-14-sourcenotes-migration-fd-cleanup/EXECUTION.md` | 1（文件 vs /dev/null 存在 diff 的正常返回码） | 三个文件均 `NO_WHITESPACE_ERRORS`（无任何 whitespace-error 输出行）；对照测试 `/tmp/opencode/ws-control.txt`（含尾随空格）→ 输出 `trailing whitespace` 且 rc=3，证明该方法能检出 whitespace 错误，rc=1+无输出 = 仅存在 diff、无 whitespace 错误 |
| VAL-09 | `git status --short --branch`、`git diff --cached --name-status`、正式/测试 Vault 与 OpenClaw 只读复核 | 0 | 12 M + 7 ?? 均前序任务 + 本任务（无新路径）；`git diff --cached --name-status` 为空（index 无 cached）；SourceNotes：`main@ec1a90eb…` porcelain=0；SourceNotes-test：`main@ec1a90eb…` porcelain=164/cached=154（冻结状态不变）；OpenClaw config SHA-256=`71321f12d664db2c2256663599d71a333321e2050ceebec36c7f56b8abc22f5b` 不变 |

未运行真实 OpenClaw E2E（SPEC §7 明确不需重跑）。

## 8. Deviations from specification

- 无（与批准简报 STEP-R2-01..08 / STEP-R3-01..05 一致；全部改动落在允许路径 `scripts/sourcenotes_ops.py`、`tests/operations/test_sourcenotes_ops.py`、本任务 `EXECUTION.md`）。
- Round 3 仅修 F-01；F-02..F-05 代码与测试未触碰。
- 未触碰 manifest/CLI/envelope 形态；symlink/非目录/目录缺失的 `OpsError` 消息与 exit code 保持原样。
- 已记录的行为增量（均不改变契约）：`authorization_header` 秘密检测模式跨度扩大（含 `Bearer <token>` 整段）；`KeyboardInterrupt`/`SystemExit` 路径下 rollback 不完整时输出单行有界 stderr 提示；round 3 新增 `_COMPOUND_SECRET_KEY_RE` 仅作用于错误记录脱敏（键名保留、值替换），不影响任何扫描/拒绝路径的命中语义。
- 未 stage/commit/push。

## 9. Unresolved risks and blockers

- 无阻塞项。
- 风险说明（与 SPEC §8 一致）：脱敏为基于模式的替换（绝对路径 POSIX/drive-letter/UNC + 已知键值/token 格式 + 敏感后缀复合键），不声称对任意自由文本的通用秘密检测；复合键判定要求敏感词为键的后缀（可选复数/数字），普通词（`tokenizer`/`author`）不会被误判；rollback 汇总捕获 `Exception` 而非 `BaseException`，控制异常在外层 `execute_migration` 边界仍保证清理后原样传播。

## 10. Git state at handoff

| Repository | Branch | HEAD | `git status --short` | Commit created? |
|---|---|---|---|---|
| `knowledge-vault-blueprint` | `main` | `badfd519b85c4d80c7875cbf7cbe23afc340c35f` | 12 M + 7 ??（前序任务 + 本任务 SPEC/EXECUTION）；index 无 cached | `no` |
| `SourceNotes` | `main` | `ec1a90eb9d41df77cf74e44d51e703d0379882e7` | clean（porcelain=0） | `no` |
| `SourceNotes-test` | `main` | `ec1a90eb9d41df77cf74e44d51e703d0379882e7` | 冻结脏状态（porcelain=164/cached=154，既有 staged 资产，未触碰） | `no` |

## 11. Handoff

- Status: `ready_for_review`
- Recommended reviewer action: 复核 round 3 对 F-01 的最小补齐（`_ABSOLUTE_PATH_RE` UNC 分支、`_COMPOUND_SECRET_KEY_RE` 后缀判定与值替换、`_sanitize_message` 顺序）、两个新测试 + `test_migrate_rollback_details_sanitized_and_bounded` 扩展的断言强度（reviewer 三探针 `credential=TOPSECRET` / `client_secret=TOPSECRET` / UNC `\\server\share\private.txt` 在条目与 JSON 两层均不泄漏、上下文保留、总长有界），确认 F-02..F-05 未改动、计数 round3 增量 +2 / 总 42，以及 VAL-01..09 全套证据。
