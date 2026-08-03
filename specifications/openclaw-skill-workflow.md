# OpenClaw Skill 开发、加载与发布规范

## 1. 目标与边界

本规范定义知识库相关 OpenClaw skill 的权威位置、目录结构、加载方式、agent 可见性、验证、发布和回滚流程。

- `knowledge-vault-blueprint` 保存规范、skill 实现与测试。
- 正式 Vault 保持为独立仓库；skill 不包含真实笔记、设备路径或凭据。
- 本仓库内所有知识库 skill 使用同一个仓库版本标签发布，避免 schema、文档和运行逻辑漂移。
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

家庭主机将本仓库的稳定版本检出到固定但不入库的路径，并在 `~/.openclaw/openclaw.json` 中通过 `skills.load.extraDirs` 直接加载：

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
        enabled: true
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

本仓库使用语义版本标签作为蓝图与所有知识库 skill 的共同发布单元：

1. 在开发分支完成规范、实现和测试。
2. 合并到 `main` 后创建稳定标签，例如 `v0.2.0`。
3. 家庭主机获取新标签并检出该明确版本，不直接跟随未验证的开发分支。
4. 运行：

```text
openclaw skills list --eligible --agent <vault-agent-id>
openclaw skills info <skill-name> --agent <vault-agent-id>
openclaw skills check --agent <vault-agent-id>
```

5. 开启新会话，在临时 Vault 执行冒烟测试；通过后才允许写入正式 Vault。
6. 出现问题时检出上一稳定标签，重新运行检查并开启新会话。

`watch: true` 可以在 `SKILL.md` 变化后刷新 skill 快照，但涉及脚本、reference、allowlist 或运行配置的发布仍以新会话验证为准。

若版本改变既有笔记含义，必须同时：

1. 在 `DECISIONS.md` 新增决策。
2. 提升 `schema_version`。
3. 提供可逆迁移与回滚步骤。
4. 在样本副本或测试分支中验证。
5. 不静默覆盖 Source 正文、Yanki `noteId` 或未知属性。

## 8. 发布检查表

- 每个 skill 的目录名、`name` 和 allowlist 项完全一致。
- `description` 能覆盖预期请求，同时不会误触发无关请求。
- 所有依赖已声明，缺失依赖时 skill 会被正确过滤或安全停止。
- `openclaw skills list/info/check` 均显示预期来源和 eligible 状态。
- 目标 agent 只能看到 allowlist 中的 skill；其他 agent 不会意外继承。
- 不存在 workspace 同名副本遮盖 `extraDirs` 版本。
- 临时 Vault 冒烟测试、版本升级和上一标签回滚均通过。
- 仓库中不存在 API Key、Token、Cookie、真实主机路径或正式 Vault 数据。

## 9. 官方参考

- [OpenClaw Skills](https://docs.openclaw.ai/tools/skills)
- [OpenClaw Skills CLI](https://docs.openclaw.ai/cli/skills)

