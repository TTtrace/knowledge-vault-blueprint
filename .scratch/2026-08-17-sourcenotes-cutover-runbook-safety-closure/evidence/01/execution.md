# Execution Evidence — safety closure Work Item 01（close final runbook findings）

- Effort: `.scratch/2026-08-17-sourcenotes-cutover-runbook-safety-closure/`
- Work Item: `issues/01-close-final-runbook-findings.md`（claimed，Role: Executor）
- 日期: 2026-08-17
- 批准链：本 Effort `spec.md`（approved）→ `plan.md`（approved）→ Operator 授权原文
  `批准新建窄范围安全闭环 Work Item 并继续。` 与 `同意再次更换 Executor 并继续安全闭环
  Work Item。` → 本 Work Item（claimed）→ `execution-brief-01.md`（唯一自包含第二层
  简报，逐字遵守）。
- 产物：修改 parent `cutover-package.md`（`../2026-08-17-sourcenotes-production-switch/`，
  round 3 safety closure 修订）与本文件。
- 范围：关闭 F-04 / F-07 / F-11 / F-13 / F-14 / F-15；证明 F-01/F-02/F-03/F-05/F-06/
  F-08/F-09/F-10/F-12 不回归；不修改产品代码、活动配置、默认 Gateway、两个 Vault、
  Git index/refs；无 Controlled Action；真实模型 E2E **NOT_RUN — OPERATOR GATE**。

## 1. 执行摘要（STEP-01..07）

| STEP | 内容 | 结果 |
|---|---|---|
| STEP-01 | F-04：DAG 重排为「先发布并验证 INGRESS_PAUSED_BASELINE → 再轮换 token」；新增 `pause_ingress.py`；canary 仅本地 `openclaw agent --session-key "$CANARY_SESSION_KEY" --message "$CANARY_PROMPT"`；唯一恢复点 Gate E | PASS（VAL-S01/S01b） |
| STEP-02 | F-07：§2.0 改为 fail-closed preamble（`set -Eeuo pipefail` + 全部 `: "${VAR:?}"`）；`CANARY_VAULT_ROOT` 只由已验证 `STATE_DIR`+`RUN_ID` 派生并验证；删除伪值/尖括号占位符 | PASS（VAL-S02） |
| STEP-03 | F-11：canary parent 创建/删除均 lstat 非 symlink；marker 与 ledger 同 schema（run_id/source_head/realpath/dev/inode）且完全匹配、常规文件（no-follow）0600 owner=uid；cleanup 失败只报告不删除 | PASS（VAL-S03） |
| STEP-04 | F-13：全部 bash 块 `set -Eeuo pipefail` + 显式 if/else 断言（含预期失败 push）+ trap 只报告；全部块 `bash -n` 通过；fixture 注入前置失败 sentinel 不执行 | PASS（VAL-S02/S01b） |
| STEP-05 | F-14：canary 唯一标记改为 Capture 生成的 Markdown note（标题/正文含 RUN_ID 派生 marker）；Query 命中同一 marker/note id；删除 `.marker.txt` 作为 query 证据；断言顺序 capture→staged `.md`→query≥1→maintenance→tool failures=0 | PASS（VAL-S04） |
| STEP-06 | F-15：新增 `vault_fingerprint.py` 预克隆指纹锁定（branch/HEAD/tree/index/status/ls-files）；clone 后/canary 前后/cleanup 前/publish 前/收尾逐项 check；clone provenance 以预克隆指纹为准；漂移拒绝 | PASS（VAL-S05） |
| STEP-07 | VAL-S01..S07 + 已关闭 finding 回归 + 隐私/空白扫描 + 本证据文件 | PASS（VAL-S06/S07） |

## 2. preflight 基线（VAL-S07 pre，只读）

三仓库（cwd 为各仓库根；Vault 只记录 basename）：

