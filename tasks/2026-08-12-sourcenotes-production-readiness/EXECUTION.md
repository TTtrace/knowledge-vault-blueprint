---
task_id: 2026-08-12-sourcenotes-production-readiness
status: ready_for_review
execution_round: 3
spec_version: 2
executor: executor
spec_path: ./SPEC.md
started_at: 2026-08-12T23:52:00+08:00
finished_at: 2026-08-13T01:40:00+08:00
round_2_started_at: 2026-08-13T01:20:00+08:00
v2_started_at: 2026-08-13T02:00:00+08:00
v2_finished_at: 2026-08-13T02:40:00+08:00
---

# Execution Record

> 本文件由 executor 所有。不得修改已批准的 `SPEC.md`，也不得在这里写 reviewer verdict。

## 1. Preflight

读取了 AGENTS.md、README.md、BLUEPRINT.md、DECISIONS.md、ROADMAP.md、tasks/README.md、SPEC.md 及两份现有规范（openclaw-skill-workflow.md、git-workflow.md）。基线核对：

- 蓝图库工作树 `/home/monottx/orca/workspaces/knowledge-vault-blueprint/正式运行SourceNotes`：branch `正式运行SourceNotes`，HEAD `f9810f1ff454aaa4c7d0561a0d4dec1ca5bd5128`。批准前除 planner 创建的本任务 3 个控制文件（SPEC/EXECUTION/REVIEW）外 clean。生产蓝图 checkout `/home/monottx/repos/knowledge-vault-blueprint`（main@f9810f1...）存在用户既有未提交改动，只读、不在本阶段范围、保持原样。
- 正式 Vault `/home/monottx/repos/SourceNotes`：`main` HEAD `ec1a90eb9d41df77cf74e44d51e703d0379882e7`，clean，remote 未变。
- 测试 Vault `/home/monottx/repos/SourceNotes-test`：`main` HEAD `ec1a90eb9d41df77cf74e44d51e703d0379882e7`；porcelain 134 条（124 staged `A `、1 unstaged ` M`、9 untracked `??`）；show-ref 排序 SHA-256 `d4687620...`；index SHA-256 `286d6c7d...`；porcelain-z SHA-256 `0b42e19a...`。顶层计数 assets 106、sources 24、notes 2、dashboards 1、`.archive` 1。
- OpenClaw `2026.7.1-2`；tasks running=0、queued=0（历史已完成任务 114 条，无运行中/排队中）；config valid；Gateway systemd active；`vault-capture.enabled=true`；`VAULT_ROOT=/home/monottx/repos/SourceNotes-test`（位于 `skills.entries.vault-capture.env.VAULT_ROOT`）。

基线全部符合 SPEC §5。

## 2. Implementation summary

阶段 0 仅做：安全冻结（测试库 push 防护 + OpenClaw 维护模式）、外部私有快照/备份、外部迁移审计、蓝图文档决策更新。未迁移数据、未改 skill/tests、未部署 production Vault、未做任何 Git 写动作。

## 3. Changed files

### 蓝图库（/home/monottx/orca/workspaces/knowledge-vault-blueprint/正式运行SourceNotes）
- `BLUEPRINT.md`：§10 Git 与备份、§11 OpenClaw Skill 交付改为 Linux 单自动写入者、同 checkout、main commit、last-known-good、临时 `*-test` Vault、维护模式验证、软件/数据回退分离。STEP-05。
- `DECISIONS.md`：新增 D-020（个人单用户 commit-based 简化发布，取代 D-015 现行流程）、D-021（Vault 数据单调保留、软件/数据回退分离、三类 schema 约束）；D-015 加 superseded 注记但正文保留；决策总表新增两行。round 2：D-013 增加 supersession 注记，明确“稳定标签”检出规则以 D-020 为准。STEP-05。
- `ROADMAP.md`：阶段 2 的 RC/tag/双 checkout 项改为简化 commit-based 流程；升级规则补长期浸泡与数据单调保留。STEP-05。
- `specifications/openclaw-skill-workflow.md`：§1/§4 去除“稳定标签/RC 强制”表述；§7 发布/部署/回滚整节重写为 `main+commit+last_known_good` 简化流程，明确同 checkout 不得同时加载不同版本、更新前维护模式、失败恢复配置并停止；§8 检查表同步更新。STEP-05。
- `specifications/git-workflow.md`：新增 §5 跨平台 Git 约束（Windows/macOS/Linux/Android 大小写、保留名、尾随字符、LF、symlink、设备状态忽略、Linux 唯一写入者）、§6 普通软件回退边界；§4 单写入者改为 Linux 唯一自动写入者 + `pull --ff-only`；后续章节重编号。STEP-05。
- `specifications/upgrade-workflow.md`：新增升级与回退规范（术语、升级前检查、同 checkout 更新验证、canary/soak、外部操作账本、回退、三类 schema 策略、灾难恢复区分）。STEP-05。
- `tasks/2026-08-12-sourcenotes-production-readiness/EXECUTION.md`：本记录。STEP-06。
- （未修改 SPEC.md、REVIEW.md）

