---
task_id: 2026-08-13-sourcenotes-runtime-foundation
status: ready_for_review
execution_round: 1
executor: executor
spec_path: ../SPEC.md
started_at: 2026-08-13
finished_at: 2026-08-14
---

# Execution Record

> This file is owned by the executor. Do not change the approved `SPEC.md` or write the review verdict here.

## 1. Preflight

| Repository | Expected baseline | Observed branch and HEAD | Worktree before execution | Result |
|---|---|---|---|---|
| `knowledge-vault-blueprint` | `main @ badfd519b85c4d80c7875cbf7cbe23afc340c35f`, 与 origin/main 一致，index 空 | `main @ badfd519b85c4d80c7875cbf7cbe23afc340c35f`；`## main...origin/main` 无 ahead/behind | `?? tasks/2026-08-13-sourcenotes-runtime-foundation/`（本任务包，含 SPEC.md，planner 已预期）；index 无 cached 变更 | pass |
| `SourceNotes`（正式 Vault） | `main @ ec1a90eb9d41df77cf74e44d51e703d0379882e7`，clean，与 origin/main 一致 | `main @ ec1a90eb9d41df77cf74e44d51e703d0379882e7`；`## main...origin/main`；`git status --porcelain` 计数 0 | clean | pass |
| `SourceNotes-test`（测试 Vault） | 冻结脏状态，只读，绝不清理/迁移/重抓取 | `main @ ec1a90eb9d41df77cf74e44d51e703d0379882e7`，既有 staged 资产文件 | 既有 staged 资产文件（assets/images/...，pre-existing） | pass |
| OpenClaw 活动配置 | SHA-256 `71321f12d664db2c2256663599d71a333321e2050ceebec36c7f56b8abc22f5b` | `sha256sum ~/.openclaw/openclaw.json` = `71321f12d664db2c2256663599d71a333321e2050ceebec36c7f56b8abc22f5b` | 未修改（只读核对） | pass |

Applicable `AGENTS.md` and referenced instructions read:

- `/home/monottx/repos/knowledge-vault-blueprint/AGENTS.md`
- `/home/monottx/repos/knowledge-vault-blueprint/tasks/README.md`
- `/home/monottx/repos/knowledge-vault-blueprint/tasks/2026-08-13-sourcenotes-runtime-foundation/SPEC.md`
- `/home/monottx/repos/knowledge-vault-blueprint/README.md`
- `/home/monottx/repos/knowledge-vault-blueprint/BLUEPRINT.md`
- `/home/monottx/repos/knowledge-vault-blueprint/DECISIONS.md`
- `/home/monottx/repos/knowledge-vault-blueprint/ROADMAP.md`
- `/home/monottx/repos/knowledge-vault-blueprint/specifications/*.md`（全部相关规格）
- `/home/monottx/repos/knowledge-vault-blueprint/skills/vault-capture/SKILL.md` 及 references、scripts
- `/home/monottx/repos/knowledge-vault-blueprint/tests/skills/test_vault_capture.py`、`tests/opencode-harness/*`

基线核对结论：蓝图库除本任务 SPEC 外无其它新漂移；正式/测试 Vault 与 OpenClaw 配置基线全部一致，无重叠用户改动。STEP-01 通过。

## 2. Implementation summary

