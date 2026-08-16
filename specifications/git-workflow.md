# Git、附件与备份规范

## 1. Git 的职责

Git 用于：

- 查看 Markdown 内容演变。
- 回退误改。
- 审计自动化写入。
- 在设备间传递明确提交。

Git 不自动等于完整备份。远程仓库被误删、凭据泄露或仓库损坏仍需独立恢复手段。

## 2. 分支策略

个人知识库首版保持简单：

- `main`：日常真实数据。
- 大规模 schema 迁移时才创建临时分支。
- 不为每条笔记建立分支。

## 3. 暂存与提交粒度

自动捕获只执行 `git add`，不执行 `git commit` 或 `git push`。Source、Annotation、正文和附件先在暂存区累积，由用户按主题、时段或维护批次统一提交，避免每次捕获都产生 commit。

人工提交时可使用：

```text
capture: add reading queue batch
ingest: update fetched sources
note: add annotation and idea batch
vault: sync 2026-08-06
note(analysis): complete analysis <source-id>
journal: add 2026-07-25
anki: add vocabulary card <id>
schema: migrate metadata to v2
```

提交前用 `git diff --cached` 检查批次边界；需要更细粒度时再选择性取消暂存或分批提交。

## 4. 单写入者原则

OpenClaw 将手机输入发送到家庭 Linux 主机，因此 Linux 工作区是自动捕获的**唯一写入者**。个人在 Windows、macOS、Linux 与 Android 设备之间同步，但只有 Linux 的自动捕获写入知识库；其余设备仅做拉取与人工编辑。

为减少冲突：

- 每条捕获创建独立文件。
- 避免手机和桌面同时追加同一个 daily note。
- 自动化写入采用临时文件完成后再原子替换。
- 跨设备默认使用 `pull --ff-only`，保证只做可审计的前进式同步。
- 远端分叉或本地工作树不干净时，停止自动处理，改为人工合并；不强制覆盖。
- 同步或切换设备前检查暂存区，由用户决定何时提交和推送。
- 发生冲突时保留双方内容，人工合并；不要强制覆盖。

## 5. 跨平台 Git 约束

本知识库在 Windows、macOS、Linux、Android 之间同步，需遵守：

- **文件系统大小写**：Git 仓库默认大小写敏感；Windows/macOS 文件系统可能大小写不敏感，因此**禁止仅大小写不同的 rename**（`Foo.md` → `foo.md`），避免跨平台无法检出。
- **Windows 保留名与尾随字符**：避免使用 Windows 保留名（`CON`、`PRN`、`AUX`、`NUL`、`COM1-9`、`LPT1-9`）以及文件名尾随空格或尾随句点；否则 Windows 无法创建/检出。
- **行尾（LF）**：仓库统一使用 LF；通过 `.gitattributes` 声明 `* text=auto eol=lf`，避免跨平台行尾漂移。
- **symlink**：不依赖仓库内的 symlink（Windows 默认支持受限）；跨平台需要时改用真实文件或显式配置。
- **Obsidian 设备状态**：忽略 `workspace.json`、`workspace-mobile.json` 等设备相关状态，不把设备特定布局提交入仓库（见 §7 `.obsidian`）。
- **Android 设备**：视同只读/人工编辑端，不承担自动捕获写入；自动捕获唯一写入者为 Linux。

## 6. 普通软件回退的边界

普通软件回退（如 `git revert` 回退蓝图代码或恢复运行配置）**禁止**：

- 倒退正式 Vault 的 HEAD 或时间线；
- 用旧 Vault 快照覆盖当前 Vault；
- 删除浸泡期（一周或更长）新增捕获、手写内容或附件。

回退软件时应先冻结并保护当前 Vault，通过新代码提交回退行为，验证浸泡期数据仍存在。破坏性 `reset`/`clean` 仅限明确授权的灾难恢复，且需用户单独批准（数据单调保留见 [D-022](../DECISIONS.md#d-022vault-数据单调保留软件回退与数据回退分离)）。详见 [升级规范](upgrade-workflow.md)。

## 7. `.obsidian`

不要忽略整个 `.obsidian/`，因为模板设置、快捷键和稳定插件配置可能值得追踪。

建议忽略：

- `workspace.json`
- `workspace-mobile.json`
- 缓存和临时状态

对社区插件的 `data.json` 逐项判断。包含设备路径、令牌或账号信息的配置不得提交。

## 8. 附件

普通 Git 适合：

- Markdown。
- 小型 PNG/JPEG/SVG。
- 小型音频片段。
- 模板、Bases 和脚本。

网页捕获的正文图片统一放在 `assets/images/<source-id>/`，与完成后的 Source 和 Annotation 在同一次完成事务中暂存。图片先下载到 `.queue/` 下的临时目录；清单不完整、格式不支持或任一下载失败时，不暂存附件，也不得把 Source 标记为 `ready`。

附件预算与去重（原则见 [D-023](../DECISIONS.md#d-023单入口运行拓扑steward-唯一入口--notesvaulter-三能力--附件预算)）：

- **同 Source 去重**：同一 Source 事务内内容 SHA-256 相同的附件只保留一个实际附件路径，正文多个 token/位置映射到该路径；不做跨 Source 全局去重，避免破坏来源隔离。
- **软告警**：单附件超过 5 MiB 或单 Source 事务**物理落盘唯一附件字节**超过 30 MiB 时，在成功 JSON 中加入稳定 machine-readable `warnings`；重复内容映射不重复计入 30 MiB 预算；warning 不降低 `ready`、不丢附件。
- **硬限制不变**：单下载图片 20 MiB、单篇**下载字节**合计 100 MiB（重复下载仍计入）继续是安全硬限制，不能被软告警取代或放宽。
- **2 GiB 决策闸门**：Vault 附件总量达到 2 GiB 时，由 health/maintenance 报告，不自动迁移、不自动删除；是否引入 Git LFS/git-annex/对象存储由用户决定。
- **日常 Git 冲突闸门**：自动化写入前检查目标文件是否存在未暂存修改或未跟踪的既有文件，存在即停止并报告冲突；远端分叉或本地工作树冲突时停止自动处理，人工合并，不强制覆盖（见 [D-016](../DECISIONS.md#d-016vault-捕获只暂存)）。

不适合：

- 大量 PDF。
- 完整视频。
- 长音频。
- 每次批注都会整体变化的二进制文件。

学术 PDF 优先放 Zotero。确需版本管理的大型附件再评估 Git LFS、git-annex 或对象存储。

## 9. 秘密与隐私

不得提交：

- API Key。
- OAuth Token。
- Cookie。
- 登录凭据。
- 私钥。
- 含凭据的 OpenClaw 或插件配置。

即使仓库是私有的，也要将秘密放在环境变量或专用密钥管理器中。

## 10. 建议备份

至少包含：

1. 工作电脑或家庭 Linux 主副本。
2. 异机 Git 远程副本。
3. 定期离线或加密快照。
4. Zotero 数据库与 PDF 附件的独立备份。
5. Anki/AnkiWeb 之外的周期性 collection 导出。

## 11. 恢复演练

每季度抽查：

- 从空目录 clone Vault。
- 用 Obsidian 打开并检查链接、Templates 和 Bases。
- 验证一条 Zotero 来源记录能够打开原 PDF。
- 验证 Yanki 卡片的 `noteId` 仍在。
- 验证离线备份可读取。
