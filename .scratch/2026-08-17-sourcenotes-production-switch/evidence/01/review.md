# Work Item 01 Review Evidence

Role: Reviewer
Review round: 1
Date: 2026-08-17

Verdict: CHANGES_REQUESTED

## Inputs reviewed

1. Approved first-layer `spec.md`, `plan.md`, Work Item 01 and Operator approval signal.
2. `execution-brief-01.md`.
3. Executor fixed return plus actual `cutover-package.md` and `evidence/01/execution.md`.

## Findings

- **F-01 [major]**：VAL-09 的声明 cwd 与目标路径矛盾，且 `git diff --check` 不覆盖未跟踪产物，扫描未证明覆盖实际工件。修复：从 Effort 根使用正确路径重跑扫描，并使用可检查未跟踪文件的 whitespace 方法。
- **F-02 [major]**：Execution Evidence 写入一次性 Vault 的绝对路径，违反 AC-09。修复：只保留 `*-test` basename，移除绝对路径并重跑 VAL-09。
- **F-03 [major]**：runbook 以直接 `cp` 覆盖备份/生产配置/恢复，未满足原子写；状态目录权限也未强制验证。修复：同目录临时文件、flush/fsync、0600/hash 校验、原子 rename 与目录 0700 验证。
- **F-04 [major]**：隔离 `*-test` runbook 有未定义占位符，未完全隔离 test Gateway/state/port/channel/凭据，也未实际验证 Steward→NotesVaulter 委派。修复：完整隔离 profile/state/config/port、禁用生产 channel、PID/trap、三技能 eligibility 与新 session 委派验证。
- **F-05 [major]**：候选配置只是语义草图，缺确定性构造与 secret-free semantic diff；`null` 删除语义不明确。修复：给出保留未知字段、精确数组替换/删除键的确定性变换与 validate/diff。
- **F-06 [major]**：`/newbot` 不保证旧 main token 失效。修复：明确 BotFather revoke/reissue 旧 bot、验证旧凭据失效；值只留私有渠道。
- **F-07 [major]**：`<SourceNotes>` 等占位符在 shell 中会成为重定向，runbook 不可直接执行。修复：使用 Operator 私有环境变量并始终引用变量，Evidence 只报告 basename。
- **F-08 [minor]**：Executor 定位了允许范围外的外部 vault-starter 路径。修复：删除该绝对路径引用，后续只用仓库内 fixture 说明缺失。

## Acceptance matrix

- AC-01: NOT_RUN（Reviewer 未独立完成全部真实状态验证）
- AC-02: NOT_RUN（历史日志存在，但 Reviewer 未独立复跑；直接 entrypoint 不等同真实委派 E2E）
- AC-03: FAIL（F-04/F-05/F-07）
- AC-04: FAIL（F-03）
- AC-05: FAIL（本轮非 PASS）
- AC-06/07/08: NOT_RUN（Work Item 02）
- AC-09: FAIL（F-01/F-02/F-08）

## Controlled Action gate

CLOSED。不得执行凭据轮换、活动配置写入、Gateway reload/restart、production cutover、ledger/last_known_good 或其它 Controlled Action。

## Next action

在现有第一层范围与允许路径内修复 F-01 至 F-08，补齐 Evidence 后复审；无需重新批准第一层计划。

---

## Review round 2

Date: 2026-08-17

Verdict: CHANGES_REQUESTED

### Findings status

- **F-01 [major, open]**：VAL-V2-04 仍漏检 `/absolute/path/to/SourceNotes` 及 `rm`、`git clone`、`git remote remove`、`os.replace` 等写路径，AC-09 未获证明。
- **F-02 [major, open]**：`cutover-package.md` 仍含绝对 Vault 路径示例。
- **F-03 [major, open]**：atomic helper 以文本读写，不能逐字节保真；固定 `.tmp` 名称且异常路径不清理。
- **F-04 [major, open]**：暂停真实入口与 main 本地新 session 仍无精确命令；canary 与 production publish 顺序重复。
- **F-05 [major, open]**：semantic projection 示例含无效 Python 语法，不能按原样执行。
- **F-06 [major, open]**：凭据 revoke 后若恢复旧备份，会恢复已失效 token，Telegram rollback 不可用。
- **F-07 [major, open]**：token 注入脚本把完整候选打印 stdout，可能泄露 token。
- **F-08 [minor, closed]**：已删除越界 vault-starter 定位行为。
- **F-09 [major, new]**：candidate 只给 `vault-capture` 注入 VAULT_ROOT；query/maintenance 也需同一环境才能 eligible。
- **F-10 [major, new]**：transformer 对缺失结构不 fail-closed；projection token 布尔表达式非法。
- **F-11 [major, new]**：canary 删除只检查绝对路径与 `-test` 后缀，未绑定 STATE_DIR、创建标记、inode 与精确 basename。
- **F-12 [major, new]**：§2.5/§2.6 重复 production publish/restart，没有唯一最终 cutover gate。

### Acceptance matrix

- AC-01/02: NOT_RUN
- AC-03: FAIL（F-04/F-05/F-09/F-10/F-12）
- AC-04: FAIL（F-03/F-06）
- AC-05: FAIL
- AC-06/07/08: NOT_RUN
- AC-09: FAIL（F-01/F-02/F-07）
- AC-10: NOT_RUN；真实模型 canary 留在 Controlled Action 与获批修订一致，但 runbook 仍需修复 F-04/F-11/F-12。

### Controlled Action gate

CLOSED。继续同一 Work Item 的第二个、也是最后一个自动修复轮；若下一次 Review 仍非 PASS，停止请求 Operator。

---

## Review round 3 — final automatic review

Date: 2026-08-17

Verdict: CHANGES_REQUESTED

### Findings

- **F-04 [major, open]**：Gate A 发布轮换基线时 Telegram 仍 enabled，NotesVaulter 旧入口尚未移除；维护窗口未真正暂停入口。
- **F-07 [major, open]**：生产/测试 Vault 私有变量只有注释示例，缺 `: "${VAR:?}"` 等 fail-closed 定义检查。
- **F-11 [major, open]**：cleanup 未拒绝 canary parent symlink，也未验证 ledger regular/0600 与完整 provenance。
- **F-13 [major, new]**：多个 Bash 步骤缺 fail-fast；前置检查/clone/backup/token 失败后可能继续，预期失败的 push 未显式断言。
- **F-14 [major, new]**：canary 唯一标记为 `.marker.txt`，Query 只扫描 Markdown，Gate C 的 query 命中条件不可成立。
- **F-15 [major, new]**：clone 前未锁定正式 Vault HEAD/index/content fingerprint；clone 后读取 source HEAD 不能证明来自批准基线。
- **F-01/F-02/F-03/F-05/F-06/F-08/F-09/F-10/F-12**：CLOSED（部分为 Evidence-backed，本轮未复跑）。

### Acceptance matrix

- AC-01/02: NOT_RUN
- AC-03: FAIL（F-04/F-07/F-11/F-14/F-15）
- AC-04: FAIL（F-07/F-13）
- AC-05: FAIL
- AC-06/07/08: NOT_RUN
- AC-09: PASS（Evidence-backed）
- AC-10: NOT_RUN；真实模型 canary 留在 Operator gate 与批准修订一致。

### Final gate

- Controlled Action gate 保持 CLOSED；不得执行凭据轮换、Gateway/config 写入、canary、production publish、rollback、ledger 或 last_known_good。
- 这是第三次复审且仍非 PASS。依 lifecycle 停止自动修复，Work Item 保持 `claimed`，请求 Operator 决定后续处理。
