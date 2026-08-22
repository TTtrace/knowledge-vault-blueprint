# 02 — post-cutover-verification

Type: task
Status: open
Blocked by: 01、Operator exact Controlled Action
Specification: `../spec.md`
Effort Plan: `../plan.md`

## Outcome

Operator 完成精确 cutover 后，只读独立证明实际运行态满足 AC-06 至 AC-09，并建立 soak 起点。

## Scope

- 只读检查实际配置摘要、Gateway、skills、delegation、两个 Vault 状态与外部记录。
- 执行 Query/Maintenance 只读 canary；不执行生产 Capture。

## Acceptance

- AC-06、AC-07、AC-08、AC-09。

## Verification

- 在 Operator Controlled Action 完成后生成第二层简报。

## Out of scope

- 修改配置、恢复配置、写正式 Vault、迁移测试库。
