# Execution Evidence — Work Item 01（preflight and cutover package）

- Effort: `/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-production-switch/`
- Work Item: `issues/01-preflight-and-cutover-package.md`
- Role: Executor
- 日期: 2026-08-17
- 批准链：`spec.md`（approved）→ `plan.md`（approved）→ Operator 批准原文
  `批准上述第一层计划；本次不迁移测试库，main 作为 Steward，切换前轮换 Telegram 凭据。`
  → 本 Work Item 01（claimed）→ `execution-brief-01.md`（逐字遵守）。
- 产物：`cutover-package.md`（本目录上级）与本文件。

## 1. 执行摘要（STEP-01..06）

| STEP | 内容 | 结果 |
|---|---|---|
| STEP-01 | 只读 preflight：阅读 AGENTS.md/map/spec/plan/issue/brief/三份 specification；记录三仓库基线、配置 SHA、Gateway/queue/skill 摘要 | PASS，无漂移 |
| STEP-02 | 仓库回归 VAL-02..VAL-07 | 全部 PASS（exit 0） |
| STEP-03 | 一次性受控入口 E2E（一次性 basename `sourcenotes-production-switch-20260817-083329-e2e-test`，绝对路径不记录） | PASS，已清理 |
| STEP-04 | 候选配置模型 → `cutover-package.md` §1 | PASS |
| STEP-05 | Operator cutover runbook → `cutover-package.md` §2 | PASS |
| STEP-06 | 本证据文件 + VAL-09 确定性扫描 | PASS |

## 2. STEP-01 只读基线（VAL-01）

三仓库（cwd 分别为各仓库根）：

| 仓库 | 命令（只读） | 退出码 | 关键输出（脱敏） |
|---|---|---|---|
| 蓝图 `knowledge-vault-blueprint` | `git branch --show-current` | 0 | `main` |
| 蓝图 | `git rev-parse HEAD` | 0 | `017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`（=批准 commit） |
| 蓝图 | `git status --short --branch` | 0 | `## main...origin/main` + 未跟踪 `?? .scratch/`（本 Effort 目录，预期） |
| 蓝图 | `git diff --cached --name-status` | 0 | 空 |
| 蓝图 | `git rev-parse origin/main` | 0 | `017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`（与 HEAD 一致） |
| 正式 Vault `SourceNotes` | `git branch --show-current` / `rev-parse HEAD` | 0 | `main` @ `ec1a90eb9d41df77cf74e44d51e703d0379882e7` |
| 正式 Vault | `git status --short --branch` | 0 | clean（无输出） |
| 正式 Vault | `git diff --cached --name-status` | 0 | 空 |
| 测试 Vault `SourceNotes-test` | `git branch --show-current` / `rev-parse HEAD` | 0 | `main` @ `ec1a90eb9d41df77cf74e44d51e703d0379882e7` |
| 测试 Vault | `git status --short --branch` | 0 | 既有脏状态（大量 staged/untracked）——只读记录，不清理、不 reset |
| 宿主 | `sha256sum ~/.openclaw/openclaw.json` | 0 | `de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424`（0600） |
| 宿主 | `openclaw --version` | 0 | `OpenClaw 2026.7.1-2 (0790d9f)` |
| 宿主 | `openclaw tasks list --status running` / `--status queued` | 0 | `Background tasks: 0`、`0 queued · 0 running · 0 issues` |
| 宿主 | `openclaw gateway status` | 0 | systemd user `openclaw-gateway.service`，running（pid 32037），bind loopback `127.0.0.1:18789`，Connectivity probe: ok，capability `connected-no-operator-scope` |
| 宿主 | `openclaw config validate` | 0 | `Config valid: ~/.openclaw/openclaw.json` |
| 宿主 | `openclaw skills list --agent notesvaulter` | 0 | `vault-capture`/`vault-query`/`vault-maintenance` 均 `disabled`、来源 `openclaw-extra` |
| 宿主 | `openclaw skills check --agent notesvaulter` | 0 | Total 119 / Eligible 81 / Visible to model 0 / Disabled 32 / Missing requirements 0 |
| 只读文档 | grep `allowAgents` `openclaw/docs/{tools/subagents.md,gateway/config-agents.md}` | 0 | `agents.list[].subagents.allowAgents` = `string[]`，默认仅同 agent，`["*"]` 宽泛；`["notesvaulter"]` 精确候选成立 |

活动配置语义摘要（secret-free，仅允许字段；未打印任何 token 值/完整路径/完整 JSON）：

- `agents.list`：`main`（name=`Main Agent`，skills 未设置，`subagents.allowAgents` 未设置）；
  `notesvaulter`（skills=`["vault-capture"]`，`subagents.allowAgents` 未设置）。
- `skills.load.extraDirs`：basename `skills`；`watch=true`。
- `skills.entries`：`vault-capture` `enabled=false`（env 键含 `PATH`、`PLAYWRIGHT_BROWSERS_PATH`、
  `VAULT_CAPTURE_PYTHON`、`VAULT_ROOT`；`VAULT_ROOT` basename=`SourceNotes-test`）；
  `vault-query` `enabled=false`；`vault-maintenance` `enabled=false`；其余大量条目 `enabled=false`。
- `channels.telegram`：`enabled=true`，`defaultAccount=default`；accounts `default`、`notesvaulter`
  （各含 1 个非空 `botToken` 字段，长度 46，值未读取/未输出）。
- `bindings`：`main`→telegram account `default`；`notesvaulter`→telegram account `notesvaulter`。
- secretish 键扫描（仅路径+类型+长度，无值）：`channels.telegram.accounts.*.botToken`（str 46×2）、
  `gateway.auth.password`（str 5）、`models.providers.agent-plan.apiKey`（str 46）、
  `plugins.entries.tavily.config.webSearch.apiKey`（str 58）、`agents.defaults.memorySearch.remote.apiKey`
  （str 46）、`mcp.servers.*.env.ASK_ECHO_SEARCH_INFINITY_API_KEY`（str 46）。
- 结论：运行态与简报「当前事实」一致（capture disabled、VAULT_ROOT basename `SourceNotes-test`、
  query/maintenance disabled、NotesVaulter 独立 Telegram binding、main 未允许 spawn notesvaulter），
  **无相关配置漂移**；蓝图 HEAD=批准 commit；正式 Vault clean；无 running/queued capture。

## 3. STEP-02 仓库回归（VAL-02..VAL-07）