| 项 | 值 |
|---|---|
| 蓝图库 | `main` @ `017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`（=origin/main），`git status --short --branch` 仅 `?? .scratch/`（本 Effort 目录，预期）；`git diff --cached` 空 |
| 正式 Vault `SourceNotes` | `main` @ `ec1a90eb9d41df77cf74e44d51e703d0379882e7`，clean；`HEAD^{tree}`=`2f8ebe40b7b61caf3a1dc8628b54fd650ec9a66d`；index 文件 SHA-256=`532676e58990bc858300231062fa67d7ece27e939a7edda90db395aaea1b7e14`；`status --porcelain=v2 -z` SHA-256=`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空，0 字节）；`ls-files -s -z` SHA-256=`ad789a83511c033dddc7ff14e464311a805477b465fe86c06839d4e6305bbe73` |
| 测试 Vault `SourceNotes-test` | `main` @ `ec1a90eb9d41df77cf74e44d51e703d0379882e7`，既有脏状态（大量 staged/untracked）——只读记录，不清理/reset |
| 活动配置 | `~/.openclaw/openclaw.json` SHA-256=`de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424`，0600 |
| OpenClaw | `2026.7.1-2 (0790d9f)`；Gateway systemd user 服务 running（pid 32037），bind loopback `127.0.0.1:18789`，probe ok |
| 队列 | `openclaw tasks list --status running|queued` → 0 queued · 0 running · 0 issues |
| /tmp 残留 | `find /tmp -maxdepth 1 -type d -name 'sourcenotes-cutover-safety-*-test'` 无输出（本轮新建前为空） |

## 3. STEP-01 — F-04 入口暂停先行（VAL-S01 / VAL-S01b）

### 3.1 对 parent package 的修改

- §2.5 顶部声明：任何 token 读取/轮换之前，Gate A 必须先构造、dry-run、原子发布并
  验证 **INGRESS_PAUSED_BASELINE**（`channels.telegram.enabled=false`，capture 保持
  disabled、无新任务），验证 config/health、queue 0/0、Telegram ingress disabled。
- 新增内嵌脚本 `pause_ingress.py`：唯一语义变化为 `channels.telegram.enabled=false`，
  深复制保留全部其它字段；fail-closed 断言（合法 JSON、telegram dict + enabled bool、
  vault-capture entry dict 且 enabled==False）；stdout 只输出 `PAUSE_WRITTEN=true sha=64位十六进制哈希`。
- Gate A 重排为 8 步：前置确认 → PRE_ROTATION_BACKUP（只审计）→ 构造+dry-run
  INGRESS_PAUSED_BASELINE → 原子发布+reload+health → 验证暂停生效（queue 0/0 +
  projection `telegram_enabled=false`）→ **只有此时才允许 main token `/revoke`** →
  `POST_MAIN_ROTATION_BASELINE` 基于 INGRESS_PAUSED_BASELINE 且保持 ingress paused →
  发布并验证。
- Gate C：canary 只由 Operator 本地
  `openclaw agent --agent main --session-key "$CANARY_SESSION_KEY" --message "$CANARY_PROMPT" --json`
  触发；Telegram 不参与。
- Gate E：只有 production 候选 `telegram_enabled=true`（唯一恢复 default main
  Telegram ingress 的点，F-12 回归）；§2.6 恢复矩阵 Gate A 行更新为
  `POST_MAIN_ROTATION_BASELINE`（ingress paused）。

### 3.2 VAL-S01 — ingress-pause/rotation 状态机 fixture

- cwd：本轮临时根 `/tmp/sourcenotes-cutover-safety-20260817-174826-test/`（脚本
  `run_state_machine_s01.py` 从 `cutover-package.md` 提取的 8 个内嵌脚本，逐字节一致）。
- 命令：`python3 -B run_state_machine_s01.py` → **exit 0**，stdout：
  `STATE_MACHINE_S01_OK` + `paused_before_rotation=yes telegram_paused_through_canary=yes
  only_production_restores=yes`。
- 关键断言：pause_ingress 只改 `telegram.enabled`（深比较 active vs paused 其余全等）；
  token 值在 pause 前后不变（无 token 先读）；POST_MAIN_ROTATION_BASELINE 保持
  `telegram_enabled=false` 且 `main_token_rotated=true`；CANARY_CANDIDATE 保持暂停且
  移除 notesvaulter binding/account；PRODUCTION_CANDIDATE 才 `telegram_enabled=true`；
  `PRE_ROTATION_BACKUP` 不在 revoke 后回滚目标集合；production publish 在 DAG 模型
  中恰 1 次。

### 3.3 VAL-S01b — 真实 Gate A bash 块 shell dry-run（openclaw shim）

- cwd：同上。
- 命令：`bash run_gateA_dryrun_s01b.sh` → **exit 0**，`GATE_A_DRYRUN_S01B_OK`。
- 做法：§2.0 preamble（block-03）+ Gate A 块（block-06）逐字提取；`openclaw` 用只读
  mock shim（tasks/validate/gateway，绝不触碰真实 Gateway/配置）；fixture 活动配置
  （telegram enabled、capture disabled、双 binding/account、fixture token）。
- 关键输出：`PAUSE_WRITTEN=true` → `ATOMIC_WRITTEN=true`（发布 INGRESS_PAUSED_BASELINE，
  sha=6a62ade392c13f22415f30bb740dab3211392fc11811004833024d6a21681cf192c13f22415f30bb740dab3211392fc11811004833024d6a21681cf1）→ projection 显示 `telegram_enabled=false`、`main_token_rotated=false`
  （此时尚未读取 token）→ 随后 `TOKEN_INJECTED=true` → projection
  `telegram_enabled=false`、`main_token_rotated=true` → 再次 `ATOMIC_WRITTEN=true`（发布
  POST_MAIN_ROTATION_BASELINE，sha=66a7a880e33c9b37691ce7cc0dff5e6552558dd9a4e3b4928d9694c43111a94ce33c9b37691ce7cc0dff5e6552558dd9a4e3b4928d9694c43111a94c）。
- 最终断言：`ACTIVE == POST_MAIN_ROTATION_BASELINE`；`telegram_enabled=false`（保持
  暂停）；`main_token` 为新值；notesvaulter 轮换前原状保留。
- fail-fast 断言（F-13 并入）：在 Gate A 块注入 `false` 前置失败 → rc=1 且
  `SENTINEL_EXECUTED` 未出现。

## 4. STEP-02 — F-07 fail-closed 变量（VAL-S02）

### 4.1 对 parent package 的修改

- §2.0 重写为 fail-closed preamble：首行 `set -Eeuo pipefail`，随后
  `: "${STATE_DIR:?未定义即退出}"` / `: "${ACTIVE_CONFIG:?未定义即退出}"` /
  `: "${PRODUCTION_VAULT_ROOT:?未定义即退出}"` / `: "${MAIN_BOT_TOKEN_FILE:?未定义即退出}"` /
  `: "${TEST_VAULT_ROOT:?未定义即退出}"` / `: "${RUN_ID:?未定义即退出}"` / `: "${CANARY_SESSION_KEY:?未定义即退出}"`。
- `CANARY_VAULT_ROOT` 只由已验证 `STATE_DIR` + `RUN_ID` 派生，并逐项验证：
  absolute、`dirname == "$STATE_DIR/canary"`、basename 精确等于
  `SourceNotes-production-canary-${RUN_ID}-test`、目标初始不存在（`-e` 则拒绝）。
- 删除全部伪值/真实路径/中文方括号占位/尖括号占位符；`PRODUCTION_VAULT_ROOT`/`TEST_VAULT_ROOT`
  只声明 basename 语义，真实值仅 Operator 私有会话持有。

### 4.2 VAL-S02 — preamble 正负例 + fail-fast sentinel + bash -n

- cwd：本轮临时根。
- 命令：`bash run_failfast_s02.sh` → **exit 0**，`PREAMBLE_AND_FAILFAST_S02_OK`。
- 正例：全部变量就绪时 source §2.0 preamble 成功；派生变量（RUN_ID、CANARY_VAULT_ROOT、
  CANARY_SESSION_KEY、CANARY_MARKER_STRING、CANARY_PROMPT、INGRESS_PAUSED_BASELINE、
  VAULT_FINGERPRINT_LEDGER 等）全部就绪。
- 负例：`env -u STATE_DIR|ACTIVE_CONFIG|PRODUCTION_VAULT_ROOT|MAIN_BOT_TOKEN_FILE|
  TEST_VAULT_ROOT` 逐一 source → 均 rc=1 且 `SENTINEL_EXECUTED` 未出现；canary 目标
  已存在（stub `date` 使 RUN_ID 在单 shell 内稳定）→ 拒绝 rc=1。
- fail-fast sentinel：`set -Eeuo pipefail; false; echo SENTINEL_EXECUTED` → rc=1、
  sentinel 未运行、trap 触发；预期失败显式断言模式（无 remote 的 push → if/else
  expected）→ rc=0 输出 `expected` + `AFTER`。
- bash -n：package 全部 15 个 bash 块逐块 `bash -n` → 全部通过（无 SYNTAX FAIL）。
- Gate A–F / §2.6 / §2.7 块均以 `set -Eeuo pipefail` 开头（grep 校验）。

## 5. STEP-03 — F-11 provenance 加固（VAL-S03）

### 5.1 对 parent package 的修改

- `canary_provenance.py init`：新增 parent `os.path.islink` 拒绝；marker 与 ledger 内容
  schema 统一为 `{run_id, source_head, realpath, dev, inode}`（**两边完全一致**）；写入
  后对两者 lstat 复验：常规文件（no-follow）、非 symlink、0600、owner==当前 uid。
- `cleanup_canary.py`：新增 parent `os.path.islink` 拒绝；新增 `_verify_private_file`
  （lstat 常规文件、非 symlink、0600、owner==uid）用于 marker 与 ledger；新增
  `PROVENANCE_KEYS` 全字段（run_id/source_head/realpath/dev/inode）marker 与 ledger
  逐项比对；任何失败 `CLEANUP_REFUSED` 且**只报告不删除**。
- §2.6 cleanup 用法块：删除前先 `vault_fingerprint.py check`（F-15），再 cleanup。

### 5.2 VAL-S03 — provenance 正负例

- cwd：本轮临时根。
- 命令：`python3 -B run_cleanup_s03.py` → **exit 0**，`CLEANUP_S03_OK`。
- 正例：fixture 源 git 库 → clone 为 `SourceNotes-production-canary-*-test` →
  `canary_provenance.py init`（ledger==marker 全等；两者均常规文件 0600 owner=uid）→
  `cleanup_canary.py` rc=0 `CANARY_CLEANED=true`；源库 status 零改动。
- 负例（全部 rc=2 `CLEANUP_REFUSED` 且克隆保留）：parent symlink（realpath 拒绝）、
  ledger symlink、ledger 0644、ledger run_id mismatch、ledger source_head mismatch、
  marker symlink、canary==production 路径。
- 输出摘要：`refused[parent-symlink]=canary path realpath mismatch`、
  `refused[ledger-symlink]=ledger not a regular file (no-follow)`、
  `refused[ledger-0644]=mode 非 0600`、`refused[ledger-mismatch-runid]=ledger
  dev/inode/run_id does not match target`、`refused[ledger-mismatch-sourcehead]=
  ledger/marker source_head mismatch`、`refused[marker-symlink]=marker not a regular
  file (no-follow)`。

## 6. STEP-04 — F-13 fail-fast shell（VAL-S02/S01b 覆盖）

- 全部 15 个 bash 块 `bash -n` 通过（VAL-S02）。
- 每个完整 Operator shell 块首行 `set -Eeuo pipefail`；每个 test/clone/backup/
  transform/validate/publish/reload/probe 以 `if ! cmd; then die; fi` 或 `&&`
  显式串联（Gate A/B/C/D/E/F、§2.3、§2.6、§2.7 均已改写）；预期失败（无 remote 的
  `git push`）显式写成 if/else 断言（Gate B 第 3 步，输出
  `GATE_B_PUSH_EXPECTED=push 按预期失败`）。
- trap 只向 stderr 报告失败点与恢复目标，不触碰正式 Vault 或未知路径（不执行删除）。
- 真实 Gate A 块注入前置失败 → 后续 sentinel 不执行（VAL-S01b）。
- 独立 fail-fast/expected-failure 模式 fixture（VAL-S02）PASS。

## 7. STEP-05 — F-14 可查询 Markdown canary 标记（VAL-S04）

### 7.1 对 parent package 的修改

- Gate B：删除「写入 `sourcenotes-canary-RUNID.marker.txt` + git add/commit」步骤
  （原 F-14 缺陷：Query 只扫 Markdown，`.txt` 命中条件不可成立）。
- Gate C：CANARY_PROMPT 要求 NotesVaulter：① Capture 一个标题/正文含
  `"${CANARY_MARKER_STRING}"`（RUN_ID 派生的非秘密 marker）的唯一 idea，确认 staged
  相对路径为 canary 克隆内 `.md`；② Query 同一 marker，报告命中数与被捕获 note
  id/相对路径（marker 必须在 Markdown note 正文中，不在独立 `.txt`）；③ 对该 vault 跑
  maintenance。返回有界 JSON：`spawned_agent, capture_ok, staged_path, query_hits,
  maintenance_ok, errors`。
- 断言顺序（写在 runbook）：capture ok/ready → staged path 为 canary 内 `.md` →
  query count>=1 且结果含相同 marker/note id → maintenance ok → tool failures=0。
- 注明：provenance marker（`.sourcenotes-canary.marker`）仅作清理绑定证据，不作为
  query target。

### 7.2 VAL-S04 — idea capture→query→maintenance（无模型，仓库受控入口）

- cwd：本轮临时根。
- 命令：`bash run_capture_query_s04.sh` → **exit 0**，`CAPTURE_QUERY_MAINT_S04_OK`。
- 步骤与关键输出：
  1. 按仓库测试套件权威结构（`tests/skills/test_vault_capture.py` setUp）构造一次性
     git Vault（basename `SourceNotes-production-canary-s04run-test`，绝对路径不记录）。
  2. `python3 -B scripts/sourcenotes_agent.py capture preflight` →
     `{"git": true, "layout": true, "ok": true, "queue_ignored": true}`（rc=0）。
  3. `capture stage --json-file <idea.json>`（idea 标题/正文含
     `sourcenotes-canary-marker-s04run`）→ `ok:true, ingest_status:ready, staged:true`，
     staged_path=`notes/ideas/ID--canary-idea-sourcenotes-canary-marker-s04run.md`
     （`.md`，相对路径，位于 canary 内）。
  4. marker 存在于 note 正文（grep 命中）。
  5. `query search 该 marker` → `{"count": 1, "ok": true, "results":[{"id": "note-id", "path": "notes/ideas/note-id.md"}]}`，
     命中刚生成的 note id/相对路径。
  6. `maintenance report` → `ok:true`，git.dirty_count=1、staged_paths 为同一 note。
  7. 泄漏断言：所有输出不含临时 Vault 绝对路径（leak_total=0）；canary git status 仅
     该 `.md` 被暂存，无 `marker.txt` 证据。
- 结论：capture ok/ready、staged path 为 canary 内 `.md`、query count>=1 且含相同
  marker/note id、maintenance ok、tool failures=0 —— 与 Gate C 断言顺序逐项一致。

## 8. STEP-06 — F-15 预克隆指纹（VAL-S05）

### 8.1 对 parent package 的修改

- 新增内嵌脚本 `vault_fingerprint.py`：
  - `capture VAULT_ROOT LEDGER [EXPECTED_HEAD]`：只读记录 branch、完整 HEAD、
    `HEAD^{tree}`、index 文件 SHA-256、`git status --porcelain=v2 -z` 的 SHA-256 与
    条目数、`git ls-files -s -z` SHA-256；要求 clean 且（给定时）HEAD==批准基线；
    ledger 0600 私有，只含 basename 与指纹值（无绝对路径）。
  - `check VAULT_ROOT LEDGER [CLONE_ROOT]`：逐项重算并等值比较；任一漂移
    `FINGERPRINT_DRIFT=字段名` 非零退出，不修改 Vault；给定 CLONE_ROOT 时同时验证
    clone HEAD/tree 等于**预克隆**记录值（clone provenance 不取 clone 后 source 读取）。
  - `head LEDGER`：输出记录 HEAD（供 canary_provenance / 比对使用）。
- §2.3 新增指纹 ledger 说明；Gate B 第 0 步 `capture`（clone 前，EXPECTED_HEAD=
  `ec1a90eb9d41df77cf74e44d51e703d0379882e7`）；clone 后 `check 并传入克隆`；canary init 前 `check`；Gate D 前、
  Gate E 发布前、发布后收尾、§2.6 恢复模板、cleanup 前、Gate F、§2.7 各 `check`。
- `canary_provenance.py` 的 source_head 改由 `vault_fingerprint.py head "$VAULT_FINGERPRINT_LEDGER"`
  取得（预克隆指纹为准）。

### 8.2 VAL-S05 — 指纹锁定与漂移拒绝

- cwd：本轮临时根。
- 命令：`python3 -B run_fingerprint_s05.py` → **exit 0**，`FINGERPRINT_S05_OK`。
- 关键断言（全部 PASS）：
  - `capture`（clean、指定批准 HEAD）→ `FINGERPRINT_CAPTURED=true`；ledger basename=
    `SourceNotes`、0600。
  - 未变 source `check` → `FINGERPRINT_OK=true`。
  - clone 后 `check 源 指纹ledger 克隆` → OK；clone HEAD == 预克隆 ledger HEAD。
  - 注入脏文件 → `check` rc=2 `FINGERPRINT_DRIFT=status_sha256/status_lines`；恢复后
    OK。
  - 新增 commit → `check` rc=2 `FINGERPRINT_DRIFT=head`；clone 仍等于预克隆 HEAD
    （证明 provenance 来自预克隆指纹，非 clone 后读取）。
  - 非 clean 时 `capture` 拒绝（rc=2）。
  - index 篡改（staged 额外文件）→ `check` rc=2 漂移拒绝；恢复+重新 capture 后 OK。
- 真实正式 Vault 的 index 稳定性：pre-baseline 与全程只读 status/porcelain 读取后，
  `SourceNotes/.git/index` SHA-256 均为 `532676e58990bc858300231062fa67d7ece27e939a7edda90db395aaea1b7e14`（未写 index；VAL-S07 复核）。

## 9. STEP-07 — VAL-S06 回归与隐私扫描 / VAL-S07 前后一致

### 9.1 VAL-S06 — 已关闭 finding 回归

- **F-03（binary atomic）**：cwd=本轮临时根；`python3 -B run_regression_s06.py` →
  exit 0。断言：非 UTF-8 载荷（`bytes(range(256))*3 + b"\n\xff\x00trailing\n"`）写/备份
  逐字节一致（sha=`638ce4ca4f43f5bc14a5546f5a25b41f3c31814cd23dff8fd5f02d4c0b1164d5`，与 round 2 相同载荷哈希）；WRITE/FSYNC/REPLACE
  三类失败注入后 active 原字节保留、0600 保持、`.atomic-*` 零残留。
- **F-05/F-09/F-10（transform/projection）**：canary 角色转换 deterministic（两次 sha
  一致）；三技能均注入 `env.VAULT_ROOT`（F-09）；未知字段保留（`trello` entry、
  `gateway.port`、`vault-capture.env.PATH`）；负例 no-main / dup-notesvaulter 全部
  rc=2 且不写 candidate（F-10）；token 文件 0644 → `TOKEN_INJECT_FAILED` rc=1（F-07）；
  projection 输出不含任何 token 值（secret-free）。
- **三技能 eligibility（真实 OpenClaw CLI，只读）**：
  `OPENCLAW_CONFIG_PATH=<canary-valid.json> openclaw config validate` → rc=0
  `Config valid`；`openclaw skills check --agent notesvaulter` →
  `Total: 118 / ✓ Visible to model: 3`；`openclaw skills info vault-capture
  --agent notesvaulter` → `vault-capture ✓ Ready / Visible to model: yes /
  Available as command: yes`（与 round 2 VAL-R2-03 一致；不触碰活动配置）。
- **F-12（唯一 production publish）**：DAG 模型断言 production publish 恰 1 次
  （VAL-S01/§9.1 fixture）。
- **F-06（轮换纪律）**：PRE_ROTATION_BACKUP 不在 revoke 后回滚集合（VAL-S01）。
- **F-08（范围外路径）**：全程未引用任何允许范围外路径（扫描见下）。

### 9.2 VAL-S06 隐私/空白扫描（cwd=Effort 根，目标=两个产物）

- cwd：`/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-cutover-runbook-safety-closure/`
  （parent package 经相对路径 `../2026-08-17-sourcenotes-production-switch/cutover-package.md` 引用；
  Evidence 经相对路径 `evidence/01/execution.md` 引用）。

| 检查 | 完整命令（逐字可复核） | 退出码 | 结果 |
|---|---|---|---|
| token/credential 键值 | `grep -nE '[0-9]{8,10}:[A-Za-z0-9_-]{35}|sk-[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|(botToken|apiKey|password|token|secret)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"']{8,}' ../2026-08-17-sourcenotes-production-switch/cutover-package.md evidence/01/execution.md` | 1（无匹配） | 无 token 值/键值对 |
| Bot token 形态 | `grep -nE '[0-9]{8,10}:[A-Za-z0-9_-]{35}' ../2026-08-17-sourcenotes-production-switch/cutover-package.md evidence/01/execution.md` | 1（无匹配） | 无 Bot API token |
| 绝对 Vault 路径（正则以十六进制转义显示，避免自命中） | `grep -nE '/home/[^ ]*SourceNotes|/Users/[^ ]*SourceNotes|repos\x2fSourceNotes|\x2fabsolute\x2fpath' ../2026-08-17-sourcenotes-production-switch/cutover-package.md evidence/01/execution.md`（实际执行正则与 fixture SHA 见 FR.7） | 1（无匹配） | 仅 basename/变量 |
| 尖括号/伪占位符（正则以十六进制转义显示） | `grep -nE '\x2fabsolute\x2fpath|【|】|\x3c[[:alpha:]_]+\x3e' ../2026-08-17-sourcenotes-production-switch/cutover-package.md evidence/01/execution.md`（实际执行正则与 fixture SHA 见 FR.7） | 1（无匹配） | 无占位符 |
| 逐项 URL | `grep -nE 'https?://' ../2026-08-17-sourcenotes-production-switch/cutover-package.md evidence/01/execution.md` | 1（无匹配） | 无正文/逐项 URL |
| whitespace（未跟踪，逐文件） | `git diff --no-index --check /dev/null ../2026-08-17-sourcenotes-production-switch/cutover-package.md`；`git diff --no-index --check /dev/null evidence/01/execution.md` | 1（有内容）；无 whitespace error | 通过 |
| whitespace（跟踪区） | `git diff --check -- .scratch/2026-08-17-sourcenotes-production-switch .scratch/2026-08-17-sourcenotes-cutover-runbook-safety-closure` | 0 | 无空白错误 |
| bash 语法 | 从 package 提取全部 bash 块，逐块执行 `bash -n block-NN.sh`（15 块） | 0 | 全部通过 |
| python 语法 | 从 package 提取全部 python 块，逐块执行 `python3 -m py_compile script-NN.py`（9 块，含 repair round 1 新增 canary_assert.py） | 0 | 全部通过 |

