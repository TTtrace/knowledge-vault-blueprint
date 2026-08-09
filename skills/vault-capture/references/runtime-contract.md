# 运行契约

## 命令

所有命令都向标准输出写出一个 JSON 对象。除非隔离测试显式传入 `--vault`，否则使用 `VAULT_ROOT`。

```text
vault_capture.py [--vault PATH] preflight
vault_capture.py [--vault PATH] stage [--json-file FILE]       # UTF-8 JSON file or stdin
vault_capture.py [--vault PATH] ingest-web ID                  # deterministic web ingestion
vault_capture.py [--vault PATH] finalize ID [--json-file FILE] # UTF-8 JSON file or stdin
vault_capture.py [--vault PATH] fail ID [--json-file FILE]     # UTF-8 JSON file or stdin
vault_capture.py [--vault PATH] inspect ID
vault_capture.py [--vault PATH] list-retryable [ID]
```

退出码 `0` 表示命令执行完毕，业务结果以 JSON 内容为准；`2` 表示输入或配置无效；`3` 表示目标冲突；`4` 表示文件系统或 Git 失败。不得根据自然语言输出推断成功。

Linux/OpenClaw 应使用 `SKILL.md` 中带单引号的 heredoc。Windows PowerShell 5 通过管道向原生进程传输内容时可能损坏非 ASCII 文本；仅在 Windows 开发测试中，将载荷写成 UTF-8 文件并改用 `--json-file FILE`。脚本不会删除调用方提供的输入文件。

调用 Python 解释器使用可选 `VAULT_CAPTURE_PYTHON`（带引号回退 `"${VAULT_CAPTURE_PYTHON:-python3}"`）：它是操作者提供的已有可执行文件路径，不做 eval/拼接 shell、不装依赖、不写仓库、不放进 `requires.env`；未设置时回退 `python3`。

## `stage` 输入

```json
{
  "kind": "web | transcript | document | ocr | idea",
  "url": "https://example.com/article",
  "title": "optional user-supplied title",
  "text": "source text or personal idea",
  "author": ["optional confirmed author"],
  "publisher": "optional publisher, account, organization, or site",
  "published": "optional YYYY-MM-DD",
  "topics": ["知识管理"],
  "priority": 2,
  "medium": "optional allowed Source medium",
  "captured_at": "optional ISO 8601 datetime",
  "annotations": [
    {
      "quote": "optional exact quote",
      "comment": "optional user comment",
      "locator": "optional section/page/time",
      "captured_at": "optional ISO 8601 datetime"
    }
  ]
}
```

`stage` 使用严格字段白名单；未知字段（包括已删除的 `why_saved`）返回退出码 `2`。`web` 必须提供 HTTP(S) URL；`idea` 必须提供 `text`。v1 会把 `transcript`、`document` 和 `ocr` 可靠保存为 `manual`，且不创建后台任务。每条 annotation 必须包含引文或评论。

`web` URL 必须是 DNS 主机名：含凭据、非 HTTP(S)、或任何 IPv4/IPv6 字面量（含公网与 Fake-IP 字面量）在 `stage` 即返回退出码 `2`，不创建可抓取的 web 任务。`stage` 只做语法校验，不做 DNS；DNS/地址校验在每次网络边界由共享 SSRF 策略执行。

缺少正式标题时，Source 仅使用 `<source-id>.md`，Annotation 仅使用 `annotated_<source-id>.md`。不得生成“待抓取”“待处理”或域名伪标题。提供可靠标题时可以直接使用最终命名；网页后台任务返回的路径仍视为临时路径，直到 `finalize` 成功。

`stage` 的关键输出字段：

```json
{
  "ok": true,
  "result": "created | updated | duplicate",
  "id": "permanent-id",
  "source_path": "Vault-relative path",
  "annotation_path": "Vault-relative path or null",
  "staged": true,
  "staged_paths": ["Vault-relative path"],
  "job_created": true,
  "ingest_status": "pending | ready | failed | manual",
  "paths_final": false
}
```

只有 `staged: true` 与 `job_created: true` 同时成立时，才允许启动后台抓取。`duplicate` 返回空的 `staged_paths`。脚本不创建 Git commit，也不要求配置 Git author identity。

## `finalize` 与 `fail` 输入

`finalize` 使用严格字段白名单，要求非空 `title`、`markdown` 以及 `images_complete: true`。`author` 必须为字符串列表；`publisher`、`published`、`summary`、`final_url`、`retrieved_at` 和 `language` 可选。图片协议如下：

```json
{
  "title": "Page title",
  "author": ["Author"],
  "publisher": "Site or account",
  "published": "2026-08-01",
  "markdown": "![Alt](vault-image://image-1)",
  "images": [
    {"token": "image-1", "url": "https://example.com/image.png"}
  ],
  "images_complete": true
}
```

每个 token 必须安全、唯一，并在 Markdown 中恰好出现一次；Markdown 中的占位符与 `images` 必须完全一致。脚本把图片写入 `assets/images/<source-id>/`，按正文顺序命名为 `<三位序号>-<内容哈希前12位>.<扩展名>`，再把占位符改为标准相对 Markdown 链接。允许 JPEG、PNG、WebP、GIF；单图上限 20 MB，单篇合计上限 100 MB。图片 URL 与每次图片重定向都必须在连接前通过共享 SSRF 策略，且必须使用 DNS 主机名（拒绝 IP 字面量）；任一图片失败时不得写入正文或设置 `ready`。

