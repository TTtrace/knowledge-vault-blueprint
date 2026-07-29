# Anki 与 Yanki 工作流

## 1. 单一真源

```text
Obsidian Markdown → Yanki → Anki Desktop → AnkiWeb / 手机
```

- 卡片内容在 Obsidian 修改。
- Anki 负责复习历史、间隔和调度。
- 在 Anki 中直接修改的 Yanki 卡片内容，会在下次同步时被 Markdown 覆盖。

## 2. 目录

```text
learning/
├── english/
│   └── candidates/         # 不监控
└── anki/                   # 唯一监控根目录
    ├── English/
    │   ├── Vocabulary/
    │   ├── Sentences/
    │   └── Listening/
    └── General/
```

Yanki 将父目录映射为 Deck。只有承诺复习的正式卡片才进入 `learning/anki/`。

## 3. 候选到正式卡片

候选：

```yaml
type: language_item
anki_status: candidate
term: take something for granted
source: "[[来源笔记]]"
```

审核问题：

- 未来真的需要主动回忆吗？
- 正面是否只有一个明确问题？
- 答案是否足够短？
- 是否有真实例句和上下文？
- 是否与已有卡片重复？

通过后，根据卡片模板在正式目录创建或移动为 `type: flashcard`。

## 4. Basic 示例

```markdown
---
schema_version: 1
id: 20260725-120000-a1b2
type: flashcard
source: "[[来源笔记#原句]]"
tags:
  - english/vocabulary
---

What does “take something for granted” mean?

---

认为某事理所当然，没有意识到它的价值或不确定性。

Example: We often take clean water for granted.

Source: [[来源笔记#原句]]
```

首次同步后 Yanki 会加入 `noteId`。不要删除、修改或复制它。

## 5. 卡片内容原则

- 一张卡只测试一个主要问题。
- 尽量短；说明和上下文放在背面。
- 语言卡优先真实例句，不只背孤立中文释义。
- 只在确有双向回忆价值时创建 reversed card。
- Cloze 不宜过多；需要经常编辑的 cloze 使用显式编号，避免学习记录错位。
- 卡片正文可以包含 `[[来源]]`，Yanki Obsidian 插件会生成返回 Obsidian 的链接。

## 6. 同步纪律

初期：

1. 只监控 `learning/anki`。
2. 使用手动同步。
3. CLI 使用 `--dry-run` 预览。
4. 禁用自动文件名管理。
5. 同步后检查 Anki 中的正反面、媒体和来源链接。
6. 提交 Yanki 写回的 `noteId`。

稳定后才考虑自动同步。

## 7. 删除和移动

- 删除 Markdown 或移出监控区，会导致对应 Anki Note 在同步时删除。
- 删除后重新创建通常无法保留原学习记录。
- 改变 Deck 前先确认文件移动对 Yanki 的影响。
- 不要从监控目录列表中随意移除目录。
- Git 回退卡片文件时要同时考虑 `noteId`。

## 8. 在复习时发现问题

推荐流程：

1. 点击卡片中的 Obsidian 来源链接。
2. 在 Obsidian 修改正式卡片 Markdown。
3. 运行 Yanki 同步。
4. 返回 Anki 继续复习。

不要把“先在 Anki 改一下，以后再同步回来”作为常规流程；Yanki 不提供反向合并。

## 9. 媒体

- 优先本地稳定媒体。
- 图片、音频和视频引用必须采用 Yanki 支持的嵌入格式。
- 语言音频建议使用兼容性较好的 MP3。
- 若启用远程媒体下载，需要接受同步速度和链接失效风险。

## 10. 两种 Yanki 使用方式

- Obsidian 为中心：使用 `yanki-obsidian` 插件，从命令面板手动同步。
- Linux 自动化为中心：使用 Yanki CLI，但需要 Anki Desktop 与 AnkiConnect 可访问。

同一组卡片应选择一个主要同步入口，避免因不同 namespace 或配置产生重复卡片。

