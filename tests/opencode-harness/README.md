# NotesVaulter 调试指南（给 opencode 用）

你在调试 vault-capture skill 时，可以通过本机 `openclaw` CLI 直接调用 NotesVaulter agent，拿到结构化 JSON 结果，自行判断是否符合预期，然后修改 skill 文件再测，直到跑通。**不需要用户中转**。

## 调用命令

```bash
openclaw agent --agent notesvaulter --message "<消息>" --json
```

- 必须加 `--json`，否则只返回纯文本，不利于自动断言
- 触发捕获的消息前缀：`收：<url>`、`转写：<文本>`、`想法：<文本>`
- 调试时建议加 `--session-key debug-<某固定值>`，保持单 session，方便追问状态；每次全新测试可换一个新 key

## 快速 harness

仓库里已放好脚本：`tests/opencode-harness/capture_debug.sh`

```bash
# 想法类（最快，无网络依赖）
./tests/opencode-harness/capture_debug.sh idea "想法：测试一条想法"

# 网页类（异步抓取，只验证 stage + 后台抓取，用 --wait 轮询终态）
./tests/opencode-harness/capture_debug.sh web "收：https://example.com/article" --wait 60 --assert

# 网页类（SSRF 判 non-public 时预期终态为 failed——不改 SSRF，只让 harness 接受该终态）
./tests/opencode-harness/capture_debug.sh web "收：https://example.com/article" --wait 60 --expect-status failed --assert

# 带断言（内置检查 Source ID / 状态 / git 暂存）
./tests/opencode-harness/capture_debug.sh idea "想法：..." --assert

# 测完自动清理本次生成的测试文件
./tests/opencode-harness/capture_debug.sh idea "想法：..." --assert --cleanup
```

脚本输出：原始 JSON 存到 `tests/opencode-harness/out/`，终端打印提取后的关键字段和断言结果（含 `ID来源`、`expect-status`、`终态`）。

## 严格测试库护栏（调用前拒绝）

在调用 `openclaw` **之前**，脚本会依次校验：

- 必要依赖存在：`jq`、`openclaw`、`python3`、`git`
- `VAULT_ROOT` 存在且为 Git 仓库
- `VAULT_ROOT` 的 basename **必须以 `-test` 结尾**

任一不满足立即退出（退出码非 0），**不会**发起任何 openclaw 调用。旧版本对非 `-test` 库只“醒目告警”，现已改为硬拒绝，避免误写正式库。

## 模式契约（`--assert`）

| 检查项 | idea | web | raw |
|---|---|---|---|
| `stopReason` | 必须 `stop` | `stop`(同步) 或 `end_turn`(异步) | `stop` 或 `end_turn` 均可 |
| `aborted != true` | ✔ | ✔ | ✔ |
| `toolSummary.failures` 字段存在且 `== 0` | ✔ | ✔ | ✔ |
| 回复非空 | ✔ | 同步要求 | ✔ |
| 拿到 Source ID | ✔ | ✔ | 不要求 |
| 回复包含落盘语义（已保存/ready/created/已落盘） | ✔ | – | – |
| 文件存在于 `notes/ideas/<id>*` | ✔ | – | – |
| 回复包含暂存/后台抓取语义（暂存/后台/抓取/staged/job） | – | 同步要求 | – |
| **本次产生了含 Source ID 的新增暂存** | ✔ | ✔ | – |
| `--wait` 时终态匹配 `--expect-status` | – | ✔ | – |

### web 两种 envelope

真实 NotesVaulter 网页捕获可能是同步回复，也可能是**真实异步 yield**（`end_turn` + `yielded: true` + 空回复/空 payload，后台子任务抓取）：

- **同步 envelope**：`stopReason == stop` + 非空回复 + 从回复文本取到 Source ID + 出现新增暂存。
- **异步 envelope**：`stopReason == end_turn` + `yielded == true` + 从**唯一新增暂存路径**恢复 Source ID；不要求回复文本语义（新增暂存本身就是证据）。

两者都要求 `aborted != true` 且 `toolSummary.failures` 字段存在并 `== 0`。普通 `end_turn`（`yielded` 缺失/`false`）、或新增暂存中**零/多个** Source ID 候选，均 FAIL。

### --expect-status（仅 web + --wait）