### 测试库（/home/monottx/repos/SourceNotes-test）
- `.git/config`：为 `origin` 设置本地 push URL `disabled://SourceNotes-test`（fetch URL 保持原值）。STEP-03。

### OpenClaw（~/.openclaw/openclaw.json）
- `skills.entries.vault-capture.enabled`：`true -> false`（round 1 授权维护模式切换）。
- `skills.entries.vault-capture.env.VAULT_CAPTURE_BROWSER_PROFILE`：round 1 意外丢失，round 2 从备份恢复原值（保持 enabled=false）。STEP-03 + round 2 F-01 修复。

### 外部私有目录（/home/monottx/.local/state/sourcenotes-production-readiness/2026-08-12/**）
- `baseline-manifest.json`、`openclaw.json.backup`、`openclaw-config-summary.json`、`sourcenotes-test-full-snapshot.tar`、`snapshot-member-list.txt`、`sha256-manifest.json`、`RECOVERY.md`、`git-config-before-freeze.txt`、`audit-tool.py`、`migration-audit.json`、`migration-audit.md`。STEP-02/04。
- round 2 新增：`round2-postfix-f01-evidence.json`、`round2-browser-profile-hash.txt`（脱敏证据，不含值本身）。

## 4. Acceptance evidence

- **AC-01 — 简化版本身份：PASS（round 2）**。DECISIONS.md 新增 D-020，明确 `main+commit hash+last_known_good`，不强制 RC/正式标签/双 checkout；D-015 标注被 D-020 取代并保留正文；round 2 为 D-013 增加 supersession 注记，明确“稳定标签”检出规则以 D-020 为准（VAL-02 人工核对 + VAL-03）。
- **AC-02 — 同 checkout 安全验证：PASS**。openclaw-skill-workflow §7 定义同 checkout 维护模式更新验证、`*-test` 临时 Vault、验证失败恢复配置并停止、同 checkout 不得同时加载不同版本（VAL-02/03）。
- **AC-03 — 数据单调保留：PASS**。D-021 + git-workflow §6 + upgrade-workflow §6 明确“回退软件不回退知识库时间线”，禁止 destructive reset/clean、旧快照覆盖、删除浸泡期内容（VAL-02/03）。
- **AC-04 — 一周浸泡回退：PASS**。upgrade-workflow 定义 checkpoint、soak 期正常捕获/手写/sync、失败先保护 Vault、新提交回退、恢复配置、协调队列、验证数据仍在（VAL-02）。
- **AC-05 — schema 分级：PASS**。D-021 边界 + upgrade-workflow §7 三类 schema 策略、breaking 需双读 Adapter 或可逆幂等迁移、逆向迁移遇后续编辑停止、保护不变量（VAL-02）。
- **AC-06 — 外部证据：PASS**。upgrade-workflow §5 定义不含正文的 operation ledger / incident bundle 位于 Vault 与蓝图库之外，关联 blueprint commit/Vault HEAD/Source ID/run/task/session/路径（VAL-02）。
- **AC-07 — 四平台 Git 约束：PASS**。git-workflow §5 覆盖大小写/保留名/尾随字符/LF/symlink/设备状态/Android 只读 + `pull --ff-only` + Linux 唯一写入者（VAL-02）。
- **AC-08 — 正式 Vault 未触碰：PASS**。VAL-05：HEAD `ec1a90e...`，branch/upstream 不变，工作树与 index 干净，无 stage/commit。
- **AC-09 — 测试库 push 防护：PASS**。VAL-06：HEAD/show-ref/index/porcelain 哈希与 134 条分类全部与变更前一致；VAL-07：fetch 原值，push=`disabled://SourceNotes-test`。
- **AC-10 — OpenClaw 维护模式：PASS（round 2）**。round 2 修复 F-01 后：修改前 running=queued=0；配置备份存在（openclaw.json.backup，sha `3b89f01f...`）；恢复 `VAULT_CAPTURE_BROWSER_PROFILE` env 键原值后，备份 vs 当前全量结构化脱敏 diff 仅剩 enabled true→false 与 `.meta.lastTouchedAt`（工具时间戳）；config validate 通过；runtime disabled=true、eligible=false；VAULT_ROOT 未变；恢复后 env_keys 与备份完全一致（5 键）。详见 DEVIATIONS 与 round2-postfix-f01-evidence.json。
- **AC-11 — 可恢复私有快照：PASS**。VAL-09：sha256 --check 全 OK，tar 可读，目录 0700/敏感文件 0600；RECOVERY.md 说明不执行 destructive restore、恢复需用户单独授权。
- **AC-12 — 完整迁移审计：PASS**。VAL-10：Source=24、Annotation=2，每项恰一个处置分类；报告区分真实数据与测试产物。
- **AC-13 — 附件与运行残留审计：PASS**。VAL-10/11：附件=147、总量 48752091 B、扩展名分布、重复组（5 组 SHA-256）、极小 9、大文件 4、大 GIF 7、queue 25/终态 25、archive 17/关联 x405、lock 1、重复 Source ID 无、重复 canonical 无。
- **AC-14 — 隐私与范围：PASS**。VAL-03 隐私扫描：蓝图文档无正文/逐篇 URL/trajectory/secret；VAL-11：审计 JSON/MD 无完整 URL/正文/secret；VAL-01 变更仅限允许路径。
- **AC-15 — 无未授权 Git/外部动作：PASS**。VAL-01/05/06：未 branch/tag/stage/commit/push/pull/merge/rebase/reset/clean；未改正式 remote；FINAL_STATE 无任何 stage/commit。
- **AC-16 — 基础质量：PASS（round 2）**。VAL-03 相对链接全有效（rerun）；VAL-04 `git diff --check` exit 0（rerun）；VAL-02 当前规范互相一致（D-015/D-013 supersession、发布流程、upgrade、Git 四平台），现行规范无未标注的 tag/RC/双 checkout 强制冲突。

