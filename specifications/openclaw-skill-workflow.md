# OpenClaw Skill 开发、加载与发布规范

## 1. 目标与边界

本规范定义知识库相关 OpenClaw skill 的权威位置、目录结构、加载方式、agent 可见性、验证、发布和回滚流程。

- `knowledge-vault-blueprint` 保存规范、skill 实现与测试。
- 正式 Vault 保持为独立仓库；skill 不包含真实笔记、设备路径或凭据。
- 本仓库内所有知识库 skill 使用同一 commit 演进发布（个人单用户简化流程，见 [D-020](../DECISIONS.md)），避免 schema、文档和运行逻辑漂移。
- 非知识库用途的 skill 只有在形成独立生命周期后，才考虑迁出本仓库。

## 2. 仓库布局

知识库 skill 统一放在仓库根目录的 `skills/`：

```text
knowledge-vault-blueprint/
├── specifications/
├── skills/
│   ├── vault-capture/
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   └── references/
│   ├── vault-deep-reading/
│   │   └── SKILL.md
│   └── vault-maintenance/
│       └── SKILL.md
└── tests/
    └── skills/
```

规则：

- skill 名称使用小写字母、数字和连字符，知识库专用 skill 以 `vault-` 开头。
- 目录名与 `SKILL.md` frontmatter 中的 `name` 保持一致。
- `SKILL.md` 只保存核心步骤和资源导航；详细 schema 与领域规则放进 `references/`。
- 重复执行且需要确定性的逻辑放进 `scripts/`，例如 URL 规范化、ID 生成、元信息校验和原子写入。
- 不在单个 skill 内增加 README、安装指南、更新日志等辅助文件；共用开发和部署规则只保存在本规范中。

## 3. Skill 设计契约

每个 skill 至少提供：

```yaml
---
name: vault-example
description: 简短说明它能做什么，以及用户在什么场景下应触发它。
---
```

设计要求：

- `description` 同时覆盖能力与触发场景，并保持简短，避免 skill 数量增加后无谓占用提示上下文。
- 正文使用命令式步骤，明确需要读取哪些 reference、运行哪些 script，以及失败时如何停止或降级。
- 通过 `metadata.openclaw.requires` 声明操作系统、二进制、环境变量或配置依赖；不满足依赖时不得假装可用。
- 捕获、迁移、同步等有副作用的操作优先提供显式斜杠命令；分析和阅读类 skill 可以允许模型根据描述自动触发。
- 使用 `{baseDir}` 引用 skill 自身目录，不写死开发机或家庭主机路径。

## 4. 家庭主机加载方式

家庭主机将本仓库在 `main` 上的指定 commit 检出到固定但不入库的路径，并在 `~/.openclaw/openclaw.json` 中通过 `skills.load.extraDirs` 直接加载：

```json5
{
  agents: {
    list: [
      {
        id: "<vault-agent-id>",
        skills: [
          "vault-capture",
          "vault-deep-reading",
          "vault-maintenance"
        ]
      }
    ]
  },

  skills: {
    load: {
      extraDirs: [
        "<blueprint-repo>/skills"
      ],
      watch: true
    },

    entries: {
      "vault-capture": {
        enabled: true,
        env: {
          VAULT_ROOT: "<runtime-secret-or-host-config>"
        }
      }
    }
  }
}
```

配置职责不得混用：

| 配置 | 职责 |
|---|---|
| `skills.load.extraDirs` | 发现本仓库中的 skill |
| `agents.list[].skills` | 定义某个 agent 最终可见的 skill allowlist |
| `skills.entries.<name>.enabled` | 全局启用或禁用指定 skill |
| `skills.entries.<name>.env/apiKey/config` | 提供运行期配置；敏感值不得提交到本仓库 |

非空的 `agents.list[].skills` 是该 agent 的最终列表，不与默认列表自动合并。Allowlist 只控制 skill 可见性，不替代 sandbox、操作系统用户隔离、命令权限和文件权限。

`vault-capture` 还要求目标 agent 能使用 `exec`、`sessions_spawn`，且 sandbox 对 `VAULT_ROOT` 具有写权限。网页正文抓取由仓库自有的 `ingest-web` 命令完成（Trafilatura + WeChat 适配 + Playwright 只读回退），不再依赖 agent 的 `web_fetch` 或 Browser 工具；`VAULT_ROOT` 的真实绝对路径只能保存在主机配置或 SecretRef 中，不得写入本仓库。

`skills.entries.vault-capture.env` 只注入宿主 agent run。若该 agent 开启 Docker sandbox，`exec` 不继承宿主环境，必须同时：

