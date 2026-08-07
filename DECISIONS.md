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
| D-014 | 每个 Source 使用一个持续累积的捕获 Annotation 文件 | accepted |
| D-015 | OpenClaw skill 候选版本先在 Linux 验证再晋级稳定版 | accepted |
| D-016 | Vault 捕获自动化只暂存，不自动提交 | accepted |

## D-017：确定性网页抓取运行时与迁移边界

**决定**：`vault-capture` 的网页正文抓取改用仓库自有的确定性运行时，而不是依赖 agent 的 `web_fetch`/Browser 工具。固定使用 Trafilatura 作为通用正文选择与 HTML 清洗，WeChat 站点专用适配处理 `#js_content`、懒加载图片与挑战页，Playwright 作为只读渲染回退；`ingest-web <id>` 是唯一新增的会改变状态的网页入口，直接复用既有原子 `finalize`/`fail` 事务。正文 Markdown 不经过 agent 或 chat 载荷。

**理由**：

- agent `web_fetch` 存在响应截断、仅标题/元数据提取、运行时无 Browser 工具等不可确定问题，无法作为可执行质量门槛。
- Trafilatura 与 Playwright 均为 Python 生态、维护活跃，符合 skill 现有 Python 运行时。
- 静态抓取优先、渲染回退按需，平衡速度与健壮性；WeChat 访问模型需要真实浏览会话且状态多变，故保留专用适配与 `manual` 边界。
- 质量门槛是确定性阈值（标题缺失、正文过短、挑战页、超限、图片清单不一致），不是提示词判断。

**边界**：`schema_version` 保持 `1`，不改变既有字段含义。现有受管 Annotation 汇总仅在被捕获追加/`finalize` 显式触达时归一化到新布局，不做全库或正式 Vault 迁移。浏览器 profile/cookie 状态位于两个仓库之外，由配置提供、不打印、不暂存。依赖与浏览器安装只走一次性验证路径，不修改全局 Python 或默认浏览器安装。

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

**决定**：捕获事务先保存链接、已确认元信息和批注，再异步获取正文。未知正式标题时只使用 ID 临时文件；处理完成后再按正式元数据重命名。

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

## D-014：每个 Source 一个捕获 Annotation 文件

**决定**：由捕获工作流产生的划线和评论按 Source 聚合。每个 Source 最多维护一个持续累积的 Annotation 文件；新引文追加引用单元，相同引文的新评论追加到原单元。

**理由**：

- 移动端可能多次转发同一材料，将批注聚合到一个位置更便于连续阅读。
- 稳定的 Source → Annotation 一对一关系简化去重、反向链接和自动化更新。
- 每条引用单元仍保存独立时间和定位，不牺牲引用粒度。

**边界**：该决定只约束自动捕获生成的 Annotation；人工细读仍可按需要创建额外 Annotation。聚合文件的 `created` 永不更新；引用单元显示为“标注 1、标注 2……”，新增内容的业务时间与 locator 写入隐藏管理元数据，整体修改历史由 Git 和 `file.mtime` 提供。

## D-015：候选版本先验证再晋级

**决定**：Git commit 只表示可传输、可回退的开发快照，不自动表示稳定发布。OpenClaw skill 在功能分支完成开发机检查后，以不可变的 RC 标签传到 Linux staging；只有 Linux 对该精确 commit 验证通过后，才将同一 commit 晋级到 `main` 并创建正式版本标签。

**理由**：

- OpenClaw 的真实运行环境在家庭 Linux 主机，开发机检查不能替代主机验证。
- 功能分支允许安全传递尚未完全验证的代码，同时保持 `main` 和正式标签的稳定含义。
- RC 标签和 commit hash 能准确复现失败候选，便于修复、比较和回滚。
- 发布与被验证的 commit 保持一致，避免测试通过后又因 squash、rebase 或 amend 引入未验证变化。

**边界**：RC 失败后创建新 commit 和下一个 RC 标签，不移动旧标签。候选通过后不得再改写该 commit；若合并、冲突处理或历史整理改变了 commit 或最终文件树，必须重新执行 Linux 验证。staging 与 production 使用不同检出目录；需要同时运行时，使用隔离的 OpenClaw profile、配置、状态、workspace 和端口。本决定采纳前已经进入共享 `main` 的未验证提交不重写历史，但视为未发布候选；首个通过 Linux 验证的正式标签建立稳定基线。

## D-016：Vault 捕获只暂存

**决定**：`vault-capture` 在创建或更新 Source、Annotation、Idea、正文状态和附件后，只对本次变化的路径执行 `git add`，不自动执行 `git commit` 或 `git push`。用户按主题、时段或维护批次统一提交。

**理由**：Source 捕获、Annotation 追加和后台抓取会在短时间内产生多次细碎变化；逐次提交会制造大量低价值 commit，增加历史浏览、同步与整理成本。暂存仍能明确本次写入范围，并允许提交前集中复核。

**边界**：已暂存的捕获结果允许继续累积；目标文件存在未暂存修改或未跟踪的既有文件时，自动化停止并报告冲突。`git add` 失败时保留落盘内容，但不得启动后续抓取或把任务标记为 `ready`。何时提交、如何分批及是否推送由用户决定。
