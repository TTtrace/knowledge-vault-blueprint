---
task_id: 2026-08-14-sourcenotes-final-safety-fixes
status: ready_for_review
execution_round: 1
executor: executor
spec_path: ../SPEC.md
started_at: 2026-08-16
finished_at: 2026-08-16
---

# Execution Record

> This file is owned by the executor. Do not change the approved `SPEC.md` or write the review verdict here.

## 1. Preflight

| Repository | Expected baseline | Observed branch and HEAD | Worktree before execution | Result |
|---|---|---|---|---|
| `knowledge-vault-blueprint` | `main @ badfd519b85c4d80c7875cbf7cbe23afc340c35f`，含前序任务未提交改动，index 为空 | `main @ badfd519b85c4d80c7875cbf7cbe23afc340c35f`；`## main...origin/main`；12 M + 7 ??（前序任务路径集合：`BLUEPRINT.md`/`DECISIONS.md`/`ROADMAP.md`/`skills/*`/`specifications/*`/`tests/skills/test_vault_capture.py` 为 M，`scripts/`/`skills/vault-maintenance/`/`skills/vault-query/`/`specifications/agent-operations.md`/`tasks/*` 三任务目录/`tests/operations/` 为 ??）；`git diff --cached --name-status` 为空 | 前序任务未提交/未暂存改动，无与本任务重叠的既有用户改动 | pass |
| `SourceNotes`（正式 Vault） | `main @ ec1a90eb9d41df77cf74e44d51e703d0379882e7`，clean | `main @ ec1a90eb9d41df77cf74e44d51e703d0379882e7`；porcelain=0 / cached=0 | clean | pass |
| `SourceNotes-test`（测试 Vault） | 冻结既有状态，只读；前序记录 porcelain=164 / cached=154 | `main @ ec1a90eb9d41df77cf74e44d51e703d0379882e7`；porcelain=165 / cached=155 | 既有 staged 资产文件 + 一个 2026-08-16 当天新 staged 的 `sources/web/20260816-014006-kv5x.md`（活跃 OpenClaw 实况写入，会话开始前已存在，本任务全程未触碰） | pass（观察到前序记录之外的漂移，见 §8） |
| OpenClaw 活动配置 | 前序记录 SHA-256 `71321f12d664db2c2256663599d71a333321e2050ceebec36c7f56b8abc22f5b` | `sha256sum ~/.openclaw/openclaw.json` = `de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424`（mtime 2026-08-15 02:56） | 会话开始前已与记录值不同（环境实况漂移，非本任务所致）；只读核对，未修改 | pass（观察到漂移，见 §8） |

Applicable instructions read:

- `/home/monottx/repos/knowledge-vault-blueprint/AGENTS.md`
- `/home/monottx/repos/knowledge-vault-blueprint/tasks/README.md`
- `/home/monottx/repos/knowledge-vault-blueprint/tasks/2026-08-14-sourcenotes-final-safety-fixes/SPEC.md`
- `/home/monottx/repos/knowledge-vault-blueprint/tasks/2026-08-14-sourcenotes-migration-fd-cleanup/EXECUTION.md`（执行记录格式参考）

允许路径核对：仅 `scripts/sourcenotes_ops.py`、`tests/operations/test_sourcenotes_ops.py`、本任务 `EXECUTION.md` 将被修改；`SPEC.md`/`REVIEW.md`/前序任务文件/两个 Vault/`~/.openclaw/**` 不触碰；不 stage/commit/push，不 reset/clean。

## 2. Implemented changes

