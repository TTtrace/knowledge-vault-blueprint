# Execution Brief 02 — post-cutover read-only verification

Role: Executor
Effort: `/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-simple-cutover/`
Work Item: `issues/02-post-cutover-verification.md`

## 1. 批准依据

- 第一层 `spec.md` / `plan.md` approved。
- Operator 已执行 controlled-action-runbook.md 的 canary 与 production 切换，并确认 canary 通过。
- 本 Work Item 只做只读复核（AC-06/07/08），不执行任何写/重启/Controlled Action。

## 2. 只读复核项（全部 read-only）

### VAL-01 配置态（AC-06）
```
openclaw config validate
openclaw config get channels.telegram.enabled          # 期望 true（production 恢复）
openclaw config get channels.telegram.accounts         # 期望仅 default
openclaw config get bindings                           # 期望仅 main→telegram:default
openclaw config get 'agents.list.0.name'               # 期望 Steward
openclaw config get 'agents.list.0.subagents.allowAgents'  # 期望 ["notesvaulter"]
openclaw config get 'agents.list.1.skills'             # 期望 3 技能
openclaw config get 'skills.entries.vault-capture.env.VAULT_ROOT'  # 期望 ${OPENCLAW_VAULT_ROOT} 或解析为正式路径
```

### VAL-02 运行态（AC-06）
```
openclaw gateway status                                 # running, healthy, loopback
openclaw skills check --agent notesvaulter              # 3 技能 eligible，Missing requirements 空
openclaw tasks list --status running --status queued    # 0/0
```

### VAL-03 正式 Vault 未变（AC-07）
```
git -C /home/monottx/repos/SourceNotes rev-parse HEAD   # 期望 ec1a90eb…
git -C /home/monottx/repos/SourceNotes status --porcelain   # 期望空
```
确认无任何 canary/测试数据泄漏进正式 Vault。

### VAL-04 只读 Query/Maintenance canary（AC-07）
在蓝图库根目录，只读调用受控入口（VAULT_ROOT 指向正式 Vault）：
```
VAULT_ROOT=/home/monottx/repos/SourceNotes python3 scripts/sourcenotes_agent.py maintenance report
VAULT_ROOT=/home/monottx/repos/SourceNotes python3 scripts/sourcenotes_agent.py query search "sourcenotes-canary-20260818"
```
- maintenance report：返回 git/sources/attachments 等只读字段，exit 0。
- query search canary marker：期望 `count=0`（marker 在 canary clone，不在正式库，证明无泄漏）。
- 运行后再次 `git -C /home/monottx/repos/SourceNotes status --porcelain` 仍空。

### VAL-05 canary clone 保留（AC-07 边界）
```
git -C /home/monottx/repos/SourceNotes-production-canary-20260818-test status --porcelain
grep -rl "sourcenotes-canary-20260818" /home/monottx/repos/SourceNotes-production-canary-20260818-test/notes/ 2>/dev/null
```
确认 canary 捕获文件仍在 clone，且 clone 未被删除。

### VAL-06 last_known_good / soak（AC-08）
只读检查 `~/.local/state/sourcenotes-simple-cutover/2026-08-17/ledger.txt` 是否存在；若存在记录其内容，不存在则报告 NOT_RUN（由 Operator 稍后跑 `soak` 补记）。

## 3. 允许/禁止

- 只读命令；不得写活动配置、不得 restart/reload Gateway、不得写任何 Vault、不得 stage/commit。
- Evidence 不得含 secret、正文、绝对 Vault 路径之外的隐私；只报告 HEAD 短 hash、布尔值、计数、basename。
- 新增 `evidence/02/execution.md`。

## 4. 返回契约
```
STATUS: READY_FOR_REVIEW | BLOCKED
CHANGED_FILES: evidence/02/execution.md 内容说明
ACCEPTANCE_EVIDENCE: AC-06/07/08 逐项 PASS/FAIL/NOT_RUN
VALIDATION_LOG: VAL-01..06 cwd/command/exit/key output
DEVIATIONS / BLOCKERS / FINAL_STATE
```
