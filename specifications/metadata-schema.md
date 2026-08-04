# 元信息规范

> `schema_version: 1`

## 1. 设计规则

- 属性名统一使用 `lower_snake_case`，Yanki 自有字段 `noteId` 除外。
- 枚举值使用稳定英文小写。
- 日期使用 `YYYY-MM-DD`，时间使用带时区 ISO 8601。
- 单值保持单值，列表始终使用 YAML 列表，不在逗号字符串与列表之间混用。
- 内部链接在属性中必须加引号，例如 `source: "[[某来源]]"`。
- 不手工维护 `updated`；最近修改时间由 Obsidian `file.mtime` 和 Git 提供。
- 空字段可以保留在模板中，但成熟笔记应删除无意义的空属性。

## 2. 通用字段

| 字段 | 类型 | 必需 | 说明 |
|---|---|---:|---|
| `schema_version` | number | 是 | 当前为 `1` |
| `id` | text | 是 | Vault 内永久 ID |
| `type` | text | 是 | 文件身份 |
| `title` | text | 建议 | 人类可读标题 |
| `created` | datetime | 是 | 创建时间 |
| `aliases` | list | 否 | Obsidian 别名 |
| `topics` | list | 否 | 主题链接或稳定主题名 |
| `tags` | tags | 否 | 轻量横向标签 |

推荐 ID：

```text
YYYYMMDD-HHMMSS-xxxx
```

其中 `xxxx` 为随机小写字母或数字。例如：

```text
20260725-143210-k4p9
```

## 3. `type` 允许值

| 值 | 使用位置 |
|---|---|
| `source` | `sources/` |
| `annotation` | `notes/annotations/` |
| `analysis` | `notes/analyses/` |
| `idea` | `notes/ideas/` |
| `essay` | `notes/essays/` |
| `journal` | `journal/` |
| `language_item` | `learning/english/candidates/` |
| `flashcard` | `learning/anki/` |
| `map` | `maps/` |

## 4. Source 字段

| 字段 | 类型 | 必需 | 允许值/说明 |
|---|---|---:|---|
| `medium` | text | 是 | `article`, `transcript`, `paper`, `book`, `chapter`, `report`, `video`, `audio`, `ai_conversation`, `document` |
| `url` | text | 视情况 | 用户输入的原始 URL |
| `canonical_url` | text | 视情况 | 去跟踪参数后的去重 URL |
| `author` | list | 否 | 网页等简易作者列表 |
| `published` | date | 否 | 发布时间 |
| `captured` | datetime | 是 | 捕获时间 |
| `retrieved_at` | datetime | 否 | 正文获取成功时间 |
| `language` | text | 否 | `zh`, `en` 等 |
| `ingest_status` | text | 是 | `pending`, `processing`, `ready`, `failed`, `manual` |
| `read_status` | text | 是 | `unread`, `reading`, `read`, `skipped`, `reference` |
| `engagement` | text | 是 | `captured`, `highlighted`, `annotated`, `analyzed`, `synthesized` |
| `priority` | number | 否 | `1` 最高，建议只用 `1`–`3` |
| `estimated_minutes` | number | 否 | 预计阅读时间 |
| `why_saved` | text | 强烈建议 | 保存此材料的理由 |
| `capture_method` | text | 否 | `openclaw`, `web_clipper`, `manual`, `zotero` |
| `content_hash` | text | 自动化 | 用于检测正文变化 |
| `ingest_error` | text | 失败时 | 简短错误摘要 |
| `retry_after` | datetime | 否 | 下次重试时间 |
| `verification` | text | AI 内容建议 | `unverified`, `partially_verified`, `verified` |

完整网页来源：

```yaml
---
schema_version: 1
id: 20260725-143210-k4p9
type: source
medium: article
title: 文章标题
url: https://example.com/article
canonical_url: https://example.com/article
author:
  - 作者
published: 2026-07-20
captured: 2026-07-25T14:32:10+08:00
retrieved_at: 2026-07-25T14:32:18+08:00
language: zh
ingest_status: ready
read_status: unread
engagement: captured
priority: 2
estimated_minutes: 15
why_saved: 想理解作者如何区分记忆和理解
capture_method: openclaw
topics:
  - "[[知识管理]]"
tags: []
---
```

