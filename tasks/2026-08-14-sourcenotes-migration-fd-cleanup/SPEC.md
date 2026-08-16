---
task_id: 2026-08-14-sourcenotes-migration-fd-cleanup
title: 修复 SourceNotes 迁移事务的回滚异常与文件描述符泄漏
status: approved
spec_version: 1
planner: primary
executor: executor
created: 2026-08-14
approved_at: 2026-08-14
approved_by: user
---

# Task Specification

## 1. 批准依据

前序任务 `2026-08-13-sourcenotes-runtime-foundation` 已完成实现、全套测试与真实 OpenClaw E2E，但第 3 轮 reviewer 仍发现两个迁移工具资源安全问题。按三轮上限，planner 停止原任务并向用户提出新建窄范围修复任务；用户明确回复：`批准新建窄范围修复任务并继续`。

本任务只修复以下两个已独立复现的问题：

1. rollback 内部的 `OpsError` 等异常可能逃出，掩盖原始失败，不能稳定报告 `rollback incomplete`。
2. descriptor-anchored 路径逐组件打开失败时，中间文件描述符未关闭；reviewer 连续 200 次失败后观察到 fd 数增加 200。

## 2. 目标

1. rollback 的每个清理步骤捕获并汇总所有预期异常；任何清理不完整都稳定报告 `rollback incomplete`，同时保留原始迁移失败摘要。
2. 所有 descriptor-anchored 路径解析和父目录创建在成功、失败、symlink、非目录及并发异常路径上均关闭中间 fd。
3. 用重复失败压力测试证明 fd 数稳定，用 rollback 异常测试证明不会掩盖或误报成功。
4. 保持前序任务的 no-follow、no-clobber、全事务回滚、路径边界及全部 AC 不退化。

## 3. 非目标

- 不改变用户→Steward→NotesVaulter 架构、委派协议或界面原则。
- 不改变 Capture、Query、Maintenance、incident、ledger 或附件策略。
- 不改变 migration manifest、迁移数据选择、schema 或阈值。
- 不修改、迁移或提交 `SourceNotes` / `SourceNotes-test` 数据。
- 不修改活动 OpenClaw、agent workspace、exec approvals 或 systemd。
- 不 stage、commit、push、pull、merge、rebase、reset、clean 或 tag。

## 4. 基线

- 蓝图库：`/home/monottx/repos/knowledge-vault-blueprint`，`main@badfd519b85c4d80c7875cbf7cbe23afc340c35f`；包含前序任务未提交、未暂存的允许路径改动，以及本任务 planner 新增的 SPEC。
- 正式 Vault：`/home/monottx/repos/SourceNotes`，`main@ec1a90eb9d41df77cf74e44d51e703d0379882e7`，clean。
- 测试 Vault：`/home/monottx/repos/SourceNotes-test`，冻结既有状态，只读。
- OpenClaw config SHA-256：`71321f12d664db2c2256663599d71a333321e2050ceebec36c7f56b8abc22f5b`，只读。

## 5. 允许路径

允许修改/新增：

- `scripts/sourcenotes_ops.py`
- `tests/operations/test_sourcenotes_ops.py`
- `tasks/2026-08-14-sourcenotes-migration-fd-cleanup/EXECUTION.md`（executor only）

planner only：本 `SPEC.md`。reviewer 不修改实现。

禁止其它所有路径，尤其是前序任务其它实现/文档、两个 Vault、`~/.openclaw/**`、systemd 与 agent workspace。

## 6. 验收标准

- **AC-01 rollback 汇总：** rollback 每个 unlink/rmdir/open/remove-tree 步骤发生 `OSError`、`OpsError` 或其它预期运行异常时均返回有界错误记录，不直接逃出。
- **AC-02 原始错误保留：** 迁移失败且 rollback 不完整时，最终非零 JSON 同时明确原始迁移失败与 `rollback incomplete`；不得包含主机绝对路径或秘密。
- **AC-03 rollback 完整成功：** rollback 无错误时仍恢复发布文件、新建父目录和 staging 为调用前状态，不误报 incomplete。
- **AC-04 fd 生命周期：** `open_rel_dir`、`ensure_target_parents` 及相关 descriptor helper 在每个成功/失败分支关闭中间 fd；调用者拥有的 fd 生命周期清晰且恰好关闭一次。
- **AC-05 压力证据：** 对 symlink 与非目录失败路径各重复至少 200 次，`/proc/self/fd` 数量在允许的微小瞬态范围内稳定，不随次数线性增长。
- **AC-06 安全不退化：** no-follow、no-clobber、TOCTOU 外部零写、并发目标不覆盖、post-publish 验证失败全 rollback 测试继续通过。
- **AC-07 全套回归：** 前序任务全部 Python 测试、operations 测试、harness 及 `git diff --check` 通过。
- **AC-08 范围与外部状态：** 仅允许路径新增变化，index 为空；两个 Vault 和 OpenClaw hash/状态不变。

## 7. 验证命令

工作目录均为 `/home/monottx/repos/knowledge-vault-blueprint`：

1. `python3 -m unittest tests.operations.test_sourcenotes_ops`：exit 0，包含 rollback/fd 压力测试。
2. `python3 tests/skills/test_vault_capture.py`：exit 0。
3. `python3 tests/skills/test_web_extract.py`：exit 0。
4. `python3 tests/skills/test_network_security.py`：exit 0。
5. `python3 -m unittest discover -s tests/operations -p 'test_*.py'`：exit 0。
6. `bash tests/opencode-harness/test_capture_debug.sh`：exit 0，全部 PASS。
7. `python3 -m py_compile scripts/sourcenotes_ops.py`：exit 0。
8. `git diff --check`：exit 0。
9. status/scope/cached 检查及两个 Vault/OpenClaw 只读基线复核：与 §4 一致。

本任务不需重跑真实 OpenClaw E2E，因为不修改 Capture、Query 或活动 Agent 路径；前序 planner E2E 证据保持有效。

## 8. 风险与回滚

- 风险：为避免 fd 泄漏而重复 close，导致调用者 fd 被错误关闭。通过 ownership 约定和成功/失败测试防止。
- 风险：捕获过宽的 `BaseException` 隐藏程序中断。正常 helper 捕获运行异常并记录；外层事务仍保证清理后传播/包装，不把取消或系统退出误报成功。
- 回滚：仅精确撤销本任务在两个实现/测试文件中的新增变化；不得 reset/clean，不触碰前序任务其它改动。

## 9. Blocked 规则

如需改变允许路径、manifest 契约、迁移设计或前序 AC，立即 `BLOCKED`；报告 STEP、原始命令/错误、已产生变化与建议，不得扩大范围。

## 10. 权限

- 允许路径内实现与测试：authorized。
- 两个 Vault、OpenClaw、外部运行配置写入：not authorized。
- Git stage/commit/push 等：not authorized。
