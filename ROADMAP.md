# 演进路线

本路线强调先验证习惯，再自动化。每一阶段都应独立可用。

## 阶段 0：蓝图确认

目标：确认信息架构不会阻碍真实使用。

- [x] 确定单 Vault。
- [x] 确定 Obsidian 为主要编辑器。
- [x] 确定抓取与阅读生命周期分开。
- [x] 确定 Zotero 管 PDF，Obsidian 管思考。
- [x] 确定 Yanki 单向同步。
- [ ] 用三篇真实文章、一篇 PDF、一次 AI 对话和三张卡片验证模板。

退出条件：不需要为真实样本新增顶层目录或重新定义核心关系。

## 阶段 1：最小可用 Vault

目标：不依赖自定义脚本也能完成完整闭环。

- 启用 Properties、Templates、Daily notes、Bases、Backlinks。
- 配置模板目录与 Daily notes。
- 使用 Web Clipper 保存网页。
- 手工创建 Annotation、Analysis 和 Idea。
- 安装 Zotero，完成一篇 PDF 的划线、批注导出和细读。
- 安装 Yanki 或 Yanki Obsidian Plugin，手动同步三张卡片。
- 初始化 Git，并完成首次异机备份。

退出条件：可以从来源追到批注、分析、观点和 Anki 卡片。

## 阶段 2：可靠捕获

目标：手机输入永不因抓取失败而丢失。

- 建立仓库级 `skills/` 和 `tests/skills/` 结构。
- 创建首个 `vault-capture` skill，定义描述、显式命令、依赖和失败边界。
- 由功能分支提交开发快照，以不可变 RC 标签传到 Linux staging 验证。
- 候选通过后，将同一 commit 晋级 `main` 和正式标签；production 只加载正式标签。
- staging 与 production 使用独立检出目录、Vault 和 OpenClaw profile。
- 使用 `agents.list[].skills` 为 Vault agent 配置完整 allowlist。
- 实现 URL 规范化和 `canonical_url` 去重。
- 立即创建 Source 占位文件。
- 建立后台抓取队列、重试和失败记录。
- 普通网页转 Markdown（仓库自有的确定性 `ingest-web`：Trafilatura + WeChat 适配 + Playwright 只读回退）。
- 音视频生成带时间戳 transcript。
- 每次自动化变更只暂存相关路径，由用户按批次生成可读 Git 提交。
- 在临时 Vault 完成 `skills list/info/check`、RC 冒烟测试、稳定版晋级和回滚演练。

退出条件：失败任务能在 `maintenance.base` 中被发现和重试；Vault agent 只加载预期 skill，且上一稳定标签可以恢复。

## 阶段 3：阅读工作台

目标：降低引用和批注摩擦。

- 固定左侧原文、右侧 Annotation/Analysis 的 Obsidian 工作区。
- 实现“选中内容 → 引文 + 来源链接 + 定位”的快捷命令。
- transcript 引用自动附带时间戳。
- Zotero 批注导出为统一 Markdown 格式。
- 从 Annotation/Analysis 一键创建 Idea。

退出条件：一次引用操作无需手工复制超过一个链接。

## 阶段 4：学习与维护自动化

目标：让知识库持续保持健康。

- 建立语言卡片候选审核面板。
- Yanki 同步前执行校验和预览。
- 增加重复 URL、缺失来源、无 ID、孤立观点检查。
- 定期生成知识库健康报告。
- 对已分析但未提炼 idea 的材料给出提示。
- 对长期待读项目执行保留、推迟或放弃决策。
- （未来）从 `journal` 提取结构化生活指标（时间管理、运动、睡眠）并汇总到个人生活面板。
- （未来）建立周期性复习流程，定期回顾旧材料、待读项与观点。

退出条件：维护不依赖记忆，而由面板和定期检查驱动。

## 阶段 5：知识问答与输出

目标：让知识库不只是存储，而是能被只读方式稳定地提问和输出。

- 只读默认的 agent 能力清单（allowlist）：回答只消费既有 `source`/`annotation`/`analysis`/`idea`/`essay`/`journal` 等对象，不写入、不修改任何笔记。
- 有依据地回答：答案引用具体 note ID 或路径，便于用户回跳到来源。
- 依据不足时明确说明缺口，不编造来源。
- （未来）成熟答案可落为 `idea`/`essay`，再进入检索与写作闭环。
- （未来）将问答结论与输出回写为新输入，形成输入→输出闭环。

退出条件：只读问答能针对既有笔记给出引用具体 note ID/路径的答案，且在不改动任何笔记的前提下覆盖主要对象类型。

## 延后需求（候选，非当前 schema）

以下两项输入能力已在设计讨论中确认方向，但**尚未在当前 schema/目录中激活**，`schema_version` 保持 `1`，不实现模板、字段或自动化，仅作未来设计登记。

### A. 引文 / 诗作输入

- 完整诗作或成形引文，连同提供的文字笔记，作为**候选 Source 子类型**，候选位置 `sources/excerpts/`；正文保持不可变。
- 个人联想/关联保留在 `annotation`，不混入 Source 正文。
- 未决问题：无 URL 的来源/出处如何登记；手机手动输入与照片 OCR 的输入路径；最终元数据与文件夹细节。

### B. 问答（QA）输入

- 候选判别符为 `type: idea` + **`kind: QA`**（大小写与拼写固定）。
- 一个问题对应一个文件；当前答案、补充视角、后续追问/反思在同一 note 内迭代演进。
- 不要求每个答案都抽成一个 Idea；仅当答案足够成熟、可独立使用时才在日后抽取为独立 Idea。
- 未决问题：最终模板与状态机。

## 未来可选方向

- 为不同抓取来源定义专用 Web Clipper 模板。
- 本地全文检索或向量检索。
- 将 AI 生成内容统一标记 `verification: unverified`。
- 从 Zotero/Obsidian 生成引用驱动的写作项目。
- 为附件引入 Git LFS、git-annex 或对象存储。
- 对 schema 进行自动迁移和版本检查。

## 升级规则

任何会改变既有文件含义的更新都必须：

1. 在 `DECISIONS.md` 新增决策。
2. 提升 `schema_version`。
3. 提供可回滚的迁移说明。
4. 先在小样本分支验证。
5. 不静默覆盖 Source 正文或 Yanki `noteId`。