## 5. Validation log

| ID | 工作目录 | 命令 | 退出码 | 关键输出 |
|---|---|---|---|---|
| VAL-01 | 蓝图库 | `git status --short --branch && git rev-parse HEAD && git diff --name-only` | 0 | HEAD f9810f1...；仅允许文档 + upgrade-workflow.md + 任务目录；round 2 仅 DECISIONS.md 增加变化（D-013 注记） |
| VAL-02 | 蓝图库 | 人工逐节核对 D-015/D-013 supersession、当前发布流程、upgrade-workflow、Git 四平台、tag/RC 扫描 | manual | 满足 AC-01–07/16；历史决策保留；所有 tag/RC/staging 表述均为历史或被取代，无未标注现行强制冲突 |
| VAL-03 | 蓝图库 | Python 相对链接检查 + 隐私扫描 | 0 | 6 份文档相对链接 ALL OK；无正文/URL/trajectory/secret |
| VAL-04 | 蓝图库 | `git diff --check` 及 `--cached --check` | 0 | 无输出 |
| VAL-05 | 正式 Vault | `git status --short --branch && git rev-parse HEAD && git remote -v && git diff --stat && git diff --cached --stat` | 0 | HEAD ec1a90e...，`## main...origin/main`，remote 原值，diff 空 |
| VAL-06 | 测试 Vault | 对比变更前后 HEAD/show-ref/index/porcelain 哈希与计数 | 0 | 前后完全一致：HEAD ec1a90e...，show-ref d4687620...，index 286d6c7d...，porcelain 0b42e19a...，134（124/1/9） |
| VAL-07 | 测试 Vault | `git remote get-url origin` / `--push origin` | 0 | fetch=`git@github.com:TTtrace/SourceNotes.git`；push=`disabled://SourceNotes-test` |
| VAL-08 | OpenClaw | config validate / enabled / VAULT_ROOT / skills info / health / daemon / tasks | 0 | **round 2 rerun**：valid；enabled=false；VAULT_ROOT=SourceNotes-test；disabled=true eligible=false；health ok；runtime running；running/queued=0；备份 vs 当前脱敏 diff 仅 enabled + lastTouchedAt；env_keys(5) 与备份一致 |
| VAL-09 | 私有目录 | sha256 --check + tar 完整性 + 权限 | 0 | snapshot/member-list/config-backup/baseline 全 OK；tar 可读；0700/0600 |
| VAL-10 | 私有目录 | 解析 audit JSON 断言 | 0 | Source=24、Annotation=2、附件=147、每项唯一分类、引用关系与 queue/archive 字段齐全，ALL_OK |
| VAL-11 | 私有目录 | 人工抽查审计报告 + 隐私扫描 | manual | 无正文/URL/secret；处置理由可追踪；needs_user 6 项明确 |