| VAL | cwd | 命令 | 退出码 | 关键输出 |
|---|---|---|---|---|
| VAL-02 | 蓝图根 | `PYTHONDONTWRITEBYTECODE=1 python3 -B tests/skills/test_vault_capture.py` | 0 | `Ran 29 tests ... OK` |
| VAL-03 | 蓝图根 | `PYTHONDONTWRITEBYTECODE=1 python3 -B tests/skills/test_web_extract.py` | 0 | `Ran 34 tests ... OK`（含 playwright/HTTP ResourceWarning，非失败） |
| VAL-04 | 蓝图根 | `PYTHONDONTWRITEBYTECODE=1 python3 -B tests/skills/test_network_security.py` | 0 | `Ran 54 tests ... OK` |
| VAL-05 | 蓝图根 | `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests/operations -p 'test_*.py'` | 0 | `Ran 67 tests ... OK` |
| VAL-06 | 蓝图根 | `bash tests/opencode-harness/test_capture_debug.sh` | 0 | `通过 19 项，失败 0 项`（A–F 全 PASS） |
| VAL-07 | 蓝图根 | `PYTHONDONTWRITEBYTECODE=1 python3 -B -m py_compile scripts/sourcenotes_agent.py scripts/sourcenotes_ops.py` | 0 | 编译通过；`-B` 未阻止 py_compile 写入：`scripts/__pycache__/sourcenotes_*.cpython-314.pyc` birth=2026-08-17 08:26:20（本命令产出）→ **已删除这两个 .pyc**；`scripts/__pycache__` 目录本身 birth=2026-08-13（既有，保留未动）；删除后 `git status --short -- scripts/` 为空。tests/skills、tests/operations 的既有 `__pycache__`（birth Aug 13/16）未被动过（-B 测试运行未写缓存） |

## 4. STEP-03 一次性受控入口 E2E（VAL-08）

- 临时 Vault：basename `sourcenotes-production-switch-20260817-083329-e2e-test`（以 `-test` 结尾，
  位于 `/tmp/`；按 AC-09 只记录 basename，不记录绝对路径）。
- **DEVIATION（详见 §7）**：简报要求「从 `vault-starter/` 复制 starter 内容」，但该目录在蓝图库
  工作树、HEAD 与全部 git 历史中均不存在（README 既有断链，先前 review 已记录）。改为使用仓库
  测试套件定义的权威 starter 结构（`tests/skills/test_vault_capture.py` setUp：`sources/{web,
  transcripts,documents}`、`notes/{annotations,ideas}` 各含 `.gitkeep`、`.gitignore=.queue/`、
  git init + 测试身份 + baseline commit），全部落在允许的临时路径内；未查找或读取任何允许范围
  外的 vault-starter 副本。
- 构造与基线：`git init`，身份 `Vault E2E Test <vault-e2e-test@example.invalid>`（仅限该临时库），
  baseline commit HEAD=`487561720ff2ead61b4315e1b872ffc51da56ece`。
- 唯一标记：`sourcenotes-e2e-unique-20260817-0833`。

| 步骤 | 命令（cwd=蓝图根，VAULT_ROOT=临时库） | 退出码 | 关键输出（脱敏） |
|---|---|---|---|
| 1 | `python3 -B scripts/sourcenotes_agent.py capture preflight` | 0 | `{"git":true,"layout":true,"ok":true,"queue_ignored":true}` |
| 2 | `capture stage`（stdin 唯一 idea JSON） | 0 | `{"ok":true,"result":"created","id":"20260817-083346-g9qv","ingest_status":"ready","staged":true,"job_created":false,"source_path":"notes/ideas/20260817-083346-g9qv--...production.md","staged_paths":["notes/ideas/..."]}`（相对路径） |
| 3 | `git -C <tmp> status --short` | 0 | 仅 `A notes/ideas/20260817-083346-g9qv--...md`（只暂存本次路径；`.queue/` 被 ignore） |
| 4 | `query search sourcenotes-e2e-unique-20260817-0833` | 0 | `{"count":1,"ok":true,"results":[{"id":"20260817-083346-g9qv","path":"notes/ideas/...","title":"...","excerpt":"..."}]}` |
| 5 | `maintenance report` | 0 | `{"ok":true,"report":{"git":{branch/head/dirty_count:1/staged_count:1},"sources":{"total":0,"failed_count":0,"manual_count":0},"missing_source_references":[],"attachments":{"count":0,"total_bytes":0,"gate_2GiB":false}}}` |
| 6 | 泄漏断言：对 preflight/stage/query/maintenance 全部输出 `grep -F "$TMP"` | — | `LEAK_TOTAL=0`（无任何输出含临时 Vault 绝对路径） |

- 断言满足：capture ok/ready 且只暂存临时 Vault 本次相对路径；query 返回 note id/相对路径；
  maintenance 返回 Git/状态/附件字段；输出不含 temp 绝对路径。
- 清理：确认临时根位于 `/tmp/` 且 basename 以 `-test` 结尾后删除；确认无
  `sourcenotes-production-switch-*-test` 残留（具体绝对路径不记录）。未调用 SourceNotes /
  SourceNotes-test。

## 5. STEP-04/05 产物（VAL-09 扫描对象）

- 新增 `cutover-package.md`：§1 候选配置模型（before→candidate 语义摘要，C1–C10）、
  §2 Operator Runbook（2.1 前置 Gate 与停止条件、2.2 私下凭据轮换/撤销、2.3 私有 0700 状态目录
  + 0600 备份 + SHA-256 + Vault checkpoint + queue 摘要 + ledger、2.4 候选构造与 validate、2.5
  独立 `*-test` 真实 NotesVaulter E2E、2.6 唯一精确写入/reload、2.7 post-check、2.8 失败恢复、
  2.9 last_known_good=017c2ce1… 与 soak start）。
- 全部真实写入命令标注 `CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED`。
- candidate 语义覆盖核对：`main.name=Steward`（保留 id=`main`）、
  `main.subagents.allowAgents=["notesvaulter"]`（无 `*`）、
  `notesvaulter.skills=["vault-capture","vault-query","vault-maintenance"]`、三 skill entries
  enabled、`vault-capture.env.VAULT_ROOT` 候选写 `<production SourceNotes path supplied privately>`
  （正文仅 basename `SourceNotes`）、移除 NotesVaulter 直接 Telegram binding/account（默认 Telegram
  仅绑 main）、main token 轮换 + notesvaulter 旧 token 撤销（新值永不入包）、模型/浏览器/web
  search/SSRF/无关 agent 与 channel 不变。

## 6. VAL-09 确定性扫描（round 0，cwd=蓝图根）

> 历史记录。F-01 指出 round 0 的 cwd 声明与目标路径矛盾、且 `git diff --check` 不覆盖
> 未跟踪产物；round 1 已按 F-01 从 Effort 根重跑扫描并改用逐文件 no-index whitespace
> 检查，见文末「Round 1 correction」的 VAL-V2-04。

