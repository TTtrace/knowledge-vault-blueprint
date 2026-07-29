# 阅读、批注与细读工作流

## 1. 稍后读

稍后读不是文件夹，而是满足以下条件的 Source 视图：

```text
type == source
read_status == unread
ingest_status == ready
```

排序建议：

1. `priority` 升序。
2. `estimated_minutes` 升序或按可用时间过滤。
3. `captured` 升序，防止旧项目永久沉底。

每个待读来源都应尽量填写 `why_saved`。如果已经无法说明为何值得读，应考虑 `skipped`。

只需要未来检索、并不承诺完整阅读的资料使用 `read_status: reference`，不会进入稍后读面板。

## 2. 快速阅读

适用于只需保存少量摘录和局部评论的材料：

1. Source 的 `read_status` 改为 `reading`。
2. 从 Annotation 模板创建独立文件。
3. 引文必须带内部来源链接和外部原文链接。
4. 完成后将 Source 的 `engagement` 改为 `annotated`。
5. `read_status` 改为 `read`。

## 3. 系统细读

推荐双栏：

- 左侧：原始 Source Markdown、Zotero PDF 或 transcript。
- 右侧：Analysis 文件。

细读前先写“阅读问题”，避免逐段摘要而没有目的。

推荐章节：

```markdown
# 标题

## 阅读问题
## 一句话结论
## 作者试图解决什么
## 关键概念
## 论证结构
## 证据与方法
## 我认同的部分
## 局限、反例与待验证项
## 与其他笔记的关系
## 可提炼的原子观点
## 后续行动
```

完成后：

- Source `engagement: analyzed`。
- Analysis `analysis_status: complete`。
- 将真正可独立复用的判断提取到 `notes/ideas/`。

## 4. 引文与评论

统一结构：

```markdown
> 引文。

来源：[[Source#小节]] · [原文](https://example.com)

评论：

这段话的隐含前提是……
```

不要只保存高亮而不说明为什么重要。最低限度可以使用：

- `支持`：支持哪一个判断。
- `反对`：反对什么。
- `疑问`：具体缺失什么证据。
- `生发`：由此得到什么新判断。
- `行动`：下一步要验证什么。

## 5. 原子观点

提取 Idea 的判断标准：

- 离开原文后仍能理解。
- 只表达一个主要判断。
- 标题本身尽量是完整判断。
- 正文包含理由、适用边界或反例。
- 使用 `derived_from` 保留出处。

Idea 不等于摘录。只有自己的可辩护判断才进入 Idea。

## 6. 日记

日记与知识库同库，允许 AI 访问。日记负责忠实记录当日，不要求原子化。

当日记中出现可复用洞见时：

1. 新建 Idea。
2. `derived_from` 链接到该日日记。
3. 在日记原段落旁加入新 Idea 的反向链接。

日记中的任务不自动进入知识笔记，除非形成长期项目或稳定结论。

## 7. AI 对话

分层：

| 内容 | 位置 |
|---|---|
| 完整对话 | `sources/conversations/` |
| 选段和局部评论 | `notes/annotations/` |
| 系统分析 | `notes/analyses/` |
| 稳定个人洞见 | `notes/ideas/` |

AI 陈述默认 `verification: unverified`。引用外部事实时应补充真实来源。

## 8. 每周维护

每周只处理少量关键问题：

- `failed` 抓取是否值得重试？
- 保存超过一定时间且无 `why_saved` 的来源是否放弃？
- `reading` 太久的项目是否继续？
- 已完成 Analysis 是否提炼了 Idea？
- `seed` Idea 是否与现有观点重复？
- Anki candidates 是否真正值得长期复习？
