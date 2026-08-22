# 01 — preflight-and-cutover-package

Type: task
Status: claimed
Blocked by: none
Specification: `../spec.md`
Effort Plan: `../plan.md`
Role: Executor

## Outcome

在不触碰活动配置或两个 Vault 的情况下，产出经验证、secret-free、可供 Operator 精确执行的 production cutover package，覆盖 AC-01 至 AC-05 与 AC-09。

## Scope

- 冻结真实只读基线。
- 运行仓库回归与全新临时 `*-test` 验证。
- 审计当前配置结构但不输出值。
- 生成候选配置 diff、Operator runbook、回滚与 post-check 清单。
- 写 `evidence/01/execution.md`。

## Acceptance

- AC-01、AC-02、AC-03、AC-04、AC-05、AC-09。
- 无活动配置、Gateway、两个 Vault、Git index/refs 写入。
- 返回固定 executor 模板。

## Verification

- 见 `execution-brief-01.md` 的 VAL-01 至 VAL-09。

## Out of scope

- 凭据轮换、配置写入、reload/restart、生产 capture、last_known_good 写入。