- **STEP-02 权威架构文档**：BLUEPRINT.md 新增 11.1 运行拓扑（用户→Steward→NotesVaulter，渐进披露/最少确认/受控入口/单层委派）；DECISIONS.md 新增唯一编号决策 D-023（单入口拓扑 + NotesVaulter 三能力 + 附件预算 + incident/ledger 外置），schema_version 保持 1、不覆盖 D-020/D-022；ROADMAP.md 新增「阶段 6：SourceNotes 单入口运行基础（本阶段）」并把 2 GiB 附件闸门落到未来可选方向；新建 `specifications/agent-operations.md`（委派 envelope REQUEST_ID/TASK_TYPE/USER_INTENT/INPUT/TARGET_VAULT_ROLE/WRITE_SCOPE/APPROVAL_STATE/EXPECTED_RESULT/FAILURE_POLICY、返回 envelope、询问时机、输出边界）；openclaw-skill-workflow / upgrade-workflow / git-workflow / capture-workflow 相关小节加入单入口、单层委派、incident/ledger 外置、附件预算与日常 Git 冲突闸门，用链接避免重复。
- **STEP-03 受控入口**：新建 `scripts/sourcenotes_agent.py` —— 只从 `VAULT_ROOT` 读取目标、resolve 后必须是 Git 根且具备必要目录；固定 capture（preflight/stage/ingest/inspect/list-retryable）/ query（search/show/related）/ maintenance（report）命令族，未知命令 exit 2；capture 仅调用/导入既有 `vault_capture.py` 事务（stdin JSON 上限 1 MiB、ID 严格校验）；query 严格只读（拒绝绝对路径/`..`/symlink 逃逸/非 Markdown，query≤500 字符、结果≤20、单摘录≤300、JSON 输出≤256 KiB）；maintenance 严格只读（branch/HEAD/ahead-behind/dirty/staged、failed/manual、缺失引用、附件预算与 2 GiB 闸门）；稳定 JSON envelope、错误不泄露绝对路径。
- **STEP-04 NotesVaulter 三技能**：vault-capture/SKILL.md 改用受控入口 + 单层委派（job_created=true 时同一委派运行内 ingest，不再 spawn worker，保留 duplicate/manual/retry/preflight/Annotation/SSRF/Git 语义）；runtime-contract.md / web-runtime.md 加入受控入口、单层委派与附件去重/告警契约；新建 skills/vault-query/SKILL.md 与 skills/vault-maintenance/SKILL.md（只读、引用 note ID/相对路径、不暴露主机绝对路径）。
- **STEP-05 附件去重与软告警**：vault_capture.py `download_image_assets` 同 Source 事务内按完整 SHA-256 内容去重（相同内容只落一份，所有 token/正文位置映射到该路径，不跨 Source）；单文件 >5 MiB → warning `attachment_over_5MiB`、事务总附件 >30 MiB → warning `attachment_total_over_30MiB`（成功 JSON 稳定 machine-readable，不降 ready、不丢附件）；20 MiB 单图/100 MiB 单篇硬限制不变（先于软告警失败关闭）。
- **STEP-06 Ops 工具**：新建 `scripts/sourcenotes_ops.py` —— `audit`（显式 --vault，正文只计 marker 间去空白/去注释内容，空 scaffold 六类样例不计正文，每项唯一 disposition，不输出正文，默认 stdout JSON，可选 --output 0600）；`validate-manifest`（拒绝重复/遗漏/路径逃逸/ID/canonical/附件冲突）；`migrate --dry-run|--apply`（manifest 精确复制、原子写、保留 bytes/hash、不删源、不 git add/commit/push；repair_then_migrate 未转成 migrate 时拒绝 apply；目标 ID/canonical/path/附件冲突即停）；`health`（复用 maintenance 指标、外部状态文件 0700/0600、2 GiB 闸门）；`ledger`（外部目录追加、原子 0600、秘密扫描拒绝）；`incident`（外部目录、递归秘密扫描失败关闭、0700/0600、允许完整 URL/错误/上下文）。
- **STEP-07 测试**：test_vault_capture.py 新增重复附件一份落盘多引用、5/30 MiB 软告警、20 MiB 硬上限、inline ingest/单层委派 skill 契约测试并更新解释器回退断言；新建 tests/operations/test_sourcenotes_agent.py（query/show/related、只读 index/worktree hash、路径逃逸、输出边界、maintenance 指标、capture 委派）与 test_sourcenotes_ops.py（审计六类样例/唯一 disposition、manifest dry-run/apply/hash/冲突/源不变/不 commit、incident 外置/权限/secret fail closed、health 2 GiB 闸门用 sparse 文件、ledger 权限）。

## 3. Changed files

### knowledge-vault-blueprint

