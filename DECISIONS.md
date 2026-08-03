# 架构决策记录

> 状态说明：`accepted` 表示首版已经采用；未来变更时保留旧记录并新增决策，不直接抹去历史。

## 决策总表

| ID | 决策 | 状态 |
|---|---|---|
| D-001 | 日记与知识笔记使用同一个 Vault | accepted |
| D-002 | Obsidian/Markdown 是内容权威来源 | accepted |
| D-003 | 目录表达类型，属性表达状态 | accepted |
| D-004 | 抓取状态与阅读状态分开 | accepted |
| D-005 | 原文与个人思考分离 | accepted |
| D-006 | 捕获立即落盘，正文后台抓取 | accepted |
| D-007 | 正文优先使用 WikiLink | accepted |
| D-008 | 学术 PDF 使用 Zotero + Obsidian 分工 | accepted |
| D-009 | Yanki 从 Markdown 单向同步到 Anki | accepted |
| D-010 | 卡片候选与 Yanki 监控区分离 | accepted |
| D-011 | PDF 和大型媒体默认不进入普通 Git | accepted |
| D-012 | 英文属性名、中文正文 | accepted |
| D-013 | 知识库 OpenClaw skill 与蓝图同仓并由 Git 版本化 | accepted |

## D-001：单 Vault

**决定**：日记允许 AI 访问，因此日记和知识笔记保存在同一个 Git 仓库与 Obsidian Vault。

**理由**：

- 日记中的洞见可以自然提取为 idea。
- 搜索、链接和 AI 检索不需要跨库。
- 降低同步、模板和备份复杂度。

**边界**：`journal/` 有独立面板。未来若出现不允许 AI 访问、需要单独加密或公开知识库的需求，再拆分安全边界。

## D-002：Markdown 是内容权威来源

**决定**：所有可长期保存的思考最终落为 Markdown。

**理由**：

- Git 可读、可比较、可回退。
- 不依赖某个数据库或单一应用。
- Obsidian、AI 工具和脚本都能直接读取。

## D-003：目录与属性各司其职

**决定**：目录只表达相对稳定的内容职责，不用目录表达待读、阅读中或成熟度。

**理由**：状态频繁变化，若靠移动目录表达，会导致链接、同步和 Git 历史噪声。

## D-004：两个生命周期

**决定**：使用 `ingest_status` 管抓取，使用 `read_status` 管阅读。

**理由**：一篇文章可以“全文抓取完成但尚未阅读”，也可能“正在阅读但 OCR 尚未补齐”。两个维度不能合并。

## D-005：原文与思考分离

**决定**：Source 原文在准备完成后原则上保持不可变；Annotation、Analysis、Idea 独立保存。

**理由**：

- 避免重新抓取覆盖人工内容。
- 清楚区分作者原话与自己的判断。
- Git 差异更容易理解。

## D-006：立即落盘、后台抓取

**决定**：捕获事务先保存链接、理由和元信息，再异步获取正文。

**理由**：网页超时、登录限制、视频转写和 OCR 不应阻止捕获成功。

## D-007：WikiLink 优先

**决定**：正文内部链接优先使用 `[[WikiLink]]`，外部出处继续保存 URL、DOI 或 Zotero URI。

**理由**：

- Obsidian 是主要编辑器。
- WikiLink 输入简单，支持反向链接。
- Yanki Obsidian 插件可将其转换为返回 Obsidian 的链接。

**限制**：块 ID 是 Obsidian 扩展；精确引用时必须同时保存引文本身。

## D-008：Zotero + Obsidian

**决定**：学术 PDF、书目信息和原始划线由 Zotero 管理；思考成果进入 Obsidian。

**理由**：Zotero 更适合 DOI、去重、引文和 PDF 批注；Obsidian 更适合跨文献分析与观点生发。

## D-009：Yanki 单向同步

**决定**：卡片内容只在 Obsidian 编辑，Yanki 单向更新 Anki；Anki 只负责学习调度。

**理由**：避免同一份卡片内容出现两个可编辑真源。

## D-010：候选区与正式卡片区分离

**决定**：

- `learning/english/candidates/`：未决定是否复习。
- `learning/anki/`：Yanki 监控且已承诺复习。

**理由**：Yanki 会同步监控目录内的所有 Markdown；候选不应自动成为卡片。

## D-011：大型附件外置

**决定**：学术 PDF 由 Zotero 存储；大型音视频放在外部媒体目录或专门对象存储。

**理由**：Git 不适合频繁变化的大型二进制文件。

## D-012：机器字段与人类内容

**决定**：属性名和枚举值采用稳定英文小写；标题、正文和说明使用自然语言。

**理由**：便于脚本、Bases、跨平台工具和未来迁移，同时不牺牲写作体验。

## D-013：OpenClaw skill 与蓝图同仓

**决定**：知识库相关 OpenClaw skill 保存在本仓库的 `skills/`，与规范和测试共同版本化；正式 Vault 继续保持独立。家庭主机检出仓库的稳定标签，通过 `skills.load.extraDirs` 直接加载，并使用 `agents.list[].skills` 限定每个 agent 可见的 skill。

**理由**：

- schema、架构决策和运行逻辑可以在同一提交与标签中演进，减少版本漂移。
- 多个相关 skill 共享一个仓库，不需要为每个 skill 建立独立仓库。
- `extraDirs` 直接读取 Git 工作区，避免本地安装副本与权威源码不一致。
- agent allowlist 可以限制提示上下文和命令发现范围，适合未来增加多个 agent。

**边界**：本仓库不保存正式 Vault 数据、机器绝对路径或凭据。Allowlist 不是安全边界；文件、命令和密钥仍需通过 sandbox、操作系统权限和独立配置约束。第三方 skill 继续由 OpenClaw/ClawHub 的安装机制管理。
