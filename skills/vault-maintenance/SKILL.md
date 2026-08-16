---
name: vault-maintenance
description: 只读报告 Vault 健康与维护指标：Git 状态、failed/manual Source、缺失 Source 引用、附件预算与 2 GiB 决策闸门。只报告不修复；任何写操作必须回 Steward 申请批准。
user-invocable: true
disable-model-invocation: false
metadata:
  openclaw:
    os:
      - linux
    requires:
      bins:
        - python3
        - git
      env:
        - VAULT_ROOT
---

# Vault 维护报告

本 skill 严格只读：输出健康与维护指标，**不修复、不 `git add`、不落盘、不清理**。任何写操作（修复冲突、重试 manual、迁移、删除附件等）必须回 Steward，由 Steward 向用户申请批准后再执行。Vault 由宿主配置的 `VAULT_ROOT` 决定；只通过受控入口 `sourcenotes_agent.py maintenance` 执行。委派 envelope 与询问时机见 [specifications/agent-operations.md](../../specifications/agent-operations.md)。

## 触发

- 收到 Steward 的 `task_type: maintenance` 委派，或用户询问 Vault 健康/维护状态时触发。

## 报告命令

使用带引号的回退解释器 `"${VAULT_CAPTURE_PYTHON:-python3}"`（未设置回退 `python3`；只选择已有可执行文件，不 eval/拼接 shell、不装依赖、不放进 `requires.env`）：

```bash
"${VAULT_CAPTURE_PYTHON:-python3}" {baseDir}/../../scripts/sourcenotes_agent.py maintenance report
```

## 报告内容与解读

- **Git 状态**：`branch`/`head`/`upstream`/`ahead`/`behind`、`dirty_count` 与 `staged_count`（含有界路径列表）。工作树脏或存在未暂存人工修改时，**停止**并提示用户人工处理，不自动覆盖。
- **Source 状态**：`total`/`failed_count`/`manual_count` 及有界列表（ID + 相对路径）；failed 可经捕获流程重试，manual 需用户解决阻塞并明确要求。
- **缺失 Source 引用**：Annotation/Analysis 引用了不存在 Source ID 的有界列表；只报告，不自动修复。
- **附件预算**：`count`/`total_bytes`、>5 MiB 文件数、>30 MiB Source 目录数、`gate_2GiB`。达到 2 GiB 是决策闸门：**只报告**，是否引入 Git LFS/git-annex/对象存储由用户决定。
- 面向用户使用中文说明，但不要翻译命令、字段名或状态值；汇总要简洁，先给结论再按需展开。

## 禁止

- 不执行任何修复/写入/暂存/清理操作；即使用户要求，也要回 Steward 走批准。
- 不暴露 `VAULT_ROOT`、主机绝对路径、底层日志或工具原始错误。
- 不在 Vault 或外部记录中写入报告之外的任何内容。