| File | Change and reason | STEP |
|---|---|---|
| `BLUEPRINT.md` | §11.1 新增用户可见运行拓扑（用户→Steward→NotesVaulter）、三能力、渐进披露、最少必要确认、受控入口、单层委派 | STEP-02 |
| `DECISIONS.md` | 决策总表 + 新决策 D-023（单入口拓扑、NotesVaulter 三能力、附件预算 5/30 MiB/2 GiB、incident/ledger 外置）；schema_version 保持 1，不覆盖 D-020/D-022 | STEP-02 |
| `ROADMAP.md` | 新增「阶段 6：SourceNotes 单入口运行基础（本阶段）」，区分本阶段支持与后续正式部署；2 GiB 附件闸门落到未来可选方向 | STEP-02 |
| `specifications/agent-operations.md`（新增） | 委派 envelope（REQUEST_ID/TASK_TYPE/USER_INTENT/INPUT/TARGET_VAULT_ROLE/WRITE_SCOPE/APPROVAL_STATE/EXPECTED_RESULT/FAILURE_POLICY）、返回 envelope、询问用户时机、输出/输入边界 | STEP-02 |
| `specifications/openclaw-skill-workflow.md` | 仓库布局与 allowlist 示例加入 vault-query/vault-maintenance 与 scripts/；新增 4.0 单入口与受控 entrypoint、4.4 附件预算/外部 incident/ledger/日常 Git 冲突闸门 | STEP-02 |
| `specifications/upgrade-workflow.md` | §5 外部操作账本补充工具与秘密边界；新增 5.1 单入口与附件预算 | STEP-02 |
| `specifications/git-workflow.md` | §8 附件加入同 Source 去重、5/30 MiB 软告警、20/100 MiB 硬限制、2 GiB 闸门、日常冲突闸门 | STEP-02 |
| `specifications/capture-workflow.md` | §2 事务图改为单层委派（同一委派运行内 ingest-web）；§6 附件去重与软告警 | STEP-02 |
| `skills/vault-capture/SKILL.md` | 改用受控入口 `sourcenotes_agent.py capture <子命令>`；job_created=true 时同一运行内 inspect+ingest（单层委派，不再 spawn worker）；保留 duplicate/manual/retry/preflight/Annotation/SSRF/Git 语义与附件预算不变量 | STEP-04 |
| `skills/vault-capture/references/runtime-contract.md` | 新增受控入口小节；finalize 加入同 Source 去重与 5/30 MiB 软告警契约；ingest-web 节说明单层委派与 warnings | STEP-04/05 |
| `skills/vault-capture/references/web-runtime.md` | 新增 5.1 附件去重与软告警小节 | STEP-04/05 |
| `skills/vault-capture/scripts/vault_capture.py` | `download_image_assets`：同 Source 事务内完整 SHA-256 去重（唯一实际附件路径，多 token 映射）；新增 5/30 MiB 软告警常量与 warnings 输出；返回类型增加 warnings；cmd_finalize 成功 JSON 增加 `warnings` | STEP-05 |
| `skills/vault-query/SKILL.md`（新增） | 只读 query 技能：只接受 Steward query 委派或明确 Vault 问答；调用受控 query 命令；答案引用 note ID/相对路径；证据不足说明缺口；禁止写入 | STEP-04 |
| `skills/vault-maintenance/SKILL.md`（新增） | 只读 maintenance 技能：调用 maintenance report；只报告不修复；写操作回 Steward 申请批准 | STEP-04 |
| `scripts/sourcenotes_agent.py`（新增） | 受控单入口：capture/query/maintenance 固定命令族，VAULT_ROOT-only，路径安全、输出有界、稳定 JSON envelope | STEP-03 |
| `scripts/sourcenotes_ops.py`（新增） | 运维工具：audit / validate-manifest / migrate(dry-run|apply) / health / ledger / incident，全部外部路径校验、0600/0700、秘密扫描失败关闭 | STEP-06 |
| `tests/skills/test_vault_capture.py` | 图片服务器支持大/中/超限图片；新增去重、5/30 MiB 告警、20 MiB 硬上限、skill 单层委派契约测试；更新解释器回退断言为受控入口形式 | STEP-07 |
| `tests/operations/test_sourcenotes_agent.py`（新增） | query/search/show/related、只读 index/worktree hash、路径逃逸、输出边界、maintenance 指标、capture 委派与 ID 校验 | STEP-07 |
| `tests/operations/test_sourcenotes_ops.py`（新增） | 审计六类样例/唯一 disposition/正文不泄露；manifest 校验与迁移 dry-run/apply/hash/冲突/源不变/不 commit；incident 外置/权限/secret fail closed；health 2 GiB sparse 闸门；ledger 追加/权限 | STEP-07 |
| `tasks/2026-08-13-sourcenotes-runtime-foundation/EXECUTION.md` | 本执行记录 | STEP-01/09 |

### SourceNotes

| File | Change and reason |
|---|---|
| none | 本任务禁止触碰正式 Vault；未修改 |

## 4. Acceptance evidence