| File | Change and reason | STEP / AC |
|---|---|---|
| `scripts/sourcenotes_ops.py` | **改动 1（AC-01..AC-04）**：`ensure_target_parents` 返回类型改为显式 `tuple[int, bool]`（`fd, owned`）；`owned = len(parts) > 0` 显式计算，绝不通过 fd 数值比较推断。顶层 rel（`Path(rel).parts[:-1]` 为空）直接返回 `(root_fd, False)`；含父目录时逐组件打开/创建后返回 `(nfd, True)`。两个调用点同步更新：staging（`staged_parent_fd, owned = ...`，`finally: if owned: os.close(...)`）与 publish 循环（`parent_fd, owned = ...`，`finally: if owned: os.close(parent_fd)`），并更新 publish 循环注释说明顶层目标复用 borrowed root_fd 绝不被调用者关闭。`root_fd` 生命周期保持 `execute_migration` 自开自关一次（外层 `finally: os.close(root_fd)`）。`open_rel_dir` docstring 补充空组件（`"."`/空）时返回的就是 borrowed root_fd、调用者不得关闭的语义，行为不变。**改动 2（AC-05、AC-06）**：`_COMPOUND_SECRET_KEY_RE` 值捕获改为三选一 —— 双引号串 `"[^"\r\n]*"` / 单引号串 `'[^'\r\n]*'`（引号随匹配吞掉） / 裸值 `[^\s'",;:\|&()\[\]{}<>]+`（在空白、引号、逗号、分号、冒号、管道、与号及全部括号/花括号/尖括号边界终止）；替换仍为 `r"\1=<redacted>"`，键名保留。正则上方注释块重写以反映引号与分隔符语义。`_bounded_message` 用 `try/except` 包裹 `f"{type(exc).__name__}: {exc}"`，`__str__` 再抛时回退为 `f"{type(exc).__name__}: <unprintable>"`（仅类型的安全摘要，不崩溃不泄漏），截断逻辑保持 | STEP-01..04 / AC-01..06 |
| `tests/operations/test_sourcenotes_ops.py` | 新增 7 个测试方法 + 2 个辅助方法（`_seed_top_level_pair`、`_top_level_entry`）；既有 42 项测试全部保留（其中 `test_ensure_target_parents_concurrent_creation_fd_stable_and_not_recorded` 改为解包 `(parent_fd, owned)` 元组并断言 `owned is True`，语义不变）；新增测试清单见 §3 | STEP-05 / AC-01..06 |
| `tasks/2026-08-14-sourcenotes-final-safety-fixes/EXECUTION.md` | 本执行记录 | STEP-06 |

未修改：`SPEC.md`、`REVIEW.md`、前序任务记录、两个 Vault、`~/.openclaw/**`、`scripts/sourcenotes_agent.py`、`skills/*`、`specifications/*`、`tests/skills/*`、`tests/operations/test_sourcenotes_agent.py`。

## 3. Test count

前序/既有测试：**42** 项（与 `2026-08-14-sourcenotes-migration-fd-cleanup` 记录一致）。

本任务新增 **7** 项：

1. `test_ensure_target_parents_returns_explicit_ownership`（AC-01）—— 顶层 rel 返回 `(root_fd, False)` 且 `os.fstat(root_fd)` 仍有效；嵌套 rel 返回 `(fd, True)` 且 `fd != root_fd`。
2. `test_ensure_target_parents_top_level_borrow_no_fd_growth`（AC-04）—— 250 次顶层借阅（owned=False、调用者不得关闭）后 `/proc/self/fd` 差值 ≤ 2。
3. `test_migrate_top_level_targets_apply_and_root_fd_survives`（AC-02）—— 两个顶层 manifest 目标（`top-source.md` / `top-annotation.md`）apply 成功，内容/hash 正确、无 `.sourcenotes-migrate-*` 残留、源不变、不 commit；两文件事务天然证明 root fd 存活（若调用者误关 root_fd，第二项 publish/unlink 必现 EBADF）；二次 apply 命中 target-path conflict（exit 3）。
4. `test_migrate_top_level_publish_failure_rolls_back_zero_residue`（AC-03）—— 复用 flaky_publish mock 模式：第二个顶层 publish 抛 OSError → OpsError(code=EXIT_STORAGE)、目标零残留、源字节不变、无 staging 残留。
5. `test_sanitize_quoted_and_delimiter_credential_values`（AC-05）—— 参数化探针 15 组：`credential="TOPSECRET"` / `credential='TOPSECRET'` 无泄漏且键保留；`| & : , ; ) ] } > ( [ {` 与空白分隔场景值被替换、`retry=3`/`ending` 上下文保留；负向控制 `token not found…` / `author=John` / `tokenizer=abc` 原样通过。
6. `test_migrate_rollback_details_sanitize_quoted_values_json_layer`（AC-05 JSON 层）—— rollback 异常带 `credential="TOPQUOTED"` / `client_secret='TOPSECRET'` 经 `cmd_migrate`/rollback → 最终 details JSON（original_error / rollback_errors）无秘密、键名与 `retry=3`/`ending` 保留、original_error ≤ `_ORIGINAL_ERROR_LIMIT`、每条 rollback_errors ≤ `_ROLLBACK_ERROR_LIMIT`。
7. `test_bounded_message_safe_when_exception_str_raises`（AC-06）—— 构造 `__str__` 再抛异常的异常实例 → `_bounded_message` 返回 `"BrokenStr: <unprintable>"`，不崩溃、不泄漏 payload；`_bounded_entry` 路径同样安全。