| 检查 | 命令 | 退出码 | 结果 |
|---|---|---|---|
| token 值模式 | `grep -nE '[0-9]{8,10}:[A-Za-z0-9_-]{35}|sk-[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|(botToken\|apiKey\|password\|token\|secret)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"']{8,}' cutover-package.md evidence/01/execution.md` | 1（无匹配） | 无 token 值/键值对泄漏（仅键名文本，无键值对） |
| 绝对 Vault 路径 | `grep -nE '/home/[^ ]*SourceNotes|/Users/[^ ]*SourceNotes|repos/SourceNotes' cutover-package.md evidence/01/execution.md`（原始命中仅本条命令描述自身的正则文本一行，经 `grep -v "grep -nE"` 排除自引用） | 1（排除自引用后无匹配） | 无绝对 SourceNotes 路径（仅 basename/占位符） |
| 正文/逐项 URL | `grep -nE 'https?://' cutover-package.md evidence/01/execution.md` | 1（无匹配） | 无正文/逐项 URL |
| 写命令标注 | 人工 + `grep -nE 'cp |rm |mkdir |restart|write|patch|set ' cutover-package.md` | — | 所有真实写入命令均带 `CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED` 标注 |
| 空白错误 | `git diff --check -- .scratch/2026-08-17-sourcenotes-production-switch` | 0 | 无空白错误 |

## 7. DEVIATIONS

1. **`vault-starter/` 缺失**（STEP-03）：简报要求从 `vault-starter/` 复制 starter 内容，但该目录在
   蓝图库工作树、HEAD 与全部历史中均不存在（README 既有断链，2026-08-12 readiness review 已记录
   为两分支共有、非本任务引入）。处置：在允许的临时路径内，用仓库测试套件定义的权威 starter 结构
   构造临时 Vault（未查找/读取允许范围外副本，round 1 已删除该叙述）。
2. **VAL-07 缓存清理**：`-B` 未阻止 `py_compile` 写缓存；按简报删除仅本命令新建的两个 .pyc
   （birth 08:26:20 今日），既有 `scripts/__pycache__` 目录（birth Aug 13）保留，其它既有缓存不动。

## 8. Controlled Actions 声明

本 Work Item **未执行**任何 Controlled Action：未 stage/commit/push、未修改活动 OpenClaw 配置、
未 reload/restart Gateway、未轮换/撤销凭据、未写两个 Vault、未写 last_known_good、未执行
cutover-package 中任何标注为 OPERATOR ONLY 的命令。凭据轮换、配置写入、Gateway reload/restart
与生产 capture 均留给后续 Operator Controlled Action gate。

## 9. 安全边界自检

- 未打印/复制/记录任何 token 值（secret 键仅以路径+类型+长度出现在 §2 摘要）。
- 未记录绝对 Vault 路径、正文或逐项 URL；一次性临时 Vault 一律只记录 basename
  （`sourcenotes-production-switch-20260817-083329-e2e-test`），绝对路径已从本文件移除
  （round 1 correction，F-02）。临时目录已删除并确认无残留，不含正式 Vault 路径。

## 10. Acceptance coverage（本 Work Item 范围）

| AC | 结论 | 证据 |
|---|---|---|
| AC-01 | PASS | §2 VAL-01：蓝图 `main@017c2ce1…`=origin/main；正式 SourceNotes clean；测试库只读记录既有状态；0 running/queued；配置与已知事实无漂移 |
| AC-02 | PASS | §3/§4：VAL-02..VAL-08 全 PASS（含一次性 `*-test` 受控入口 E2E），未触碰正式 Vault |
| AC-03 | PASS | §5：cutover-package 给出唯一公开入口、窄 `allowAgents`、三技能、生产 VAULT_ROOT（basename）、凭据轮换与回滚的精确脱敏 runbook |
| AC-04 | PASS | §2.3/§5：0700/0600、原子/逐字节备份 + SHA-256、checkpoint/queue 摘要/ledger 方案齐备；Evidence 无 secret |
| AC-05 | NOT_RUN | 本 Work Item 不自证；等待独立 Reviewer 对工件/证据/配置候选给出 PASS |
| AC-06 | NOT_RUN | 属 Work Item 02（Operator Controlled Action 后复核） |
| AC-07 | NOT_RUN | 属 Work Item 02（生产 canary 只读复核） |
| AC-08 | NOT_RUN | 属 Work Item 02（last_known_good 写入与 soak 起点） |
| AC-09 | PASS | §6 VAL-09：无 token 模式、无绝对 Vault 路径、无正文/逐项 URL；写命令全部标注 Operator-only；`git diff --check` exit 0 |

## 11. FINAL_STATE

- 蓝图库：`main` @ `017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`（=origin/main），工作树仅新增
  未跟踪 `.scratch/2026-08-17-sourcenotes-production-switch/`（本 Effort 产物），未 stage/commit。
- 正式 Vault：`main` @ `ec1a90eb9d41df77cf74e44d51e703d0379882e7`，clean，未触碰。
- 测试 Vault：`main` @ `ec1a90eb9d41df77cf74e44d51e703d0379882e7`，既有脏状态原样保留，未触碰。
- 活动配置：hash `de9b9cb1…934424` 不变（本 Work Item 全程只读）。
- Gateway：systemd user 服务运行中（pid 32037），未 restart/reload。
- 队列：0 running / 0 queued。
- 临时目录：basename `sourcenotes-production-switch-20260817-083329-e2e-test` 已删除，无残留。
- Controlled Action：**未执行任何**（见 §8）。

---

# Round 1 correction（F-01..F-08 修复，2026-08-17）

依据：`evidence/01/review.md`（CHANGES_REQUESTED，F-01..F-08）、
`execution-brief-01-repair-round-1-v2.md`、Operator 批准原文 `好的 同意此方案`
（正式库完整一次性 `*-test` 克隆 canary；不复制模型密钥；不向正式 SourceNotes
写测试数据；真实模型委派 E2E 属后续 Operator Controlled Action）。

## R1.1 F-01..F-08 closure

