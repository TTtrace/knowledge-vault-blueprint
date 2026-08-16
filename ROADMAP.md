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
- 在 `main` 上以 commit hash 作为版本身份开发；使用外部 `last_known_good` 记录稳定基线。
- 更新时进入维护模式，在同一 checkout 中完成验证；合成/自动 E2E 只写入一次性 `*-test` 临时 Vault。
- 使用 `agents.list[].skills` 为 Vault agent 配置完整 allowlist。
- 实现 URL 规范化和 `canonical_url` 去重。
- 立即创建 Source 占位文件。
- 建立后台抓取队列、重试和失败记录。
- 普通网页转 Markdown（仓库自有的确定性 `ingest-web`：Trafilatura + WeChat 适配 + Playwright 只读回退）。
- 音视频生成带时间戳 transcript。
- 每次自动化变更只暂存相关路径，由用户按批次生成可读 Git 提交。
- 在临时 Vault 完成 `skills list/info/check`、E2E 冒烟测试和回滚演练。

退出条件：失败任务能在 `maintenance.base` 中被发现和重试；Vault agent 只加载预期 skill，且上一 `last_known_good` 可以恢复。

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

## 阶段 6：SourceNotes 单入口运行基础（本阶段）

目标：为正式生产运行建立「用户 → Steward（唯一入口）→ NotesVaulter」单入口拓扑、受控入口与 Vault 外运维工具。**本阶段只建立并验证蓝图、技能与通用工具，不迁移正式数据、不切换生产、不修改活动 OpenClaw 配置。**

- 单入口拓扑：Steward 规范委派/授权/汇总，不直接写 Vault；NotesVaulter 统一 Capture / Query / Maintenance 三能力（原则见 [D-023](DECISIONS.md#d-023单入口运行拓扑steward-唯一入口--notesvaulter-三能力--附件预算)）。
- 受控 entrypoint（`scripts/sourcenotes_agent.py`）：固定 capture/query/maintenance 子命令，只从 `VAULT_ROOT` 读取目标，拒绝路径穿越、任意 Vault、非 Markdown 读取与超限输出；后续可用 exec allowlist 收窄 NotesVaulter。
- 单层委派：网页抓取在当前 NotesVaulter 委派运行内确定性完成（`ingest-web`），不再要求 spawn worker。
- Query 只读能力：有界 search/show/related，答案携带 note ID/相对路径（阶段 5 的实现基础）。
- Maintenance 只读报告：Git 状态、failed/manual、缺失引用、附件预算与 2 GiB 闸门（阶段 4 的实现基础）。
- 附件策略：同 Source 事务内内容去重；单附件 5 MiB、单 Source 30 MiB（物理落盘唯一附件字节）为软告警；总量 2 GiB 为决策闸门（仅报告）。
- 运维工具（`scripts/sourcenotes_ops.py`）：audit / manifest 驱动的冲突安全迁移 / health / 外置 ledger / 外置 incident（秘密扫描失败关闭）。
- 测试：`tests/operations/**` 覆盖受控入口、只读 Query/Maintenance、审计与迁移、incident/ledger/health 边界。

退出条件：临时 Vault 与单元测试证明受控入口、只读 Query/Maintenance、审计/迁移、incident/ledger/health 契约稳定；正式生产切换（迁移数据、修改活动配置、启用 Steward 委派）是后续阶段，须另行批准后执行。

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
- 为附件引入 Git LFS、git-annex 或对象存储（**触发条件**：Vault 附件总量达到 2 GiB 决策闸门后评估；在此之前只由 health/maintenance 报告附件预算，见 [D-023](DECISIONS.md#d-023单入口运行拓扑steward-唯一入口--notesvaulter-三能力--附件预算)）。
- 对 schema 进行自动迁移和版本检查。

## 升级规则

任何会改变既有文件含义的更新都必须：

1. 在 `DECISIONS.md` 新增决策。
2. 提升 `schema_version`。
3. 提供可回滚的迁移说明。
4. 先在小样本分支验证。
5. 不静默覆盖 Source 正文或 Yanki `noteId`。

另需满足：

- 长期浸泡（一周或更长）允许在正式环境运行，期间正常捕获、手写、commit 与 sync 继续。
- 失败时先保护当前 Vault，再以新代码提交（通常 `git revert`）回退软件；正式 Vault 数据时间线单调保留（见 [D-022](DECISIONS.md#d-022vault-数据单调保留软件回退与数据回退分离)），禁止回退整周数据 commit。
- breaking schema 在进入长期正式测试前必须提供双读兼容 Adapter 或可逆、幂等、冲突安全的字段级迁移，并提供 migration/rollback 指导。
