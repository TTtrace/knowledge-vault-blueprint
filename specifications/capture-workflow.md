# 捕获与抓取工作流

## 1. 目标

无论网页、音视频、PDF 还是纯文本，捕获操作必须满足：

- 用户输入先可靠落盘。
- 抓取失败不导致链接丢失。
- 同一 URL 不产生无法识别的重复文件。
- 原文与个人评论分离。
- 每次自动化变更可由 Git 审计。
- 来源与用户批注可在同一次输入中到达；批注须在捕获阶段落入该来源唯一的 Annotation 文件。

## 2. 捕获事务

```mermaid
flowchart TD
    A["收到 URL / 文本"] --> B["规范化并检查重复"]
    B --> C["生成 ID 和最终文件路径"]
    C --> D["写入 Source 占位文件"]
    D --> E["Git 提交：capture stub"]
    E --> F["创建后台任务"]
    F --> G["抓取 / 转写 / OCR"]
    G -->|成功| H["写入正文与元信息"]
    G -->|失败| I["记录错误并等待重试"]
    H --> J["Git 提交：ingest ready"]
    I --> K["Git 提交：ingest failed"]
```

占位文件必须在网络请求前写入。

## 3. 推荐输入协议

最短输入：

```text
收：https://example.com
```

推荐输入：

```text
收：https://example.com/article
原因：作者可能给出了反对“知识等于信息”的好论证
主题：知识管理, 学习
优先级：2
```

音视频：

```text
转写：https://video.example/123
原因：需要保留 15 分钟以后关于 spaced repetition 的部分
语言：en
```

纯个人想法不进入 Source：

```text
想法：稍后读系统真正管理的不是文章，而是未来注意力的承诺
主题：知识管理
```

带批注的捕获：

```text
收：https://example.com/article
原因：作者可能给出了反对“知识等于信息”的好论证
主题：知识管理, 学习
优先级：2
批注：
> 稍后读列表管理的不是文章，而是一个人未来愿意投入的注意力。
评论：这解释了为什么 why_saved 比自动摘要更重要。
---
> 收藏只降低了未来再次找到信息的成本。
评论：但这可能窄化了“理解”。
```

每条批注单元以 `---` 分隔；以 `>` 开头的行是划线原文，`评论：` 后是用户评论。阅读器导出、聊天转发和截图 OCR 等输入可由 Agent 先归一化为“引文 + 评论 + 可选定位”列表，用户不必严格遵守示例格式。完整规则见 §11。

## 4. URL 去重

自动化应：

1. 移除常见跟踪参数。
2. 处理结尾斜杠和默认端口。
3. 尽可能读取 canonical URL。
4. 在已有 Source 的 `canonical_url` 中查重。

发现重复时不静默创建新 Source。可选择：

- 返回现有笔记。
- 保留原 `why_saved`，将新的保存理由与时间追加到正文的“捕获历史”。
- 若网页内容确实是不同版本，显式创建 revision。
- 新批注合并到该 Source 已有的 Annotation 文件，而不是新建 Source 或第二个 Annotation 汇总文件。

## 5. 状态

| 状态 | 含义 |
|---|---|
| `pending` | 已保存输入，等待工作进程 |
| `processing` | 正在抓取、转写或 OCR |
| `ready` | 可供阅读 |
| `failed` | 自动处理失败，可重试 |
| `manual` | 需要登录、验证码、版权限制或人工操作 |

`ingest_status` 与 `read_status` 独立。一篇 `ready` 的文章可以仍是 `unread`。

带批注捕获时，Source 的 `engagement` 在捕获阶段即提升为 `highlighted` 或 `annotated`；抓取与阅读状态仍独立演进。

## 6. 正文写入规则

- `ready` 后的 Source 正文原则上不可手工混入批注。
- 再抓取必须通过显式 refresh。
- refresh 前计算 `content_hash`。
- 内容变化时生成独立 Git 提交，不覆盖无法追踪的历史。
- 页面噪声、导航、推荐列表和评论区应在转换时清理。
- 保留标题、作者、发布时间、URL 和抓取时间。
- Annotation 中保存的引文是用户标注时看到的版本，refresh Source 正文时不得回写或覆盖这些引文。

## 7. Transcript

Transcript 应：

- 标记语言和生成方式。
- 尽可能按说话者和时间戳分段。
- 用可链接标题保存重要时间点。
- 标记是否经过人工校对。

推荐：

```markdown
## 00:13:42 记忆与理解

**Speaker A：** ...
```