| Criterion | Result | Evidence |
|---|---|---|
| `AC-01 架构清晰` | pass | BLUEPRINT.md §11.1 拓扑 + D-023（编号唯一、schema 仍为 1、D-020/D-022 未覆盖）；VAL-07 `git diff --check` exit 0；VAL-08 仅允许路径 |
| `AC-02 Capture 兼容` | pass | VAL-01 test_vault_capture.py 28 项 OK exit 0；VAL-02 test_web_extract.py 34 项 OK exit 0（第二轮，chromium 1228 已装）；VAL-03 network_security 54 项 OK；VAL-05 harness 19 PASS/0 FAIL；不自动 commit/push（既有断言 + VAL-08 cached 空）；失败保留 stub 语义未改 |
| `AC-03 单层委派` | pass | SKILL.md 断言（test_skill_single_delegation_inline_ingest：`sourcenotes_agent.py capture ingest`、`单层委派`、无 `sessions_spawn`）+ VAL-01 通过 + VAL-05 同步/异步 envelope 契约通过 |
| `AC-04 受控入口` | pass | VAL-04：未知命令/未知子命令 exit 2、路径穿越/绝对路径/非 Markdown 拒绝、超限 query 拒绝均有测试 |
| `AC-05 Query` | pass | VAL-04：search/show/related 返回 id+相对路径+有界摘录；只读断言（index/worktree hash 前后一致、HEAD 不变） |
| `AC-06 Maintenance` | pass | VAL-04：branch/HEAD/ahead-behind/dirty/staged、failed/manual 计数与列表、缺失引用、附件预算与 gate_2GiB=False 均断言 |
| `AC-07 审计正确` | pass | VAL-04：六类 scaffold 样例 disposition 均为 no_markers/empty（不计正文），真实 marker 正文为 body；每项唯一 disposition；正文不泄露 |
| `AC-08 迁移安全` | pass | VAL-04：dry-run/apply 在临时仓库证明 manifest 定向复制、src/dst hash 相等、链接/附件复制、二次 apply 冲突停止、源库不变、目标无 stage/commit、HEAD 不变；repair_then_migrate 拒绝 apply |
| `AC-09 附件策略` | pass | VAL-01：重复附件一份落盘多引用（asset_paths==1 且正文两处映射同一路径）；5/30 MiB 只产生 warning 且 ready；20 MiB 硬上限仍失败关闭；VAL-04 health 2 GiB sparse 闸门 True |
| `AC-10 Incident/ledger` | pass | VAL-04：外部路径拒绝（vault 内/蓝图库内）、0700/0600 权限断言、完整 URL 允许、secret fail closed（bundle 未创建）、ledger 追加/权限/秘密拒绝 |
| `AC-11 范围与质量` | pass | VAL-07 `git diff --check` exit 0；VAL-08 仅允许路径、cached 空、未 stage/commit；VAL-09 正式 Vault clean、测试 Vault 冻结状态、OpenClaw config hash 一致（两轮均复核） |

## 5. Validation log

工作目录：`/home/monottx/repos/knowledge-vault-blueprint`（除 VAL-09 在对应 Vault 目录）

| Validation | Exact command or inspection | Exit/result | Evidence summary |
|---|---|---|---|
| VAL-01 | `python3 tests/skills/test_vault_capture.py` | 0 | `Ran 28 tests ... OK` |
| VAL-02 | `python3 tests/skills/test_web_extract.py` | 0 | **首次运行 exit 1**（`Ran 34 tests ... FAILED (errors=3)`，均为 Playwright 真实浏览器测试：`web_extract.ExtractionError: Browser is not available; install Chromium`；根因：环境 playwright 1.61.0 需要 chromium build 1228，`~/.cache/ms-playwright` 仅有 1234）。**用户授权安装 chromium/headless-shell build 1228（`python3 -m playwright install chromium`）后重跑：`Ran 34 tests ... OK`，exit 0**。`web_extract.py` 与 `test_web_extract.py` 全程未被改动（git diff 不含） |
| VAL-03 | `python3 tests/skills/test_network_security.py` | 0 | `Ran 54 tests ... OK` |
| VAL-04 | `python3 -m unittest discover -s tests/operations -p 'test_*.py'` | 0 | `Ran 22 tests ... OK`（agent 11 + ops 11） |
| VAL-05 | `bash tests/opencode-harness/test_capture_debug.sh` | 0 | `通过 19 项，失败 0 项`；A–F 与 (a)–(f) 全部 PASS |
| VAL-06 | `python3 -m py_compile scripts/sourcenotes_agent.py scripts/sourcenotes_ops.py` | 0 | `PYCOMPILE_EXIT=0` |
| VAL-07 | `git diff --check` | 0 | 无输出（`DIFFCHECK_EXIT=0`） |
| VAL-08 | `git status --short --branch && git diff --name-status && git diff --cached --name-status` | 0 | 仅允许路径（12 个 M + 7 个 ?? 均在允许路径内）；`git diff --cached --name-status` 为空（cached 空，未 stage/commit） |
| VAL-09 | 只读复核正式 Vault / 测试 Vault / OpenClaw 配置 | pass | SourceNotes：`main@ec1a90eb9d41df77cf74e44d51e703d0379882e7` clean porcelain=0；SourceNotes-test：`main@ec1a90eb9d41df77cf74e44d51e703d0379882e7` 冻结脏状态 porcelain=164/cached=154（既有 staged 资产）；OpenClaw config SHA-256=`71321f12d664db2c2256663599d71a333321e2050ceebec36c7f56b8abc22f5b` —— 均与 STEP-01 一致 |

## 5.1 Blocker 解除与全套重跑（第二轮）

用户已在环境中成功执行 `python3 -m playwright install chromium`（`~/.cache/ms-playwright` 现含 chromium-1228、chromium_headless_shell-1228，`p.chromium.executable_path` 指向 `chromium-1228/chrome-linux64/chrome`）。

