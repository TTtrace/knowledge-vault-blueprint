# PDF 与 Zotero 工作流

## 1. 职责边界

```text
Zotero：文献条目、PDF、DOI、作者、期刊、原始划线、引文
Obsidian：来源索引、导出批注、系统细读、跨文献关系、个人观点
```

PDF 文件本身是 Source，不是 Analysis。对 PDF 的系统性思考才是 Analysis。

## 2. 保存文献

推荐入口优先级：

1. Zotero Connector 从出版社、数据库或预印本页面保存。
2. DOI、ISBN、PMID 等标识符添加。
3. 拖入 PDF 后检索元信息。
4. 最后才手工录入。

保存后检查：

- 标题和作者。
- 年份、期刊、卷期页码。
- DOI。
- PDF 是否完整。
- 是否已有重复条目。

## 3. Obsidian 来源记录

为值得进入知识库的文献创建：

```text
sources/documents/<id>--<标题>.md
```

最小元信息：

```yaml
---
schema_version: 1
id: 20260725-110000-r4p2
type: source
medium: paper
title: 论文标题
authors:
  - Author One
  - Author Two
year: 2026
journal: Journal Name
doi: 10.xxxx/example
citation_key:
zotero_uri: zotero://select/library/items/...
pdf_status: zotero
captured: 2026-07-25T11:00:00+08:00
ingest_status: ready
read_status: unread
engagement: captured
why_saved: 与正在研究的问题直接相关
---
```

正文可以保存摘要、目录和 Zotero 打开链接，但不复制完整 PDF。

## 4. 划线与批注

原始划线可以留在 Zotero。进入 Obsidian 时，统一导出到：

```text
notes/annotations/<id>--<标题>-批注.md
```

每项至少包括：

- 引文。
- 页码。
- 返回 Zotero PDF 的链接。
- 自己的评论。
- 颜色语义如果确实长期稳定。

不建议一开始建立复杂颜色体系。首版最多使用：

| 颜色语义 | 用途 |
|---|---|
| 重点 | 作者核心主张 |
| 证据 | 数据、案例和方法 |
| 疑问 | 不清楚、可疑或待核实 |
| 生发 | 可形成个人观点 |

## 5. 系统细读

细读文件位于：

```text
notes/analyses/<id>--<标题>-细读.md
```

重点不在逐页摘录，而在重建：

- 研究问题。
- 核心结论。
- 论证链。
- 方法和证据。
- 适用边界。
- 与其他文献的异同。
- 自己能够继续推进的观点。

## 6. AI 全文访问

若 AI 需要全文：

- 临时任务：直接向 AI 提供 Zotero 中的 PDF。
- 长期检索：按需提取文本到 `sources/documents/text/`。
- 扫描 PDF：OCR 后标记质量。

建议增加：

```yaml
text_extraction: none       # none / extracted / ocr
text_quality: unreviewed    # unreviewed / reviewed
```

提取文本不是权威排版副本；引用页码仍以 PDF 为准。

## 7. Git 与同步

- PDF 默认由 Zotero 管理，不复制进 Git Vault。
- Obsidian 只提交 Markdown 来源记录、批注、分析和观点。
- Zotero 数据库及附件需要独立备份或同步。
- 若确需 Vault 内 PDF，放入明确附件目录，并考虑 Git LFS；不要假定普通 Git 适合大型二进制文件。

## 8. 不使用 Zotero 的情形

以下情况 Obsidian 单独即可：

- PDF 数量很少。
- 几乎不需要 DOI、引文和参考文献。
- 文件主要是说明书、内部报告或临时材料。

只要学术论文阅读成为常态，就采用 Zotero + Obsidian，避免后期重新整理书目信息。