增加：

```yaml
transcript_quality: raw_ai   # raw_ai / reviewed / verified
duration_seconds:
```

## 8. AI 对话

完整 AI 对话属于：

```yaml
type: source
medium: ai_conversation
verification: unverified
```

应保存服务、模型、日期和必要的上下文，但不得将密码、令牌和私密密钥写入 Vault。对话中的局部评论进入 Annotation，稳定洞见另建 Idea。

## 9. 失败与重试

- 指数退避或固定时间窗口均可，首版建议限制自动重试次数。
- 登录墙、验证码和付费墙直接设为 `manual`。
- `ingest_error` 只保存简短、无敏感信息的错误。
- 失败任务必须出现在维护面板。
- 用户可以将无价值来源标记为 `read_status: skipped`，而不是无限重试。
- 抓取失败不影响已落盘批注；Annotation 自带引文、评论和 `source_url`，仍可独立阅读与定位。

## 10. Git 提交建议

```text
capture(source): add queued article <id>
capture(source+annotations): add <id> with N entries
ingest(source): fetch article <id>
ingest(source): mark <id> failed
transcribe(source): add transcript <id>
```

## 11. 伴随批注的捕获

### 11.1 解析与聚合

- 链接与批注可以出现在同一条输入中；每条批注至少包含引文或评论之一。
- 同一 Source 最多对应一个由捕获工作流维护的 Annotation 文件；后续输入继续追加到该文件。
- 对引文和评论执行 Unicode NFKC 归一化并折叠空白。相同 Source 下，归一化后完全相同的引文视为同一引用单元。
- 同一引文和同一评论不重复写入；同一引文出现新评论时追加评论并保留旧评论；不同引文追加为新引用单元。
- 聚合后的 `annotation_kind`：全部为纯引文时取 `highlights`，全部为纯评论时取 `comments`，其他组合取 `mixed`。
- Annotation 或 Source 中只要存在评论，`engagement` 取 `annotated`；只有引文时取 `highlighted`。

### 11.2 原子落盘与 Git

1. 规范化输入并完成 Source 去重。
2. 原子写入新的 Source 占位或更新已有 Source 的捕获历史。
3. 原子创建或更新该 Source 唯一的 Annotation 文件。
4. Source 与 Annotation 的本次变更生成一次 `capture(source+annotations)` 提交；无批注时使用 `capture(source)`。
5. 正文抓取在后台独立执行，成功或失败状态生成第二次提交。

不得先提交 Source、再声称 Source 与 Annotation 属于同一次提交。若 Git 提交失败，保留已经落盘的文件并停止启动后台抓取，等待显式修复。

### 11.3 Annotation 结构

- frontmatter 保留 `source`、`source_id`、`source_title`、`source_url`、`annotation_kind`、`engagement` 和首次创建时间 `created`。
- 汇总文件不使用单个顶层 `locator` 代表全部批注；定位信息写入每个引用单元。
- 每个引用单元记录本次捕获时间、可选 locator、引文、Source WikiLink、外部 URL 和零条或多条评论。
- 后续追加不得修改 `created`，也不新增通用 `updated`；具体新增内容在正文旁记录捕获时间，文件整体修改历史由 Git 和 `file.mtime` 提供。

推荐正文：

```markdown
## 2026-08-04T09:30:00+08:00 · 稍后读的真正约束

> 稍后读列表管理的不是文章，而是一个人未来愿意投入的注意力。

来源：[[来源#稍后读的真正约束]] · [原文](https://example.com/article)

评论：

- 2026-08-04T09:30:00+08:00 — 这解释了为什么 why_saved 比自动摘要更重要。
```

### 11.4 重复捕获

- 命中已有 Source 时不创建新 Source；新保存理由追加到“捕获历史”。
- 若该 Source 尚无 Annotation，则首次创建；若已有，则按 §11.1 合并。
- 重复输入没有产生任何新理由、引文或评论时返回现有记录，不生成空提交。
- Annotation 文件使用首次创建时生成的永久 ID 和稳定文件名，后续捕获不重命名。

### 11.5 失败边界

- Source 抓取失败或永久处于 `manual` 时，Annotation 仍保持有效。
- 后来抓取的正文与既有引文不一致时，以 Annotation 内保存的引文为准。
- 纯评论无引文时允许落盘，但必须保留捕获时间和 Source 链接；可在之后补充定位。
- 目标 Source 或 Annotation 存在未提交人工修改时，自动化必须停止合并并报告冲突，不得覆盖。
