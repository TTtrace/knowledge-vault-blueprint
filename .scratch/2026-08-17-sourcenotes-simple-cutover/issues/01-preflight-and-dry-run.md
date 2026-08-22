# 01 — preflight-and-dry-run

Type: task
Status: resolved
Blocked by: none
Specification: `../spec.md`
Effort Plan: `../plan.md`
Role: Executor

## Outcome

在不触碰活动配置或两个 Vault 的情况下，冻结基线、dry-run 验证两条 native patch、/tmp 完成 clone rehearsal，产出脱敏 cutover runbook 覆盖 AC-01 至 AC-05。

## Scope

- 只读基线冻结。
- native `config patch --dry-run` 与 `config validate`。
- /tmp 一次性 clone rehearsal（源零写入、push 禁用、不自动删除）。
- 产出 cutover runbook 与两条 patch。

## Acceptance

- AC-01、AC-02、AC-03、AC-04、AC-05。
- 无活动配置/Gateway/两个 Vault/Git写；返回固定模板。

## Out of scope

- 凭据轮换、配置写入、reload/restart、生产 capture、canary clone 实际创建于正式环境、last_known_good 写入。