- 用 `agents.list[].sandbox.docker.binds` 将主机 Vault 以 `:rw` 挂载到容器内的专用路径，例如 `/vault`。
- 在同一 agent 的 `sandbox.docker.env` 中设置 `VAULT_ROOT: "/vault"`；skill entry 中的宿主值仍用于 eligibility 检查。
- Vault 位于 agent workspace 之外时，显式评估并设置 `dangerouslyAllowExternalBindSources: true`，且只挂载该 Vault，不挂载整个 home。
- 修改 sandbox 配置后执行 `openclaw sandbox recreate --agent <vault-agent-id>`，再做临时 Vault 冒烟测试。

登录态网页只允许通过显式配置的 Chrome extension `chrome` profile 读取。该 profile 可访问用户登录态，必须限制为打开、导航、快照和正文提取；不得由捕获工作流输入凭据、提交表单或执行账户写操作。sandboxed session 还必须显式设置 `sandbox.browser.allowHostControl: true` 并在 sandbox tool policy 中允许 browser；浏览器插件、profile 与权限均应在临时 Vault 冒烟测试中验证。

### 4.1 网页抓取安全配置（可选，默认失败关闭）

`vault-capture` 的网页抓取默认以最严格方式运行：要求 DNS 主机名且全部地址全局可路由或属于豁免的 `198.18.0.0/16`（`198.18.0.0`–`198.18.255.255`，在默认与 Clash 模式都无条件放行且不触发 DoH，无需环境变量），拒绝任何 IPv4/IPv6 字面量（含豁免网段字面量）与私有/内网目标。**不需要任何环境变量即可正常工作**，切勿把可选 Fake-IP 配置放进 `requires.env` 使默认 skill 不可用。

仅在 Clash/FlClash TUN Fake-IP 代理环境下，为让合法公网域名通过残余 `198.19.0.0/16`（完整 `198.18.0.0/15` Fake-IP 范围的另一半）的系统解析，可按需在测试 agent/Gateway 显式注入两个取值固定的环境变量：

```text
VAULT_CAPTURE_SSRF_FAKE_IP_MODE=clash
VAULT_CAPTURE_SSRF_DOH_PROVIDER=cloudflare|google
```

两个变量必须**同时精确**设置才生效；缺失、部分或未知值一律失败关闭，绝不回落为私有访问。DoH provider 由代码固定为 Cloudflare 或 Google 的 HTTPS DNS JSON 端点，不接受任意 URL 或 HTTP；DoH 只用于复核 `198.19.0.0/16` 残余 Fake-IP 背后的真实 A/AAAA 是否全局可路由，不授权连接任何私有真实地址，也**不适用于豁免的 `198.18.0.0/16`（该网段永不触发 DoH）**。生产与测试必须配置隔离：测试只面向 basename 以 `-test` 结尾的 Vault 与独立 agent/Gateway，验证后恢复既有值并重载测试 Gateway，不回写正式配置。

### 4.2 可选 Python 解释器

`SKILL.md` 中每个 Python 命令统一使用带引号的回退变量 `"${VAULT_CAPTURE_PYTHON:-python3}"`。该变量由操作者在宿主配置或 SecretRef 中提供，只用于选择一个**已存在**的 Python 可执行文件；它不做 eval/拼接 shell、不安装依赖、不写入仓库、不放宽网络策略，也不放进 `requires.env`（未设置时默认回退 `python3`）。

推荐把 `VAULT_CAPTURE_PYTHON` 指向一个已安装 `requirements-web.txt`/`requirements-web.lock` 的专用 venv 解释器（例如 `/path/to/vault-capture/venv/bin/python`，作为泛化占位符，不写入任何真实主机绝对路径）。配置前先在该解释器验证 `sys.executable` 与 `import trafilatura`/`import playwright`；变更或回滚后保持宿主值恢复。不要依赖 skill entry 的 `PATH` 注入去选中该解释器——应显式设置 `VAULT_CAPTURE_PYTHON`。

### 4.3 微信抓取的 manual 边界

`vault-capture` 抓取微信文章遇到验证、验证码、登录要求或限流时，一律**安全结束为 `manual`**，交由用户人工处理；当前规范**不使用** `VAULT_CAPTURE_BROWSER_PROFILE` 环境键，**不创建**专用 persistent profile，也**不以任何方式技术绕过**验证、登录或限流。本边界只约束 `vault-capture` 的微信自动抓取，不替代上文通用登录态浏览器的安全说明（该通用说明仅适用于确有用户显式登录态、属手动范畴的场景，不构成对微信自动抓取的 profile 授权）。

## 5. 优先级与副本管理

OpenClaw 发生同名冲突时，workspace skill 的优先级高于 `extraDirs`。因此：

- 自研知识库 skill 采用“Git 工作区 + `extraDirs`”直接加载，不再执行 `openclaw skills install`。
- 不在 `<workspace>/skills` 或其他高优先级目录保留同名副本，否则 Git 中的新版本可能被旧副本遮盖。
- 只有紧急临时修复才允许放置 workspace 覆盖版；必须记录原因，并在正式版本发布后删除。
- 第三方或 ClawHub skill 继续使用 OpenClaw 的安装与更新命令，与本仓库自研 skill 分开管理。