`--expect-status ready|failed|manual|terminal`，**默认 `ready`**。只允许在 `mode=web` 且 `--wait>0` 时使用，否则在调用 openclaw 前 `exit 2`。

- `ready`/`failed`/`manual`：终态须**精确匹配**。
- `terminal`：接受 `ready`/`failed`/`manual` 任一。
- 默认 `ready`，**绝不允许 failed 通过**。

> ⚠️ 当前环境（Clash Fake-IP 等）下，部分 RFC/私有 URL 会被 SSRF 判为 non-public，终态为 `failed`。**本 harness 不修改 SSRF**；需要验证这种终态时显式传 `--expect-status failed`，把“当前确实判失败”当作通过。SSRF 本身的修复是独立任务，不在本 harness 范围。

### ID 来源与歧义安全

`ID来源` 取值为 `text`（从回复文本提取，支持 `Source ID:`、`记录 ID：`、反引号、路径）/ `staged`（web 无回复时从唯一新增暂存路径恢复）/ `none` / `ambiguous`。**只允许恰好一个唯一候选**时从暂存路径 fallback；零/多候选一律不猜。`ID来源` 为 `none`/`ambiguous` 时：

- 断言 FAIL；
- `--cleanup` **跳过清理，不碰任何候选**，避免误删。

关键点：**“产生了含 Source ID 的新增暂存”是相对“调用前基线”判定的**（先记录调用前的已暂存路径与文件集合，调用后再 diff），**不是**“暂存区非空”。因此：

- 全新捕获：新建了含本次 ID 的文件并加入暂存 → 该项通过。
- **重复捕获**：若同一 Source ID 的路径在上一次就已存在并已暂存，本次调用不会产生“新增”暂存 → 该项 FAIL。**重复记录会因不是本次新 capture 而断言失败**，这正是期望行为，避免把旧记录误判为本次成功。

缺失关键 JSON 元字段（如 `stopReason` 缺省、`toolSummary.failures` 缺省、`yielded` 缺省）会被当作空值进入断言，从而 FAIL，不会静默伪装成成功。

## 唯一测试消息 / URL 建议

由于重复捕获会断言失败，建议每次测试使用**唯一的测试消息**（如 `想法：测试唯一内容 <时间戳>`）或**唯一的 URL**，让本次生成全新的 Source ID，确保能命中“新增暂存”断言。

## --wait 轮询（显式 --vault）与“通过”含义

`--wait <秒>`：拿到 Source ID 后脚本侧调用 `python3 skills/vault-capture/scripts/vault_capture.py --vault "$VAULT_ROOT" inspect <id>` 轮询，直到 `ready/failed/manual` 或超时，再对终态断言。**显式传 `--vault`**，不依赖环境变量 `VAULT_ROOT` 是否导出——即使未导出 `VAULT_ROOT`，wait 轮询也能通过显式 vault 正常工作。web 类请用 `--wait` 做确定性验证，**不要**靠再问一次 LLM。

**区分两层“通过”**：

- **harness 流程通过**：`--assert` 全部检查项通过（envelope、失败数为 0、新增暂存、以及 `--expect-status` 匹配）。这只说明“本次调用流程符合预期”。
- **抓取 ready**：`--expect-status ready`（默认）通过才表示抓取真到了 `ready` 终态。

`--expect-status ready` 通过 ≠ 一定 ready；同理 `--expect-status failed` 通过只是“接受 failed 终态”，不代表成功抓取。按你想验证的语义选对 flag。

## JSON 结果结构（jq 路径）

顶层是 `{runId, status, result}` 包装，关键字段在 `.result` 下：

| 字段 | jq 路径 | 说明 |
|---|---|---|
| agent 最终回复 | `.result.meta.finalAssistantVisibleText`（或 `.result.payloads[0].text`） | 给用户看的文本，含 Source ID / 路径 / 状态 |
| 是否被中止 | `.result.meta.aborted` | true 表示被人工/系统打断 |
| 停止原因 | `.result.meta.stopReason` | 正常应为 `"stop"` |
| 工具调用次数 | `.result.meta.toolSummary.calls` | |
| 工具失败数 | `.result.meta.toolSummary.failures` | 非 0 说明脚本执行出错 |
| 模型 | `.result.meta.agentMeta.model` | |

从回复文本中提取 Source ID（形如 `20260808-131519-sz9x`，可能在 `Source ID:` 后或路径里）：

