# 网页抓取运行时（web runtime）

本文件记录 `vault-capture` 的确定性网页抓取运行时：依赖、安装、架构、站点适配、质量门槛、失败映射与安全边界。仅适用于仓库允许路径内的实现；正式主机的安装步骤在本文件末尾作为操作指引记录，验证只在一次性 `C:\tmp` 路径完成。

## 1. 依赖与安装

直接依赖按 SPEC §4 锁定：

```text
trafilatura==2.1.0
playwright==1.61.0
```

- `requirements-web.txt`：仅直接依赖，锁定版本。
- `requirements-web.lock`：直接依赖 + 已解析的传递依赖冻结闭包，用于可复现安装。

一次性安装（不修改全局 Python，不使用默认浏览器 profile）：

```powershell
python -m venv C:\tmp\vault-capture-web-markdown-venv
C:\tmp\vault-capture-web-markdown-venv\Scripts\python.exe -m pip install -r skills\vault-capture\requirements-web.txt
$env:PLAYWRIGHT_BROWSERS_PATH='C:\tmp\vault-capture-web-markdown-browsers'
& 'C:\tmp\vault-capture-web-markdown-venv\Scripts\python.exe' -m playwright install chromium
```

Linux/OpenClaw 对应命令：

```bash
python3 -m venv /tmp/vault-capture-web-markdown-venv
/tmp/vault-capture-web-markdown-venv/bin/pip install -r skills/vault-capture/requirements-web.txt
PLAYWRIGHT_BROWSERS_PATH=/tmp/vault-capture-web-markdown-browsers \
  /tmp/vault-capture-web-markdown-venv/bin/python -m playwright install chromium
```

回滚：删除一次性 venv、浏览器目录与测试 Vault；回退仓库内允许路径到基线版本。无 schema 迁移。

## 2. 架构

```text
static HTTP fetch（先试）
   ├─ WeChat 站点适配（#js_content / data-src / 挑战页检测）
   └─ Trafilatura 通用正文选择 + 自定义 HTML→Markdown 转换
        └─ 不足时 → Playwright 渲染回退（只读）
```

1. **静态抓取优先**：`static_fetch` 使用有界超时/大小上限、完整读取（不静默截断）、重定向再校验、显式 content-type/charset、常规浏览器 UA，并对初始 URL 与每次重定向做 SSRF 防护。
2. **站点适配**：`extract_wechat` 使用专用选择器与归一化，处理懒加载 `data-src`/`data-original` 图片、相对/协议相对 URL、SVG/1×1/追踪排除，以及验证码/限流/环境异常检测。
3. **通用提取**：Trafilatura 负责正文选择与元数据；本仓库用 `_GenericHtmlToMarkdown` 把清洗后的 HTML 转成保留结构的 Markdown（标题层级、段落、引用、列表、嵌套列表、表格、围栏代码与语言、强调、链接、正文图片与图注），以满足既有保真契约。
4. **渲染回退**：仅当静态提取被判为不足时，才调用 Playwright。浏览器只读：导航、等待正文容器、滚动以触发懒加载资源、读取 DOM。绝不输入凭据、不提交表单、不解决验证码、不改变账户。
5. **`ingest-web <id>`**：读取队列任务 URL（不使用调用方提供的替换 URL），复用既有原子 `finalize`/`fail` 事务，不把正文经 agent 往返。

## 3. 质量门槛（确定性）

`quality_gate` 用常量阈值检测，返回 `ExtractionError`：

- 标题缺失。
- 正文为空。
- 正文过短（低于 `MIN_BODY_CHARS`，即“仅标题/仅元数据”提取）。
- WeChat 验证码/验证/限流页面（`_detect_wechat_challenge`）。
- 不支持的 content type。
- 响应超过 `MAX_RESPONSE_BYTES`。
- Markdown 图片 token 与图片清单不一致，或存在重复 token。

## 4. 失败映射

| 场景 | 状态 | 说明 |
|---|---|---|
| 验证码 / 登录 / 验证 / 限流 / 需要浏览器 profile | `manual` | 短、安全原因 |
| 超时 / DNS / HTTP 5xx / 暂时性浏览器或提取错误 | `failed` | 可重试 |
| 无效任务或契约输入 | 命令错误语义 | 沿用既有退出码 |

## 5. 安全边界