## 6. 开发与验证

一次 skill 变更按以下顺序进行：

1. 用真实使用请求明确触发方式、成功结果和失败边界。
2. 同步修改相关 specification、schema、skill 和测试。
3. 校验 `SKILL.md` frontmatter、命名和资源链接。
4. 实际运行新增或修改的脚本。
5. 在临时 Vault 中执行正常、重复输入、非法输入、依赖缺失和部分失败场景。
6. 检查 skill 不会写出目标 Vault，不会泄露凭据，也不会覆盖未知字段或不可变 Source 正文。
7. 对复杂 skill 使用独立、最小上下文的真实任务做前向测试。

禁止直接将正式 Vault 作为开发测试目录。需要真实样本时，使用去敏副本或专用测试 Vault。

## 7. 发布、部署与回滚

个人单用户采用 `main + commit hash + last_known_good` 简化流程，不再强制 RC 标签、正式语义版本标签或 staging/production 双蓝图 checkout（见 [D-020](../DECISIONS.md)）。

| 标识 | 含义 |
|---|---|
| `main` 上的 commit | 版本身份；可精确复现 |
| 外部 `last_known_good` | 最近一次通过 Linux 验证的稳定 commit，供回退恢复 |

同一 checkout 在维护模式下完成更新与验证后供 production 加载。**同一 checkout 不得同时为测试和 production 加载不同版本**；更新时先暂停 production（维护模式），验证通过后再恢复。

发布顺序（个人单用户简化版）：

1. 在 `main` 上同步修改规范、实现和测试；提交为可复现 commit（记录 commit hash）。
2. 进入维护模式：先确认无运行中/排队中的 Vault capture 任务。
3. 在同一 checkout 上更新并验证：
   - `openclaw config validate`
   - `openclaw skills list --eligible --agent <vault-agent-id>`
   - `openclaw skills info <skill-name> --agent <vault-agent-id>`
   - `openclaw skills check --agent <vault-agent-id>`
4. 运行单元测试（`python tests/skills/test_vault_capture.py`）。
5. 开启新会话，在一次性、basename 以 `-test` 结尾的临时 Vault 执行真实 NotesVaulter E2E 冒烟测试（不写正式 Vault）。
6. 若验证失败：恢复配置，在 `main` 上创建新的修复 commit 或 `git revert`，记录新的 `last_known_good`；不得改写已验证 commit。
7. 若验证通过：将 `last_known_good` 指向该 commit，恢复 production 配置，开启新会话验证。
8. production 加载该 commit 的 skill；出现问题时回退到上一个 `last_known_good` commit，重新运行检查并开启新会话。

更新后必须以新会话验证为准；`watch: true` 可在 `SKILL.md` 变化后刷新 skill 快照，但脚本、reference、allowlist 或运行配置仍以新会话验证为准。

若版本改变既有笔记含义，必须同时：

1. 在 `DECISIONS.md` 新增决策。
2. 提升 `schema_version`。
3. 提供可逆迁移与回滚步骤。
4. 在样本副本或测试分支中验证。
5. 不静默覆盖 Source 正文、Yanki `noteId` 或未知属性。

长期浸泡（一周或更长）允许在正式环境运行候选版本；失败时先保护当前 Vault，再以新代码提交回退软件，正式 Vault 数据时间线单调保留，不删除浸泡期新增捕获/手写/附件。详见 [升级规范](upgrade-workflow.md)。

## 8. 发布检查表

- 每个 skill 的目录名、`name` 和 allowlist 项完全一致。
- `description` 能覆盖预期请求，同时不会误触发无关请求。
- 所有依赖已声明，缺失依赖时 skill 会被正确过滤或安全停止。
- `openclaw skills list/info/check` 均显示预期来源和 eligible 状态。
- 目标 agent 只能看到 allowlist 中的 skill；其他 agent 不会意外继承。
- 不存在 workspace 同名副本遮盖 `extraDirs` 版本。
- `last_known_good` 记录指向明确的 commit hash；验证后未发生历史改写。
- 同一 checkout 不在测试与 production 同时加载不同版本；更新时先进入维护模式。
- 临时 Vault 冒烟测试、版本升级和 `last_known_good` 回退演练均通过。
- 仓库中不存在 API Key、Token、Cookie、真实主机路径或正式 Vault 数据。

## 9. 官方参考

- [OpenClaw Skills](https://docs.openclaw.ai/tools/skills)
- [OpenClaw Skills CLI](https://docs.openclaw.ai/cli/skills)
- [OpenClaw Multiple Gateways](https://docs.openclaw.ai/gateway/multiple-gateways)
