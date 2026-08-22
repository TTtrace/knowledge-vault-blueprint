# SourceNotes cutover runbook safety closure — Specification

Phase: `SPECIFY`
Status: approved
Date: 2026-08-17
Approved by: Operator
Route: `STANDARD`

## Goal

仅修复 parent cutover package 的六个剩余安全/可执行性 finding：F-04、F-07、F-11、F-13、F-14、F-15。

## Non-goals

- 不修改产品代码、schema、skill 或测试。
- 不执行真实模型 E2E、凭据轮换、配置写入、Gateway reload/restart、Vault 写入、ledger/last_known_good。
- 不重新打开已关闭的 F-01/F-02/F-03/F-05/F-06/F-08/F-09/F-10/F-12，除非本项变更造成回归。
- 不改变父 Effort 第一层意图与 AC。

## Allowed paths

- 修改：parent `cutover-package.md`。
- 新增：本 Effort `evidence/01/execution.md`。
- 临时：本轮 `/tmp/sourcenotes-cutover-safety-*-test/**`，结束删除。

其余路径只读或禁止；不得 stage/commit。

## Acceptance criteria

- **AC-S01 / F-04**：Gate A 在任何 token 轮换前先原子发布并验证 ingress-paused baseline；Telegram/自动 capture 均暂停，本地 CLI 是唯一 canary 入口。
- **AC-S02 / F-07**：所有私有变量在任何使用前 fail-closed 校验，文档不含真实或伪绝对 Vault 路径。
- **AC-S03 / F-11**：canary cleanup 拒绝 symlink parent，ledger 必须 no-follow regular 0600，完整 provenance 匹配。
- **AC-S04 / F-13**：所有 Operator shell 流程 fail-fast；预期非零显式断言；trap 只清理本次安全确认的临时对象。
- **AC-S05 / F-14**：真实 canary capture 产生可查询 Markdown 唯一标记，后续 Query 对同一标记命中；不依赖 `.txt`。
- **AC-S06 / F-15**：clone 前锁定正式 Vault branch/HEAD/tree/index/porcelain 指纹，clone 后、canary 后、cleanup 前后均比较；漂移停止。
- **AC-S07**：已关闭 findings 不回归；package secret/path/URL/write classification 与 whitespace 检查通过。
- **AC-S08**：活动 config hash、默认 Gateway/queue、两个 Vault、Git index/refs 前后不变；无 Controlled Action。

## Risk and rollback

- 本项只修改 Markdown 工件；回滚只精确恢复 parent package 本项增量，不 reset/clean。
- 任何需真实 secret/生产写或产品代码时 BLOCKED/NEEDS_REPLAN。