| Finding | 修复动作 | 状态 |
|---|---|---|
| F-01 [major] 扫描 cwd 矛盾/不覆盖未跟踪 | round 1 从 Effort 根对实际两个产物重跑 secret/path/URL/写命令扫描；未跟踪 Markdown 用 `git diff --no-index --check /dev/null <file>` 逐文件检查（rc=1 且无 whitespace-error） | CLOSED（VAL-V2-04） |
| F-02 [major] Evidence 写入临时 Vault 绝对路径 | 全部改为 basename（`sourcenotes-production-switch-20260817-083329-e2e-test`），绝对路径从 evidence 移除 | CLOSED（VAL-V2-04 扫描确认） |
| F-03 [major] runbook 非原子写/权限未验证 | cutover-package §2.0/§2.3/§2.6/§2.8 全部改为 atomic helper（同目录 tmp→0600→fsync→os.replace→parent fsync）+ 0700/0600 stat 验证；§2.3 演练 | CLOSED（VAL-V2-02） |
| F-04 [major] 隔离 E2E 占位符/未验证委派 | 废弃独立隔离 Gateway 方案；cutover-package §2.5 给出活动 Gateway + 正式库完整 `*-test` 克隆 canary 的完整无占位符 runbook（全变量化、全 Operator-only）；真实模型 E2E 明确 NOT_RUN — OPERATOR CONTROLLED ACTION GATE；本轮完成无模型 clone rehearsal | CLOSED（runbook + VAL-V2-03；真实模型 E2E 不属本轮） |
| F-05 [major] 候选配置只是草图/null 语义不明 | cutover-package §1.1 给出确定性 transformer（深复制保留未知字段、数组精确过滤、pop 键删除非 null、merge-patch null 语义说明）；fixture 上运行两次幂等 | CLOSED（VAL-V2-01） |
| F-06 [major] /newbot 不保证旧 token 失效 | cutover-package §2.2 改为对现有 main bot 的 BotFather `/revoke`/reissue（旧 token 立即失效），禁止 `/newbot`；NotesVaulter bot revoke 后移除 account/binding；Evidence 只布尔确认 | CLOSED（runbook 修订） |
| F-07 [major] shell 尖括号占位符 | cutover-package §2.0 定义并全程双引号引用 `STATE_DIR`/`ACTIVE_CONFIG`/`BACKUP_CONFIG`/`CANDIDATE_CONFIG`/`PRODUCTION_VAULT_ROOT`/`CANARY_VAULT_ROOT`/`MAIN_BOT_TOKEN_FILE`；无尖括号占位符 | CLOSED（runbook 修订） |
| F-08 [minor] 允许范围外 vault-starter 路径 | evidence 删除该绝对路径与定位叙述；仅保留「仓库内 vault-starter 不存在，使用仓库内测试 fixture 结构」 | CLOSED（VAL-V2-04 扫描确认） |

## R1.2 VAL-V2-01..05 记录

### VAL-V2-01 / AC-03（transformer deterministic + validate + projection）

- cwd：本轮临时根 `/tmp/...-test`（basename 不记录绝对路径）与宿主。
- 命令与退出码：
  1. `python3 -B transformer.py <fixture-config.json> <canary-vault-root>` 两次 → rc=0/0，
     两次 stdout 完全一致（deterministic/idempotent）。
  2. `OPENCLAW_CONFIG_PATH=<candidate-fixture.json> openclaw config validate` → rc=0，
     输出 `Config valid: <candidate>`。
  3. semantic projection 断言（stdout 关键脱敏输出）：
     `agents=[main(name=Steward, allowAgents=["notesvaulter"]), notesvaulter(skills=[三技能])]`；
     `vault_skills_enabled={vault-capture:true, vault-query:true, vault-maintenance:true}`；
     `vault_root_basename=SourceNotes-production-canary-r1-test`；
     `bindings=[{agentId:main, channel:telegram, accountId:default}]`（仅 1 条，无 `*`）；
     `telegram_account_keys=["default"]`；`notesvaulter_token_field_present=false`；
     `main_token_field_present=true`（fixture 占位值，非真实 secret）。
  4. candidate 结构核对：main 的 `identity`、notesvaulter 的 `workspace`、无关 entry
     `trello` 均保留（未知字段不丢）。
- 结论：PASS。

### VAL-V2-02 / AC-04（atomic backup/publish/restore 演练）

- cwd：本轮临时根。
- 命令与退出码：`python3 -B atomic_helper.py <state-dir> <active-config-fixture.json>` → rc=0。
- 关键输出：`state_dir_mode: 0o700`、`backup_mode: 0o600`、`active_mode: 0o600`、
  `backup_sha == restore_sha == 备份 sha`（逐字节恢复）、candidate 阶段 hash 不同、
  `ATOMIC_ASSERTIONS_OK`；无 `.tmp` 残留；恢复后 active 内容与原文逐字节一致。
- 演练对象为临时 fixture，**绝不针对活动配置**。结论：PASS。

### VAL-V2-03 / AC-03+AC-10（完整 clone rehearsal，无模型）

- cwd：本轮临时根。
- 命令与退出码：
  1. `git clone --no-hardlinks <fixture-source> <SourceNotes-production-canary-r1b-test>` → rc=0；
     clone HEAD == source HEAD（`c356d5cacc183718cf4d95e4ae486bde6796b69b`）。
  2. `git remote remove origin` → remotes=0；`git push` → rc=128，
     `fatal: No configured push destination.`（push 禁用确认）。
  3. 只向 clone 写入 1 个 canary 文件并 `git add`（模拟 capture 只写 canary）→ staged=1。
  4. source 复核：HEAD 不变、`status --porcelain` 0 行、内容 sha256 不变
     （`b8c88683af433408e431be72abf760d53520710cec775f4342b8084e42e01b55`）。
  5. `rm -rf <canary>` + `ls -d` 确认无残留；无 `SourceNotes-production-canary-*-test` 残留。
- 结论：PASS（演练证明 clone 只产生于 `*-test` 目标、源零改动、push 不可达、删除干净）。

### VAL-V2-04 / AC-09（Effort 根扫描 + no-index whitespace）

- cwd：Effort 根 `.scratch/2026-08-17-sourcenotes-production-switch/`。
- 命令与退出码（见下表）；所有扫描 rc 符合期望；两个未跟踪 Markdown
  （`cutover-package.md`、`evidence/01/execution.md`）的
  `git diff --no-index --check /dev/null <file>` rc=1 且无 whitespace-error
  （rc=1 表示两文件不同即有内容；stdout 无 whitespace 错误即通过）。
- 结论：PASS。

| 检查 | 命令（cwd=Effort 根） | 退出码 | 关键输出 |
|---|---|---|---|
| token/credential 键值 | `grep -nE '[0-9]{8,10}:[A-Za-z0-9_-]{35}|sk-[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|(botToken\|apiKey\|password\|token\|secret)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"']{8,}' cutover-package.md evidence/01/execution.md` | 1（无匹配） | 无 token 值/键值对 |
| Bot token 形态 | `grep -nE '[0-9]{8,10}:[A-Za-z0-9_-]{35}' cutover-package.md evidence/01/execution.md` | 1（无匹配） | 无 Bot API token |
| 绝对 SourceNotes 路径 | `grep -nE '/home/[^ ]*SourceNotes|/Users/[^ ]*SourceNotes|repos/SourceNotes' cutover-package.md evidence/01/execution.md`（排除扫描命令自引用行） | 1（无匹配） | 无绝对 Vault 路径（仅变量/basename） |
| 逐项 URL | `grep -nE 'https?://' cutover-package.md evidence/01/execution.md` | 1（无匹配） | 无正文/逐项 URL |
| 写命令分类 | 人工 + `grep -nE 'cp |mv |install |chmod |mkdir |restart|patch|set |unset|gateway ' cutover-package.md` | — | 每个写入 bash 块首行为 `CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED`；只读命令块显式标注 |
| whitespace（未跟踪） | `git diff --no-index --check /dev/null cutover-package.md`；`git diff --no-index --check /dev/null evidence/01/execution.md` | 1（有内容）；stdout 无 whitespace error | 通过 |
| whitespace（跟踪区） | `git diff --check -- .scratch/2026-08-17-sourcenotes-production-switch` | 0 | 无空白错误 |