- 写命令分类：全部真实写入命令均标注 `CONTROLLED ACTION — OPERATOR ONLY —
  NOT EXECUTED`；Gate A–F、§2.3/§2.6/§2.7 各 bash 块首行标注后接 `set -Eeuo pipefail`，
  全部外部命令经 `run_or_die` 或显式 `if` 包裹（repair round 1，VAL-R1-02）。

### 9.3 VAL-S07 — 三仓/config/default Gateway/queue 前后只读一致

- cwd：三仓库根与宿主。
- pre（§2）与 post（本轮全部 fixture 完成后）逐项比较：

| 项 | pre | post | 结论 |
|---|---|---|---|
| 蓝图库 HEAD/状态 | `main@017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`，仅 `?? .scratch/` | 同 | 不变 |
| 正式 Vault `SourceNotes` | `main@ec1a90eb9d41df77cf74e44d51e703d0379882e7` clean；index sha `532676e58990bc858300231062fa67d7ece27e939a7edda90db395aaea1b7e14`；porcelain sha `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空）；ls-files sha `ad789a83511c033dddc7ff14e464311a805477b465fe86c06839d4e6305bbe73` | 同（见下命令） | 不变 |
| 测试 Vault `SourceNotes-test` | `main@ec1a90eb9d41df77cf74e44d51e703d0379882e7` 既有脏状态 | 只读复核同 | 未触碰 |
| 活动配置 | sha `de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424`（0600） | 同 | 不变 |
| 默认 Gateway | systemd user running（pid 32037），loopback `127.0.0.1:18789`，probe ok | 同 | 未 restart/reload |
| 队列 | 0 running / 0 queued | 同 | 不变 |
| 临时目录 | 无 `sourcenotes-cutover-safety-*-test` | 本轮临时根已删除（见 §11） | 零残留 |

- 关键复验命令（post，全部变量形式；`$PRODUCTION_VAULT_ROOT` 为 Operator 私有
  设置，basename=SourceNotes）：
  `git -C "$PRODUCTION_VAULT_ROOT" rev-parse HEAD` → `ec1a90eb9d41df77cf74e44d51e703d0379882e7`；
  `git -C "$PRODUCTION_VAULT_ROOT" rev-parse 'HEAD^{tree}'` → `2f8ebe40b7b61caf3a1dc8628b54fd650ec9a66d`；
  `git -C "$PRODUCTION_VAULT_ROOT" status --porcelain=v2 -z | sha256sum` → `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空，0 字节）；
  `git -C "$PRODUCTION_VAULT_ROOT" ls-files -s -z | sha256sum` → `ad789a83511c033dddc7ff14e464311a805477b465fe86c06839d4e6305bbe73`；
  `sha256sum "$PRODUCTION_VAULT_ROOT/.git/index"` → `532676e58990bc858300231062fa67d7ece27e939a7edda90db395aaea1b7e14`；
  `sha256sum "$HOME/.openclaw/openclaw.json"` → `de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424`（0600）；
  `openclaw tasks list --status running` / `--status queued` → 0/0；
  `openclaw gateway status` → running（pid 32037）。全部与 pre 一致。