## 6. Assumptions

- `.meta.lastTouchedAt` 变化来自 `openclaw config set` 工具自身维护的时间戳，非语义配置字段；故唯一语义差异为 enabled true→false。
- 审计处置为建议，不授权删除/迁移；`needs_user_decision` 项（6 个 failed/manual Source）留待用户决策。
- round 2：`VAULT_CAPTURE_BROWSER_PROFILE` 原值从既有 `openclaw.json.backup` 读取并恢复；恢复后 env_keys 与备份逐键一致，browser-profile 值 SHA-256（`1e3c68ff...`）与备份一致。值本身未打印、未复制到蓝图库或最终返回，仅记录哈希与存在性。

## 7. Deviations from specification

- **round 1（reviewer F-01 发现）**：round 1 修改 OpenClaw 配置时，除授权的 `skills.entries.vault-capture.enabled` true→false 外，意外丢失了 `skills.entries.vault-capture.env.VAULT_CAPTURE_BROWSER_PROFILE` 环境键并留下多余空行，违反 SPEC §6.4，使 round 1 AC-10 的“唯一语义差异 enabled true→false”声明不准确。
- **round 2 修复（F-01 closure）**：从外部私有目录的既有已验证备份 `openclaw.json.backup` 读取该键原值并恢复，去除空行，保持 `enabled=false` 与 `VAULT_ROOT` 及其它键不变；恢复后全量结构化脱敏 diff 仅剩 enabled 与 `.meta.lastTouchedAt`；config validate、health、skills info（disabled=true/eligible=false）、tasks=0 全通过；写入 round2-postfix-f01-evidence.json 作为脱敏证据。未改其它配置键。
- **round 2（F-02 closure）**：DECISIONS.md D-013 增加 supersession 注记，明确“稳定标签”检出规则以 D-020 为准，消除与 D-020 的冲突；核心决定（同仓、Vault 独立、extraDirs/allowlist）保留。
- 其余无偏差。

## 8. Unresolved risks and blockers

- 生产蓝图 checkout `/home/monottx/repos/knowledge-vault-blueprint` 存在用户既有未提交改动；不在本阶段范围，已原样保留，未触碰。
- 测试库 `assets/images/.gitkeep` 与附件计数：附件=147（含排除 `.gitkeep` 后）；archive 17 文件 + queue 中对应 x405 的 json。
- 测试库 `git diff --cached --check` 因既有暂存 capture 文件存在 trailing whitespace 而 exit 2；此为测试库**既有用户内容**（index SHA-256 `286d6c7d...` 与基线逐字节一致，证明未被本任务触碰），本任务只改 `.git/config`（非 tracked 内容，不受 `diff --check` 约束）。VAL-04 仅针对蓝图库（exit 0）通过；AC-16 的 `git diff --check` 以蓝图库为准，测试库既存 whitespace 非本任务引入、且禁止修改。

## 9. Git state at handoff