### VAL-V2-05 / AC-01（只读复核前后不变）

- cwd：三仓库根与宿主。
- 命令：`git rev-parse HEAD` / `git status --short --branch` /
  `sha256sum ~/.openclaw/openclaw.json` / `openclaw tasks list --status running|queued` /
  `openclaw gateway status`。
- pre/post 均一致：蓝图 `main@017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`、正式 Vault
  clean @`ec1a90eb…`、测试 Vault 既有脏状态 166 行未变、配置 hash
  `de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424` 不变、queue 0/0、
  默认 Gateway running（pid 32037）。结论：PASS。

## R1.3 真实模型委派 E2E 声明

- **NOT_RUN — OPERATOR CONTROLLED ACTION GATE**。模型凭据只存在于活动 OpenClaw
  私有配置/auth profile（`$OPENCLAW_STATE_DIR` 内），不在 shell env 或独立 SecretRef；
  按获批边界不复制模型密钥。真实委派 canary（活动 Gateway + 正式库完整 `*-test`
  克隆）由 Operator 在后续 Controlled Action 执行，Work Item 02 独立复核 Evidence；
  本 Work Item 不执行、不自证、不报 PASS。

## R1.4 Acceptance 更新（round 1）

| AC | 结论 | 证据 |
|---|---|---|
| AC-01 | PASS | VAL-V2-05：三仓库/config hash/Gateway/queue 前后不变 |
| AC-02 | PASS | round 0 VAL-02..VAL-08 全 PASS（未触碰正式 Vault） |
| AC-03 | PASS | cutover-package round 1：唯一公开入口、窄 allowAgents、三技能、生产 VAULT_ROOT（变量/basename）、凭据轮换与回滚的精确脱敏 runbook + 确定性 transformer/semantic diff（VAL-V2-01） |
| AC-04 | PASS | VAL-V2-02：0700/0600、原子写（tmp→0600→fsync→os.replace→parent fsync）、hash/bytes 断言通过 |
| AC-05 | NOT_RUN | 等待独立 Reviewer 对修复后工件给出 PASS |
| AC-06 | NOT_RUN | Work Item 02 |
| AC-07 | NOT_RUN | Work Item 02 |
| AC-08 | NOT_RUN | Work Item 02 |
| AC-09 | PASS | VAL-V2-04：无 secret/绝对 Vault 路径/逐项 URL；写命令 Operator-only 分类；no-index whitespace 无错误 |
| AC-10 | PASS（rehearsal） | VAL-V2-03：完整 clone 演练证明测试目标为一次性 `*-test` 克隆、源零改动、push 禁用、clone 删除无残留；真实模型 canary 本身 NOT_RUN — OPERATOR GATE |

## R1.5 Round 1 FINAL_STATE

- 蓝图库：`main` @ `017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`，仅未跟踪
  `.scratch/2026-08-17-sourcenotes-production-switch/`，未 stage/commit。
- 正式/测试 Vault：未触碰（HEAD/状态同 round 0）。
- 活动配置 hash `de9b9cb1…934424` 不变；默认 Gateway 未 restart/reload；queue 0/0。
- 本轮临时根（`sourcenotes-production-switch-r1-*-test`）已删除，无残留；无测试
  Gateway PID（未启动隔离 Gateway）。
- 未执行 Controlled Action（未写活动配置/未轮换凭据/未写 Vault/未写
  last_known_good/未 stage/commit）。
---

# Round 2 correction（最终自动修复轮，2026-08-17）

依据：`execution-brief-01-repair-round-2.md`（本轮唯一权威自包含简报）与
`evidence/01/review.md` round 2（F-01..F-07、F-09..F-12 open，F-08 closed）。
本轮只修改 `cutover-package.md`、本文件与本轮新建 `/tmp/sourcenotes-production-switch-r2-*-test/**`
（已删除）；不改第一层/issue/review/产品代码/活动配置/两 Vault/Git index/refs。

## R2.1 Finding closure