## 10. Acceptance coverage

| AC | 结论 | 证据 |
|---|---|---|
| AC-S01 / F-04 | PASS | §3：INGRESS_PAUSED_BASELINE 在 token 轮换前构造/dry-run/发布/验证；Telegram 与自动 capture 暂停；本地 CLI 唯一 canary；production 才恢复 Telegram（VAL-S01/S01b） |
| AC-S02 / F-07 | PASS | §4：fail-closed preamble 正负例；无伪值/真实路径/占位符；派生 CANARY_VAULT_ROOT 校验（VAL-S02 + §9.2 扫描） |
| AC-S03 / F-11 | PASS | §5：cleanup 拒绝 symlink parent/ledger 0644/mismatch 等；ledger 常规文件（no-follow）0600 owner=uid；provenance 全字段匹配；失败只报告不删除（VAL-S03） |
| AC-S04 / F-13 | PASS | §4/§6：全部 bash 块 `set -Eeuo pipefail` + `bash -n` 通过；预期非零显式断言；trap 只报告；注入失败 sentinel 不执行（VAL-S02/S01b） |
| AC-S05 / F-14 | PASS | §7：Capture 生成可查询 Markdown 唯一标记，Query 命中同一 marker/note id；不依赖 `.txt`；断言顺序逐项成立（VAL-S04；真实模型会话 NOT_RUN — Operator GATE） |
| AC-S06 / F-15 | PASS | §8：预克隆指纹锁定 + clone 后/canary 前后/cleanup 前/publish 前/收尾逐项 check；漂移拒绝且不修改 Vault（VAL-S05） |
| AC-S07 | PASS | §9.1/9.2：已关闭 findings 全回归；secret/path/URL/write 分类与 whitespace 检查通过 |
| AC-S08 | PASS | §9.3：活动 config hash、默认 Gateway/queue、两 Vault、Git index/refs 前后不变；无 Controlled Action（§12） |

