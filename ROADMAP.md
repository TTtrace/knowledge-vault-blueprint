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

- 定义 OpenClaw 捕获命令。
- 实现 URL 规范化和 `canonical_url` 去重。
- 立即创建 Source 占位文件。
- 建立后台抓取队列、重试和失败记录。
- 普通网页转 Markdown。
- 音视频生成带时间戳 transcript。
- 每次自动化变更生成可读 Git 提交。

退出条件：失败任务能在 `maintenance.base` 中被发现和重试。

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

退出条件：维护不依赖记忆，而由面板和定期检查驱动。

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

