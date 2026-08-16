---
task_id: 2026-08-14-sourcenotes-final-safety-fixes
status: accepted
review_round: 1
reviewer: primary
reviewed_at: 2026-08-16
---

# Review Record

## Verdict

`ACCEPTED`

本任务按已批准 SPEC（spec_version 1）实现两个安全修复：descriptor-anchored parent fd 显式 ownership 与 migration 错误摘要的引号/分隔符脱敏边界。executor 改动与批准范围一致，全套验证与独立探针通过，无未解决 blocker/major 问题。

## Scope and state

- 实现改动限于批准路径：`scripts/sourcenotes_ops.py`、`tests/operations/test_sourcenotes_ops.py`、本任务 `EXECUTION.md`。
- `SPEC.md`、`REVIEW.md`（本轮前）、前序任务文件、`scripts/sourcenotes_agent.py`、`skills/*`、`specifications/*` 未修改。
- blueprint index 为空；未 stage、commit 或 push。
- `SourceNotes` 保持 clean，HEAD 为 `ec1a90eb9d41df77cf74e44d51e703d0379882e7`。
- `SourceNotes-test` 为冻结 Vault：porcelain=165/cached=155（与 exec 前置基线一致；含一个 2026-08-16 当天由活跃 OpenClaw 实况新增的 staged `sources/web/20260816-014006-kv5x.md`，属外部活动，全程未触碰）。
- OpenClaw 配置 SHA-256 为 `de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424`（mtime 2026-08-15，早于本会话，属外部变更；只读记录）。
- 按 SPEC，不要求真实 OpenClaw E2E。

## Findings

无 blocker/major finding。两个观察项（minor，记录但不影响 AC）：

- `open_rel_dir` docstring 补充了空组件返回 borrowed root_fd 的语义（行为未变）；调用方在 `parent_rel == "."` 时均显式分支，不受影响。
- `_COMPOUND_SECRET_KEY_RE` 三选一值捕获中，引号字面量按「随匹配吞掉」处理（`credential="TOPSECRET"` → `credential=<redacted>`），引号不保留在摘要里；符合 SPEC AC-05「值被替换」语义。

## Acceptance matrix

| AC | Result | Evidence |
|---|---|---|
| AC-01 | pass | `ensure_target_parents` 返回显式 `(fd, owned)`；`owned = len(parts) > 0` 显式计算（无数值比较推断）；顶层返回 `(root_fd, False)`、嵌套 `(nfd, True)`；两个调用点 `finally` 均 `if owned:` 保护；`os.fstat(root_fd)` 借阅后仍有效。独立探针 + `test_ensure_target_parents_returns_explicit_ownership` 通过。 |
| AC-02 | pass | 两个顶层 manifest 目标 apply 成功，dst sha==src sha、内容逐字节一致，无 `.sourcenotes-migrate-*` 残留，源不变，`git diff --cached` 空、HEAD 不变；二次 apply 命中 target-path conflict。`test_migrate_top_level_targets_apply_and_root_fd_survives` 通过。 |
| AC-03 | pass | 顶层第二个 publish 抛 OSError → OpsError(code=EXIT_STORAGE 非零)、目标零残留、无 staging 残留、源 SHA 不变；既有 publish/verify/hash 失败回滚测试保持。`test_migrate_top_level_publish_failure_rolls_back_zero_residue` 通过。 |
| AC-04 | pass | 顶层借阅 250 次 `/proc/self/fd` 差值 0（≤2）；既有 symlink/非目录失败各 250 次、并发创建 250 次测试保持。独立探针 delta=0。 |
| AC-05 | pass | 引号值（`credential="TOPSECRET"`/`credential='TOPSECRET'`）值级脱敏、键保留；裸值在 `| & : , ; ) ] } > ( [ {` 与空白处终止，`retry=3`/`ending` 保留；普通词（`tokenizer`/`author`）负向控制原样通过；JSON 层 details 无秘密、有界。6 组独立探针 + `test_sanitize_quoted_and_delimiter_credential_values` + `test_migrate_rollback_details_sanitize_quoted_values_json_layer` 通过。 |
| AC-06 | pass | `__str__` 再抛异常 → `_bounded_message` 回退 `"BrokenStr: <unprintable>"`，payload 不泄漏；SECRET_PATTERNS/`_ABSOLUTE_PATH_RE` 既有行为不退化；输出单行有界。`test_bounded_message_safe_when_exception_str_raises` + 独立探针通过。 |
| AC-07 | pass | rollback 汇总、KeyboardInterrupt/SystemExit 传播、staging 创建失败、no-follow/no-clobber/TOCTOU 全部既有测试保持（ops 49 / operations discover 67 / vault_capture 29 / web_extract 34 / network_security 54 / harness 19·0）。 |
| AC-08 | pass | 仅三个允许路径变化；index 空；SourceNotes clean@`ec1a90e`；SourceNotes-test 与 OpenClaw 状态与 exec 前置基线一致（外部漂移非本任务引入）。 |

## Independent validation

Reviewer 以 primary agent 身份独立执行（非仅凭 executor 摘要）：

- `python3 -m unittest tests.operations.test_sourcenotes_ops` → `Ran 49 tests ... OK`（42 既有 + 7 新增）
- `python3 tests/skills/test_vault_capture.py` → `Ran 29 tests ... OK`
- `python3 tests/skills/test_web_extract.py` → `Ran 34 tests ... OK`
- `python3 tests/skills/test_network_security.py` → `Ran 54 tests ... OK`
- `python3 -m unittest discover -s tests/operations -p 'test_*.py'` → `Ran 67 tests ... OK`
- `bash tests/opencode-harness/test_capture_debug.sh` → `通过 19 项，失败 0 项`
- `python3 -m py_compile scripts/sourcenotes_agent.py scripts/sourcenotes_ops.py` → exit 0
- `git diff --check` → exit 0
- 独立探针（`/tmp/opencode/verify_probes.py`）：AC-01/04/05/06 全部 PASS（顶层借用+嵌套 owned、250 次借阅 delta=0、6 组分隔+引号+负向控制、`__str__` 回退）
- 只读复核：SourceNotes clean@`ec1a90e` porcelain=0；SourceNotes-test porcelain=165/cached=155；OpenClaw config SHA-256 `de9b9cb1…` —— 均与 exec 前置基线一致

## Notes on process

本任务 reviewer 由 primary agent 依仓库协议（`tasks/README.md`：REVIEW.md 由 Reviewer/primary agent 所有；`AGENTS.md`：primary agent 即 reviewer）完成。全局 `reviewer` 子代理配置（`~/.config/opencode/agents/reviewer.md`）引用本仓不存在的 `docs/agents/lifecycle.md` 且 bash 仅放行其它项目的测试命令、`edit: deny`，与本仓协议不兼容；独立验证与审查结论均由 primary agent 逐项执行，未依赖 executor 摘要。

## Next decision

- 评审通过。提交本任务与 foundation / migration-fd-cleanup 任务改动需用户显式授权（三个 SPEC §10 均声明 stage/commit 不授权）。
- 已知外部漂移（SourceNotes-test 新增 1 个 staged 文件、OpenClaw config hash 变更）为会话开始前的外部活动，提交前无需处理。