- 先只读复核：蓝图库 `main@badfd519b85c4d80c7875cbf7cbe23afc340c35f`，变更集与第一轮一致（12 个 M + 7 个 ??，cached=0，未 stage/commit）；SourceNotes clean；SourceNotes-test 冻结状态 porcelain=164/cached=154；OpenClaw config hash `71321f12…` —— 全部无意外漂移。
- 重跑 VAL-02 → exit 0（34 项 OK），原阻塞解除。
- 为避免环境安装后隐藏回归，重跑全套：
  - VAL-01 `python3 tests/skills/test_vault_capture.py` → exit 0，`Ran 28 tests ... OK`
  - VAL-02 `python3 tests/skills/test_web_extract.py` → exit 0，`Ran 34 tests ... OK`
  - VAL-03 `python3 tests/skills/test_network_security.py` → exit 0，`Ran 54 tests ... OK`
  - VAL-04 `python3 -m unittest discover -s tests/operations -p 'test_*.py'` → exit 0，`Ran 22 tests ... OK`
  - VAL-05 `bash tests/opencode-harness/test_capture_debug.sh` → exit 0，`通过 19 项，失败 0 项`
  - VAL-06 `python3 -m py_compile scripts/sourcenotes_agent.py scripts/sourcenotes_ops.py` → exit 0
  - VAL-07 `git diff --check` → exit 0，无输出
  - VAL-08 `git status --short --branch` + `git diff --name-status` + `git diff --cached --name-status` → 仅允许路径，cached 空
  - VAL-09 只读复核 → SourceNotes `ec1a90e` clean（porcelain=0）；SourceNotes-test `ec1a90e` porcelain=164/cached=154（冻结状态不变）；OpenClaw config hash `71321f12…` 不变
## 5.2 Reviewer round-1 fixes（FIX-F01..F08，第三轮）

Reviewer 返回 `CHANGES_REQUESTED`（FIX-F01..F08）。以下按 finding 记录根因/修复/测试/证据；未扩大范围，未修改 SPEC/REVIEW。