- 蓝图库：branch `正式运行SourceNotes`，HEAD `f9810f1ff454aaa4c7d0561a0d4dec1ca5bd5128`；有未提交文档改动（未 stage/commit）。
- 正式 Vault：`main` HEAD `ec1a90eb9d41df77cf74e44d51e703d0379882e7`，clean。
- 测试 Vault：`main` HEAD `ec1a90eb9d41df77cf74e44d51e703d0379882e7`，工作树/index/refs 未变，仅 `.git/config` push 防护（fetch 原值、push=`disabled://SourceNotes-test`）。
- OpenClaw：enabled=false（维护模式），health ok，VAULT_ROOT 未变，`VAULT_CAPTURE_BROWSER_PROFILE` env 键已恢复（与备份一致，值未泄露）。
- 未执行任何 stage/commit/push/pull/branch/tag/merge/rebase/reset/clean。

## 10. Handoff

交由 reviewer 独立核对。

---

# SPEC v2（round 3）执行记录

> 以下为 SPEC v2（spec_version=2，已批准）的执行记录。v1/round 2 的执行与偏差历史保留在本文档上文，不删除、不改写。本段只记录 v2 相对 v1 的重新规划执行：以 post-WeChat-rollback 只读基线重建，纳入 main 已接受的 D-021「输入与输出双向可追溯」与微信回退语义，并将数据单调决策改号为 D-022。

## V2-1. Preflight（STEP-01）

读取 SPEC v2、v1 EXECUTION、main 的 BLUEPRINT/DECISIONS/ROADMAP、main 与当前 openclaw-skill-workflow/git-workflow、私有证据 manifest/audit。只读核对基线，全部与 SPEC §5 一致：

- 当前蓝图 worktree：branch `正式运行SourceNotes` @ `f9810f1ff454aaa4c7d0561a0d4dec1ca5bd5128`，index 空。
- main 蓝图：`main` @ `8882d771356210913054ec31b769e4eb4acceb93`，clean，与 origin/main 一致。
- 正式 Vault：`main` @ `ec1a90eb9d41df77cf74e44d51e703d0379882e7`，clean，remote 原值。
- 测试 Vault：`main` @ `ec1a90eb9d41df77cf74e44d51e703d0379882e7`，134（124 A / 1 M / 9 ??），冻结三 hash 一致，push=`disabled://SourceNotes-test`。
- 活动 OpenClaw：config valid，SHA-256 `71321f12...`，`enabled=false`，`VAULT_ROOT` basename `SourceNotes-test`，`VAULT_CAPTURE_BROWSER_PROFILE` 缺失，env_keys 4，skill disabled/ineligible/modelVisible=false，health ok，running/queued=0，profile/helper 缺失。

## V2-2. Changed files（STEP-03/04/05/06）

- `BLUEPRINT.md`：在 `## 1. 目标` 后插入 main 的 `### 1.1 输入与输出全景`（语义等同、逐字组合），保持 `## 2` 标题；§10 数据回退 bullet 引用 D-022。STEP-03。
- `DECISIONS.md`：总表与正文各恰一个 D-020/D-021/D-022；main 的 D-021 表行与完整 section 逐字节保留；原 v1 数据单调内容改号为 D-022 并修正引用；D-013/D-015 supersession 注记保留。STEP-04。
- `ROADMAP.md`：stage 2 保持 v1 简化流程；stage 4 补 main 的「生活面板/周期性复习」两未来项；新增独立 stage 5 与延后需求 A/B；升级规则保留一周浸泡与数据单调并引用 D-022。STEP-05。
- `specifications/openclaw-skill-workflow.md`：保留 v1 简化发布；新增 §4.3 微信抓取 manual 边界（不使用 `VAULT_CAPTURE_BROWSER_PROFILE`、专用 persistent profile 或技术绕过），不误删通用浏览器安全说明。STEP-06。
- `specifications/git-workflow.md`：保留 v1 四平台/Linux 唯一写入者/普通软件回退边界；§6 引用 D-022。STEP-06。
- `specifications/upgrade-workflow.md`：保留 v1 内容，明确受 D-022 约束；强化「立即升级前」配置记录与浸泡失败后的 Source ID/相对路径/附件集合包含性验证（未实现工具）。STEP-06。
- `tasks/.../EXECUTION.md`：本记录，v2 段。STEP-02/09。

## V2-3. 私有证据（STEP-07）