## 5. 来源依附型字段

适用于 Annotation 和 Analysis：

| 字段 | 类型 | 必需 | 说明 |
|---|---|---:|---|
| `source` | link | 是 | Vault 内 Source 链接 |
| `source_id` | text | 建议 | 来源永久 ID，便于脚本校验 |
| `source_title` | text | 是 | 即使内部链接失效也可识别 |
| `source_url` | text | 视情况 | 网页原始链接 |
| `zotero_uri` | text | 文献时建议 | Zotero 条目或 PDF 链接 |
| `locator` | text | 否 | 单一定位时使用的页码、章节、时间戳或段落 |

Annotation 可增加：

| 字段 | 类型 | 说明 |
|---|---|---|
| `annotation_kind` | text | `highlights`, `comments`, `mixed` |
| `engagement` | text | 通常为 `highlighted` 或 `annotated` |

捕获工作流按 Source 聚合 Annotation 时，一个文件可包含多个引用单元。此时省略顶层 `locator`，在每个引用单元正文中分别保存捕获时间与 locator；`annotation_kind` 和 `engagement` 表达整个文件的聚合状态。旧的单引文 Annotation 继续使用顶层 `locator`，无需迁移或提升 `schema_version`。

Analysis 可增加：

| 字段 | 类型 | 说明 |
|---|---|---|
| `analysis_status` | text | `draft`, `active`, `complete`, `archived` |
| `engagement` | text | 通常为 `analyzed` 或 `synthesized` |

## 6. Idea 与 Essay 字段

| 字段 | 类型 | 适用 | 说明 |
|---|---|---|---|
| `provenance` | text | idea/essay | `personal`, `mixed` |
| `maturity` | text | idea | `seed`, `developing`, `evergreen`, `archived` |
| `derived_from` | list of links | idea/essay | 生发来源 |
| `related` | list of links | idea/essay | 对等关系 |
| `publication_status` | text | essay | `draft`, `revising`, `final`, `published`, `archived` |

## 7. PDF 文献字段

在通用 Source 字段外增加：

| 字段 | 类型 | 说明 |
|---|---|---|
| `authors` | list | 规范作者列表 |
| `year` | number | 出版年份 |
| `journal` | text | 期刊或出版物 |
| `volume` | text | 卷 |
| `issue` | text | 期 |
| `pages` | text | 页码范围 |
| `doi` | text | DOI 原值 |
| `citation_key` | text | 稳定引用键，可选 |
| `zotero_uri` | text | Zotero 条目 URI |
| `pdf_status` | text | `zotero`, `vault`, `external`, `missing` |
| `abstract` | text | 单行简短摘要；长摘要放正文 |

## 8. Journal 字段

| 字段 | 类型 | 必需 | 说明 |
|---|---|---:|---|
| `date` | date | 是 | 日记日期 |
| `journal_kind` | text | 是 | `daily`, `log` |
| `ai_access` | checkbox | 是 | 当前默认 `true` |

情绪、睡眠、运动等字段应等到确有稳定记录习惯后再增加，不在首版强制规定。

## 9. Language item 与 Flashcard

语言候选：

| 字段 | 类型 | 说明 |
|---|---|---|
| `term` | text | 单词、短语或句型 |
| `language` | text | 通常 `en` |
| `anki_status` | text | `candidate`, `ready`, `exported`, `suspended` |
| `source` | link | 出现该表达的笔记 |
| `source_locator` | text | 原句位置 |

正式 Yanki 卡片：

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | text | `flashcard` |
| `tags` | tags | Yanki 会同步 |
| `noteId` | number/text | Yanki 自动写入，禁止手改 |
| `source` | link | 可保留；Yanki 会忽略但保存 |

`id` 与 `noteId` 不可互相替代。

## 10. 字段升级

修改字段含义或枚举时：

1. 提升 `schema_version`。
2. 在 `DECISIONS.md` 新增决策。
3. 提供批量迁移和回滚办法。
4. 在备份分支或副本上验证。
5. 不静默删除未知属性。