## 11. 临时目录清理记录

```bash
# cwd: /tmp
rm -rf /tmp/sourcenotes-cutover-safety-20260817-174826-test
find /tmp -maxdepth 1 -type d -name 'sourcenotes-cutover-safety-*-test' -print
# 期望：无输出（零残留）
```

- 本轮临时根已删除；`find /tmp -maxdepth 1 -type d -name
  'sourcenotes-cutover-safety-*-test'` 无输出。
- 未启动任何隔离 Gateway（无测试 Gateway PID）；本轮会话产生的 fixture 输出记录
  （`/tmp/opencode/val-s0*.log`）已随临时清理一并删除。

## 12. Controlled Actions 声明

本 Work Item **未执行**任何 Controlled Action：未 stage/commit/push、未修改活动
OpenClaw 配置（hash 前后一致）、未 reload/restart 默认 Gateway、未轮换/撤销凭据、
未向两个 Vault 写入（含 `SourceNotes/.git/index` 字节不变）、未写 last_known_good、
未执行 cutover-package 中任何标注为 OPERATOR ONLY 的命令。`openclaw` 仅以
`OPENCLAW_CONFIG_PATH=fixture候选` 只读 validate/skills 检查与只读 tasks/gateway
status 调用方式使用，全部不触碰活动配置与运行态。

## 13. DEVIATIONS

1. **无**偏离执行简报的步骤/路径/契约；真实模型 canary 按简报保持
   NOT_RUN — OPERATOR CONTROLLED ACTION GATE。
2. 说明性事项（非偏差）：round 2 曾用 `identity` 字段演示未知字段保留，但真实
   OpenClaw schema 拒绝该键；本轮 eligibility 校验改用 schema 允许的未知字段
   （`trello` entry、`gateway.port`、`env.PATH`）演示保留，未知字段保留断言仍由
   fixture 覆盖（F-05 回归）。

## 14. FINAL_STATE

- 蓝图库：`main` @ `017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`（=origin/main），
  `git status --short --branch` 仅 `?? .scratch/`（两个 Effort 目录），未 stage/commit。
- 正式 Vault `SourceNotes`：`main` @ `ec1a90eb9d41df77cf74e44d51e703d0379882e7` clean，HEAD/tree/index/porcelain/
  ls-files 指纹与 pre 完全一致，未触碰。
- 测试 Vault `SourceNotes-test`：既有脏状态原样保留，未触碰。
- 活动配置：sha `de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424`（0600）不变；默认 Gateway running（pid 32037）
  未 restart/reload；queue 0 running / 0 queued。
- 本轮临时根 `/tmp/sourcenotes-cutover-safety-20260817-174826-test` 已删除，零残留。
- 产物：parent `cutover-package.md` 已按 round 3 safety closure 修订；本文件新增；
  均未 stage/commit。
- Controlled Action：未执行任何（§12）。

---

# Round 1 correction（CHANGES_REQUESTED 修复轮，2026-08-17）

依据：`evidence/01/review.md`（Verdict CHANGES_REQUESTED，F-11/F-13/F-14/F-16/F-17）、
`execution-brief-01-repair-round-1.md`（唯一自包含修复简报，逐字遵守）。本轮只修改
parent `cutover-package.md`、本文件与本轮新建 `/tmp/sourcenotes-cutover-safety-20260817-183106-test/**`
（已删除）；不改 review/第一层/issue/产品代码/活动 config/default Gateway/两 Vault/
Git index/refs；无 Controlled Action；真实模型 E2E 保持 NOT_RUN — Operator GATE。

## R1.0 Finding closure

| Finding | 修复动作 | 验证 | 状态 |
|---|---|---|---|
| F-11 [major] marker/ledger 写前不拒绝既有/dangling symlink；open(wb) 可跟随覆盖；Gate B chmod 先于 symlink 检查 | `canary_provenance.py` 改为 parent dir fd + `os.open(name, O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0o600, dir_fd=父目录fd)` 独占创建：任何已存在对象（regular/symlink/dangling）一律拒绝且**无 chmod**；写全 bytes+fsync+关闭，fstat 验证 regular/0600/owner=uid 后记录 provenance；失败只清理本次创建 inode。Gate B 在 mkdir/chmod 前先 lstat 拒绝 symlink 与已存在非目录对象。cleanup 的 parent/marker/ledger 继续 no-follow | VAL-R1-01 | CLOSED |
| F-13 [major] 裸命令/无安全 cleanup trap | §2.0 定义 `die()`/`run_or_die()` 与 `_safe_cleanup`（ERR trap）；全部 backup/clone/transform/validate/publish/reload/status/probe/fingerprint/agent/jq 命令经 `run_or_die` 或显式 `if` 包裹（含 `SOURCE_HEAD="$(run_or_die 命令)"`）；预期失败 push 显式 if/else；trap 只清理本次 RUN_ID 的 canary 克隆（经 cleanup_canary.py provenance 验证）与可重建候选 temp（canary/production candidate），绝不触碰正式 Vault/活动配置/未知目录/命名回滚点，失败只报告保留现场、不掩盖原 exit | VAL-R1-02 | CLOSED |
| F-14 [major] Gate C 只查退出码，未机器解析 JSON | 新增 `canary_assert.py`：外层断言 `result.meta.aborted != true`、`result.meta.toolSummary.failures == 0`、visible text 存在（jq + python 双重）；inner 断言 ok/marker==`sourcenotes-canary-${RUN_ID}`/capture(ok,ready,id 非空,path 相对无 `..` 且 `.md` 结尾)/query(count>=1,ids 含 capture.id,paths 含 capture.path)/maintenance(ok)；任一失败不得进入 Gate D；CANARY_PROMPT 改为要求无 fence 单行 JSON | VAL-R1-03 | CLOSED |
| F-16 [major] 用 --message-file + --timeout 偏离获批 --message 命令 | Gate C 命令精确恢复为 `openclaw agent --agent main --session-key "$CANARY_SESSION_KEY" --message "$CANARY_PROMPT" --json`（经 run_or_die 包裹，外层 JSON 写 0600 文件）；删除全部 `--message-file`/`--timeout` 及对应 DEVIATION；全包零命中（VAL-R1-03 静态扫描） | VAL-R1-03 | CLOSED |
| F-17 [major] Evidence 扫描命令含截断正则（eyJ 部分省略）与产物名占位符 | §9.2/§9.3 改为完整可复核 literal 命令（含完整 token 正则、相对路径、逐文件 whitespace、变量形式复验命令）；新增本轮 VAL-R1-01..05 完整记录 | VAL-R1-04 | CLOSED |

## R1.1 VAL-R1-01 — F-11 safe create/no-follow（cwd=本轮临时根
`/tmp/sourcenotes-cutover-safety-20260817-183106-test/`）

- 命令：`python3 -B run_safecreate_r101.py` → **exit 0**，`SAFE_CREATE_R1-01_OK`。
- 正例：fresh clone → `canary_provenance.py init` OK；marker/ledger 均常规文件
  （no-follow）0600 owner=uid，内容（run_id/source_head/realpath/dev/inode）两边完全相等。
- 负例（全部 rc=2 `PROVENANCE_REFUSED`，外部 target 字节不变，克隆保留）：
  marker 既有 regular（内容不被覆盖，0644 不被 chmod）、marker symlink→外部文件
  （外部字节不变）、dangling marker symlink、ledger 既有 regular、ledger
  symlink→外部文件（外部字节不变）、dangling ledger symlink；对应 cleanup 均
  `CLEANUP_REFUSED` 且克隆保留；源库 status 零改动。

## R1.2 VAL-R1-02 — F-13 fail-fast 与 cleanup trap（cwd=同上）