总计：42 + 7 = **49**（VAL-01 实测 `Ran 49 tests`）。

## 4. Acceptance evidence

| Criterion | Result | Evidence |
|---|---|---|
| AC-01 显式 ownership | pass | `ensure_target_parents` 返回 `tuple[int, bool]`；`owned = len(parts) > 0` 显式计算（无 fd 数值比较）。顶层 `(root_fd, False)` 借用、调用者绝不关闭；嵌套 `(nfd, True)` 恰好关闭一次。两处调用点 `finally` 均 `if owned:` 保护。`test_ensure_target_parents_returns_explicit_ownership`（含 `os.fstat(root_fd)` 存活断言）+ 独立复现探针（VAL-09）通过 |
| AC-02 顶层成功 | pass | `test_migrate_top_level_targets_apply_and_root_fd_survives`：两个顶层文件 apply 成功，dst sha == src sha、内容逐字节一致，无 staging 残留，源不变，`git diff --cached` 空、HEAD 不变；二次 apply 正确命中冲突（非 EBADF）。两文件事务证明 root fd 在全部 publish/unlink 期间存活 |
| AC-03 顶层失败回滚 | pass | `test_migrate_top_level_publish_failure_rolls_back_zero_residue`：flaky_publish 第 2 次抛 OSError → `OpsError`（`Publish failed`，code=EXIT_STORAGE 非零）、目标零残留、无 staging 残留、源 SHA 不变；既有 publish/verify/hash 失败回滚测试保持通过 |
| AC-04 fd 压力 | pass | 顶层借阅 250 次 `/proc/self/fd` 差值 0（≤2）；既有 symlink/非目录失败路径各 250 次、并发创建 250 次测试全部保持（VAL-01）；独立探针（VAL-09）差值 0 |
| AC-05 引号与分隔符脱敏 | pass | `_COMPOUND_SECRET_KEY_RE` 三选一值捕获：`credential="TOPSECRET"`/`credential='TOPSECRET'` 值级脱敏、键保留；裸值在 `| & : , ; ) ] } > ( [ {` 与空白处终止，`retry=3`/`ending` 保留；`test_sanitize_quoted_and_delimiter_credential_values`（15 组探针）+ 既有「普通词不误判」测试（`tokenizer`/`author`）通过；JSON 层 `test_migrate_rollback_details_sanitize_quoted_values_json_layer` 通过；独立探针（VAL-09）全过 |
| AC-06 安全摘要韧性 | pass | `_bounded_message` 对 `__str__` 再抛回退 `"<Type>: <unprintable>"`；SECRET_PATTERNS（Authorization/Bearer、Cookie、password/token/api_key/secret/credential、sk-/ghp_/AKIA/AIza/JWT、PEM）、`_ABSOLUTE_PATH_RE`（POSIX/Windows/UNC）既有行为不退化；输出单行有界（`_ROLLBACK_ERROR_LIMIT`/`_ORIGINAL_ERROR_LIMIT`）；`test_bounded_message_safe_when_exception_str_raises` + 既有脱敏/有界测试全部通过 |
| AC-07 安全不退化 | pass | rollback 汇总、KeyboardInterrupt/SystemExit 传播、staging 创建失败、no-follow（symlink 逃逸四件套）、no-clobber（并发目标）、TOCTOU 全部既有测试保持通过（VAL-01/VAL-05，Ran 49/67 OK） |
| AC-08 范围与外部状态 | pass | 仅三个允许路径变化；`git diff --cached --name-status` 为空（未 stage/commit）；SourceNotes clean@`ec1a90e` 不变；SourceNotes-test 与 OpenClaw 配置与**会话开始前**观测一致（漂移为实况环境所致，非本任务引入，见 §8） |