| Finding | 修复动作 | 验证 | 状态 |
|---|---|---|---|
| F-01 [major] 扫描漏检伪路径与写 primitive | 从 Effort 根对最终两产物重跑全量扫描：绝对路径（allowlist 分类）、token/credential 键值、Bot token 形态、URL、全部 shell/Python 写 primitive，并生成**逐命令分类表**（行号/动作/目标角色/Operator-only/fixture 执行）；未跟踪产物用 `git diff --no-index --check /dev/null <file>` 逐文件检查 | VAL-R2-01 | CLOSED |
| F-02 [major] 包内含绝对 Vault 路径示例 | round 2 包 §2.0 删除全部伪绝对路径占位示例；正文只允许角色变量名与 basename；VAL-R2-01 行 A（绝对 SourceNotes 路径）与行 B（伪路径字面量）对包均无匹配 | VAL-R2-01 | CLOSED |
| F-03 [major] atomic helper 文本读写/固定 temp/异常不清理 | 重写 `atomic.py`：bytes 读写、`tempfile.mkstemp` 唯一 temp、fchmod 0600、完整 write loop、flush/fsync、`os.replace`、parent dir fsync、`finally` 定向 unlink；无固定 `.tmp`、无文本 decode、无 shell/cp 覆盖 | VAL-R2-02 | CLOSED |
| F-04 [major] 暂停入口/本地会话无精确命令；publish 重复 | §2.5 重构为 Gate A–F 精确 DAG：canary 入口暂停用 `channels.telegram.enabled=false`（依据本机 `docs/gateway/config-channels.md` "Each channel starts automatically ... unless `enabled: false`"）；canary 会话用本地 `openclaw agent --agent main --session-key canary-<run_id> --message-file ...`（活动 Gateway loopback，非 `--local`，不复制模型密钥）；Telegram 不用于 canary；**唯一 production publish/reload 只在 Gate E** | VAL-R2-04 | CLOSED |
| F-05 [major] projection 非法 Python | `projection.py` 为完整可执行脚本（无省略号、无非法表达式），只输出批准字段/basename/键集合/token 布尔 | VAL-R2-03 | CLOSED |
| F-06 [major] revoke 后恢复旧 token | 命名回滚点：`PRE_ROTATION_BACKUP`（只审计）→ `POST_MAIN_ROTATION_BASELINE`（main revoke 后回滚目标）→ `CANARY_CANDIDATE` → `POST_ROTATION_SAFE_ROLLBACK`（NotesVaulter revoke 后回滚目标）→ `PRODUCTION_CANDIDATE`；§2.6 恢复矩阵显式**禁止**恢复 `PRE_ROTATION_BACKUP`/任何含旧 token 文件 | VAL-R2-04 | CLOSED |
| F-07 [major] token 注入打印完整候选 | `token_inject.py`/`transform.py` 直接写 0600 私有文件；stdout 只输出固定 `*_WRITTEN=true` + sha；无 `print(json.dumps(full_config))`；投影不读 token 值 | VAL-R2-03 | CLOSED |
| F-08 [minor] | 保持 round 1 CLOSED；本轮未引用任何允许范围外路径 | VAL-R2-01 | CLOSED（保持） |
| F-09 [major] 仅 capture 有 VAULT_ROOT | 三个 skill entry 均 `enabled=true` 且**均**设 `env.VAULT_ROOT`（保留各自其它 env/未知键）；projection `vault_roots` 三值一致 | VAL-R2-03 | CLOSED |
| F-10 [major] transformer 不 fail-closed | `transform.py` fail-closed 断言（agents.list 存在且 main/notesvaulter 各恰一、skills.entries 存在且三 entry 为 dict、bindings 为 list、telegram accounts 为 dict、VAULT_ROOT 绝对且 basename 符合角色）；六类结构冲突负例 + role/basename 负例 + token 文件 0600 负例全部 exit≠0 且不写 candidate | VAL-R2-03 | CLOSED |
| F-11 [major] canary 删除只查后缀 | `canary_provenance.py init` 写私有 marker（0600，不入 Git）+ ledger（同 dev/inode）；`cleanup_canary.py` 删除前重验父目录 0700/realpath、精确 basename/run_id、marker 常规 0600 非跟随、dev/inode 与 ledger、非 symlink、无运行中进程（/proc cwd/fd）、与正式路径不相等；仅经 fail-closed helper 定向删除（rename tombstone → 复验 inode → rmtree），无裸 `rm -rf` | VAL-R2-05 | CLOSED |
| F-12 [major] §2.5/§2.6 重复 production publish | 唯一 production publish/reload 只在 Gate E（§2.5）；Gate F 只读复核不 publish；恢复矩阵每失败边单目标 | VAL-R2-04 | CLOSED |

## R2.2 VAL-R2-01 — AC-09 隐私扫描与写 primitive 分类（cwd=Effort 根）

- cwd：`/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-production-switch/`
  （Project State 自身路径，扫描目标为 `cutover-package.md` 与 `evidence/01/execution.md`）。

| 检查 | 命令 | 退出码 | 关键输出 |
|---|---|---|---|
| 绝对 SourceNotes 路径 | `grep -nE '/[A-Za-z0-9_./-]*SourceNotes(-test)?([/ ")]|$)' cutover-package.md evidence/01/execution.md` | 1（无匹配） | 无绝对 Vault 路径；唯一 SourceNotes 出现均为 basename/变量名/历史 finding 描述 |
| 伪绝对路径占位符 | `grep -nE '/absolute/path' cutover-package.md evidence/01/execution.md` | 0（唯一命中为本行扫描命令自身描述文本，排除自引用后无匹配） | 包与 Evidence 均无 `/absolute/path` 字面量内容 |
| shell 尖括号占位符 | bash 块内 `<`/`>` 行扫描 | 3 处均为合法 shell 语法 | `printf ... > "$CANARY_VAULT_ROOT/..."`、`cat > ... <<EOF`、注释 `query_hits>=1`；无 shell 尖括号占位符 |
| token/credential 键值 | `grep -nE '[0-9]{8,10}:[A-Za-z0-9_-]{35}|sk-[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|(botToken\|apiKey\|password\|token\|secret)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"']{8,}' cutover-package.md evidence/01/execution.md` | 1（无匹配） | 无 token 值/键值对 |
| Bot token 形态 | `grep -nE '[0-9]{8,10}:[A-Za-z0-9_-]{35}' cutover-package.md evidence/01/execution.md` | 1（无匹配） | 无 Bot API token |
| 逐项 URL | `grep -nE 'https?://' cutover-package.md evidence/01/execution.md` | 1（无匹配） | 无正文/逐项 URL |
| whitespace（未跟踪） | `git diff --no-index --check /dev/null cutover-package.md`；`git diff --no-index --check /dev/null evidence/01/execution.md` | 1（有内容）；stdout 无 whitespace error | 通过 |
| whitespace（跟踪区） | `git diff --check -- .scratch/2026-08-17-sourcenotes-production-switch` | 0 | 无空白错误 |

逐命令写 primitive 分类表（行号指向最终 `cutover-package.md`；全部真实写入命令首行为
`CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED`）：