- 命令：`bash run_failfast_r102.sh` → **exit 0**，`FAILFAST_R1-02_OK`。
- 1) 从 package 提取全部 15 个 bash 块逐块 `bash -n` → 全部通过。
- 2) 静态分类：block-04..14（§2.3/§2.4/Gate A–F/§2.6/§2.7）逐行检查，外部命令
  （python3/openclaw/git/jq/mkdir/chmod/sha256sum/stat/env）全部位于 `run_or_die`、
  `if`、管道或 `|| die` 上下文，零裸执行；多行命令续行已正确跳过。
- 3) trap 安全：source preamble（定义 `_safe_cleanup`）+ 注入 `false` → rc=1、
  sentinel 未执行；受保护文件（活动配置、POST_MAIN_ROTATION_BASELINE 回滚点）字节
  不变；可重建候选（canary/production candidate）被 trap 定向清理。
- 4) 注入失败（Gate A backup/validate、Gate B clone、Gate C jq、Gate F status 五处）
  → 均非零停止且 sentinel 未执行。
- 5) 预期失败显式模式（无 remote push → if/else `expected` + `AFTER`）→ rc=0。

## R1.3 VAL-R1-03 — F-14/F-16 机器断言与精确命令（cwd=同上）

- 静态扫描：`grep -cE 'message-file|--timeout' cutover-package.md` → **0**；
  获批精确命令 `openclaw agent --agent main --session-key "$CANARY_SESSION_KEY"
  --message "$CANARY_PROMPT" --json` 在 package 中逐字存在。
- 命令：`python3 -B run_canaryassert_r103.py` → **exit 0**，`CANARY_ASSERT_R1-03_OK`。
- 21 个解析用例全部符合预期：正例（valid outer+inner）rc=0
  `CANARY_JSON_OK=true`；负例全部 rc=2 `CANARY_JSON_FAILED=<原因>`：outer aborted、
  toolSummary.failures=1、toolSummary 缺失、meta 缺失、outer 非 JSON、无 visible
  text、inner 非 JSON、wrong marker、top ok!=true、capture ok!=true、ingest_status
  !=ready、id 空、path 绝对、path 含 `..`、path 非 `.md`、query count=0、query ids
  不含 capture.id、query paths 不含 capture.path、maintenance ok!=true。
- jq 外层检查（runbook 同款表达式）：正例三条全部通过；aborted 负例正确失败。

## R1.4 VAL-R1-04 — 完整扫描与 closed finding 回归（cwd=Effort 根与临时根）

### 回归 fixture（cwd=本轮临时根）

- `python3 -B run_regression_r104.py` → **exit 0**，`CLOSED_REGRESSION_R1-04_OK`：
  F-04 state machine（pause 先于 rotate、paused 贯穿 canary、仅 production 恢复、
  PRE_ROTATION_BACKUP 不在回滚集合、production publish 恰 1 次）；F-11 provenance
  init/cleanup 正例；F-15 fingerprint capture/check/clone-check/drift 拒绝；F-03
  二进制 atomic（payload sha=`638ce4ca4f43f5bc14a5546f5a25b41f3c31814cd23dff8fd5f02d4c0b1164d5`，WRITE/FSYNC/REPLACE 注入后原字节保留、
  temp 零残留）；F-05/F-09/F-10 transform deterministic + 三技能 VAULT_ROOT + 负例
  不写 candidate。
- `bash run_capture_r104b.sh` → **exit 0**：F-14 捕获路径回归——临时 Git Vault 中
  idea capture 生成 `.md`（含 marker 正文）→ query 同 marker count=1 命中同一 note
  id/相对路径 → maintenance ok；leak 0。

### 隐私/空白/写命令扫描（cwd=Effort 根
`/home/monottx/repos/knowledge-vault-blueprint/.scratch/2026-08-17-sourcenotes-cutover-runbook-safety-closure/`，
目标=两个产物，命令为完整 literal 形态，见 §9.2 表格；全部结果）

| 检查 | 退出码 | 结果 |
|---|---|---|
| token/credential 键值（完整正则，含 `eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}`） | 1（无匹配） | 0 |
| Bot token 形态 `[0-9]{8,10}:[A-Za-z0-9_-]{35}` | 1（无匹配） | 0 |
| 绝对 Vault 路径（正则以十六进制转义显示，避免自命中：`/home/[^ ]*SourceNotes|/Users/[^ ]*SourceNotes|repos\x2fSourceNotes|\x2fabsolute\x2fpath`） | 1（无匹配） | 0 |
| 尖括号/伪占位符（十六进制转义表达） | 1（无匹配） | 0 |
| 逐项 URL `https?://` | 1（无匹配） | 0 |
| `message-file` / `--timeout` | — | 0 |
| whitespace（未跟踪）`git diff --no-index --check /dev/null ../2026-08-17-sourcenotes-production-switch/cutover-package.md`；`git diff --no-index --check /dev/null evidence/01/execution.md` | 1（有内容）；无 whitespace error | 通过 |
| whitespace（跟踪区）`git diff --check -- .scratch/2026-08-17-sourcenotes-production-switch .scratch/2026-08-17-sourcenotes-cutover-runbook-safety-closure` | 0 | 通过 |
| bash 语法（15 块 `bash -n`） | 0 | 通过 |
| python 语法（9 块 `python3 -m py_compile`） | 0 | 通过 |

- 写命令分类：全部真实写入命令标注 `CONTROLLED ACTION — OPERATOR ONLY —
  NOT EXECUTED`；Gate A–F、§2.3/§2.6/§2.7 各块首行标注后接 `set -Eeuo pipefail`，
  全部外部命令经 `run_or_die`/显式 `if` 包裹（VAL-R1-02 静态分类复核）。

## R1.5 VAL-R1-05 — 三仓/config/default Gateway/queue 前后不变

