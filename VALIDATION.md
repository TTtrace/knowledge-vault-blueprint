# 交付验证记录

验证日期：2026-08-05

## 结构

- 蓝图主文档：完成。
- 架构决策记录：完成。
- 演进路线：完成。
- 专项规范：8 份。
- OpenClaw skill 的仓库边界、加载、allowlist、发布与回滚规范：完成。
- OpenClaw skill 的 RC → Linux staging → 稳定版晋级规范：完成。
- 首个 `vault-capture` skill、确定性脚本与运行契约：完成。
- 完整示例：9 份。
- Obsidian Templates：12 份。
- Obsidian Bases：6 份。
- 空目录保留文件：完成。

## 自动检查

- [x] 所有 `.base` 文件均为合法 YAML。
- [x] 所有带 frontmatter 的 Markdown 均可解析为合法 YAML。
- [x] 蓝图内标准 Markdown 相对链接均指向现有文件或目录。
- [x] Starter Vault 必需目录全部存在。
- [x] Yanki Basic 模板包含 frontmatter 和独立正反面分隔线。
- [x] 抓取状态和阅读状态使用不同字段。
- [x] Annotation 与 Analysis 模板均保留来源链接、标题和外部定位字段。
- [x] Yanki 候选目录不在正式监控目录之内。
- [x] `vault-capture` 的 URL 规范化、临时/最终命名、原文结构保留、图片本地化、批注聚合、重复输入、状态转换与 Git 路径隔离测试通过。
- [x] `vault-capture` 的测试全部使用一次性临时 Git Vault，不写入正式 Vault。
- [x] 独立前向测试验证 Source/Annotation 提交、队列忽略及中文输入逐字保留；Windows PowerShell 5 使用 UTF-8 `--json-file` 降级接口。

## 人工检查

- [x] PDF 原件、批注、细读和观点职责分离。
- [x] AI 对话默认标记未经核实。
- [x] 日记默认允许 AI 访问。
- [x] `.gitignore` 不会忽略整个 `.obsidian`。
- [x] 大型本地附件目录默认不进入普通 Git。
- [x] 首页嵌入六个面板中的关键视图。

## 仍需在真实环境验证

以下项目依赖实际安装环境，不属于静态蓝图验证：

- Obsidian 当前版本加载全部 `.base` 视图后的显示效果。
- Yanki/AnkiConnect 首次同步及 `noteId` 写回。
- Linux 上 `obsidian://` 链接注册。
- Zotero 批注导出格式。
- 家庭主机加载 `vault-capture` 后的 `skills list/info/check`、子任务抓取和失败重试。
- `web_fetch` 失败后通过个人 Chrome extension profile 只读提取登录态页面。