| 行号 | 动作 | 目标角色 | Operator-only | fixture 执行 |
|---|---|---|---|---|
| 262 | `transform.py --role canary`（§1.1 示例） | 私有 STATE_DIR candidate | ✔ | ✔ VAL-R2-03 |
| 339 | `token_inject.py`（§1.1 示例） | 私有 candidate | ✔ | ✔ VAL-R2-03 |
| 673–674 | `mkdir -p "$STATE_DIR"` + `chmod 0700` | 私有状态目录 | ✔ | ✔ VAL-R2-02/04（0700 断言） |
| 676–677 | `atomic.py backup/checksum` | PRE_ROTATION_BACKUP | ✔ | ✔ VAL-R2-02（字节精确） |
| 730–731 | `atomic.py backup/checksum`（Gate A） | PRE_ROTATION_BACKUP | ✔ | ✔ VAL-R2-04 |
| 738–739 | `atomic.py backup` + `token_inject.py` | POST_MAIN_ROTATION_BASELINE | ✔ | ✔ VAL-R2-04 |
| 746 | `atomic.py write` | ACTIVE_CONFIG（基线发布） | ✔ | ✔ VAL-R2-02 |
| 747 | `openclaw gateway restart` | 活动 Gateway | ✔ | ✗（不执行 Controlled Action） |
| 880–881 | `mkdir -p "$STATE_DIR/canary"` + `chmod 0700` | canary 父目录 | ✔ | ✔ VAL-R2-05（0700） |
| 887 | `git clone --no-hardlinks` | canary 克隆（*-test） | ✔ | ✔ VAL-R2-05 / round 1 VAL-V2-03 |
| 889 | `git remote remove origin` | canary 克隆 | ✔ | ✔ round 1 VAL-V2-03 |
| 890 | `git push`（预期 fatal） | canary 克隆 | ✔ | ✔ round 1 VAL-V2-03（rc=128） |
| 894–895 | `canary_provenance.py init` | marker+ledger（0600） | ✔ | ✔ VAL-R2-05 |
| 899 | `printf ... > "$CANARY_VAULT_ROOT/...marker.txt"` | canary 克隆 | ✔ | ✔ VAL-R2-05（写 clone 文件） |
| 900–903 | `git -C clone config/add/commit` | canary 克隆 | ✔ | ✔（clone 内 git 写原语，VAL-R2-05/round 1 演练等价） |
| 907 | `transform.py --role canary`（Gate B） | CANARY_CANDIDATE | ✔ | ✔ VAL-R2-03 |
| 908 | `token_inject.py` | CANARY_CANDIDATE | ✔ | ✔ VAL-R2-03 |
| 919 | `atomic.py write` | ACTIVE_CONFIG（canary publish） | ✔ | ✔ VAL-R2-02 |
| 920 | `openclaw gateway restart` | 活动 Gateway | ✔ | ✗ |
| 929 | `cat > "$STATE_DIR/canary-prompt-<id>.txt" <<EOF` | 私有 prompt 文件 | ✔ | ✔（heredoc 写文件原语；会话本体 NOT_RUN） |
| 941 | `openclaw agent --agent main --session-key canary-<id> --message-file ... --json` | 活动 Gateway 本地会话（委派 canary） | ✔ | ✗（真实模型 E2E NOT_RUN — Operator GATE） |
| 956 | `transform.py --role safe-rollback` | POST_ROTATION_SAFE_ROLLBACK | ✔ | ✔ VAL-R2-04 |
| 957 | `token_inject.py` | POST_ROTATION_SAFE_ROLLBACK | ✔ | ✔ VAL-R2-04 |
| 976 | `transform.py --role production` | PRODUCTION_CANDIDATE | ✔ | ✔ VAL-R2-04 |
| 977 | `token_inject.py` | PRODUCTION_CANDIDATE | ✔ | ✔ VAL-R2-04 |
| 987 | `atomic.py write`（★唯一 production publish） | ACTIVE_CONFIG | ✔ | ✔ VAL-R2-02 |
| 989 | `openclaw gateway restart` | 活动 Gateway | ✔ | ✗ |
| 1020 | `atomic.py write`（恢复模板） | ACTIVE_CONFIG | ✔ | ✔ VAL-R2-02 |
| 1022 | `openclaw gateway restart` | 活动 Gateway | ✔ | ✗ |
| 1227 | `cleanup_canary.py` | canary 克隆删除 | ✔ | ✔ VAL-R2-05 |
| §2.2 散文 | `touch "$TOKEN_ROTATED_MARKER"` + `chmod 0600` | 私有轮换标记 | ✔ | ✔（fixture chmod 0600 等价） |

脚本内部写 primitive（嵌入式，fixture 全部实际执行）：`atomic.py` 的
`open(...,'wb')`/memoryview write loop/`flush`/`fsync`/`os.replace`/parent dir
fsync/`finally` unlink（VAL-R2-02 成功 + WRITE/FSYNC/REPLACE 三类失败注入）；
`transform.py`/`token_inject.py` 经 `atomic_write` 写 0600 candidate（VAL-R2-03）；
`canary_provenance.py` 的 `open/wb`+`chmod 0600`（VAL-R2-05）；`cleanup_canary.py`
的 `os.rename`→tombstone→`shutil.rmtree`+parent fsync（VAL-R2-05）。只读命令
（validate/status/rev-parse/checksum/projection/skills check/agent 会话/gateway
status/health/tasks list）不属写 primitive，未列入。

结论：PASS。

## R2.3 VAL-R2-02 — AC-04 二进制安全 atomic fixture（cwd=本轮临时根）

- cwd：`/tmp/sourcenotes-production-switch-r2-20260817-134145-test/`
- 命令：`python3 -B scripts/run_atomic_fixture.py` → **exit 0**，`ATOMIC_FIXTURE_OK`。
- 关键输出（脱敏）：
  - 载荷 = `bytes(range(256))*3 + b"\n\xff\x00trailing\n"`（非 UTF-8 + 尾随换行）；
    写/备份/发布/恢复四处 sha 全同 `638ce4ca…164d5`，逐字节一致。
  - 失败注入（`ATOMIC_FAULT_WRITE|FSYNC|REPLACE=1`）：三次 rc=1，active 原字节
    `ORIGINAL-BYTES` 保留、0600 保持、`.atomic-*` temp 零残留。
  - 权限：state dir `0o700`、文件 `0o600`（脚本断言）。
- 结论：PASS（F-03）。

## R2.4 VAL-R2-03 — AC-03 transformer/projection/eligibility fixture（cwd=本轮临时根）

- 命令：`python3 -B scripts/run_transform_fixture.py` → **exit 0**，`TRANSFORM_FIXTURE_OK`。
- 关键输出（脱敏）：
  - canary/production/safe-rollback 三角色转换 rc=0；确定性两次 sha 同
    `68ca9563d33138831786b69e7291b6accfd7ea1240464927662c77c914cd3ad2`（det-1/det-2 cmp 一致）；
    未知字段保留（main `identity`、`trello` entry、`gateway.port`）。
  - F-09：三技能 `env.VAULT_ROOT` 均等于 canary 目标；projection
    `vault_roots` 三值均 `SourceNotes-production-canary-r2fixture-test`。
  - candidate validate：`OPENCLAW_CONFIG_PATH=<candidate-canary-1.json> openclaw config validate`
    → rc=0，`Config valid: ...`。
  - 三技能 eligible：`OPENCLAW_CONFIG_PATH=<candidate> openclaw skills check --agent notesvaulter`
    → rc=0，`Total: 118 / Eligible: 82 / Visible to model: 3 / Available as command: 3 /
    Missing requirements: 0`；`skills info` 三技能均 `✓ Ready`、`Visible to model: yes`、
    `Available as command: yes`（只读 CLI，不触碰活动配置）。
  - projection（canary candidate + rotated marker）：`main name=Steward`、
    `allowAgents=["notesvaulter"]`、notesvaulter 三技能、bindings 仅
    `main→telegram:default`、`telegram_account_keys=["default"]`、
    `telegram_enabled=false`、`main_token_present=true`、`main_token_rotated=true`、
    `notesvaulter_token_present=false`；stdout 无任何 token 值。
  - 负例（全部 rc=2 且不写 candidate）：no-main、dup-notesvaulter、
    skill-not-dict、bindings-not-list、no-accounts、role/basename 不符；
    token 文件 0644 → `TOKEN_INJECT_FAILED` rc=1。
