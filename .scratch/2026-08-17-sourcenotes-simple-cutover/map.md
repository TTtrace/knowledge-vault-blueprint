# SourceNotes simple cutover — Project State

Phase: `EXECUTE`
Status: in progress
Date: 2026-08-17
Current phase: EXECUTE
Active Work Item: `01-preflight-and-dry-run`
Next gate: Operator 执行 `soak` 记录 last_known_good 并开启浸泡期；随后进入正式 soak

## Objective

以蓝图 `main@017c2ce1fb2ef00f4fdc4e6f872a9877c49890da` 为候选，把活动 OpenClaw 切换到「用户 → main(Steward) → notesvaulter(Capture/Query/Maintenance)」生产运行态。**只使用 OpenClaw 原生配置操作**；canary clone 保留不自动删除；不维护任何自定义安全 helper。

## Supersedes

本 Effort 取代此前两个在 cutover runbook/自定义 helper 上反复审查未过的 Effort：

- `.scratch/2026-08-17-sourcenotes-production-switch/`
- `.scratch/2026-08-17-sourcenotes-cutover-runbook-safety-closure/`

两者保留为历史，不再继续委派；其已核验的真实基线（蓝图 HEAD、两 Vault HEAD、活动配置 hash、queue 0/0、Gateway pid）仍作为来源事实沿用。本 Effort 的 cutover 方案采用全新简化形态，不复用旧 runbook 或旧 helper。

## Decisions so far

- Operator 多次明确批准简化重规划，最终批准原文：
  `批准简化重规划：使用 OpenClaw 原生配置操作，canary clone 暂不自动删除，停止维护自定义安全 helper。`
- 使用 OpenClaw 原生 `config patch --dry-run` / `config patch`（原子写由 OpenClaw 负责）、`config set`、`config validate`、`skills check`、`gateway`、`secrets`。
- 真实模型 canary 使用**活动 Gateway** + 正式 SourceNotes 的完整一次性 clone（basename 以 `-test` 结尾），clone 保留、不自动删除。
- 生产 Vault 路径与 Telegram 新 token 通过 `~/.openclaw/.env`（0600）的 env 变量 + 配置内 `${VAR}` env 替换注入；仓库/Evidence 不含绝对 Vault 路径或 secret。
- 首次 production Capture 等待用户下一条真实输入；不向正式 Vault 写合成测试数据。

## Approval record

- Approval statement: `批准简化重规划：使用 OpenClaw 原生配置操作，canary clone 暂不自动删除，停止维护自定义安全 helper。`
- Approved by: Operator
- Date: 2026-08-17
- Controlled Action boundary: 本批准锁定第一层并授权 Work Item 01 只读 Technical Loop；不授权凭据轮换、活动配置写入、Gateway reload/restart、canary、production 切换或其它 Controlled Action。