- 修正 `RECOVERY.md`：移除无效 `sha256sum -c sha256-manifest.json`，改为只读 Python 解析结构化 JSON 并核对 snapshot_archive/member_list_file/openclaw_config_backup/baseline_manifest；保留 tar 检查与不执行恢复边界；新增历史证据说明（旧含 profile 备份为 pre-WeChat-rollback、禁止整文件恢复）。
- 新增 `openclaw-post-wechat-rollback.json.backup`：活动 `~/.openclaw/openclaw.json` 逐字节副本，mode 0600，SHA-256 与活动配置一致。
- 新增 `openclaw-post-wechat-rollback-summary.json`：脱敏摘要（enabled/VAULT_ROOT basename+sha16/env_keys/browser_profile_key_present/skill 状态/gateway health/tasks/profile-helper 存在性/historical_evidence），不含值/秘密/完整配置。
- 新增 `v2-revalidation-manifest.json`：task/spec version、各 HEAD、冻结三 hash、快照四项核验、840 成员、审计 24/2/147、活动配置 hash、新文件 hash/权限、旧证据 historical-only 声明。

## V2-4. Acceptance evidence（STEP-09，逐 AC）

- **AC-01 — 权威基线：PASS**。main clean@8882d77；微信回退与输入输出任务为已接受状态（SPEC 背景）；执行前无共享状态漂移（VAL-01/04/05/06）。
- **AC-02 — 决策编号与语义：PASS**。D-020/D-021/D-022 各恰一行一节；current 的 D-021 表行与完整 section 与 main 逐字节相同；D-022 承载数据单调内容，未被标为 D-021；D-013/D-015 supersession 正确（VAL-02）。
- **AC-03 — main 文档保留：PASS**。BLUEPRINT `### 1.1` 输入输出全景逐字组合；ROADMAP stage 4 生活/复习、stage 5、延后需求 A/B 完整保留（VAL-02）。
- **AC-04 — 简化发布一致性：PASS**。当前规范使用 `main+commit hash+last_known_good+维护模式+*-test Vault`；不强制 RC/正式标签/双 checkout；D-015 保留历史并被 D-020 取代（VAL-02）。
- **AC-05 — 微信 manual 边界：PASS**。openclaw-skill-workflow §4.3 明确 manual、不使用 `VAULT_CAPTURE_BROWSER_PROFILE`/profile 绕过；活动配置无该键（VAL-02/06）。
- **AC-06 — 数据单调与一周浸泡：PASS**。D-022 + upgrade/git 规范定义正常写入、失败先保护 Vault、只回退软件/配置、不得倒退 HEAD/覆盖快照/删除浸泡期数据、operation ledger 定向修复（VAL-02）。
- **AC-07 — schema 分级：PASS**。D-022 边界 + upgrade-workflow §7 三类策略；breaking 需双读 Adapter 或可逆幂等迁移；逆向迁移不覆盖后续编辑/正文/未知属性/noteId（VAL-02）。
- **AC-08 — 正式 Vault 未触碰：PASS**。VAL-04 全部一致、clean。
- **AC-09 — 测试库冻结未触碰：PASS**。VAL-05 全一致（HEAD/134/三 hash/fetch+push URL）。
- **AC-10 — 快照与恢复说明：PASS**。VAL-07 快照四项 hash、840 成员、tar 可读、0700/0600；RECOVERY 新校验命令与 JSON manifest 一致且只读；未执行恢复。
- **AC-11 — 审计仍有效：PASS**。VAL-08 24/2/147、每项唯一处置、queue/archive/lock 字段齐全；不重写审计。
- **AC-12 — OpenClaw 只读维护态：PASS**。VAL-06 变更前后活动配置 hash 不变（`71321f12...`），enabled=false、VAULT_ROOT=SourceNotes-test、profile 键缺失、skill disabled/ineligible、healthy、0/0、外部 profile/helper 缺失；未 reload/restart。
- **AC-13 — 当前配置私有证据：PASS**。VAL-09 新备份 SHA 等于活动配置；脱敏摘要不含值/秘密；旧含 profile 备份标记 historical-only/do-not-restore。
- **AC-14 — 隐私与范围：PASS**。VAL-03 相对链接全有效、敏感扫描无泄露；只改允许路径。
- **AC-15 — 无未授权动作：PASS**。VAL-01/04/05 无 Git 写操作、无 OpenClaw 配置写入/reload/restart、无捕获/迁移/重抓取；FINAL_STATE 无 stage/commit。
- **AC-16 — 基础质量：PASS**。VAL-03 相对链接 + `git diff --check` exit 0；`git diff --cached --name-only` 为空；蓝图组合正确（VAL-02）。