```bash
jq -r '.result.meta.finalAssistantVisibleText' out.json | grep -oP '[0-9]{8}-[0-9]{6}-[a-z0-9]{4}' | head -1
```

## 断言参考（想法类）

一次成功的 `想法：` 调用应满足（与 harness `--assert` 一致）：

1. `stopReason == "stop"` 且 `aborted != true` 且 `toolSummary.failures == 0`
2. 回复非空，且包含格式为 `YYYYMMDD-HHMMSS-XXXX` 的 Source ID
3. 回复中包含 已保存/ready/created/已落盘 之一（想法类直接落盘，无后台抓取）
4. 文件实际存在于 `$VAULT_ROOT/notes/ideas/`
5. **本次产生了含本次 Source ID 的新增暂存**——按“调用前基线后新增”判定（先记录调用前已暂存路径，调用后 diff），**不是**"暂存区非空"（测试库可能有遗留暂存导致假阳性）；同一 ID 重复捕获因没有“新增”暂存而 FAIL。

网页类（`收：`）有两种 envelope：同步回复（stop + 文本含 Source ID）或真实异步 yield（`end_turn` + `yielded: true` + 空回复，ID 从唯一新增暂存路径恢复）。抓取在后台子任务异步完成，用 `--wait <秒>` 让脚本轮询 `inspect` 到终态（`ready/failed/manual`）后按 `--expect-status` 断言；否则可用同一 session-key 追问"`<id>` 抓取完成了吗"，或手动：

```bash
python3 skills/vault-capture/scripts/vault_capture.py --vault "$VAULT_ROOT" inspect <id>
```

## 清理测试数据

`--cleanup` 会在清理**前**相对“调用前基线”重新计算差异（纳入 wait 期间新建/暂存的 annotation/assets/queue），然后**只 unstage 本次新增的暂存路径、只删除调用前不存在的新建文件**，不碰测试库里其它既有暂存/改动，也不删除重复 ID 的既有文件或既有暂存。若 `ID来源` 为 `none`/`ambiguous` 则**跳过清理**。手动清理（在 `$VAULT_ROOT` 下）：

```bash
git status --porcelain | grep '<本次SourceID>'   # 先看要清理的路径
git reset -q -- <含该ID的路径...>                 # 取消暂存(新库可能无 HEAD, restore --staged 会失败)
rm -f <含该ID的文件...>
```

> 旧版本曾用 `git restore --staged .` 全量取消暂存——已弃用，它会误伤测试库里无关的既有暂存；也曾对含本次 ID 的路径全量 restore/delete，会误删上一次遗留的旧记录。现改为按“调用前基线后的新增内容”定向清理。注意 `git restore --staged` 在尚无任何 commit 的新测试库会报 `could not resolve 'HEAD'`，因此手动与 harness 均用 `git reset -q -- <path>`（无需 HEAD 也能安全取消暂存且不动工作区）。

## 环境变量

- `VAULT_ROOT=/home/monottx/repos/SourceNotes-test`（已在 gateway 环境里配置，脚本直接可用）。本地直接跑 harness 时请自行 `export VAULT_ROOT=<某 *-test 库>`；未导出也可，脚本有默认值，但 **basename 必须以 `-test` 结尾**，否则在调用 openclaw 前拒绝。
- 宿主机上 `openclaw` 在 PATH 中；gateway 正在运行（`openclaw health` 可验证）
- ⚠️ gateway 的 `VAULT_ROOT` 现指向测试库，Telegram 等真实入口进来的捕获也会落进测试库。调试结束记得指回正式 vault

## 回归测试

`tests/opencode-harness/test_capture_debug.sh` 用 mktemp 临时目录（内含 basename 以 `-test` 结尾的测试库）和 fake `openclaw`/fake `python3`，**绝不调用真实 OpenClaw**，覆盖：非测试库拒绝、重复 ID 误判、全新 idea 断言与清理、web 同步 `--wait` 显式 vault、raw 通用契约；以及 v2 的 fake `python3` 强校验 `--vault`、web 异步 yield 从唯一新增暂存恢复 ID、`--expect-status failed` 通过、默认 `ready` 拒绝 `failed`、多候选不猜 ID 且 cleanup 安全、wait 期新增 annotation/queue 后 cleanup 无残留。运行：

```bash
bash tests/opencode-harness/test_capture_debug.sh
```
