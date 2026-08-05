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

OpenClaw 将手机输入发送到家庭 Linux 主机，因此可将 Linux 工作区作为主要写入点。

为减少冲突：

- 每条捕获创建独立文件。
- 避免手机和桌面同时追加同一个 daily note。
- 自动化写入采用临时文件完成后再原子替换。
- 同步或切换设备前检查暂存区，由用户决定何时提交和推送。
- 发生冲突时保留双方内容，人工合并；不要强制覆盖。

## 5. `.obsidian`

不要忽略整个 `.obsidian/`，因为模板设置、快捷键和稳定插件配置可能值得追踪。

建议忽略：

- `workspace.json`
- `workspace-mobile.json`
- 缓存和临时状态

对社区插件的 `data.json` 逐项判断。包含设备路径、令牌或账号信息的配置不得提交。

## 6. 附件

普通 Git 适合：

- Markdown。
- 小型 PNG/JPEG/SVG。
- 小型音频片段。
- 模板、Bases 和脚本。

网页捕获的正文图片统一放在 `assets/images/<source-id>/`，与完成后的 Source 和 Annotation 在同一次完成事务中暂存。图片先下载到 `.queue/` 下的临时目录；清单不完整、格式不支持或任一下载失败时，不暂存附件，也不得把 Source 标记为 `ready`。

不适合：

- 大量 PDF。
- 完整视频。
- 长音频。
- 每次批注都会整体变化的二进制文件。

学术 PDF 优先放 Zotero。确需版本管理的大型附件再评估 Git LFS、git-annex 或对象存储。

## 7. 秘密与隐私

不得提交：

- API Key。
- OAuth Token。
- Cookie。
- 登录凭据。
- 私钥。
- 含凭据的 OpenClaw 或插件配置。

即使仓库是私有的，也要将秘密放在环境变量或专用密钥管理器中。

## 8. 建议备份

至少包含：

1. 工作电脑或家庭 Linux 主副本。
2. 异机 Git 远程副本。
3. 定期离线或加密快照。
4. Zotero 数据库与 PDF 附件的独立备份。
5. Anki/AnkiWeb 之外的周期性 collection 导出。

## 9. 恢复演练

每季度抽查：

- 从空目录 clone Vault。
- 用 Obsidian 打开并检查链接、Templates 和 Bases。
- 验证一条 Zotero 来源记录能够打开原 PDF。
- 验证 Yanki 卡片的 `noteId` 仍在。
- 验证离线备份可读取。