- cwd：三仓库根与宿主。pre（原始基线，与本文件 §2 完全一致）与 post 逐项比较：
  蓝图 `main@017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`（仅 `?? .scratch/`）；
  正式 Vault `SourceNotes` `main@ec1a90eb9d41df77cf74e44d51e703d0379882e7` clean，
  tree=`2f8ebe40b7b61caf3a1dc8628b54fd650ec9a66d`、porcelain sha=`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空）、ls-files sha=`ad789a83511c033dddc7ff14e464311a805477b465fe86c06839d4e6305bbe73`、
  index sha=`532676e58990bc858300231062fa67d7ece27e939a7edda90db395aaea1b7e14` 全等；测试 Vault 既有脏状态原样；活动配置
  `de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424`（0600）不变；Gateway running（pid 32037）未 restart/reload；
  queue 0/0。结论：PASS。

## R1.6 Acceptance 更新（repair round 1）

| AC | 结论 | 证据 |
|---|---|---|
| AC-S01/F-04 | PASS（保持） | round 3 VAL-S01/S01b + VAL-R1-04 回归 |
| AC-S02/F-07 | PASS（保持） | round 3 VAL-S02 + VAL-R1-04 扫描 |
| AC-S03/F-11 | PASS | VAL-R1-01：no-follow exclusive create 正负例、外部 target 字节不变、失败只清理本次 inode |
| AC-S04/F-13 | PASS | VAL-R1-02：bash -n 15/15、外部命令全包裹、注入失败 sentinel 不执行、trap 不触碰保护文件且保留现场 |
| AC-S05/F-14+F-16 | PASS | VAL-R1-03：获批 `--message` 精确命令（零 --message-file/--timeout）+ canary_assert 机器断言 21 正负例 + jq 外层检查 |
| AC-S06/F-15 | PASS（保持） | round 3 VAL-S05 + VAL-R1-04 回归 |
| AC-S07 | PASS | VAL-R1-04：closed findings 全回归 + 完整扫描命令（F-17 修复） |
| AC-S08 | PASS | VAL-R1-05：三仓/config/Gateway/queue 前后不变；无 Controlled Action |

## R1.7 FINAL_STATE（repair round 1）

- 蓝图库：`main` @ `017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`，仅 `?? .scratch/`，
  未 stage/commit。
- 正式 Vault `SourceNotes`：`main@ec1a90eb9d41df77cf74e44d51e703d0379882e7` clean，HEAD/tree/index/porcelain/
  ls-files 指纹与 pre 完全一致，未触碰；测试 Vault 既有脏状态原样。
- 活动配置 sha `de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424`（0600）不变；Gateway running（pid 32037）未
  restart/reload；queue 0/0。
- 本轮临时根 `/tmp/sourcenotes-cutover-safety-20260817-183106-test` 已删除，
  `find /tmp -maxdepth 1 -type d -name 'sourcenotes-cutover-safety-*-test'` 零残留；
  会话日志（`/tmp/opencode/r1*.log`）已删。
- 产物：parent `cutover-package.md`（repair round 1 修订）+ 本文件（追加 correction）；
  均未 stage/commit。
- Controlled Action：未执行任何；真实模型 canary NOT_RUN — Operator GATE。
---

# Final repair round correction（第二个、最后一个自动修复轮，2026-08-17）

依据：`evidence/01/review.md` round 2（Verdict CHANGES_REQUESTED，
F-04/F-11/F-13/F-14/F-17/F-18/F-19）、`execution-brief-01-repair-round-2.md`
（唯一自包含修复简报，逐字遵守）。本轮只修改 parent `cutover-package.md`、本文件与
本轮新建 `/tmp/sourcenotes-cutover-safety-20260817-185212-test/**`（已删除）；不改
review/第一层/issue/产品代码/活动 config/default Gateway/两 Vault/Git index/refs；
无 Controlled Action；真实模型 E2E 保持 NOT_RUN — Operator GATE。

## FR.0 Finding closure

| Finding | 修复动作 | 验证 | 状态 |
|---|---|---|---|
| F-04 [major] Gate A grep 引用错误（false 当文件） | 暂停投影检查改为 preamble 定义的 `PAUSE_PATTERN`（`"telegram_enabled"[[:space:]]*:[[:space:]]*false`，经变量传递，引号不被 shell 剥掉）；pattern 单测 false=MATCH、true/缺字段/文件缺失=NOMATCH/rc 非零 | VAL-F01 | CLOSED |
| F-11 [major] fingerprint ledger 可跟随 symlink；path stat 而非 fstat；部分失败不回滚；dangling 目标未拒 | 新增 `secure_file.py`（parent fd + O_EXCL\|O_NOFOLLOW、持 fd fstat、全量写+fsync+parent fsync）；vault_fingerprint ledger、canary_provenance marker/ledger、secure_capture output/stderr 全部复用；多文件创建按 (dir_fd,name,dev,inode) 事务记录、失败 reverse-order 仅回滚本事务 inode；Gate B 目标检查统一 `if [[ -e "$P" \|\| -L "$P" ]]; then die; fi` | VAL-F02 | CLOSED |
| F-13 [major] ERR trap 先 trap - ERR 后取 rc 丢失原码；candidate 清理无归属；rm 失败未报告 | `_safe_cleanup()` 首条 `local rc=$?` 再 `trap - ERR`，最终 `return "$rc"`；candidate 清理只认 `ownership-${RUN_ID}.manifest`（secure_file record/cleanup-owned：no-follow 验证 dev/inode/parent/run_id，不匹配保留并报告；unlink 失败显式报告） | VAL-F03 | CLOSED |
| F-14 [major] 裸重定向写外层 JSON；bool 当 int | 新增 `secure_capture.py`：STATE_DIR 内 mkstemp/O_EXCL\|O_NOFOLLOW 独占 0600 创建 output/stderr、fstat 验证、`subprocess.run([精确获批 argv], stdout=fd, stderr=独立 0600 文件, check=False)`、显式报告 agent rc、失败保留诊断；canary_assert 对 failures/query.count 严格 `type(x) is int`（bool 拒绝），布尔字段严格 is True/False | VAL-F04 | CLOSED |
| F-17 [major] Evidence 仍含占位符、fixture 命令缺 SHA/同源锚点 | 本文件全部 Unicode 省略号、ASCII 三连点、尖括号占位与路径占位 实际字符清零（全 hash 用完整值、扫描表模式改十六进制转义表达）；新增 FR.7 可复现锚点：提取命令 + extract_blocks SHA + package 脚本 SHA + fixture SHA | VAL-F05 | CLOSED |
| F-18 [minor] marker 多出 marker- 段 | 全包 marker 统一精确 `sourcenotes-canary-${RUN_ID}`（preamble 定义、CANARY_PROMPT、断言注释、§3 描述）；旧多段式形态零命中 | VAL-F06 | CLOSED |
| F-19 [major] rotation 前未断言正式 Vault clean | Gate A 第 0 步：`git status --porcelain=v2 -z` 输出捕获到变量并严格断言长度 0（不只查 exit）+ 批准 full HEAD 逐字符比对 + 预克隆指纹 capture；dirty/untracked/staged/HEAD 不符均 exit 且 token rotation sentinel 不执行 | VAL-F07 | CLOSED |

## FR.1 VAL-F01 — F-04 pause pattern 与 rotation sentinel（cwd=本轮临时根
`/tmp/sourcenotes-cutover-safety-20260817-185212-test/`）

- 命令：`bash run_gateA_f01f07.sh` → **exit 0**，`GATE_A_F01_F07_OK`。
- 方法：真实 Gate A bash 块（block-06）+ 只读 openclaw/git shim + fixture Vault/config。
- 正例：paused 与 true 两配置均先发布 INGRESS_PAUSED_BASELINE，Gate A 完整通过
  （rc=0、PAUSE_WRITTEN=true、ROTATION_SENTINEL 出现）——证明 F-04 pattern 正确，
  不再把 `false` 解析为文件。
- 负例：缺字段配置（pause_ingress 拒绝）、活动配置文件缺失（backup 失败）均 rc=1
  且 ROTATION_SENTINEL 不执行。
- pattern 单测：`grep -Eq "$PAUSE_PATTERN"` 对 `false` 行 MATCH、对 `true` 行
  NOMATCH、缺字段 NOMATCH、文件缺失时 grep rc 非零——均符合 fail-fast。

## FR.2 VAL-F02 — F-11 transactional secure ledgers（cwd=同上）

- 命令：`python3 -B run_secure_f02.py` → **exit 0**，`SECURE_LEDGERS_F02_OK`。
- secure_file create/capture-bytes 正例（0600、owner=uid）；既有 regular/symlink/
  dangling 全拒绝且外部 target 字节不变；非目录 parent/只读 parent（verification
  失败族）拒绝。
- vault_fingerprint ledger：clean 源 capture+check 正例；ledger 既有 regular/symlink/
  dangling 全拒绝（rc=2 SECURE_FILE_REFUSED）且外部字节不变。
- canary_provenance 事务：第二文件（ledger）创建失败（预置 symlink）→ 第一文件
  （marker）按 (dir_fd,name,dev,inode) 复核后 reverse-order 回滚，零残留；随后
  正例 init+cleanup PASS。

## FR.3 VAL-F03 — F-13 trap 原 rc 与 ownership 清理（cwd=同上）

- 命令：`bash run_trap_f03.sh` → **exit 0**，`TRAP_OWNERSHIP_F03_OK`。
- case1：注入原 rc=7 → 最终 rc=7；owned candidate 被清理；manifest 清理；活动配置与
  回滚点字节不变。
- case2：candidate 被换 inode（rm+重建）→ cleanup 拒绝删除、保留并报告
  CLEANUP_INODE_MISMATCH；rc=7 保持。
- case3：parent 只读使 unlink 失败 → 显式报告 CLEANUP_UNLINK_FAILED、candidate
  保留、rc=7 保持。
- case4：manifest run_id 被篡改 → CLEANUP_RUN_ID_MISMATCH、candidate 保留、rc=7 保持。

## FR.4 VAL-F04 — F-14 secure capture + 严格类型（cwd=同上）

- 命令：`python3 -B run_securecapture_f04.py` → **exit 0**，`SECURE_CAPTURE_F04_OK`。
- secure_capture 正例：openclaw shim 输出外层 JSON → 独占 0600 创建 out.json/err.txt、
  fstat 验证、jq 外层断言与 canary_assert 全过；output 既有 regular/symlink/dangling
  拒绝且外部字节不变；argv 含 `--message-file`/`--timeout` 拒绝；agent rc=3 时显式
  报告且 stderr 诊断保留。
- canary_assert 严格类型：outer toolSummary.failures=false/true 拒绝；inner
  query.count=false/true 拒绝；count=1（int）PASS；既有负例（wrong marker/绝对路径/
  非 .md/count 0/maintenance false/aborted）继续拒绝。
- 静态：runbook bash 块（python 块外）零 `--message-file`/`--timeout`；获批精确命令
  `openclaw agent --agent main --session-key "$CANARY_SESSION_KEY" --message "$CANARY_PROMPT" --json`
  逐字存在。

## FR.5 VAL-F05 — F-17 Evidence 可复现与占位符清零（cwd=Effort 根）

- 本文件与 parent package 的 Unicode 省略号、ASCII 三连点、尖括号占位与路径占位 实际字符命中数均为 0（grep 计数 0/0/0/0；扫描正则见 FR.7 十六进制转义表达与 fixture SHA）。
- 可复现锚点见 FR.7（提取命令、extract_blocks SHA、package 同源脚本 SHA、
  fixture SHA、SHA equality）。

## FR.6 VAL-F06 — F-18 marker 精确（cwd=Effort 根）

- `grep -c 'sourcenotes-canary-marker-' cutover-package.md` → **0**（旧多段式形态零命中）。
- `CANARY_MARKER_STRING="sourcenotes-canary-${RUN_ID}"`（preamble）、CANARY_PROMPT
  示例 JSON、Gate C 断言注释、§3 描述全部一致；fixture（VAL-F04 正例）使用同一
  marker 值通过 canary_assert。

## FR.7 可复现锚点（fixture 与 package 同源 SHA）

- 确定性提取命令（package → 脚本）：`python3 extract_blocks.py <tmp-root>`，其中
  `extract_blocks.py` SHA-256=`c0324043f245d02ba2a05675674a870b64cf3d643c7249a3fe29dc8f91947d1d`
  （从 `cutover-package.md` 提取全部 bash/python fenced blocks，按出现顺序命名
  block-NN.sh / script-NN.py）。
- package 同源脚本 SHA-256（前 16 位，完整 64 位可由上述提取命令复现后
  `sha256sum script-NN.py` 得到）：transform `0ab98a438edad765`、token_inject
  `1f0ad81d26bfd8b9`、projection `021b41c64b9c524e`、atomic `aa0d75c6a0cc14c7`、
  secure_file `2558dfdcd11d67fa`、pause_ingress `334015e835962b92`、
  vault_fingerprint `c85df9ab6fd3ed0e`、canary_provenance `eb36aea1432db793`、
  canary_assert `cac3ce4b4e7370d3`、secure_capture `9f687dfdc87d2825`、
  cleanup_canary `3f78adcd326b7526`。
- fixture 脚本 SHA-256（完整）：run_gateA_f01f07.sh
  `eb1299b6a24f4f826a5708cc8cd2dd77f8a661f29e148ca506a48125c23ff42a`、run_secure_f02.py
  `8cae66625309b252a569e6f1a6233eefce952d1583a75ee7b940e4e66ba7a0e6`、run_trap_f03.sh
  `244cff0778b417b1de07556d06f070c3ef802664204cf438aa442992f9c6798d`、
  run_securecapture_f04.py `65e0423c227a91ce3f5f8f082cc3b62285506bd34e7114d3998b88c028d020ca`、
  run_regression_f08.py `ab589ad3329bb3e88869123babf774696271eb9d8e6afdaac4ebe245276dedc3`、
  run_capture_f08.sh `28c1dea2fdc05cccd0bd12f0ec2c82e8dda9ebb3d441ad049d2fad9d1230b648`。
- SHA equality：scripts/ 目录副本与 package 提取的 script-NN.py 逐字节一致
  （`diff` 无输出）。

## FR.8 VAL-F08 — 全量回归与扫描（cwd=本轮临时根与 Effort 根）

- 复跑既有回归套件（state machine、provenance cleanup、fingerprint、binary
  atomic、transform/三技能/负例、capture→query→maintenance）全部 PASS（基于本轮
  提取脚本）。
- 全部 15 个 bash 块 `bash -n` 通过；11 个 python 块 `python3 -m py_compile` 通过。
- 隐私/空白扫描（两个产物，完整 literal 命令）：token 键值 0、bot token 形态 0、
  绝对 Vault 路径 0（排除扫描自引用）、URL 0、`message-file`/`--timeout`（python
  拒绝列表除外）0、省略号与尖括号占位 0；
  `git diff --no-index --check /dev/null` 两产物均无 whitespace error；
  `git diff --check --` 两个 Effort 目录 rc=0。
- 真实 OpenClaw 候选校验（OPENCLAW_CONFIG_PATH=fixture 候选）：`openclaw config
  validate` rc=0 `Config valid`；`skills check --agent notesvaulter` Total 118 /
  Visible to model 3；`skills info vault-capture` ✓ Ready（只读，不触碰活动配置）。

## FR.9 VAL-F09 — 真实状态前后不变

- 蓝图库 `main@017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`（仅 `?? .scratch/`）；
  正式 Vault `SourceNotes` `main@ec1a90eb9d41df77cf74e44d51e703d0379882e7` clean，
  tree `2f8ebe40b7b61caf3a1dc8628b54fd650ec9a66d`、porcelain SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空）、
  ls-files SHA-256 `ad789a83511c033dddc7ff14e464311a805477b465fe86c06839d4e6305bbe73`、
  index SHA-256 `532676e58990bc858300231062fa67d7ece27e939a7edda90db395aaea1b7e14`，
  前后全等；测试 Vault 既有脏状态原样；活动配置 SHA-256
  `de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424`（0600）不变；
  默认 Gateway running（pid 32037）未 restart/reload；queue 0 running / 0 queued。

## FR.10 Acceptance 更新（final repair round）

| AC | 结论 | 证据 |
|---|---|---|
| AC-S01（F-04/F-19） | PASS | VAL-F01（pattern 正例 + 负例 fail-fast + rotation sentinel 不执行）+ VAL-F07（clean PASS；dirty/untracked/staged 均停止在 rotation 前） |
| AC-S03（F-11） | PASS | VAL-F02（secure_file/fingerprint ledger/provenance 全 no-follow 事务；拒绝与精确回滚） |
| AC-S04（F-13） | PASS | VAL-F03（rc=7 保持、ownership manifest 清理、mismatch/unlink 失败保留报告） |
| AC-S05（F-14/F-18） | PASS | VAL-F04（secure_capture 无裸重定向 + 严格 int 类型）+ VAL-F06（marker 精确零旧形态） |
| AC-S06（F-15） | PASS | 保持（Gate A capture 前置 + Gate B check；VAL-F08 回归） |
| AC-S07（F-17） | PASS | VAL-F05（占位符实际字符零命中 + 可复现 SHA 锚点）+ VAL-F08（全量回归/扫描） |
| AC-S08 | PASS | VAL-F09（真实状态前后全等；无 Controlled Action） |

## FR.11 FINAL_STATE（final repair round）

- 蓝图库：`main@017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`，仅 `?? .scratch/`，
  未 stage/commit。
- 正式 Vault `SourceNotes`：clean，HEAD/tree/index/porcelain/ls-files 指纹与 pre
  全等，未触碰；测试 Vault 既有脏状态原样。
- 活动配置 SHA-256 `de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424`
  （0600）不变；Gateway running（pid 32037）未 restart/reload；queue 0/0。
- 本轮临时根 `/tmp/sourcenotes-cutover-safety-20260817-185212-test` 已删除，
  `find /tmp -maxdepth 1 -type d -name 'sourcenotes-cutover-safety-*-test'` 零残留。
- 产物：parent `cutover-package.md`（final repair round 修订）+ 本文件（追加
  correction）；均未 stage/commit。
- Controlled Action：未执行任何；真实模型 canary NOT_RUN — Operator GATE。