- 结论：PASS（F-05/F-07/F-09/F-10）。

## R2.5 VAL-R2-04 — AC-03/04 轮换状态机与唯一 cutover DAG（cwd=本轮临时根）

- 命令：`python3 -B scripts/run_state_machine_fixture.py` → **exit 0**，`STATE_MACHINE_FIXTURE_OK`。
- 断言（脱敏）：PRE_ROTATION_BACKUP 含旧 token 且 main revoke 后从恢复选择中排除；
  POST_MAIN_ROTATION_BASELINE（新 token）为 revoke 前回滚目标；CANARY_CANDIDATE
  ingress paused（`telegram_enabled=false`）且无 notesvaulter binding/account；
  POST_ROTATION_SAFE_ROLLBACK 为 revoke 后唯一回滚目标（vault-capture disabled、
  VAULT_ROOT basename=SourceNotes-test、main token 新）；PRODUCTION_CANDIDATE 由
  safe-rollback 派生（三技能 enabled、production VAULT_ROOT、telegram enabled）；
  DAG 模型 `publish_production` 恰出现 1 次（F-12）。
- 结论：PASS（F-04/F-06/F-12）。

## R2.6 VAL-R2-05 — AC-10 clone provenance-safe cleanup（cwd=本轮临时根）

- 命令：`python3 -B scripts/run_cleanup_fixture.py` → **exit 0**，`CLEANUP_FIXTURE_OK`。
- 断言（脱敏）：正例——fixture 源 git 库 → 完整 clone 为
  `SourceNotes-production-canary-r2clean-test` → `canary_provenance.py init`
  （marker 0600 不入 Git、ledger 同 dev/inode）→ `cleanup_canary.py` rc=0
  `CANARY_CLEANED=true`；克隆删除、父目录 0700 清空、源 HEAD/树/status 零改动。
  负例——伪 run_id marker、换 inode（目录重建）、symlink 目标、错误父目录、
  canary==production 路径、运行中进程（/proc cwd 检测）全部 `CLEANUP_REFUSED` rc=2
  且克隆保留、源不变。
- 结论：PASS（F-11）；真实模型 E2E 本身仍 **NOT_RUN — OPERATOR CONTROLLED ACTION GATE**。

## R2.7 VAL-R2-06 — AC-01 只读基线前后不变

- cwd：三仓库根与宿主；命令与 round 1 VAL-V2-05 相同。
- pre/post 一致：蓝图 `main@017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`（=origin/main，
  `git status --short --branch` 仅 `?? .scratch/` 本 Effort 目录）；正式 Vault
  `main@ec1a90eb…` clean；测试 Vault 既有脏状态原样（只读）；活动配置 sha
  `de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424`（0600）不变；
  queue 0/0；默认 Gateway running（pid 32037，loopback 127.0.0.1:18789），未
  restart/reload。结论：PASS。

## R2.8 嵌入脚本一致性（额外证据）

从最终 `cutover-package.md` 提取六个内嵌脚本（atomic/transform/token_inject/
projection/canary_provenance/cleanup_canary）与 fixture 验证版本逐字节一致
（去除围栏尾随换行后 `identical=True`，`ast.parse` 全部通过），并在全新
`/tmp/sourcenotes-production-switch-r2-e2e-*-test` 上重跑四套 fixture 全 PASS。

## R2.9 Acceptance 更新（round 2）

| AC | 结论 | 证据 |
|---|---|---|
| AC-01 | PASS | VAL-R2-06：三仓库/config hash/Gateway/queue 前后不变 |
| AC-02 | PASS | round 0 VAL-02..VAL-08 全 PASS（未触碰正式 Vault） |
| AC-03 | PASS | round 2 包：唯一公开入口、窄 allowAgents、三技能（均 VAULT_ROOT）、生产 VAULT_ROOT（变量/basename）、凭据轮换与命名回滚点 runbook、确定性 fail-closed transformer/projection、Gate A–F 精确 DAG（VAL-R2-03/04） |
| AC-04 | PASS | VAL-R2-02：二进制安全原子写（唯一 temp→0600→fsync→os.replace→parent fsync→finally 清理）+ 失败注入 + 0700/0600 断言 |
| AC-05 | NOT_RUN | 等待独立 Reviewer 对修复后工件给出 PASS（本轮不自证） |
| AC-06 | NOT_RUN | Work Item 02（Operator Controlled Action 后复核） |
| AC-07 | NOT_RUN | Work Item 02（生产 canary 只读复核） |
| AC-08 | NOT_RUN | Work Item 02（last_known_good 写入与 soak 起点） |
| AC-09 | PASS | VAL-R2-01：无 secret/绝对 Vault 路径/伪路径/尖括号占位符/逐项 URL；写 primitive 逐命令分类；no-index whitespace 无错误 |
| AC-10 | PASS（rehearsal） | VAL-R2-05：provenance-safe 克隆创建/删除正负例、源零改动；真实模型 canary 本身 NOT_RUN — OPERATOR GATE |

## R2.10 Round 2 FINAL_STATE

- 蓝图库：`main` @ `017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`（=origin/main），仅未跟踪
  `.scratch/2026-08-17-sourcenotes-production-switch/`，未 stage/commit。
- 正式 Vault：`main` @ `ec1a90eb…` clean，未触碰；测试 Vault：既有脏状态原样，未触碰。
- 活动配置 sha `de9b9cb1…934424` 不变；默认 Gateway 未 restart/reload；queue 0/0。
- 本轮临时根 `sourcenotes-production-switch-r2-20260817-134145-test` 与
  `sourcenotes-production-switch-r2-e2e-*-test` 均已删除，无残留（见下节清理命令）。
- 未执行 Controlled Action：未写活动配置、未轮换/撤销凭据、未写两 Vault、未写
  last_known_good、未 stage/commit、未执行 runbook 中任何 OPERATOR ONLY 命令。

## R2.11 临时目录清理记录

```bash
# cwd: 宿主（/tmp 下）
rm -rf /tmp/sourcenotes-production-switch-r2-20260817-134145-test
rm -rf /tmp/sourcenotes-production-switch-r2-e2e-854514-test   # 嵌入脚本端到端复验临时根
find /tmp -maxdepth 1 -type d -name 'sourcenotes-production-switch-*-test' -print
# 期望：无输出（零残留）
```

结果：两个 round 2 临时根均已删除；`find /tmp -maxdepth 1 -type d -name
'sourcenotes-production-switch-*-test'` 无输出；无测试 Gateway PID（未启动隔离
Gateway）。`/tmp/opencode/` 下的生成脚本/模板/schema 属本机既有 scratch 目录，
非本轮 `*-test` 产物（不含 Vault 数据/secret；`oc-schema.json` 为公开 JSON
schema）。
