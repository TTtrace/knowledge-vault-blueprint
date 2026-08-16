---
name: vault-query
description: 只读检索与问答知识库笔记：search / show / related 三类有界查询，答案必须引用 note ID 或 Vault 相对路径；证据不足时明确说明缺口。只接受 Steward 的 query 委派或用户明确的 Vault 问答，不执行任何写入。
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

# Vault 只读查询

本 skill 严格只读：只消费既有 `source`/`annotation`/`analysis`/`idea`/`essay`/`journal` 等 Markdown 对象，**不写入、不修改任何文件，不触碰 Git index**。Vault 由宿主配置的 `VAULT_ROOT` 决定；只通过受控入口 `sourcenotes_agent.py query` 执行，不接受任意 shell/Python/任意目标根目录。委派 envelope 与输出边界见 [specifications/agent-operations.md](../../specifications/agent-operations.md)。

## 触发

- 收到 Steward 的 `task_type: query` 委派 envelope，或用户明确的 Vault 知识问答/检索请求时触发；普通闲聊不触发。

## 查询命令

所有命令使用带引号的回退解释器 `"${VAULT_CAPTURE_PYTHON:-python3}"`（未设置回退 `python3`；只选择已有可执行文件，不 eval/拼接 shell、不装依赖、不放进 `requires.env`）：

1. 关键词检索：

```bash
"${VAULT_CAPTURE_PYTHON:-python3}" {baseDir}/../../scripts/sourcenotes_agent.py query search <检索词>
```

2. 查看单条笔记（只读，返回有界摘录）：

```bash
"${VAULT_CAPTURE_PYTHON:-python3}" {baseDir}/../../scripts/sourcenotes_agent.py query show <Vault相对路径>
```

3. 查找指向某条笔记的关联笔记（接受 note ID 或相对路径）：

```bash
"${VAULT_CAPTURE_PYTHON:-python3}" {baseDir}/../../scripts/sourcenotes_agent.py query related <note ID 或相对路径>
```

## 回答规则

- 每条结论必须引用 note ID（可解析时）与 Vault 相对路径，便于用户跳回来源；不要只引用没有定位意义的标题。
- 证据不足或检索无结果时，**明确说明缺口**（例如“Vault 中没有提到 X 的笔记”），不编造来源、不臆测。
- 摘录有界：按命令 JSON 中的 `excerpt` 引用，不要复述整篇正文；结果过多时以 `count`/`truncated` 为准如实说明。
- 面向用户使用中文说明，但不要翻译命令、字段名或状态值。

## 禁止

- 不执行任何写路径：不落盘、不 `git add`、不修改文件/目录。
- 不接受绝对路径、`..` 穿越、symlink 逃逸或非 Markdown 读取；命令会拒绝，同样不要尝试绕过。
- 不暴露 `VAULT_ROOT`、主机绝对路径、底层日志或工具原始错误。
- 不把查询 JSON 之外的信息写入 Vault 或任何外部记录。