| Finding | 根因 | 修复 | 新增/更新测试 | 证据 |
|---|---|---|---|---|
| FIX-F01 migration 全事务 | 原 migrate 逐 entry 写，后续冲突会留下前序部分迁移 | `plan_migration` 先完成全部 manifest 语义、源文件读取与 source hash、目标路径安全、目标 ID/canonical/path/附件冲突的完整预检，任一失败目标零变化；`execute_migration` 先把全部输出写入 target Vault 内受控临时 staging 目录（`.sourcenotes-migrate-*`，随 finally 删除），再以 `_publish_file` 可回滚发布，任一 publish/hash 失败调用 `rollback_publish` 恢复目标到调用前字节/不存在状态，并清理新建空父目录；不 reset/clean、不 git add/commit | `test_migrate_all_or_nothing_on_any_conflict`（entry A 可迁移、entry B 冲突 → apply 后 A 全部路径不存在、B 原文件不变、无 staging 残留、源不变）；`test_migrate_rolls_back_on_publish_failure`（in-process patch `_publish_file` 第 2 项抛 OSError → 全部目标路径不存在、无 staging 残留） | VAL-R1-04 37 项 OK |
| FIX-F02 target symlink/路径逃逸 | 目标 `sources`/`assets` 若为 symlink 可写 Vault 外 | `check_target_path_safety`：逐相对组件检查 symlink（含最终路径），拒绝后 resolve 必须 `relative_to(target.resolve())`；staging 与 rollback 均在 target Vault 内且路径安全；冲突预检中 symlink 检查先于 exists 检查，避免被遮蔽 | source/annotation/attachment 三个 symlink 逃逸代表测试 + 最终目标 symlink 测试；外部 sentinel 保持不变 | VAL-R1-04 37 项 OK |
| FIX-F03 ledger 必须绑定 Vault | ledger 可不传 `--vault` 从而写 Vault 内 | dispatch 强制 `--vault`（`ensure_git_root` 校验 Git Vault 根），`require_external_dir` 校验输出同时在 Vault 与蓝图库外 | `test_ledger_requires_vault`（缺 --vault 失败且不创建）；`test_ledger_rejects_blueprint_dir`；既有 Vault 内路径与合法外部路径测试保持 | VAL-R1-04 37 项 OK |
| FIX-F04 query symlink 读取 | search 的 rglob 可读取 Vault 外 symlink Markdown | `ensure_path_safe` 对 path 本身与所有相对父组件检查 symlink（fail closed，稳定错误「Vault contains a symlinked note path」）并校验 resolve 在 vault 内；`iter_markdown` 改用 `os.walk(followlinks=False)` 且与 `safe_vault_path` 共享同一检查（search/show/related 统一） | `test_query_fails_closed_on_symlinked_note_file`（search/related/show 均 exit 2 且外部 secret 不出现）；`test_query_never_reads_symlinked_directory`（secret 不出现、结果为空） | VAL-R1-04 37 项 OK |
| FIX-F05 全命令输出总上限 | 256 KiB 上限未统一覆盖 show 等 envelope，超长 frontmatter 可放大 JSON | 新增 `cap_str`/`cap_value` 字段上限（id≤128、title/type≤300、path≤512、error≤500、details≤500）；`emit` 成为唯一出口并在 stdout 前强制 UTF-8 byte 上限，超限输出短安全错误（`Output limit exceeded`）并返回非 0；query 结果仍先经 `bounded_output` 截断列表 | `test_query_caps_oversized_frontmatter_fields`（5000 字符 id/title → 结果 id≤129、title≤301、单 JSON <256 KiB）；`test_query_related_bounded`（25 条关联 → count==20）；`test_emit_global_output_cap_returns_short_safe_error`（in-process 300 KiB payload → 非 0 退出 + 短错误 + 合法单 JSON <256 KiB） | VAL-R1-04 37 项 OK |
| FIX-F06 maintenance 按 Source 聚合 30 MiB | 原按 `assets/images` 总目录聚合，跨 Source 错报 | 只按 `assets/images/<source-id>/` 直接子目录分别统计 physical file bytes，每 Source 独立判断 >30 MiB；根散落/未知结构文件单独 `unassigned_count`/`unassigned_paths` 报告，不混入 Source；2 GiB 闸门按全部附件总字节 | `test_maintenance_per_source_30MiB_and_unassigned`（两 Source 各 20 MiB 不触发、单 Source 31 MiB 触发、根散落文件 unassigned 不误算） | VAL-R1-04 37 项 OK |
| FIX-F07 incident 文件名/路径秘密 | 只扫内容，manifest 保存原始 source path，文件名可泄露 secret | 在 bundle 创建前扫描 operator 元数据字符串、诊断 source 路径文本、文件 basename、文件内容；新增 `FILENAME_SECRET_RE` 与 `scan_filename`（仅用于路径/文件名，不影响 ledger/metadata 内容级扫描）；命中整体失败关闭、bundle 零创建；manifest 只保存生成的安全 artifact 名（`diag-NNNN.<safesuffix>`）+ sha256 + bytes，绝不保存原始绝对路径/basename | `test_incident_secret_filenames_fail_closed_with_zero_bundle`（`diag-token=abc.log`、`diag-password-x.log`、`diag-bearer-token.log`、`sk-...` 均失败且外部目录不存在）；更新合法 incident 测试断言 artifact 名且原始路径/basename 不出现在 manifest | VAL-R1-04 37 项 OK |
| FIX-F08 30 MiB 去重预算语义 | 重复下载字节被重复计入 30 MiB warning | 锁定：预算按物理落盘唯一附件字节；`download_total`（100 MiB 硬上限，下载字节语义不变）与 `physical_total`（仅新 SHA 首次进入物理附件集合时计入）分离；重复 token 映射不重复计数；5 MiB 单文件 warning 仅对新物理文件触发；20 MiB 单图硬限制不变 | `test_finalize_duplicate_large_images_budget_physical_unique_bytes`（两个相同 16 MiB → 一份落盘、预算 16 MiB、不触发 30 MiB、两处引用同一路径、仅一次暂存）；既有两不同 16 MiB → 32 MiB 触发测试保持 | VAL-R1-01 29 项 OK |
| 参考/规范措辞 | runtime-contract.md / web-runtime.md / git-workflow.md / DECISIONS.md D-023 的 30 MiB 表述可被解读为重复计数 | 统一改为「物理落盘唯一附件字节（重复 token 映射不重复计入）」，100 MiB 明确为下载字节语义 | — | 人工核对 + VAL-R1-07 |

第三轮验证（工作目录 `/home/monottx/repos/knowledge-vault-blueprint`）：
- VAL-R1-01 `python3 tests/skills/test_vault_capture.py` → exit 0，`Ran 29 tests ... OK`
- VAL-R1-02 `python3 tests/skills/test_web_extract.py` → exit 0，`Ran 34 tests ... OK`
- VAL-R1-03 `python3 tests/skills/test_network_security.py` → exit 0，`Ran 54 tests ... OK`
- VAL-R1-04 `python3 -m unittest discover -s tests/operations -p 'test_*.py'` → exit 0，`Ran 37 tests ... OK`（agent 17 + ops 20）
- VAL-R1-05 `bash tests/opencode-harness/test_capture_debug.sh` → exit 0，`通过 19 项，失败 0 项`
- VAL-R1-06 `python3 -m py_compile scripts/sourcenotes_agent.py scripts/sourcenotes_ops.py` → exit 0
- VAL-R1-07 `git diff --check` → exit 0，无输出
- VAL-R1-08 `git status --short --branch` + `git diff --name-status` + `git diff --cached --name-status` → 仅允许路径（12 个 M + 7 个 ??），cached 空，未 stage/commit
## 5.3 Reviewer round-2 fixes（F-01/F-02/F-04/F-08，第四轮）

Reviewer round-2 返回 `CHANGES_REQUESTED`（F-01..F-08 中的 4 项）。以下按 finding 记录根因/修复/测试/证据；未扩大范围，未修改 SPEC/REVIEW。