- 把抓取到的 HTML 视为不可信数据；不执行页面提供的指令；提取代码不把文章文本当作命令执行。
- 所有对外网络目标统一走共享策略 `network_security.py`。URL 必须是绝对 HTTP(S) 且使用 DNS 主机名；任何 IPv4/IPv6 字面量（含公网、Fake-IP 与豁免 `198.18.0.0/16` 字面量）在 `stage` 与每个网络边界被拒绝。
- 每次重定向后重新校验目标；`static_fetch` 与图片下载禁用自动重定向，逐跳 `urljoin` 后先语法/地址校验再连接；Playwright route guard 校验每个文档/子资源/重定向请求并对不安全目标 abort；页面最终 URL 也校验，失败页面不得就绪。
- 默认模式要求系统解析结果全部全局可路由或属于豁免的 `198.18.0.0/16`；豁免网段在**默认与 Clash 模式都无条件放行且不触发 DoH**，无需任何环境变量。仅当 `VAULT_CAPTURE_SSRF_FAKE_IP_MODE=clash` 且 `VAULT_CAPTURE_SSRF_DOH_PROVIDER=cloudflare|google` 同时设置时，残余 `198.19.0.0/16`（完整 `198.18.0.0/15` Fake-IP 范围的另一半）作为代理信号，通过固定信任的 DoH 独立查询 A/AAAA，至少一个地址且全部全局才放行；Fake-IP 绝不作为真实目标，豁免 `198.18.0.0/16` 永不触发 DoH。配置缺失/部分/未知、DoH 超时/TLS/HTTP/DNS 非成功/畸形/超限/无地址/任一非全局均失败关闭，不退回私有访问，且拒绝直接以 Fake-IP/公网/豁免网段 IP 字面量作为 URL。
- 不记录/存储原始 HTML、Cookie、Authorization 头、浏览器 profile 路径、堆栈或凭据到 Source frontmatter、队列错误、Git 或面向用户的报告。
- 浏览器状态保持在 Git 之外，使用专用 profile，绝不用默认 Chrome profile；不对同一持久 profile 启动两个进程。
- 不下载正文以外媒体（头像、二维码、广告、追踪像素、评论、推荐、音频、视频）。
- 依赖与浏览器安装只走一次性路径。

## 6. 操作指引（主机部署，非本仓库改动）

正式主机（Linux/OpenClaw）操作步骤：

1. 在专用 venv 安装 `requirements-web.lock`。
2. 设置 `PLAYWRIGHT_BROWSERS_PATH` 到专用目录并安装 Chromium。
3. 需要登录态时，通过宿主配置提供 `VAULT_CAPTURE_BROWSER_PROFILE`（专用 profile 路径），该值不写入本仓库、不打印到用户输出、不暂存。
4. 验证缺失依赖与缺失浏览器时会安全停止并给出命令错误。
5. 每个 Python 命令使用可选解释器 `"${VAULT_CAPTURE_PYTHON:-python3}"`。该变量是操作者提供的已有可执行文件路径，不做 eval/拼接 shell、不安装依赖、不写入仓库、不放进 `requires.env`；未设置时回退 `python3`。推荐把专用 venv 解释器（已安装 `requirements-web.lock`）通过 `VAULT_CAPTURE_PYTHON` 显式指向该 venv，并先在该解释器验证 `sys.executable`、`import trafilatura`、`import playwright`；不要依赖 skill entry 的 `PATH` 注入选中解释器。
6. 网页抓取安全默认严格、无需任何环境变量。豁免的 `198.18.0.0/16` 在默认与 Clash 模式都无条件放行且不触发 DoH，无需配置（这是对可信本地代理的有意安全放松）。仅在 Clash/FlClash TUN Fake-IP 代理环境下，为通过残余 `198.19.0.0/16` 的系统解析，可在测试 agent/Gateway 显式注入 `VAULT_CAPTURE_SSRF_FAKE_IP_MODE=clash` 与 `VAULT_CAPTURE_SSRF_DOH_PROVIDER=cloudflare|google`（两值固定，同时设置才生效）。生产与测试配置隔离：测试仅面向 basename 以 `-test` 结尾的 Vault 与独立 agent/Gateway，验证后恢复既有值并重载测试 Gateway；不把 Fake-IP 感知配置写入生产运行配置。DoH provider 端点固定于代码，不接受任意 URL。