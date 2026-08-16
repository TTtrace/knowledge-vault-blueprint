---
task_id: 2026-08-14-sourcenotes-final-safety-fixes
title: 关闭 SourceNotes 迁移工具最后两个安全缺口
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

提交预检独立复现两个未关闭的 major 问题后，用户选择选项 1：`好的执行 1`，即先修复两个问题、独立审查通过后再准备提交。本任务是前序批准设计内的窄修复，不改变架构、范围或业务契约。

## 2. 目标

1. 为 descriptor-anchored parent fd 建立显式 ownership，使顶层目标路径复用 borrowed `root_fd` 时绝不被调用者关闭，子目录返回的 owned fd 恰好关闭一次。
2. 使 migration 错误摘要对带单/双引号的敏感值及 `|`、`&`、冒号、括号等常见分隔场景正确脱敏，同时保留后续普通诊断上下文。
3. 补充独立可复现测试，并保持迁移事务、回滚、no-follow、no-clobber、TOCTOU 与所有既有功能不退化。

## 3. 非目标

- 不改变 Steward→NotesVaulter 架构、Capture/Query/Maintenance 契约、manifest、CLI、schema、附件阈值或错误 envelope。
- 不修改两个 Vault、OpenClaw、agent workspace、systemd 或运行配置。
- 不迁移数据，不 stage、commit、push、fetch、pull、merge、rebase、reset、clean 或 tag。
- 不顺手重构其它模块。

## 4. 基线

- 蓝图库：`main@badfd519b85c4d80c7875cbf7cbe23afc340c35f`，含前序任务未提交改动；index 为空。
- 正式 Vault：`main@ec1a90eb9d41df77cf74e44d51e703d0379882e7`，clean。
- 测试 Vault：冻结既有状态，只读。
- OpenClaw config SHA-256：`71321f12d664db2c2256663599d71a333321e2050ceebec36c7f56b8abc22f5b`。
- 已复现：`ensure_target_parents(root_fd, "top.md", [])` 返回与 `root_fd` 相同的整数，调用者关闭后 `os.fstat(root_fd)` 得到 `EBADF`；`_sanitize_message('credential="TOPSECRET"|retry=3|ending')` 保留 `TOPSECRET`。

## 5. 允许与禁止路径

允许：

- `scripts/sourcenotes_ops.py`
- `tests/operations/test_sourcenotes_ops.py`
- `tasks/2026-08-14-sourcenotes-final-safety-fixes/EXECUTION.md`（executor）
- `tasks/2026-08-14-sourcenotes-final-safety-fixes/REVIEW.md`（review record）

本 `SPEC.md` 由 planner 所有。禁止修改其它所有路径；前序任务文件只读。

## 6. 验收标准

- **AC-01 显式 ownership：** parent-dir helper 返回显式 `owned` 信息或等价 context abstraction；不得通过 fd 数值比较推断 ownership。borrowed root 永不由调用者关闭，owned fd 在全部成功/失败分支恰好关闭一次。
- **AC-02 顶层成功：** 顶层 manifest 目标正常迁移成功，内容/hash正确，无 staging 残留；同一事务后 root fd 仍有效。
- **AC-03 顶层失败回滚：** 顶层 publish、post-publish verify、hash/evidence 失败均非零并恢复调用前状态，无目标或 staging 残留；root fd 仍有效。
- **AC-04 fd 压力：** 顶层成功/失败与既有 symlink/非目录路径重复至少 200 次后 `/proc/self/fd` 不线性增长，允许瞬态差值不超过 2。
- **AC-05 引号与分隔符脱敏：** 单/双引号敏感值及裸值在空白、`|`、`&`、逗号、分号、冒号、括号/方括号/花括号等边界正确终止；值被替换，敏感键名与后续 `retry=3`/`ending` 等普通上下文保留。
- **AC-06 安全摘要韧性：** POSIX/Windows/UNC/file URL、Authorization/Bearer、Cookie、password/token/api_key/secret/credential、PEM、常见 token 均不泄漏；输出单行有界；异常 `__str__` 再抛时仍返回安全的异常类型摘要。
- **AC-07 安全不退化：** rollback 汇总、KeyboardInterrupt/SystemExit 传播、staging 创建失败、no-follow/no-clobber/TOCTOU、全部前序测试继续通过。
- **AC-08 范围与外部状态：** 仅允许路径有新增变化，index 空；两个 Vault 与 OpenClaw 状态不变。

## 7. 验证

工作目录 `/home/monottx/repos/knowledge-vault-blueprint`：

1. `python3 -m unittest tests.operations.test_sourcenotes_ops`
2. `python3 tests/skills/test_vault_capture.py`
3. `python3 tests/skills/test_web_extract.py`
4. `python3 tests/skills/test_network_security.py`
5. `python3 -m unittest discover -s tests/operations -p 'test_*.py'`
6. `bash tests/opencode-harness/test_capture_debug.sh`
7. `python3 -m py_compile scripts/sourcenotes_agent.py scripts/sourcenotes_ops.py`
8. `git diff --check`，并对未跟踪允许文件执行 no-index whitespace 检查。
9. 独立复现 AC-01、AC-04、AC-05、AC-06。
10. status/scope/cached 与两个 Vault/OpenClaw 只读基线复核。

全部预期 exit 0；本任务不修改 Capture/Query/活动 Agent，无需重跑真实 OpenClaw E2E。

## 8. 风险与回滚

- 风险：ownership API 改动漏掉调用点或 double-close。通过全调用点审计、顶层/子目录/异常与 fd 压力测试防止。
- 风险：脱敏过宽吞掉诊断文本，或过窄泄漏值。通过正反例参数化测试锁定键、值和分隔符语义。
- 回滚：精确撤销本任务在两个代码/测试文件的增量，不 reset/clean，不触碰前序改动。

## 9. Blocked 规则

需要修改允许路径外、改变既有契约、覆盖未知用户改动或环境验证失败时立即 `BLOCKED`，报告 STEP、原始命令/错误、当前变化和建议。

## 10. 权限

- 允许路径内实现与测试：authorized。
- 外部状态写入、Git stage/commit/push：not authorized。