| Finding | 根因 | 修复 | 新增/更新测试 | 证据 |
|---|---|---|---|---|
| F-01 publish 后 hash 异常未 rollback | 原实现中 publish 后 `sha256_file()` 异常直接逃出，未触发 rollback，目标文件与 staging 残留 | `execute_migration` 改为统一事务：staging、publish、publish 后 hash/size 验证（`_verify_published` 锚定 `O_NOFOLLOW` 读取）、证据组装全部在单个 try 内；`except BaseException` 统一触发 `rollback_transaction`（已发布文件 unlink、本轮新建父目录逆序 rmdir、staging 树整体删除；调用前不存在的路径恢复为不存在）；rollback 错误被收集，任一存在即抛 `Migration failed and rollback incomplete`（含 `rollback_errors`），绝不伪报成功；成功路径同样清理 staging 树 | `test_migrate_post_publish_verify_failure_rolls_back_zero_residue`（patch `_verify_published` 第 3 次读取抛错 → 全部目标文件/新建父目录 `assets/images`/staging 零残留）；`test_migrate_reports_rollback_incomplete`（patch `_unlink_anchored` 抛错 → 非 0 且 `rollback incomplete` + `rollback_errors`）；更新 `test_migrate_rolls_back_on_publish_failure`（patch `_publish_link`，捕获真实函数避免 mock 递归） | VAL-R2-04 42 项 OK；VAL-R2-10 2 项 OK |
| F-02 target symlink TOCTOU | 预检后 publish 前 parent 可被换成 symlink；字符串路径 mkdir/os.replace 可越界 | 锁定 descriptor-anchored 实现（标准库/Linux）：`root_fd = os.open(target, O_RDONLY\|O_DIRECTORY\|O_NOFOLLOW)`；所有相对路径逐组件 `dir_fd` + `O_DIRECTORY\|O_NOFOLLOW` 打开/创建（`open_rel_dir`/`ensure_target_parents`，拒 symlink/非目录）；publish 用同文件系统 staging 文件到目标的 `os.link(..., src_dir_fd, dst_dir_fd, follow_symlinks=False)` 原子 no-clobber（EEXIST → 并发冲突失败 + rollback，绝不覆盖），随后 unlink staging；发布后 hash/size 通过锚定 parent dir_fd + `O_NOFOLLOW` 读取（`read_rel_bytes_anchored`）；rollback 删除用锚定 dir_fd（`_unlink_anchored`/`_rmdir_anchored`），新建目录逆序 `rmdir(dir_fd=...)`，目录非空（并发写入）→ 收集为 rollback incomplete；staging 为 target 内随机 0700 目录且经 root fd 创建；目录枚举经 `/proc/self/fd/<fd>` 锚定（本构建 `os.listdir` 无 dir_fd 支持）；fd 全部 finally 关闭 | `test_migrate_toctou_parent_symlink_fails_closed`（publish 前 hook 将 `notes/annotations` 换成指向外部 sentinel 目录的 symlink → apply 抛错、外部零写、目标无部分迁移/staging 残留）；`test_migrate_concurrent_target_never_overwritten`（publish 前并发创建同名目标 → no-clobber 失败、并发文件字节不变、无残留）；既有 symlink 逃逸测试（source/annotation/attachment/最终路径）保持 | VAL-R2-04 42 项 OK；VAL-R2-11 2 项 OK |
| F-04 symlink 目录静默跳过 | `os.walk(followlinks=False)` 静默跳过 Vault 内 symlink 目录 → ok/count0 不完整结果 | `iter_markdown` 在遍历中检查每个进入查询范围的目录项：非 SKIP_DIRS 的 symlink 目录 → 抛稳定安全错误 `Vault contains a symlinked directory; refusing to read`（exit 2，fail closed）；SKIP_DIRS（`.git`/`.obsidian`/`.queue`/`assets` 等）按契约完全排除，内部 symlink 不失败；search/show/related 共用同一遍历与 `ensure_path_safe` | 更新 `test_query_fails_closed_on_symlinked_directory`（原 ok/count0 测试改为 search/related 均 exit 2 且外部 secret 不出现）；新增 `test_query_ignores_symlinks_inside_excluded_dirs`（`.obsidian`/`assets` 内 symlink 不失败、正常结果返回） | VAL-R2-04 42 项 OK |
| F-08 契约措辞未全同步 | SKILL.md / agent-operations.md / capture-workflow.md / openclaw-skill-workflow.md / upgrade-workflow.md / git-workflow.md / ROADMAP.md 的 30/100/20 MiB 表述未统一 | 统一为：30 MiB 按同 Source **物理落盘唯一附件字节**（重复 token/正文位置不重复计入）；100 MiB 为该文章**下载字节**硬上限（重复下载仍计入）；20 MiB 为单下载图片硬上限；保留 DECISIONS/runtime-contract/web-runtime 已同步措辞；未改历史任务记录 | — | 全局 grep（`30 MiB|100 MiB|20 MiB`）逐文件人工核对 + VAL-R2-07 |