## 5. Targeted test evidence

- AC-01/04：`ensure_target_parents(root_fd, "top.md", [])` → `(root_fd, False)`；250 次顶层借阅后 fd 计数不变（before=5 after=5 delta=0）；`os.fstat(root_fd)` 在借阅后仍有效。
- AC-02：`test_migrate_top_level_targets_apply_and_root_fd_survives` 中两个顶层文件 publish 均成功（旧代码下第二次 publish 因 `dir_fd=root_fd` 已关闭而 EBADF）。
- AC-03：flaky_publish 第二次抛 OSError → 两个顶层文件均不存在、无 staging 残留、源 SHA 不变、exit=EXIT_STORAGE。
- AC-05：`_sanitize_message('credential="TOPSECRET"|retry=3|ending')` → `'credential=<redacted>|retry=3|ending'`（SPEC §4 原始复现用例关闭）；15 组引号/分隔符探针全过；JSON 层断言 `TOPQUOTED`/`TOPSECRET` 不出现、`credential=<redacted>`/`client_secret=<redacted>`/`retry=3`/`ending` 保留。
- AC-06：`BrokenStr.__str__` 抛 ValueError → `_bounded_message` 返回 `"BrokenStr: <unprintable>"`，payload 不泄漏。

## 6. Validation log

工作目录：`/home/monottx/repos/knowledge-vault-blueprint`（VAL-10 中 Vault/OpenClaw 检查在对应目录）

| Validation | Exact command | Exit | Evidence summary |
|---|---|---|---|
| VAL-01 | `python3 -m unittest tests.operations.test_sourcenotes_ops` | 0 | `Ran 49 tests ... OK`（42 既有 + 7 新增） |
| VAL-02 | `python3 tests/skills/test_vault_capture.py` | 0 | `Ran 29 tests ... OK` |
| VAL-03 | `python3 tests/skills/test_web_extract.py` | 0 | `Ran 34 tests ... OK` |
| VAL-04 | `python3 tests/skills/test_network_security.py` | 0 | `Ran 54 tests ... OK` |
| VAL-05 | `python3 -m unittest discover -s tests/operations -p 'test_*.py'` | 0 | `Ran 67 tests ... OK`（agent 18 + ops 49） |
| VAL-06 | `bash tests/opencode-harness/test_capture_debug.sh` | 0 | `通过 19 项，失败 0 项` |
| VAL-07 | `python3 -m py_compile scripts/sourcenotes_agent.py scripts/sourcenotes_ops.py` | 0 | `PYCOMPILE_EXIT=0` |
| VAL-08a | `git diff --check` | 0 | 无输出（`DIFFCHECK_EXIT=0`） |
| VAL-08b | `git diff --no-index --check /dev/null <file>`（三个允许文件分别执行） | 1（文件 vs /dev/null 存在 diff 的正常返回码） | 三个文件均无任何 whitespace-error 输出行（rc=1 + 空输出 = 仅存在 diff、无 whitespace 错误） |
| VAL-09 | `python3 /tmp/opencode/repro_ac_probes.py`（独立复现 AC-01/04/05/06） | 0 | `REPRO_RESULT: all independent probes passed`（3 项 AC-01、1 项 AC-04、17 项 AC-05 含负向控制、1 项 AC-06 全部 PASS） |
| VAL-10 | `git status --short --branch`、`git diff --cached --name-status`、SourceNotes / SourceNotes-test / OpenClaw 只读复核 | 0 | 蓝图库：`main@badfd519…` 12 M + 7 ??（路径集合与会话开始前一致）、cached 空；SourceNotes：`main@ec1a90eb…` porcelain=0/cached=0（clean 不变）；SourceNotes-test：`main@ec1a90eb…` porcelain=165/cached=155（与会话开始前一致，未触碰）；OpenClaw config SHA-256 `de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424`（与会话开始前一致，未触碰） |

未运行真实 OpenClaw E2E（SPEC §7 明确不需重跑）。

## 7. Independent reproduction (VAL-09 details)

`/tmp/opencode/repro_ac_probes.py` 在蓝图库根目录运行（scratch 仅用 `/tmp/opencode`，不落库、不触碰 Vault）。关键输出：