## V2-5. Validation log（STEP-09，逐 VAL）

| VAL | 工作目录 | 命令 | 退出码 | 关键输出 |
|---|---|---|---|---|
| VAL-01 | 当前 & main | `git branch --show-current && git rev-parse HEAD && git status --short --branch && git diff --name-status && git diff --cached --name-status` | 0 | main clean@8882d77；当前 `正式运行SourceNotes`@f9810f1，仅允许路径改动，cached 空 |
| VAL-02 | 当前 | inline Python 断言 + 人工 | 0 | D-020/021/022 各 1 行 1 节；D-021 表行+section 与 main 逐字节相同；BLUEPRINT 1.1 与 main 相同；ROADMAP stage4/5/延后 保留；manual 边界、D-022、last_known_good、浸泡保留 全部 PASS；人工确认 RC/tag/staging 表述仅在 superseded 历史或否定语句 |
| VAL-03 | 当前 | Python 相对链接 + 隐私扫描 + `git diff --check` + `git diff --cached --name-only` | 0 | 11 相对链接 ALL_OK；diff --check 无输出；cached 空；隐私扫描仅命中例示微信 URL/禁止性“trajectory”/执行记录库路径，无真实正文/逐篇 URL/secret/完整配置 |
| VAL-04 | 正式 Vault | `git branch --show-current && git rev-parse HEAD && git status --porcelain=v2 --branch && git remote -v && git diff --stat && git diff --cached --stat && sha256sum $(git rev-parse --git-path index)` | 0 | main@ec1a90e...，`main...origin/main` 同步，remote 原值，diff 空，index 532676e5... |
| VAL-05 | 测试 Vault | `git rev-parse HEAD`、sorted `show-ref`/index/`porcelain -z` hash、134 分类、`remote get-url origin`/`--push` | 0 | HEAD ec1a90e...；show-ref d4687620...、index 286d6c7d...、porcelain-z 0b42e19a...；124 A/1 M/9 ??；fetch 原值、push=`disabled://SourceNotes-test` |
| VAL-06 | OpenClaw（只读） | `config validate`、config SHA、结构化摘要、`skills info --json`、`health --json`、`gateway status`、tasks、profile/helper 存在性 | 0 | config hash 71321f12... 不变；enabled=false、VAULT_ROOT=SourceNotes-test、profile 键缺失、skill disabled/ineligible/modelVisible=false、health ok、0/0、profile/helper 缺失 |
| VAL-07 | 私有目录 | RECOVERY 新 JSON hash 校验 + `tar -tf >/dev/null` + 成员数 + 权限 | 0 | 四项 ALL_OK；tar 可读；840 成员；根 0700、全文件 0600 |
| VAL-08 | 私有目录 | 解析 migration-audit.json 断言 | 0 | sources=24、annotations=2、attachments=147；每项唯一非空 disposition；queue_count=25/terminal=25/lock=1/archive=17 及关键附件字段齐全；未重写审计 |
| VAL-09 | 私有目录 | 新备份 vs 活动配置 hash、summary/manifest schema+脱敏、权限、RECOVERY 历史标记 | 0 | 备份 SHA==活动配置；summary/manifest 无完整 VAULT_ROOT/profile 值/token/secret；新文件 0600；RECOVERY 明确 pre-WeChat-rollback/不得整文件恢复 |

## V2-6. Deviations（STEP-09）

- 无。所有改动严格落在简报允许路径内；未改变批准意图/编号/AC；未触碰 main/Vault/活动配置/旧证据。

## V2-7. Final state（STEP-09）

- 当前蓝图 worktree：branch `正式运行SourceNotes` @ `f9810f1ff454aaa4c7d0561a0d4dec1ca5bd5128`，仅允许路径有未提交文档改动，index 空；未 stage/commit。
- 正式 Vault：clean@ec1a90e...；测试 Vault：冻结基线不变。
- OpenClaw：活动配置 hash `71321f12...` 未变，维护态保持。
- 私有证据：新增/修改文件 mode 0600，根 0700；未覆盖/删除旧证据。

---

# SPEC v2 corrective round（reviewer F-03 closure）

> 本段为 reviewer round 1 唯一 finding（F-03）的更正记录。不改写上文任何历史；仅修正 manifest 中一处过期 hash 并披露根因。