第四轮验证（工作目录 `/home/monottx/repos/knowledge-vault-blueprint`）：
- VAL-R2-01 `python3 tests/skills/test_vault_capture.py` → exit 0，`Ran 29 tests ... OK`
- VAL-R2-02 `python3 tests/skills/test_web_extract.py` → exit 0，`Ran 34 tests ... OK`
- VAL-R2-03 `python3 tests/skills/test_network_security.py` → exit 0，`Ran 54 tests ... OK`
- VAL-R2-04 `python3 -m unittest discover -s tests/operations -p 'test_*.py'` → exit 0，`Ran 42 tests ... OK`（agent 18 + ops 24）
- VAL-R2-05 `bash tests/opencode-harness/test_capture_debug.sh` → exit 0，`通过 19 项，失败 0 项`
- VAL-R2-06 `python3 -m py_compile scripts/sourcenotes_agent.py scripts/sourcenotes_ops.py` → exit 0
- VAL-R2-07 `git diff --check` → exit 0，无输出
- VAL-R2-08 `git status --short --branch` + `git diff --name-status` + `git diff --cached --name-status` → 仅允许路径（12 个 M + 7 个 ??），cached 空，未 stage/commit
- VAL-R2-09 只读复核 → SourceNotes `main@ec1a90eb9d41df77cf74e44d51e703d0379882e7` clean（porcelain=0）；SourceNotes-test `main@ec1a90eb9d41df77cf74e44d51e703d0379882e7` 冻结状态 porcelain=164/cached=154（未触碰）；OpenClaw config SHA-256=`71321f12d664db2c2256663599d71a333321e2050ceebec36c7f56b8abc22f5b` 不变
- VAL-R2-10 定向复现 reviewer 的 post-publish-hash 读取失败 → 目标文件/新建父目录/staging 零残留（`test_migrate_post_publish_verify_failure_rolls_back_zero_residue`、`test_migrate_reports_rollback_incomplete`）→ 2 项 OK
- VAL-R2-11 定向 TOCTOU parent symlink + 并发同名目标 no-clobber（`test_migrate_toctou_parent_symlink_fails_closed`、`test_migrate_concurrent_target_never_overwritten`）→ 2 项 OK


## 6. Assumptions

- `test_web_extract.py` 的 3 个 Playwright 浏览器测试在第一轮运行中因环境缺失 chromium build 1228 无法通过（`web_extract.py` 与 `test_web_extract.py` 均未改动）；用户已授权并执行 `python3 -m playwright install chromium`，第二轮重跑全部通过，该假设已消除。
- reviewer round-1 的 FIX-F01..F08 均在允许路径内完成，未改变 manifest 契约、阈值或架构。

## 7. Deviations from specification

- `none`（实现与简报 STEP-01..09 一致；第一轮 VAL-02 的 3 项环境依赖失败已在用户安装 chromium 1228 后解除；第三轮按 reviewer round-1 findings、第四轮按 reviewer round-2 findings 修订，均未偏离批准范围与允许路径）

## 8. Unresolved risks and blockers

- **BLOCKER-1（已解除）**：VAL-02 的 3 个 Playwright 浏览器测试第一轮失败（`web_extract.ExtractionError: Browser is not available; install Chromium`，playwright 1.61.0 需 chromium build 1228 而环境仅有 1234）。用户已在环境中执行 `python3 -m playwright install chromium` 安装 build 1228；第二/三/四轮重跑均 exit 0。
- 当前无未解决的阻塞项。

## 9. Git state at handoff

| Repository | Branch | HEAD | `git status --short` | Commit created? |
|---|---|---|---|---|
| `knowledge-vault-blueprint` | `main` | `badfd519b85c4d80c7875cbf7cbe23afc340c35f` | 仅允许路径未跟踪/已修改变更；index 无 cached | `no` |
| `SourceNotes` | `main` | `ec1a90eb9d41df77cf74e44d51e703d0379882e7` | clean | `no` |
| `SourceNotes-test` | `main` | `ec1a90eb9d41df77cf74e44d51e703d0379882e7` | 冻结脏状态（既有 staged 资产，未触碰） | `no` |

## 10. Handoff

- Status: `ready_for_review`（实现完成；第四轮按 reviewer round-2 findings 闭环 F-01/F-02/F-04/F-08，全套 VAL-R2-01..11 通过）
- Recommended reviewer action: 复核 §5.3 的 F-01/F-02/F-04/F-08 根因/修复/测试证据与 VAL-R2 全套结果（含 descriptor-anchored no-clobber/rollback 与 TOCTOU 定向测试）
