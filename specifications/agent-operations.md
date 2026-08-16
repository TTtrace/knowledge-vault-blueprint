# Agent 委派与操作规范

> 本规范定义「用户 → Steward（唯一入口）→ NotesVaulter（Capture / Query / Maintenance）」运行拓扑下的委派 envelope、返回 envelope、询问用户时机与内部详情披露边界。正式生产切换属于后续阶段；本规范只约束蓝图、技能与通用工具契约。

## 1. 拓扑与职责

```text
用户 → Steward（唯一入口）
          │  规范委派 / 授权 / 简洁汇总
          ▼
      NotesVaulter（Capture / Query / Maintenance）
```

- **Steward**：用户唯一对话入口。负责把用户意图规范化为委派 envelope、向 NotesVaulter 下发、把结果汇总为简洁中文回复、在需要用户决策时提出问题。Steward 不直接写 Vault，不复制 NotesVaulter 的知识职责。
- **NotesVaulter**：统一承担三类能力。所有操作通过受控 entrypoint `scripts/sourcenotes_agent.py` 执行，不接受任意 shell、任意 Python、任意目标根目录或路径穿越。opencode 只在代码级调试或升级时介入。
- **opencode**：不承担日常运行；仅用于调试 skill/脚本或执行蓝图升级。

## 2. 委派 envelope

Steward 向 NotesVaulter 委派任务时携带结构化 envelope，字段白名单如下；未知字段拒绝处理。

```json
{
  "request_id": "稳定请求 ID（可由 Steward 生成，如 rq-<ts>-<rand>）",
  "task_type": "capture | query | maintenance",
  "user_intent": "用户原始意图的简短、非敏感描述",
  "input": {
    "kind": "web | transcript | document | ocr | idea（capture 必填）",
    "url": "绝对 HTTP(S) URL（web 必填）",
    "text": "正文或想法文本（idea 必填）",
    "annotations": [],
    "query": "检索词（query 必填）",
    "report_scope": "maintenance 可选范围"
  },
  "target_vault_role": "production | test",
  "write_scope": "none | source_annotation | queue",
  "approval_state": "approved | pending",
  "expected_result": "ready | failed | manual | results | report",
  "failure_policy": "preserve | stop | ask_user"
}
```

约束：

- `target_vault_role` 只作声明，Vault 本体仍由宿主配置的 `VAULT_ROOT` 决定；受控 entrypoint 不接受任意 vault/root 参数。
- `write_scope: none` 时任何写路径（`git add`、落盘）都不允许；Query/Maintenance 一律为 `none`。
- `approval_state` 为 `pending` 时只允许只读操作；写操作必须先回 Steward 取得 `approved`。
- 未知命令、未知 `task_type`、envelope 超限（见 §5）一律拒绝并返回错误，不猜测意图。

## 3. 返回 envelope

NotesVaulter 每个委派返回稳定 JSON envelope：

```json
{
  "ok": true,
  "task_type": "capture | query | maintenance",
  "request_id": "回显委派 request_id",
  "result": { "summary": "一行简洁结论" },
  "warnings": [],
  "details": {}
}
```

- Capture 的 `result` 复用 `vault_capture.py` 语义：`result: created|updated|duplicate`、`id`、`ingest_status`、`staged_paths`（仅相对路径）、`job_created`、`paths_final`、附件软告警放入 `warnings`。
- Query 的 `result.results` 每条含 `id`（可解析时）、`path`（Vault 相对路径）与有界摘录 `excerpt`；`ok: false` 且证据不足时在 `summary` 中明确说明缺口。
- Maintenance 的 `result` 含 Git 状态、failed/manual 计数或列表、缺失引用、附件预算与 2 GiB 闸门，全部为只读观测。
- 错误一律不包含绝对 Vault 路径、主机路径、凭据、原始 DNS 载荷或堆栈；内部详情放 `details`，按需展开。

## 4. 询问用户的时机（最少必要确认）

以下场景必须回 Steward 并由 Steward 询问用户，NotesVaulter 不得自行决定：

1. 任何写操作前（capture 落盘/暂存属于已批准契约，不算额外询问；除此之外的写操作必须询问）。
2. 跨 Source 迁移（audit 后 manifest `migrate`/`repair_then_migrate`/`exclude` 处置）——工具只报告与执行 manifest 精确批准内容，不自行猜测价值。
3. `manual` 任务的显式重试（用户解决阻塞并明确要求后才重试）。
4. Git 冲突、未暂存人工修改或目录缺失等停止性冲突的处置。
5. Vault 附件总量达到 2 GiB 决策闸门——只报告，不自动迁移/删除，是否引入 Git LFS/git-annex/对象存储由用户决定。
6. 任何写入正式 Vault 或修改活动 OpenClaw 配置的操作（本阶段一律 not authorized）。

## 5. 输出与输入边界（渐进披露）

- 用户界面默认只显示结果、异常与必要决策；命令输出、中间产物、队列与底层日志按需展开，不主动暴露。
- 输入边界：capture stdin JSON 上限 1 MiB；query 长度上限 500 字符；query 结果数上限 20；单条摘录上限 300 字符；JSON 输出总大小上限 256 KiB（超出则截断并标记 `truncated: true`）。
- 只读边界：Query/Maintenance 不得修改任何文件或 Git index；show/related 不改变工作树。
- 附件：同一 Source 事务内内容 SHA-256 相同只落一份；单文件 >5 MiB、单 Source **物理落盘唯一附件字节** >30 MiB 产生稳定 `warnings`（重复 token/正文位置不重复计入，不降低 `ready`、不丢附件）；20 MiB 单下载图片、100 MiB 单篇**下载字节**仍是安全硬限制（重复下载仍计入 100 MiB）；2 GiB 只报告。

## 6. 错误与失败策略

- 命令退出码：`0` 完成（业务结果以 JSON 为准）、`2` 输入/配置无效、`3` 冲突、`4` 文件系统/Git 失败。
- `failure_policy: preserve`：失败保留已落盘内容与 stub，不丢输入。
- `failure_policy: stop`：遇到停止性冲突（未暂存人工修改、目标已存在、Git 失败）立即停止并上报。
- `failure_policy: ask_user`：需要用户决策（manual 重试、迁移处置、2 GiB 闸门）时停止并询问。
- 任何秘密（token/Cookie/password/private key）不得进入 Vault、队列、ledger、incident bundle 或面向用户的报告；incident 工具命中秘密时失败关闭。

## 7. 外部记录边界

- incident bundle、operation ledger 与 health 状态文件必须位于正式 Vault 与公开蓝图库之外；目录 0700、文件 0600；ledger 不含正文，只含 `blueprint_commit`/`vault_head`/`source_id`/`run_id`/时间戳/处置状态等最小字段。
- 蓝图库只保存格式、工具与 runbook，不保存真实正文、逐篇标题/URL、trajectory、secret 或完整主机配置。

## 8. 相关规范

- 单入口拓扑与附件预算原则：[D-023](../DECISIONS.md#d-023单入口运行拓扑steward-唯一入口--notesvaulter-三能力--附件预算)
- 捕获契约：[capture-workflow.md](capture-workflow.md)、`skills/vault-capture/references/runtime-contract.md`
- 只读问答与维护：`skills/vault-query/SKILL.md`、`skills/vault-maintenance/SKILL.md`
- Git 与附件：[git-workflow.md](git-workflow.md)；升级与外部账本：[upgrade-workflow.md](upgrade-workflow.md)
- 发布与加载：[openclaw-skill-workflow.md](openclaw-skill-workflow.md)