完成后 Source 使用 `<作者>--<正式标题>--<captured日期>--<source-id>.md`，Annotation 使用 `annotated_<作者>--<正式标题>--<captured日期>--<source-id>.md`。作者按署名、publisher、域名、`未知作者` 的顺序回退。作者和标题文件名部分分别限制为 32 与 80 字符，frontmatter 保留完整值。脚本负责计算 `content_hash`；存在摘要时设置 `verification: unverified`；只有 Source、Annotation、图片和 Git 暂存全部成功后才把队列与 Source 改为 `ready`。输出返回最终 `source_path`、`annotation_path`、`asset_paths`、`staged_paths` 和 `paths_final: true`。

`fail` 接受：

```json
{
  "status": "failed | manual",
  "error": "short non-sensitive summary",
  "retry_after": "optional ISO 8601 datetime"
}
```

不得把原始 HTML、堆栈信息、Token、Cookie、Authorization Header 或主机绝对路径写入 `error`。

## `ingest-web`

`ingest-web ID` 是唯一新增的会改变状态的网页入口。它读取队列任务中的 URL（不使用调用方提供的替换 URL），使用仓库自有的确定性抓取运行时（详见 [web-runtime.md](web-runtime.md)）：

- 静态抓取优先，WeChat 站点专用适配，不足时用只读 Playwright 渲染回退。
- 完整读取响应，不静默截断；正文 Markdown 不经过 agent 或 chat 载荷。
- 提取正文与元数据，生成 `vault-image://` token 图片清单，并直接复用既有原子 `finalize`/`fail` 事务完成最终命名、图片本地化与 Git 暂存。
- 标题/元数据仅提取、正文过短、挑战页、不支持 content type、超限响应、Markdown 与图片清单不一致时，绝不进入 `ready`。

输出与 `finalize` 成功一致：`ingest_status: ready`、最终 `source_path`/`annotation_path`/`asset_paths` 与 `paths_final: true`。验证码/登录/验证/限流/浏览器 profile 需要映射为 `manual`；超时/DNS/HTTP 5xx/暂时性错误保持 `failed` 可重试。

SSRF 安全配置为可选且默认失败关闭。只有同时设置 `VAULT_CAPTURE_SSRF_FAKE_IP_MODE=clash` 与 `VAULT_CAPTURE_SSRF_DOH_PROVIDER=cloudflare|google` 才启用 Fake-IP 感知；缺失/部分/未知的配置、DoH 超时/异常、或复核得到任一非全局地址，都映射为简短安全 `failed`（不泄露原始 DNS 载荷、主机配置、堆栈或绝对路径），并保留已落盘 Source 与 URL。生产代码不读取任何私有放行环境变量。

## Annotation 汇总

捕获流程使用 `<!-- vault-capture:annotation-rollup -->` 标识其管理的汇总文件。没有该标记的人工 Annotation 文件不得合并或替换。汇总规则如下：

- 使用 Unicode NFKC 和空白折叠规范化引文与评论；
- 含引文的单元按规范化后的引文精确匹配；
- 只有评论的单元按规范化后的评论精确匹配；
- 同一引文出现新评论时追加评论，并保留旧评论；
- 使用 `## 标注 1`、`## 标注 2` 顺序呈现引用单元；
- 捕获时间、locator、评论时间和去重键只写入隐藏管理元数据，不在标题或评论正文中显示；
- 汇总正文在 H1 标题下方恰好呈现一行 `来源：[[<source-id>|<来源标题>]] · [原文](<source-url>)`，不渲染 `## 摘录与批注`，也不在每个编号单元内重复来源行；
- 只有该单元实际包含一条或多条用户批注时才呈现 `批注：` 及其列表；纯评论单元仍用 `批注：`，全文不出现面向用户的 `评论：`；
- 有 locator 时只把它用于 Source 链接锚点；没有时不得输出“未定位”；
- 根据全部单元聚合 `annotation_kind` 和 `engagement`。

新创建的受管汇总使用上述布局。既有受管汇总只有在捕获追加/`finalize` 显式触达时才被归一化；不做全库或正式 Vault 迁移。

## 重试状态

队列文件位于 `.queue/vault-capture/`，且不进入 Git 暂存区。无过滤条件的 `list-retryable` 只返回 `failed` 任务。用户明确解决阻塞并要求重试后，指定 ID 的 `list-retryable ID` 也可以返回 `manual`。`conflict`、`blocked_git` 和 `ready` 永远不会被返回。队列项缺失时，只能通过新的显式捕获或人工维护进行重建；不得猜测 Source 路径。

## Git 暂存与冲突边界

`stage`、`finalize` 和 `fail` 只对本次实际变化的路径执行 `git add -- <paths>`，保留索引中已有的其他变更，不执行 `git commit` 或 `git push`。已暂存的捕获结果可继续累积 Annotation 或完成正文抓取；目标文件存在未暂存修改或未跟踪的既有文件时必须停止，以免覆盖人工编辑。