## C-1. 原因披露（FIX-03）

- `v2-revalidation-manifest.json` 中 `new_evidence_files["RECOVERY.md"].sha256` 记为 `5a7b8840…`，但实际 RECOVERY.md 为 `911a458d…`。
- 根因：上一轮 v2 执行中，我在写入 manifest 前先计算了当时 RECOVERY.md 的 hash（`5a7b8840…`）并写入 manifest，随后才完成对 RECOVERY.md 的最终编辑（补「校验方法」说明与历史证据说明），但未回写同步 manifest 中的该条 hash，导致 manifest mtime（02:40）早于 RECOVERY.md mtime（02:41），指纹证据过期。
- reviewer 实测并确认：RECOVERY.md 当前内容合规（结构化 JSON 校验命令、tar 校验、pre-WeChat-rollback 历史证据标记、不执行恢复边界均在，无秘密）；manifest 中其余新文件 hash（backup `71321f12…`、summary `4df0697f…`）、活动 config hash、权限均仍准确。

## C-2. 精确修复（FIX-02）

- 仅修改 `/home/monottx/.local/state/sourcenotes-production-readiness/2026-08-12/v2-revalidation-manifest.json` 中 `new_evidence_files["RECOVERY.md"].sha256` 为当前实测值 `911a458deb6a469ca87461aa77564ab88227825fea918f7dac2c5a26376a27d1`，并在该条目 note 中记录更正时间与原因。
- 未更改 RECOVERY.md 内容本身；未触碰旧证据。

## C-3. 验证（FIX-04）

- manifest `new_evidence_files` 三项 hash 与实测文件逐一重算全相等（RECOVERY/backup/summary）；新文件 permissions 均 0600，根 0700。
- 实际运行 RECOVERY 中的 JSON hash 校验命令：snapshot_archive/member_list_file/openclaw_config_backup/baseline_manifest 四项全 OK；`tar -tf` 可读且 840 成员。
- 新备份 `openclaw-post-wechat-rollback.json.backup` 与活动 `~/.openclaw/openclaw.json` 逐字节一致，活动 config hash 仍 `71321f12…`；只读检查 enabled=false、profile 缺失。
- `git diff --check --` 原 6 文档与任务包 exit 0；current cached diff 为空；main/两 Vault/OpenClaw/冻结 hash 无漂移。

## C-4. F-03 closure & 受影响 AC 复报

- **F-03（major）CLOSED**：manifest 中 RECOVERY.md 指纹已与实际文件一致，证据链自洽；再复核者可区分「记录过期」与「文件被篡改」。
- **AC-10（快照与恢复说明）：PASS** — sha256-manifest 四项 hash 实测一致；RECOVERY 校验命令为只读 Python 解析结构化 JSON、键名与 manifest 一致；tar 840 可读；0700/0600；未执行恢复；RECOVERY 内容未因本轮变更。
- **AC-13（当前配置私有证据）：PASS** — 新备份与活动配置逐字节一致且 hash=`71321f12…`；脱敏摘要无值/秘密；旧含 profile 备份标记 pre-WeChat-rollback/不得整文件恢复；manifest 中 RECOVERY.md 指纹现已与实际一致。
- **AC-14（隐私与范围）：PASS** — 仅修改 manifest 单条 hash 与 EXECUTION 更正记录，均在允许路径；无正文/URL/secret/完整配置泄露。
- **AC-15（无未授权动作）：PASS** — 无 Git 写操作、无 OpenClaw 配置写入/reload/restart、无捕获/迁移/重抓取。
- **AC-16（基础质量）：PASS** — 更正后 `git diff --check` exit 0；cached 空；证据链自洽。

## C-5. Final state

- 当前蓝图 worktree：branch `正式运行SourceNotes` @ `f9810f1ff454aaa4c7d0561a0d4dec1ca5bd5128`，仅允许路径有未提交文档改动，index 空；未 stage/commit。
- 私有证据：仅 manifest 的 RECOVERY.md 条目 hash 更新为 `911a458deb6a469ca87461aa77564ab88227825fea918f7dac2c5a26376a27d1`（与实测一致）；其余文件 hash 与权限未变；根 0700、文件 0600。
- main/两 Vault/OpenClaw 活动配置：未变。