```
PASS  AC-01 top-level -> (root_fd, False) fd=3 owned=False
PASS  AC-01 root_fd still valid after top-level borrow
PASS  AC-01 nested -> (new_fd, True), fd != root_fd root=3 nested=5 owned=True
PASS  AC-04 250 top-level borrows fd delta <= 2 before=5 after=5 delta=0
PASS  AC-05 'credential="TOPSECRET"|retry=3|ending' -> 'credential=<redacted>|retry=3|ending'
PASS  AC-05 "credential='TOPSECRET'|retry=3|ending" -> "credential=<redacted>|retry=3|ending"
…（15 组 AC-05 探针 + 2 组负向控制全 PASS）
PASS  AC-06 __str__ raising -> 'BrokenStr: <unprintable>' 'BrokenStr: <unprintable>'
REPRO_RESULT: all independent probes passed
```

## 8. Deviations from specification

- **无**与批准简报的偏差：全部改动落在允许路径 `scripts/sourcenotes_ops.py`、`tests/operations/test_sourcenotes_ops.py`、本任务 `EXECUTION.md`；不修改 SPEC/REVIEW/前序文件/Vault/OpenClaw；未 stage/commit/push，未 reset/clean。
- 外部状态观测说明（非本任务偏差）：`SourceNotes-test`（porcelain=165/cached=155，前序记录为 164/154）与 `~/.openclaw/openclaw.json`（SHA-256 `de9b9cb1…`，前序记录为 `71321f12…`）在**本会话开始前**即已漂移 —— 测试 Vault 新增了一个 2026-08-16 当天 staged 的 `sources/web/20260816-014006-kv5x.md`（活跃 OpenClaw 实况捕获），config mtime 为 2026-08-15 02:56。本任务全程只读核对、未触碰二者；VAL-10 记录的是与会话开始前一致的观测值。正式 Vault `SourceNotes` 与 SPEC §4 基线完全一致（clean @ `ec1a90e`）。
- 行为增量（均不改变既有契约，SPEC §3 非目标未触及）：`_COMPOUND_SECRET_KEY_RE` 的值捕获由单裸值改为三选一（引号随匹配吞掉、裸值新增 `: | & ( [ { <` 终止符），仅影响错误记录脱敏的替换跨度，不影响任何扫描/拒绝路径的命中语义；`ensure_target_parents` 返回 `(fd, owned)` 二元组，两个调用点同步消费。

## 9. Unresolved risks and blockers

- 无阻塞项。
- 风险说明（与 SPEC §8 一致）：脱敏为基于模式的替换，不声称对任意自由文本的通用秘密检测；复合键判定要求敏感词为键的后缀（可选复数/数字），普通词（`tokenizer`/`author`）不会被误判；ownership 由显式 `owned` 标志表达，调用点全部审计并覆盖顶层/子目录/异常/fd 压力测试。

## 10. Git state at handoff

| Repository | Branch | HEAD | `git status --short` | Commit created? |
|---|---|---|---|---|
| `knowledge-vault-blueprint` | `main` | `badfd519b85c4d80c7875cbf7cbe23afc340c35f` | 12 M + 7 ??（前序任务 + 本任务 SPEC/EXECUTION；路径集合与会话开始前一致）；`git diff --cached --name-status` 为空 | `no` |
| `SourceNotes` | `main` | `ec1a90eb9d41df77cf74e44d51e703d0379882e7` | clean（porcelain=0 / cached=0） | `no` |
| `SourceNotes-test` | `main` | `ec1a90eb9d41df77cf74e44d51e703d0379882e7` | 冻结脏状态（porcelain=165 / cached=155，含会话开始前已存在的 2026-08-16 实况新增 staged 文件；未触碰） | `no` |

## 11. Handoff

- Status: `ready_for_review`
- Recommended reviewer action: 复核改动 1（`ensure_target_parents` 二元组返回 + 两个调用点 `if owned:` 关闭 + 注释；`open_rel_dir` docstring 补充，无行为变更）与改动 2（`_COMPOUND_SECRET_KEY_RE` 三选一值捕获与注释块、`_bounded_message` 的 `__str__` 回退），7 个新测试 + 既有 42 项全套回归（VAL-01..10 全 0），以及外部状态漂移说明（会话开始前已存在、非本任务引入）。
