# SourceNotes production switch — Cutover Package（Work Item 01 产物，round 3 safety closure 修订）

- Effort: `.scratch/2026-08-17-sourcenotes-production-switch/`
- Work Item: `issues/01-preflight-and-cutover-package.md`（Role: Executor）
- 日期: 2026-08-17（round 3：独立窄范围安全闭环 Work Item
  `.scratch/2026-08-17-sourcenotes-cutover-runbook-safety-closure/` 修订，
  关闭 F-04/F-07/F-11/F-13/F-14/F-15；F-01/F-02/F-03/F-05/F-06/F-08/F-09/F-10/F-12 保持 closed；
  repair round 1：按 Reviewer round 1 修复 F-11/F-13/F-14/F-16/F-17；
  final repair round：按 Reviewer round 2 修复 F-04/F-11/F-13/F-14/F-17/F-18/F-19）
- 候选 commit: `main@017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`
- 修订依据: `../2026-08-17-sourcenotes-cutover-runbook-safety-closure/spec.md` /
  `plan.md`（approved）、`execution-brief-01.md`（唯一自包含第二层简报）、
  `evidence/01/review.md` round 3（F-04/F-07/F-11/F-13/F-14/F-15 open）；
  Operator 授权原文 `批准新建窄范围安全闭环 Work Item 并继续。` 与
  `同意再次更换 Executor 并继续安全闭环 Work Item。`（真实模型 E2E 仍属后续
  Operator Controlled Action，本修订只做 fixture rehearsal）。

> **本文件是给 Operator 的精确执行包。** 本 Work Item 只产出本文件与
> `evidence/01/execution.md`；本包列出的所有真实写入命令均标注
> `CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED`，一律由 Operator 在
> 看到精确命令、目标与 diff 后单独执行/授权。Planner/Executor/Reviewer 不执行
> 也不授权任何 Controlled Action。
>
> 本包不含任何 token 值、绝对 Vault 路径、正文或逐项 URL；正式 SourceNotes
> 路径只以变量 `"$PRODUCTION_VAULT_ROOT"`（Operator 私有设置，本包只声明
> basename=`SourceNotes`）或 basename 形式出现。正文中出现的 Unix 绝对路径仅限
> 本 Effort 的 Project State 自身路径（`.scratch/2026-08-17-sourcenotes-production-switch/`）
> 与 `$HOME/.openclaw/openclaw.json` 等变量展开形态，不构成 Vault 角色路径。
> 真实模型委派 canary 在本 Work Item **NOT_RUN — OPERATOR CONTROLLED ACTION
> GATE**，本包只给出精确 runbook（§2.5 Gate A–F）。
>
> 本包内嵌的全部脚本（`atomic.py`、`transform.py`、`token_inject.py`、
> `projection.py`、`pause_ingress.py`、`secure_file.py`、`vault_fingerprint.py`、
> `canary_provenance.py`、`cleanup_canary.py`、`canary_assert.py`、
> `secure_capture.py`）已在 `/tmp/sourcenotes-cutover-safety-*-test` 无 secret
> fixture 上实际运行验证（见本 Effort `evidence/01/execution.md` VAL-S01..S05、
> repair round 1 VAL-R1-01..05、final repair round VAL-F01..F09，与本包文本逐字节
> 一致；round 2 的 VAL-R2-02..05 记录见 parent `evidence/01/execution.md`）。
> 全部 bash 块通过 `bash -n`（F-13，VAL-F03）；canary agent 命令精确为获批
> `--message` 形式（F-16，VAL-F04）；本包不含任何 token 值、绝对 Vault 路径、
> 正文或逐项 URL、省略号/尖括号占位形态（VAL-F05/F08）。

---

## 0. 基线快照（secret-free，取自 evidence/01/execution.md）

| 项 | 值 |
|---|---|
| 蓝图库 branch/HEAD | `main` @ `017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`（= origin/main） |
| 正式 Vault HEAD/状态 | `main` @ `ec1a90eb9d41df77cf74e44d51e703d0379882e7`，工作树 clean |
| 测试 Vault HEAD/状态 | `main` @ `ec1a90eb9d41df77cf74e44d51e703d0379882e7`，既有脏状态（只读记录，不清理） |
| 活动配置 SHA-256 | `de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424`（0600） |
| OpenClaw | `2026.7.1-2 (0790d9f)`；Gateway loopback `127.0.0.1:18789`，运行中，probe ok |
| 队列摘要 | 0 running / 0 queued（`openclaw tasks list --status running|queued`） |
| 配置 schema 状态 | `openclaw config validate` → `Config valid` |

当前运行态（语义摘要）：capture disabled、`VAULT_ROOT` basename=`SourceNotes-test`、
query/maintenance disabled、NotesVaulter 有独立 Telegram binding（agent
`notesvaulter` → telegram account `notesvaulter`）、`main` 未显式配置
`subagents.allowAgents`（默认仅同 agent，无法 spawn `notesvaulter`）。

**真实模型委派 E2E 状态**：`NOT_RUN — OPERATOR CONTROLLED ACTION GATE`。原因：
模型凭据只存在于活动 OpenClaw 私有配置/auth profile（`$OPENCLAW_STATE_DIR` 内），
不在 shell env 或独立 SecretRef；按获批边界不复制模型密钥。Operator 已批准替代：
真实委派 canary 使用**活动 Gateway + 正式库完整一次性 `*-test` 克隆**（§2.5
Gate B/C），先暂停真实入口并暂时指向克隆，通过后才切换正式 Vault。

---

## 1. 候选配置模型（before 语义摘要 → candidate 语义摘要）

只记录语义摘要，不复制原配置。字段依据：OpenClaw 本机文档
（`docs/tools/subagents.md`、`docs/gateway/config-agents.md`、`docs/gateway/config-channels.md`）
与本机 `openclaw config schema` 一致；`agents.list[].subagents.allowAgents` 为
`string[]`，默认仅允许同 agent，`["*"]` 属宽泛通配，**candidate 禁止 `*`**；
`channels.{id}.enabled=false` 使该通道不启动（ingress 暂停的精确机制）。

| # | 配置点 | before（语义摘要） | candidate（语义摘要） |
|---|---|---|---|
| C1 | `agents.list` main | id=`main`，name=`Main Agent`，skills 未设置（默认），`subagents.allowAgents` 未设置（默认仅自身） | id=`main`（保留），name=`Steward`（显示名），`subagents.allowAgents=["notesvaulter"]`（精确窄列表，无 `*`） |
| C2 | `agents.list` notesvaulter | id=`notesvaulter`，skills=`["vault-capture"]` | skills=`["vault-capture","vault-query","vault-maintenance"]`（三技能 allowlist，精确数组替换） |
| C3 | `skills.entries` 三技能 env | `vault-capture.enabled=false` 且 `env.VAULT_ROOT` basename=`SourceNotes-test`；query/maintenance `enabled=false` 无 VAULT_ROOT | **三个 skill entry 均** `enabled=true` 且**均**设 `env.VAULT_ROOT`（F-09）：canary 阶段=`"$CANARY_VAULT_ROOT"`、production 阶段=`"$PRODUCTION_VAULT_ROOT"`；各自其它 env/未知键保留 |
| C4 | `bindings` | `main`→telegram account `default`；`notesvaulter`→telegram account `notesvaulter`（直接第二入口） | 仅 `main`→telegram account `default`；notesvaulter binding 条目**删除**（数组精确过滤） |
| C5 | `channels.telegram.accounts` | accounts `default`（botToken）、`notesvaulter`（botToken） | 仅保留 account `default`；`notesvaulter` 账号键**删除**（pop 键，非 JSON null）；旧 token 由 Operator 私下 revoke |
| C6 | `channels.telegram.defaultAccount` / `enabled` | `default`；`enabled=true` | `default` 不变；canary 候选 `enabled=false`（暂停入口，Gate B/C）；production 候选 `enabled=true`（恢复 main Telegram，Gate E） |
| C7 | main Telegram token | 旧值（已被工具输出触及，必须轮换） | **轮换后的新值**，只由 Operator 从 0600 私有文件 `"$MAIN_BOT_TOKEN_FILE"` 经 `token_inject.py` 写入 candidate；永不出现在本包/仓库/Evidence/命令日志 |
| C8 | models / browser / web search / SSRF / gateway / mcp / 其它 agent 与 channel | 现状 | 一律不变（transformer 深复制保留全部未知/无关字段） |

NotesVaulter 直接 Telegram 入口移除后，NotesVaulter 只通过 Steward（`main`）的
内部委派服务被调用，符合单入口拓扑。

### 1.1 确定性 fail-closed candidate transformer（F-05/F-09/F-10 修复）

以下脚本已在 `/tmp/*-test` fixture 上运行验证（VAL-R2-03）：canary/production/
safe-rollback 三角色转换、deterministic/idempotent（两次 sha 一致）、未知字段保留、
六类结构冲突负例全部 fail-closed 且不写 candidate、`openclaw config validate` exit 0。
把脚本保存为 `"$STATE_DIR/transform.py"`（0600）后使用（依赖同目录 `atomic.py`）：

```python
#!/usr/bin/env python3
"""transform.py — deterministic fail-closed candidate transformer (Work Item 01 round 2).

Usage:
  python3 transform.py SRC DST VAULT_ROOT --role canary|production|safe-rollback

Fail-closed assertions (any violation -> non-zero exit, DST never written):
  - agents.list exists and is a list; exactly one id=="main", exactly one id=="notesvaulter"
  - skills.entries exists and is a dict; the three vault skill entries exist and are dicts
  - bindings is a list; main->telegram:default binding present
  - channels.telegram is a dict; accounts is a dict
  - VAULT_ROOT is absolute; basename matches role:
      canary          -> basename endswith "-test"
      production      -> basename == "SourceNotes"
      safe-rollback   -> basename == "SourceNotes-test"
  - role canary: channels.telegram.enabled must become false (pause ingress)
  - role production: channels.telegram.enabled must become true (restore main Telegram)
  - role safe-rollback: vault-capture enabled=false, telegram enabled=true

Transform (deep copy preserves all unknown fields):
  - main: name="Steward", subagents.allowAgents=["notesvaulter"] (exact narrow list, no "*")
  - notesvaulter: skills = exactly ["vault-capture","vault-query","vault-maintenance"]
  - the three skill entries: enabled=true (safe-rollback: vault-capture disabled) and
    env.VAULT_ROOT = VAULT_ROOT for ALL THREE (F-09), preserving other env keys and unknown keys
  - bindings: precise array replacement dropping agentId=="notesvaulter"
  - channels.telegram.accounts: pop("notesvaulter") (delete key, not JSON null)

stdout: only fixed tokens (TRANSFORM_WRITTEN=true sha=哈希值) — never the config body.
"""
import argparse
import copy
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from atomic import atomic_write

VAULT_SKILLS = ["vault-capture", "vault-query", "vault-maintenance"]
PRODUCTION_BASENAME = "SourceNotes"
TEST_BASENAME = "SourceNotes-test"


class TransformError(AssertionError):
    pass


def _fail(msg):
    raise TransformError("fail-closed: " + msg)


def _expect(cond, msg):
    if not cond:
        _fail(msg)


def load_config(path):
    with open(path, "rb") as f:
        data = f.read()
    try:
        return json.loads(data.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        _fail("source config not valid UTF-8 JSON: %s" % exc)


def transform(cfg, vault_root, role):
    out = copy.deepcopy(cfg)

    # structural assertions (F-10 fail-closed)
    agents = out.get("agents", {}).get("list")
    _expect(isinstance(agents, list), "agents.list missing or not a list")
    mains = [a for a in agents if isinstance(a, dict) and a.get("id") == "main"]
    notes = [a for a in agents if isinstance(a, dict) and a.get("id") == "notesvaulter"]
    _expect(len(mains) == 1, "exactly one agents.list[].id==main required, got %d" % len(mains))
    _expect(len(notes) == 1, "exactly one agents.list[].id==notesvaulter required, got %d" % len(notes))

    entries = out.get("skills", {}).get("entries")
    _expect(isinstance(entries, dict), "skills.entries missing or not a dict")
    for name in VAULT_SKILLS:
        _expect(name in entries and isinstance(entries[name], dict),
                "skills.entries.%s missing or not a dict" % name)

    binds = out.get("bindings")
    _expect(isinstance(binds, list), "bindings missing or not a list")
    main_bindings = [b for b in binds
                     if isinstance(b, dict) and b.get("agentId") == "main"
                     and (b.get("match") or {}).get("channel") == "telegram"
                     and (b.get("match") or {}).get("accountId") == "default"]
    _expect(len(main_bindings) == 1, "exactly one main->telegram:default binding required")

    tg = out.get("channels", {}).get("telegram")
    _expect(isinstance(tg, dict), "channels.telegram missing or not a dict")
    _expect(isinstance(tg.get("accounts"), dict), "channels.telegram.accounts missing or not a dict")

    # vault_root assertions
    _expect(isinstance(vault_root, str) and vault_root.startswith("/"),
            "VAULT_ROOT must be an absolute path")
    base = vault_root.rstrip("/").rsplit("/", 1)[-1]
    if role == "canary":
        _expect(base.endswith("-test"), "canary VAULT_ROOT basename must end with -test, got %r" % base)
    elif role == "production":
        _expect(base == PRODUCTION_BASENAME, "production VAULT_ROOT basename must be %r, got %r"
                % (PRODUCTION_BASENAME, base))
    elif role == "safe-rollback":
        _expect(base == TEST_BASENAME, "safe-rollback VAULT_ROOT basename must be %r, got %r"
                % (TEST_BASENAME, base))
    else:
        _fail("unknown role: %r" % role)

    # main: Steward + narrow allowAgents
    main = mains[0]
    main["name"] = "Steward"
    main.setdefault("subagents", {})
    main["subagents"]["allowAgents"] = ["notesvaulter"]

    # notesvaulter: exactly the three approved skills
    notes[0]["skills"] = list(VAULT_SKILLS)

    # three skill entries: env.VAULT_ROOT (all three, F-09) + enabled
    for name in VAULT_SKILLS:
        entries[name]["enabled"] = True
        entries[name].setdefault("env", {})
        entries[name]["env"]["VAULT_ROOT"] = vault_root

    # bindings: precise array replacement dropping notesvaulter
    out["bindings"] = [b for b in binds if not (isinstance(b, dict) and b.get("agentId") == "notesvaulter")]

    # telegram accounts: delete notesvaulter key (not JSON null)
    tg["accounts"].pop("notesvaulter", None)

    # ingress policy per role
    if role == "canary":
        tg["enabled"] = False
    elif role in ("production", "safe-rollback"):
        tg["enabled"] = True

    if role == "safe-rollback":
        entries["vault-capture"]["enabled"] = False

    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("vault_root")
    ap.add_argument("--role", required=True, choices=["canary", "production", "safe-rollback"])
    args = ap.parse_args(argv)

    cfg = load_config(args.src)
    out = transform(cfg, args.vault_root, args.role)
    body = json.dumps(out, indent=2, ensure_ascii=False).encode("utf-8")
    h = atomic_write(args.dst, body, expected_sha=None)
    print("TRANSFORM_WRITTEN=true role=%s sha=%s" % (args.role, h))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except TransformError as exc:
        print("TRANSFORM_FAILED=%s" % exc, file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001
        print("TRANSFORM_ERROR=%s" % exc, file=sys.stderr)
        sys.exit(3)
```

用法（canary 阶段；production 阶段角色换为 `--role production`）：

```bash
# CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED
python3 -B transform.py "$POST_MAIN_ROTATION_BASELINE" "$CANARY_CANDIDATE" "$CANARY_VAULT_ROOT" --role canary
# stdout 只输出：TRANSFORM_WRITTEN=true role=canary sha=64位十六进制哈希（不输出配置正文）
```

fail-closed 断言（任一不满足则 exit 2 且不写 candidate）：`agents.list` 存在且
main/notesvaulter 各**恰一**；`skills.entries` 存在且三技能 entry 均为 dict；
`bindings` 为 list 且 main→telegram:default 恰一条；`channels.telegram.accounts`
为 dict；`VAULT_ROOT` 为绝对路径且 basename 符合角色（canary 以 `-test` 结尾 /
production=`SourceNotes` / safe-rollback=`SourceNotes-test`）。

轮换后的 main token 由 `token_inject.py` 从 0600 私有文件写入 candidate（F-07：
直接写 0600 文件；stdout 只输出固定 `TOKEN_INJECTED=true sha=哈希值`，**绝不输出
配置正文或 token**；token 文件非 0600 / 非 regular file 则 fail-closed）。保存为
`"$STATE_DIR/token_inject.py"`（0600）：

```python
#!/usr/bin/env python3
"""token_inject.py — inject the rotated main bot token from a 0600 private file (Work Item 01 round 2).

Usage:
  python3 token_inject.py CANDIDATE TOKEN_FILE

Fail-closed:
  - TOKEN_FILE must be a regular file with mode 0600
  - token non-empty after strip; no newline handling beyond strip
  - channels.telegram.accounts.default must exist as dict

Writes the candidate back atomically (0600) with botToken replaced.
stdout: only fixed tokens (TOKEN_INJECTED=true sha=哈希值) — NEVER the token or the config body.
"""
import json
import os
import pathlib
import stat
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from atomic import atomic_write


def main(argv):
    if len(argv) != 2:
        raise SystemExit("usage: token_inject.py CANDIDATE TOKEN_FILE")
    candidate_path, token_path = argv

    st = os.stat(token_path)
    if not stat.S_ISREG(st.st_mode):
        raise SystemExit("TOKEN_INJECT_FAILED=token file not a regular file")
    if (st.st_mode & 0o777) != 0o600:
        raise SystemExit("TOKEN_INJECT_FAILED=token file mode must be 0600, got %s"
                         % oct(st.st_mode & 0o777))

    with open(token_path, "rb") as f:
        raw = f.read()
    token = raw.decode("utf-8").strip()
    if not token:
        raise SystemExit("TOKEN_INJECT_FAILED=token file empty")

    with open(candidate_path, "rb") as f:
        cfg = json.loads(f.read().decode("utf-8"))
    default_acc = ((cfg.get("channels") or {}).get("telegram") or {}).get("accounts", {}).get("default")
    if not isinstance(default_acc, dict):
        raise SystemExit("TOKEN_INJECT_FAILED=channels.telegram.accounts.default missing or not a dict")
    default_acc["botToken"] = token

    body = json.dumps(cfg, indent=2, ensure_ascii=False).encode("utf-8")
    h = atomic_write(candidate_path, body)
    print("TOKEN_INJECTED=true sha=%s" % h)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

```bash
# CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED
python3 -B token_inject.py "$CANDIDATE" "$MAIN_BOT_TOKEN_FILE"
# stdout 只输出：TOKEN_INJECTED=true sha=64位十六进制哈希
```

### 1.2 secret-free semantic projection（F-05/F-07 修复）

以下脚本是完整可执行 Python（无省略号、无非法表达式），只输出批准字段、Vault
basename、键集合与 token 存在/轮换布尔；**绝不读取后输出 token 值**。保存为
`"$STATE_DIR/projection.py"`（0600）后使用：

```python
#!/usr/bin/env python3
"""projection.py — secret-free semantic projection of a candidate config (Work Item 01 round 2).

Usage:
  python3 projection.py CONFIG [--rotated-marker MARKER_FILE]

Outputs a single JSON object (stdout) containing ONLY approved fields:
  - agents: id / name / skills / subagents.allowAgents
  - vault_skills: enabled boolean for each of the three approved skills
  - vault_roots: basename of env.VAULT_ROOT for each approved skill
  - bindings: agentId / channel / accountId triples
  - telegram_account_keys: sorted account key set
  - main_token_present: bool (non-empty botToken field on account "default")
  - notesvaulter_token_present: bool
  - main_token_rotated: bool derived from the Operator-maintained private marker file
    (marker exists -> true; marker argument omitted -> false)
  - telegram_enabled: bool

Never reads, prints, or derives any token VALUE. Valid complete Python (F-05/F-10).
"""
import argparse
import json
import os
import pathlib
import sys

VAULT_SKILLS = ["vault-capture", "vault-query", "vault-maintenance"]


def _basename(value):
    if not value:
        return None
    return str(value).rstrip("/").rsplit("/", 1)[-1]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--rotated-marker", default=None)
    args = ap.parse_args(argv)

    with open(args.config, "rb") as f:
        cfg = json.loads(f.read().decode("utf-8"))

    agents_out = []
    for a in cfg.get("agents", {}).get("list") or []:
        if isinstance(a, dict):
            agents_out.append({
                "id": a.get("id"),
                "name": a.get("name"),
                "skills": a.get("skills"),
                "allowAgents": (a.get("subagents") or {}).get("allowAgents"),
            })

    entries = (cfg.get("skills") or {}).get("entries") or {}
    vault_skills = {}
    vault_roots = {}
    for name in VAULT_SKILLS:
        e = entries.get(name)
        if isinstance(e, dict):
            vault_skills[name] = bool(e.get("enabled"))
            vault_roots[name] = _basename((e.get("env") or {}).get("VAULT_ROOT"))

    bindings_out = []
    for b in cfg.get("bindings") or []:
        if isinstance(b, dict):
            bindings_out.append({
                "agentId": b.get("agentId"),
                "channel": (b.get("match") or {}).get("channel"),
                "accountId": (b.get("match") or {}).get("accountId"),
            })

    tg = (cfg.get("channels") or {}).get("telegram") or {}
    accounts = tg.get("accounts") or {}
    default_acc = accounts.get("default") or {}
    nv_acc = accounts.get("notesvaulter") or {}

    rotated = False
    if args.rotated_marker:
        rotated = os.path.isfile(args.rotated_marker)

    result = {
        "agents": agents_out,
        "vault_skills": vault_skills,
        "vault_roots": vault_roots,
        "bindings": bindings_out,
        "telegram_account_keys": sorted(accounts.keys()),
        "telegram_enabled": bool(tg.get("enabled")),
        "main_token_present": bool(default_acc.get("botToken")),
        "notesvaulter_token_present": bool(nv_acc.get("botToken")),
        "main_token_rotated": rotated,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

```bash
# CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED（只读输出）
python3 -B projection.py "$CANDIDATE" --rotated-marker "$TOKEN_ROTATED_MARKER"
```

- `--rotated-marker` 指向 Operator 在轮换完成后创建的 0600 私有 marker 文件
  （`"$TOKEN_ROTATED_MARKER"`，仅存在性，不含值）；存在则 `main_token_rotated=true`。
- 期望（语义断言）：main name=`Steward`；allowAgents=`["notesvaulter"]`（无 `*`）；
  notesvaulter skills=三 vault skill；三技能 `enabled=true` 且
  `vault_roots` 三值 basename 一致（canary=`SourceNotes-production-canary-${RUN_ID}-test`、
  production=`SourceNotes`）；bindings 仅 1 条 main→telegram:default；
  `telegram_account_keys=["default"]`；`notesvaulter_token_present=false`；
  任何输出不含 secret 值。

---

## 2. Operator Runbook（round 2：精确单一 cutover DAG，F-04/F-06/F-12 修复）

### 2.0 私有变量定义（F-07 修复：fail-closed preamble；无尖括号占位符、无伪绝对路径示例）

> 任何 Operator command 之前，先 source 本块。全部私有变量以 `: "${VAR:?}"`
> 定义检查 fail-closed：缺失/为空立即非零退出，不继续任何后续命令（F-07/F-13）。
> 本包不提供任何变量伪值、真实路径或尖括号占位符；`PRODUCTION_VAULT_ROOT` /
> `TEST_VAULT_ROOT` 的真实值只存在于 Operator 私有会话。

```bash
# CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED
# —— fail-closed preamble（F-07）：缺失变量立即退出，任何命令执行前必须 source ——
set -Eeuo pipefail
: "${STATE_DIR:?STATE_DIR 未定义（Operator 私有状态目录，0700）}"
: "${ACTIVE_CONFIG:?ACTIVE_CONFIG 未定义（活动 OpenClaw 配置路径）}"
: "${PRODUCTION_VAULT_ROOT:?PRODUCTION_VAULT_ROOT 未定义（basename=SourceNotes，Operator 私有）}"
: "${MAIN_BOT_TOKEN_FILE:?MAIN_BOT_TOKEN_FILE 未定义（轮换后新 main token 的 0600 私有文件）}"
: "${TEST_VAULT_ROOT:?TEST_VAULT_ROOT 未定义（basename=SourceNotes-test，Operator 私有）}"

# —— F-13 fail-fast 基础设施：die / run_or_die / 安全 cleanup trap ——
# F-04：暂停投影检查的单一完整安全引用 pattern（经变量传递，引号不被 shell 剥掉，
#       false 不会被解析为文件名）
export PAUSE_PATTERN='"telegram_enabled"[[:space:]]*:[[:space:]]*false'
die() {
  echo "FATAL: $*" >&2
  exit 1
}
# 显式包裹任何外部命令；失败即 die，绝不静默继续
run_or_die() {
  local desc="$1"
  shift
  "$@" || die "$desc 失败: $*"
}
# 只清理本次 RUN_ID 的：canary 克隆（经 cleanup_canary.py provenance 验证）与
# ownership manifest 记录的本次可重建候选（canary/production candidate）；
# 绝不触碰正式 Vault/活动配置/未知目录/命名回滚点（PRE_ROTATION_BACKUP、
# INGRESS_PAUSED_BASELINE、POST_MAIN_ROTATION_BASELINE、POST_ROTATION_SAFE_ROLLBACK）。
_safe_cleanup() {
  local rc=$?          # F-13：必须先取原 rc，再动 trap
  trap - ERR           # 防递归（此时 rc 已保存）
  if [ -n "${CANARY_VAULT_ROOT:-}" ] && [ -d "$CANARY_VAULT_ROOT" ] \
     && [ -f "$STATE_DIR/cleanup_canary.py" ]; then
    if python3 -B "$STATE_DIR/cleanup_canary.py" "$STATE_DIR" "$CANARY_VAULT_ROOT" \
         --production-vault-root "$PRODUCTION_VAULT_ROOT" >/dev/null 2>&1; then
      echo "TRAP_CLEANED=canary 克隆已删除" >&2
    else
      echo "TRAP_CLEANUP_SKIPPED=cleanup_canary 拒绝删除（保留现场，人工处置）" >&2
    fi
  fi
  # 候选清理只认 ownership manifest（secure_file.py cleanup-owned 逐项 no-follow
  # 验证 dev/inode/parent/run_id；不匹配则保留并报告；rm/unlink 失败显式报告）
  if [ -f "$STATE_DIR/secure_file.py" ]; then
    if ! python3 -B "$STATE_DIR/secure_file.py" cleanup-owned \
         "$STATE_DIR" "ownership-${RUN_ID}.manifest" "$RUN_ID" 2>&1; then
      echo "TRAP_CLEANUP_ERROR=ownership cleanup 失败，已报告并保留现场" >&2
    fi
  fi
  return "$rc"         # 保留原退出码，cleanup 错误只报告、不覆盖原 rc
}
# 记录本次 RUN_ID 创建的可重建候选（secure 0600 manifest；role=canary-candidate|production-candidate）
record_owned() {
  python3 -B "$STATE_DIR/secure_file.py" record \
    "$STATE_DIR" "ownership-${RUN_ID}.manifest" "$1" "$2" "$RUN_ID" \
    || die "ownership 记录失败: $2"
}
# 失败路径（set -Eeuo pipefail + ERR trap）触发安全清理；成功路径不清理任何东西
trap '_safe_cleanup' ERR

# —— 命名回滚点（F-06；PRE_ROTATION_BACKUP 只审计，token revoke 后不得作为回滚目标）——
export PRE_ROTATION_BACKUP="$STATE_DIR/pre-rotation-baseline.json"     # 审计用
export INGRESS_PAUSED_BASELINE="$STATE_DIR/ingress-paused-baseline.json"  # 入口暂停基线（Gate A 第 1 步发布）
export POST_MAIN_ROTATION_BASELINE="$STATE_DIR/post-main-rotation-baseline.json"  # main 轮换后回滚目标
export CANARY_CANDIDATE="$STATE_DIR/canary-candidate.json"
export POST_ROTATION_SAFE_ROLLBACK="$STATE_DIR/post-rotation-safe-rollback.json"  # NotesVaulter revoke 后回滚目标
export PRODUCTION_CANDIDATE="$STATE_DIR/production-candidate.json"
# —— 私有 secret/标记文件（0600）——
export MAIN_BOT_TOKEN_FILE="$STATE_DIR/main-bot-token"          # 轮换后新 main token
export TOKEN_ROTATED_MARKER="$STATE_DIR/main-token-rotated.marker"  # 轮换完成标记（空文件，0600）

# —— canary 运行标识（RUN_ID 派生，非 secret；CANARY_SESSION_KEY 为本地会话键）——
export RUN_ID="$(date +%Y%m%d-%H%M%S)-$$"
: "${RUN_ID:?RUN_ID 派生失败}"
export CANARY_SESSION_KEY="canary-${RUN_ID}"
: "${CANARY_SESSION_KEY:?CANARY_SESSION_KEY 派生失败}"
export CANARY_MARKER_STRING="sourcenotes-canary-${RUN_ID}"
# F-14/F-16：CANARY_PROMPT 为提示文本（--message 直接传入，非文件路径）
export CANARY_PROMPT
IFS= read -r -d '' CANARY_PROMPT <<EOF || true
You are the Steward. Execute the canary steps by delegating exclusively to the
notesvaulter sub-agent via sessions_spawn(agentId="notesvaulter"); do not touch the
vault yourself. The notesvaulter agent is configured with a disposable *-test clone
vault.
1) Capture one real idea whose title or text contains the unique marker "${CANARY_MARKER_STRING}".
   The capture must produce a Markdown note; confirm the staged relative path (must be a
   .md file inside the canary clone).
2) Query search for the same unique marker "${CANARY_MARKER_STRING}" and report the hit
   count plus the just-captured note id / relative path. The marker must be found in the
   Markdown note body — not in any separate .txt file.
3) Run the maintenance report for that vault.
Your FINAL visible output MUST be exactly ONE line of JSON with NO markdown fences and NO
prose before or after, matching exactly this schema (example values; substitute real ones):
{"ok":true,"marker":"${CANARY_MARKER_STRING}","capture":{"ok":true,"ingest_status":"ready","id":"20260817-000000-0000","path":"notes/ideas/20260817-000000-0000--canary-idea.md"},"query":{"ok":true,"count":1,"ids":["20260817-000000-0000"],"paths":["notes/ideas/20260817-000000-0000--canary-idea.md"]},"maintenance":{"ok":true}}
Never print secrets, tokens, or absolute vault paths.
EOF
export CANARY_OUTPUT="$STATE_DIR/canary-output-${RUN_ID}.json"   # 外层 JSON（0600 私有，不含 secret）

# —— 派生 CANARY_VAULT_ROOT（F-07/F-11）：只能由已验证 STATE_DIR + RUN_ID 计算——
#    验证：absolute、父目录精确等于 STATE_DIR/canary、basename 精确模式、目标初始不存在。
case "$STATE_DIR" in
  /*) ;;
  *) echo "CANARY_PREAMBLE_FAILED=STATE_DIR 不是绝对路径" >&2; exit 1 ;;
esac
export CANARY_VAULT_ROOT="$STATE_DIR/canary/SourceNotes-production-canary-${RUN_ID}-test"
[ "$(dirname "$CANARY_VAULT_ROOT")" = "$STATE_DIR/canary" ] || {
  echo "CANARY_PREAMBLE_FAILED=canary parent 必须是 STATE_DIR/canary" >&2; exit 1; }
case "$(basename "$CANARY_VAULT_ROOT")" in
  "SourceNotes-production-canary-${RUN_ID}-test") ;;
  *) echo "CANARY_PREAMBLE_FAILED=canary basename 模式不匹配" >&2; exit 1 ;;
esac
[ -e "$CANARY_VAULT_ROOT" ] && {
  echo "CANARY_PREAMBLE_FAILED=canary 目标已存在（应初始不存在）" >&2; exit 1; }

# —— F-15：正式 Vault 预克隆指纹 ledger（0600 私有，只含 basename 与指纹，无绝对路径）——
export VAULT_FINGERPRINT_LEDGER="$STATE_DIR/vault-fingerprint.json"
```

### 2.1 前置 Gate 与停止条件

执行前**先 source §2.0 preamble**（`set -Eeuo pipefail` + 全部 `: "${VAR:?}"`
定义检查通过），然后逐项确认；任一不满足则**停止**，不继续：

1. 蓝图 `main` HEAD == `017c2ce1fb2ef00f4fdc4e6f872a9877c49890da` 且与
   `origin/main` 一致。
2. 正式 SourceNotes 工作树 clean（`git -C "$PRODUCTION_VAULT_ROOT" status
   --short --branch` 无输出），且预克隆指纹与批准 HEAD 一致（F-15，§2.5 Gate B 第 0 步）。
3. `openclaw tasks list --status running` 与 `--status queued` 均为 0。
4. 本 Work Item 已由独立 Reviewer 给出 PASS（AC-05 门）。
5. 入口暂停基线已在 token 轮换**前**发布并验证（F-04，§2.5 Gate A），旧凭据失效已确认。
6. 私有状态目录（0700）、逐字节备份与 SHA-256 已就绪（见 2.3）。
7. 脚本已安装至 `"$STATE_DIR"` 且候选 validate / projection 通过（见 2.4）。
8. 真实委派 canary 已按 §2.5 Gate B/C 通过（Operator Controlled Action 前半段）。

停止条件（出现即冻结，人工处置，不自动继续）：任一基线漂移（蓝图 HEAD、正式
Vault clean 状态与预克隆指纹、活动配置 hash 与 evidence 记录不一致）、出现
running/queued capture、任一验证失败、需要在聊天/命令历史/Evidence 中传递真实
secret。**fail-fast 纪律（F-13）**：每个完整 shell 块首行 `set -Eeuo pipefail`；
§2.0 preamble 定义 `die()` / `run_or_die()` 与 `_safe_cleanup`（ERR trap）；
所有 backup/clone/transform/validate/publish/reload/status/probe/fingerprint/
agent/jq 命令必须经 `run_or_die` 或显式 `if ! 命令; then die; fi` 包裹，不得裸执行；
预期失败写成显式 if/else 断言；`_safe_cleanup` 只清理本次 RUN_ID 的 canary 克隆
（经 cleanup_canary.py provenance 验证）与可重建候选 temp，绝不触碰正式 Vault、
活动配置、未知目录或命名回滚点；cleanup 失败只报告并保留现场，不掩盖原 exit。

### 2.2 Operator 私下轮换/撤销凭据（F-06 修复：revoke/reissue；PRE_ROTATION_BACKUP 只审计）

- **顺序约束（F-04）**：任何 token 读取/轮换**之前**，必须先完成 §2.5 Gate A
  第 1–4 步——构造、dry-run、原子发布并验证 **INGRESS_PAUSED_BASELINE**
  （`channels.telegram.enabled=false`，capture 保持 disabled），确认 config/health、
  queue 0/0、Telegram ingress disabled。只有该验证 PASS，Operator 才可进入本节的
  main token `/revoke`。
- **main Telegram bot token 轮换（针对现有 main bot）**：Operator 在
  Telegram BotFather 中对**现有 main bot**执行 `/revoke`（或 `/token` 重新签发），
  使**旧 token 立即失效**；**禁止用 `/newbot` 创建新 bot 代替轮换**（那会留下
  旧 bot/旧 token 仍有效的第二入口）。新 botToken 由 Operator 直接写入
  `"$MAIN_BOT_TOKEN_FILE"`（0600 私有文件），绝不粘贴到聊天、命令参数、本包、
  仓库或 Evidence；随后 `touch "$TOKEN_ROTATED_MARKER" && chmod 0600 "$TOKEN_ROTATED_MARKER"`。
- **NotesVaulter 旧 bot token 撤销**：发生在 canary PASS 之后（§2.5 Gate D），
  Operator 在 BotFather 中对 notesvaulter 旧 bot 执行 `/revoke`，旧 token 立即
  失效；随后按 §1.1 从配置移除其 account/binding。是否删除 bot 本身不在本切换范围。
- 轮换完成后、cutover 前，Operator 可私下用 `getMe` 验证新 token 有效
  （一次性、不回显 token），并**确认旧凭据失效**（BotFather revoke 回执）。
- **回滚纪律（F-06）**：`PRE_ROTATION_BACKUP` 只作审计（记录轮换前原样）；任何
  revoke 之后**禁止**恢复 `PRE_ROTATION_BACKUP` 或任何含旧 token 的文件——那会把
  已失效 token 重新放回活动配置，Telegram 将不可用。回滚只允许使用
  `POST_MAIN_ROTATION_BASELINE`（main 轮换后、NotesVaulter revoke 前；保持
  ingress paused）与 `POST_ROTATION_SAFE_ROLLBACK`（NotesVaulter revoke 后），
  见 §2.6 恢复矩阵。

### 2.3 二进制安全原子 helper（F-03 修复）+ 状态目录 + checkpoint + ledger

`atomic.py` 为二进制安全（bytes、`tempfile.mkstemp` 唯一 temp、fchmod 0600、
完整 write loop、flush/fsync、`os.replace`、parent dir fsync、`finally` 定向
unlink 尚存在的 temp）；无固定 `.tmp` 名、无文本 decode/encode、无 shell
redirection 覆盖。已在 fixture 验证：非 UTF-8 bytes/尾随换行的逐字节
backup→publish→restore、write/fsync/replace 三类失败注入后 active 原字节保留且
temp 零残留（VAL-R2-02）。保存为 `"$STATE_DIR/atomic.py"`（0600）：

```python
#!/usr/bin/env python3
"""atomic.py — binary-safe atomic write / backup helper (Work Item 01 round 2).

Usage:
  python3 atomic.py write PATH DATA_FILE [EXPECTED_SHA]   # byte-copy DATA_FILE -> PATH atomically
  python3 atomic.py backup SRC DST                        # byte-exact backup SRC -> DST atomically
  python3 atomic.py checksum PATH                         # print sha256 only

Properties (F-03):
  - binary safe: reads/writes bytes, never text decode/encode
  - unique temp via tempfile.mkstemp in the TARGET directory (no fixed .tmp name)
  - fchmod 0600 before writing
  - full write loop + flush + fsync
  - os.replace (atomic rename) + parent dir fsync
  - finally: best-effort unlink of the unique temp if still present
  - optional EXPECTED_SHA assertion after replace
  - stdout: only fixed tokens + sha (never file content)

Test-only fault injection (set env var in fixture runs only; never in production):
  ATOMIC_FAULT_WRITE=1    raise OSError during the write loop
  ATOMIC_FAULT_FSYNC=1    raise OSError during fsync
  ATOMIC_FAULT_REPLACE=1  raise OSError during os.replace
"""
import hashlib
import os
import pathlib
import sys
import tempfile

MODE = 0o600


def _fault(name):
    if os.environ.get("ATOMIC_FAULT_" + name) == "1":
        raise OSError("injected fault: " + name)


def _fsync_dir(path):
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    dfd = os.open(path, flags)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write(path, data, mode=MODE, expected_sha=None):
    p = pathlib.Path(path)
    parent = str(p.parent)
    if not os.path.isdir(parent):
        raise OSError("parent directory does not exist: " + parent)
    fd, tmp = tempfile.mkstemp(prefix=".atomic-", suffix=".tmp", dir=parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as f:
            view = memoryview(data)
            written = 0
            while written < len(view):
                _fault("WRITE")
                n = f.write(view[written:])
                if n is None or n == 0:
                    raise OSError("short write")
                written += n
            f.flush()
            _fault("FSYNC")
            os.fsync(f.fileno())
        _fault("REPLACE")
        os.replace(tmp, p)
        _fsync_dir(parent)
        st = os.stat(p)
        if (st.st_mode & 0o777) != mode:
            raise AssertionError(
                "mode %s != %s" % (oct(st.st_mode & 0o777), oct(mode)))
        h = sha256_file(path)
        if expected_sha is not None and h != expected_sha:
            raise AssertionError("sha mismatch: %s != %s" % (h, expected_sha))
        return h
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass


def atomic_backup(src, dst):
    with open(src, "rb") as f:
        data = f.read()
    h = atomic_write(dst, data)
    if sha256_file(src) != sha256_file(dst):
        raise AssertionError("backup not byte-exact")
    return h


def main(argv):
    op = argv[1]
    if op == "write":
        # atomic.py write PATH DATA_FILE [EXPECTED_SHA]
        path, data_file = argv[2], argv[3]
        expected = argv[4] if len(argv) > 4 else None
        data = open(data_file, "rb").read()
        h = atomic_write(path, data, expected_sha=expected)
        print("ATOMIC_WRITTEN=true sha=%s" % h)
    elif op == "backup":
        # atomic.py backup SRC DST
        h = atomic_backup(argv[2], argv[3])
        print("ATOMIC_BACKUP_OK=true sha=%s" % h)
    elif op == "checksum":
        print("sha256=%s" % sha256_file(argv[2]))
    else:
        raise SystemExit("unknown op: %s" % op)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

```bash
# CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED
set -Eeuo pipefail
trap 'echo "SECTION_FAILED=2.3 失败，已停止；不清理任何非本次临时对象" >&2; _safe_cleanup' ERR
# 1) 私有状态目录（强制 0700 并验证）+ PRE_ROTATION_BACKUP 原子备份（0600）+ SHA-256
run_or_die "mkdir STATE_DIR" mkdir -p "$STATE_DIR"
run_or_die "chmod STATE_DIR" chmod 0700 "$STATE_DIR"
[ "$(stat -c '%a' "$STATE_DIR")" = "700" ] || die "STATE_DIR mode != 0700"
run_or_die "PRE_ROTATION_BACKUP 备份" python3 -B atomic.py backup "$ACTIVE_CONFIG" "$PRE_ROTATION_BACKUP"
run_or_die "PRE_ROTATION_BACKUP checksum" python3 -B atomic.py checksum "$PRE_ROTATION_BACKUP"
# 期望：SHA-256 == de9b9cb15bf022341d152badecd8cad78d82fb4f97ac758623fc61eaff934424

# 2) Vault checkpoint（只读记录，不覆盖任何内容）
run_or_die "prod HEAD 记录" git -C "$PRODUCTION_VAULT_ROOT" rev-parse HEAD          # 期望 ec1a90eb9d41df77cf74e44d51e703d0379882e7
run_or_die "prod status 记录" git -C "$PRODUCTION_VAULT_ROOT" status --short --branch # 期望 clean
run_or_die "prod cached diff 记录" git -C "$PRODUCTION_VAULT_ROOT" diff --cached --name-status
run_or_die "prod remote 记录" git -C "$PRODUCTION_VAULT_ROOT" remote -v              # URL 只报告是否一致，不记录值
run_or_die "test HEAD 记录" git -C "$TEST_VAULT_ROOT" rev-parse HEAD               # 只读记录既有状态，不清理/reset

# 3) queue 摘要（显式断言 0/0）
run_or_die "queue running 检查" bash -c 'openclaw tasks list --status running | grep -q "0 running"'
run_or_die "queue queued 检查" bash -c 'openclaw tasks list --status queued | grep -q "0 queued"'

# 4) 外部 operation ledger（目录 0700/文件 0600，不含正文与 secret；
#    affected_path 使用路径角色，避免绝对路径）
run_or_die "pre-cutover ledger" python3 scripts/sourcenotes_ops.py ledger \
  --dir "$STATE_DIR" --vault "$PRODUCTION_VAULT_ROOT" \
  add --type release \
  --data '{"blueprint_commit":"017c2ce1fb2ef00f4fdc4e6f872a9877c49890da","affected_path":"role=production-vault","disposition":"pre-cutover baseline"}'
```

> **F-15 指纹 ledger**：正式 Vault 的预克隆指纹（branch/HEAD/`HEAD^{tree}`/index
> SHA-256/`status --porcelain=v2 -z` SHA-256 与行数/`ls-files -s -z` SHA-256）由
> `vault_fingerprint.py capture` 在 §2.5 Gate A（token 轮换前、clone 前，F-19）写入
> `"$VAULT_FINGERPRINT_LEDGER"`（0600 no-follow secure create，只含 basename 与指纹值）。
> clone 后/canary 前后/cleanup 前/production publish 前/收尾各重算并逐项等值
> （`vault_fingerprint.py check`）；任一漂移立即停止并按 §2.6 恢复配置，**不清理、
> 不修改正式 Vault**。clone 的 provenance 一律以**clone 前**指纹为准（F-15：
> 不允许在 clone 后首次读取 source HEAD 作证明）。

`secure_file.py` 是全部私有文件写入共用的 no-follow 安全原语（F-11/F-13/F-14）：
`create`/`capture-bytes` 用 parent fd + `O_EXCL|O_NOFOLLOW` 独占创建 0600 文件，
持 fd `fstat` 验证 regular/0600/uid，全量写+fsync+parent fsync；`record` 把本次
RUN_ID 创建的可重建候选写入 0600 ownership manifest（lstat 对象 no-follow 校验后
追加）；`cleanup-owned` 逐项 no-follow 验证 dev/inode/parent/run_id 后才 unlink，
不匹配则保留并报告，rm/unlink 失败显式报告；`capture-bytes` 从 stdin 收字节写
0600 文件（用于 F-19 pre-rotation clean 断言）。保存为 `"$STATE_DIR/secure_file.py"`（0600）：

```python
#!/usr/bin/env python3
"""secure_file.py — no-follow secure file primitives (Work Item final repair round, F-11/F-13/F-14).

Library:
  create_exclusive(parent_fd, name, data) -> (dev, inode)
      O_EXCL|O_NOFOLLOW|O_CREAT 0600 via parent dir fd; write all bytes + fsync;
      fstat on the HELD fd verifies regular/0600/owner==uid; on failure unlinks
      ONLY the inode created by this call (verified no-follow), fsyncs parent.

CLI:
  create PARENT NAME DATA_FILE
      exclusive-create NAME (in PARENT) from DATA_FILE bytes; stdout CREATED=dev inode
  capture-bytes PARENT NAME
      read stdin bytes; exclusive-create NAME 0600; stdout CAPTURED=dev inode size
  record PARENT MANIFEST_NAME ROLE PATH RUN_ID
      lstat PATH (no-follow): must be regular, non-symlink, 0600; append line
      role、realpath、dev、inode、run_id（制表符分隔） to MANIFEST_NAME (created
      exclusively 0600 if absent; append via O_APPEND|O_NOFOLLOW fd; symlink
      manifest refused)
  cleanup-owned PARENT MANIFEST_NAME RUN_ID
      for each manifest line: verify lstat(PATH) dev/inode == recorded AND
      parent realpath == PARENT realpath AND run_id == RUN_ID; match -> unlink
      (report UNLINKED), mismatch -> refuse (report KEPT, preserve); finally
      unlink the manifest itself if it matches its own created inode; fsync parent.

stdout only fixed tokens; never the object content.
"""
import argparse
import json
import os
import pathlib
import stat
import sys


class SecureFileError(Exception):
    pass


def _refuse(msg):
    raise SecureFileError("SECURE_FILE_REFUSED=" + msg)


def _open_dir(path):
    try:
        return os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError as exc:
        _refuse("cannot open parent directory %s: %s" % (path, exc))


def _fsync_dir(fd):
    os.fsync(fd)


def create_exclusive(parent_fd, name, data, mode=0o600):
    """No-follow exclusive create via parent dir fd; fstat-verified on held fd."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(name, flags, mode, dir_fd=parent_fd)
    except OSError as exc:
        _refuse("cannot exclusively create %s (pre-existing or symlink?): %s" % (name, exc))
    try:
        view = memoryview(data)
        written = 0
        while written < len(view):
            n = os.write(fd, view[written:])
            if n is None or n == 0:
                raise OSError("short write")
            written += n
        os.fsync(fd)
        st = os.fstat(fd)          # fstat on held fd — no path race
        if not stat.S_ISREG(st.st_mode):
            _refuse("%s not a regular file" % name)
        if (st.st_mode & 0o777) != mode:
            _refuse("%s mode %s != %s" % (name, oct(st.st_mode & 0o777), oct(mode)))
        if st.st_uid != os.getuid():
            _refuse("%s owner != current uid" % name)
        return (st.st_dev, st.st_ino)
    except Exception:
        try:
            lst = os.lstat(name, dir_fd=parent_fd)
            if stat.S_ISREG(lst.st_mode):
                os.unlink(name, dir_fd=parent_fd)
        except OSError:
            pass
        raise


def _append_line(parent_fd, name, line):
    flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError as exc:
        _refuse("cannot append %s (missing or symlink?): %s" % (name, exc))
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def _lstat_nofollow(parent_fd, name):
    try:
        return os.lstat(name, dir_fd=parent_fd)
    except OSError as exc:
        _refuse("lstat %s failed: %s" % (name, exc))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("op", choices=["create", "capture-bytes", "record", "cleanup-owned"])
    ap.add_argument("parent")
    ap.add_argument("name")
    ap.add_argument("rest", nargs="*")
    args = ap.parse_args(argv)

    parent = args.parent
    if not parent.startswith("/"):
        _refuse("parent not absolute")
    pfd = _open_dir(parent)
    try:
        if args.op == "create":
            if len(args.rest) != 1:
                raise SystemExit("usage: secure_file.py create PARENT NAME DATA_FILE")
            with open(args.rest[0], "rb") as f:
                data = f.read()
            dev, ino = create_exclusive(pfd, args.name, data)
            _fsync_dir(pfd)
            print("CREATED=%s %s" % (dev, ino))
        elif args.op == "capture-bytes":
            if len(args.rest) != 0:
                raise SystemExit("usage: secure_file.py capture-bytes PARENT NAME")
            data = sys.stdin.buffer.read()
            dev, ino = create_exclusive(pfd, args.name, data)
            _fsync_dir(pfd)
            print("CAPTURED=%s %s %d" % (dev, ino, len(data)))
        elif args.op == "record":
            if len(args.rest) != 3:
                raise SystemExit("usage: secure_file.py record PARENT MANIFEST_NAME ROLE PATH RUN_ID")
            role, obj_path, run_id = args.rest
            if not obj_path.startswith("/"):
                _refuse("object path not absolute")
            lst = os.lstat(obj_path)          # no-follow
            if not stat.S_ISREG(lst.st_mode) or os.path.islink(obj_path):
                _refuse("object not a regular non-symlink file: %s" % obj_path)
            if (lst.st_mode & 0o777) != 0o600:
                _refuse("object mode %s != 0600: %s" % (oct(lst.st_mode & 0o777), obj_path))
            # manifest: exclusive-create if absent; refuse existing symlink
            try:
                create_exclusive(pfd, args.name, b"", mode=0o600)
                _fsync_dir(pfd)
            except SecureFileError:
                lstm = _lstat_nofollow(pfd, args.name)
                if not stat.S_ISREG(lstm.st_mode):
                    _refuse("manifest not a regular file: %s" % args.name)
            line = "%s\t%s\t%d\t%d\t%s\n" % (role, obj_path, lst.st_dev, lst.st_ino, run_id)
            _append_line(pfd, args.name, line)
            print("RECORDED=%s %s" % (role, obj_path))
        elif args.op == "cleanup-owned":
            if len(args.rest) != 1:
                raise SystemExit("usage: secure_file.py cleanup-owned PARENT MANIFEST_NAME RUN_ID")
            run_id = args.rest[0]
            try:
                lstm = _lstat_nofollow(pfd, args.name)
            except SecureFileError:
                print("CLEANUP_MANIFEST_ABSENT=%s" % args.name)
                return 0
            if not stat.S_ISREG(lstm.st_mode):
                print("CLEANUP_MANIFEST_INVALID=%s (not regular; preserved)" % args.name)
                return 0
            parent_real = os.path.realpath(parent)
            try:
                with open(os.path.join(parent, args.name), "rb") as f:
                    lines = f.read().decode("utf-8").splitlines()
            except OSError as exc:
                _refuse("manifest unreadable: %s" % exc)
            for line in lines:
                parts = line.split("\t")
                if len(parts) != 5:
                    print("CLEANUP_LINE_INVALID=%r (preserved)" % line)
                    continue
                role, obj_path, dev_s, ino_s, line_run = parts
                try:
                    dev, ino = int(dev_s), int(ino_s)
                except ValueError:
                    print("CLEANUP_LINE_INVALID=%r (preserved)" % line)
                    continue
                if line_run != run_id:
                    print("CLEANUP_RUN_ID_MISMATCH=%s (preserved)" % obj_path)
                    continue
                if os.path.realpath(os.path.dirname(obj_path)) != parent_real:
                    print("CLEANUP_PARENT_MISMATCH=%s (preserved)" % obj_path)
                    continue
                try:
                    lst = os.lstat(obj_path)
                except OSError:
                    print("CLEANUP_GONE=%s (already absent)" % obj_path)
                    continue
                if (lst.st_dev, lst.st_ino) != (dev, ino) or os.path.islink(obj_path):
                    print("CLEANUP_INODE_MISMATCH=%s (preserved)" % obj_path)
                    continue
                try:
                    os.unlink(obj_path)
                    print("UNLINKED=%s" % obj_path)
                except OSError as exc:
                    print("CLEANUP_UNLINK_FAILED=%s: %s (preserved)" % (obj_path, exc))
            # remove the manifest itself (verified its own inode)
            try:
                os.unlink(args.name, dir_fd=pfd)
                _fsync_dir(pfd)
            except OSError as exc:
                print("CLEANUP_MANIFEST_UNLINK_FAILED=%s: %s" % (args.name, exc))
            return 0
    finally:
        os.close(pfd)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SecureFileError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print("SECURE_FILE_ERROR=%s" % exc, file=sys.stderr)
        sys.exit(3)
```

> **F-13 ownership manifest**：Gate B/C 创建 `CANARY_CANDIDATE`/`PRODUCTION_CANDIDATE`
> 后立即 `record_owned 角色 路径` 写入 `ownership-${RUN_ID}.manifest`（0600）；
> `_safe_cleanup` 只删除 manifest 内 dev/inode/parent/run_id 全匹配的对象；不匹配
> 保留并报告；`rm/unlink` 失败显式报告。命名回滚点与诊断文件（canary output、
> PRE_ROTATION_BACKUP、INGRESS_PAUSED_BASELINE、POST_MAIN_ROTATION_BASELINE、
> POST_ROTATION_SAFE_ROLLBACK）一律不记录、不清理。

### 2.4 脚本安装与通用候选校验（Gate A–E 复用）

```bash
# CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED
set -Eeuo pipefail
trap 'echo "INSTALL_FAILED=脚本安装失败，已停止" >&2; _safe_cleanup' ERR
# 把 §1.1/§1.2/§2.3/§2.5/§2.6 内嵌脚本保存到 STATE_DIR（atomic.py transform.py
# token_inject.py projection.py pause_ingress.py secure_file.py vault_fingerprint.py
# canary_provenance.py cleanup_canary.py canary_assert.py secure_capture.py）并 chmod
# 0600；随后全部过 `python3 -m py_compile` 与 `bash -n`（F-13）。
# 每个候选构造后通用校验（具体命令见各 Gate）：
#   1) env OPENCLAW_CONFIG_PATH="$CANDIDATE" openclaw config validate   → 期望 Config valid
#   2) python3 -B projection.py "$CANDIDATE" --rotated-marker "$TOKEN_ROTATED_MARKER"
#      → 断言批准字段精确匹配（§1.2 期望）
#   3) 候选与 before 的 semantic diff 只有 C1–C8 字段变化，其余无 diff。
# 候选 validate+projection 通过前，不得进入下一 Gate。
```

### 2.5 精确单一 cutover DAG（Gates A–F；F-04/F-12 修复）

> 本节为 **Operator Controlled Action**；本 Work Item 只提供 runbook，**NOT_RUN**。
> 设计（spec AC-10 / plan）：不复制模型密钥；不向正式 SourceNotes 写测试数据；
> 用正式库的只读完整克隆做高保真 canary；失败只恢复配置并删除克隆。
> **唯一的 production publish/reload 只在 Gate E 出现一次**（F-12）。
> **任何 token 读取/轮换之前，Gate A 必须先把 INGRESS_PAUSED_BASELINE 发布并
> 验证通过（F-04）**；canary 只由 Operator 本地
> `openclaw agent --agent main --session-key "$CANARY_SESSION_KEY" --message "$CANARY_PROMPT" --json`
> 触发，Telegram 不参与；只有 Gate E 的 production 候选才恢复 default main
> Telegram ingress。

`pause_ingress.py` 构造 INGRESS_PAUSED_BASELINE：唯一语义变化是
`channels.telegram.enabled=false`，capture 保持 disabled、无新任务；深复制保留
全部其它字段。保存为 `"$STATE_DIR/pause_ingress.py"`（0600）：

```python
#!/usr/bin/env python3
"""pause_ingress.py — build the INGRESS_PAUSED_BASELINE (Work Item safety closure, F-04).

Usage:
  python3 pause_ingress.py SRC DST

Purpose: the ONLY semantic change is channels.telegram.enabled=false (pause the
Telegram ingress) while capture stays disabled and no new tasks are accepted.
Everything else is a byte-identical deep copy. Runs BEFORE any bot token is read
or rotated.

Fail-closed assertions (any violation -> non-zero exit, DST never written):
  - SRC is valid UTF-8 JSON
  - channels.telegram exists and is a dict; channels.telegram.enabled is a bool
  - skills.entries.vault-capture exists, is a dict, and enabled==False (capture stays disabled)

stdout: only fixed tokens (PAUSE_WRITTEN=true sha=哈希值) — never the config body.
"""
import argparse
import copy
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from atomic import atomic_write


class PauseError(AssertionError):
    pass


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    args = ap.parse_args(argv)

    with open(args.src, "rb") as f:
        try:
            cfg = json.loads(f.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise PauseError("source config not valid UTF-8 JSON: %s" % exc)

    tg = (cfg.get("channels") or {}).get("telegram")
    if not isinstance(tg, dict):
        raise PauseError("channels.telegram missing or not a dict")
    if not isinstance(tg.get("enabled"), bool):
        raise PauseError("channels.telegram.enabled missing or not a bool")

    entries = (cfg.get("skills") or {}).get("entries") or {}
    cap = entries.get("vault-capture")
    if not isinstance(cap, dict):
        raise PauseError("skills.entries.vault-capture missing or not a dict")
    if cap.get("enabled") is not False:
        raise PauseError("skills.entries.vault-capture.enabled must be false (capture stays disabled)")

    out = copy.deepcopy(cfg)
    out["channels"]["telegram"]["enabled"] = False

    body = json.dumps(out, indent=2, ensure_ascii=False).encode("utf-8")
    h = atomic_write(args.dst, body, expected_sha=None)
    print("PAUSE_WRITTEN=true sha=%s" % h)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except PauseError as exc:
        print("PAUSE_FAILED=%s" % exc, file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001
        print("PAUSE_ERROR=%s" % exc, file=sys.stderr)
        sys.exit(3)
```

#### Gate A — maintenance 基线（先暂停入口）→ INGRESS_PAUSED_BASELINE → main token 轮换 → POST_MAIN_ROTATION_BASELINE

```bash
# CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED
set -Eeuo pipefail
trap 'echo "GATE_A_FAILED=已停止；main revoke 前失败用 PRE_ROTATION_BACKUP 审计，之后失败恢复 POST_MAIN_ROTATION_BASELINE" >&2; _safe_cleanup' ERR
# 0) 正式 Vault clean 基线锁定（F-19）：porcelain v2 字节严格长度 0 + 批准 full HEAD
#    + 预克隆指纹 capture（token 轮换/clone 之前）
if ! PRE_ROTATION_CLEAN="$(git -C "$PRODUCTION_VAULT_ROOT" status --porcelain=v2 -z)"; then
  die "正式 Vault git status 失败"
fi
[ "${#PRE_ROTATION_CLEAN}" -eq 0 ] || die "正式 Vault 非 clean（porcelain v2 长度 ${#PRE_ROTATION_CLEAN}）"
if [ "$(git -C "$PRODUCTION_VAULT_ROOT" rev-parse HEAD)" != "ec1a90eb9d41df77cf74e44d51e703d0379882e7" ]; then
  die "正式 Vault HEAD 与批准基线不符"
fi
run_or_die "预克隆指纹 capture" python3 -B vault_fingerprint.py capture "$PRODUCTION_VAULT_ROOT" "$VAULT_FINGERPRINT_LEDGER" \
  ec1a90eb9d41df77cf74e44d51e703d0379882e7
# 期望 stdout：FINGERPRINT_CAPTURED=true basename=SourceNotes head=ec1a90eb9d41df77cf74e44d51e703d0379882e7

# 1) 只读前置确认（queue 0/0）
run_or_die "queue running 检查" bash -c 'openclaw tasks list --status running | grep -q "0 running"'
run_or_die "queue queued 检查" bash -c 'openclaw tasks list --status queued | grep -q "0 queued"'

# 2) PRE_ROTATION_BACKUP（只审计，见 §2.2 回滚纪律）
run_or_die "PRE_ROTATION_BACKUP" python3 -B atomic.py backup "$ACTIVE_CONFIG" "$PRE_ROTATION_BACKUP"
run_or_die "PRE_ROTATION_BACKUP checksum" python3 -B atomic.py checksum "$PRE_ROTATION_BACKUP"   # 记录 sha（审计）

# 3) 构造并 dry-run INGRESS_PAUSED_BASELINE（F-04：先暂停入口，再碰任何 token）
run_or_die "pause_ingress" python3 -B pause_ingress.py "$ACTIVE_CONFIG" "$INGRESS_PAUSED_BASELINE"
run_or_die "ingress-paused validate" env OPENCLAW_CONFIG_PATH="$INGRESS_PAUSED_BASELINE" openclaw config validate   # 期望 Config valid
run_or_die "ingress-paused projection" python3 -B projection.py "$INGRESS_PAUSED_BASELINE"
# 期望：telegram_enabled=false；vault-capture enabled=false（capture 保持 disabled）；
#       vault_root basename=SourceNotes-test；bindings 仍含 main 与 notesvaulter（轮换前原状）

# 4) 原子发布 INGRESS_PAUSED_BASELINE + reload + health（按 OpenClaw 当前版本提示执行必要 reload/restart）
run_or_die "INGRESS_PAUSED_BASELINE 发布" python3 -B atomic.py write "$ACTIVE_CONFIG" "$INGRESS_PAUSED_BASELINE"
run_or_die "gateway restart" openclaw gateway restart
run_or_die "gateway validate/status/health" bash -c 'openclaw config validate && openclaw gateway status && openclaw gateway health'
# 5) 验证暂停生效：queue 0/0、Telegram ingress disabled
#    F-04：投影检查用 PAUSE_PATTERN（preamble 定义，引号保留，false 不作文件）
run_or_die "暂停后 running 检查" bash -c 'openclaw tasks list --status running | grep -q "0 running"'
run_or_die "暂停后 queued 检查" bash -c 'openclaw tasks list --status queued | grep -q "0 queued"'
run_or_die "活动配置 ingress 已暂停" bash -c 'python3 -B projection.py "$1" | grep -Eq "$2"' _ "$ACTIVE_CONFIG" "$PAUSE_PATTERN"

# 6) 只有以上验证 PASS 才允许 Operator 对现有 main bot 执行 /revoke 并重新签发（禁止 /newbot）；
#    新 token 写入 "$MAIN_BOT_TOKEN_FILE"（0600）；touch "$TOKEN_ROTATED_MARKER"（0600）。

# 7) POST_MAIN_ROTATION_BASELINE：基于 INGRESS_PAUSED_BASELINE（保持 ingress paused），
#    仅 main token 更新；成为 main 轮换后的回滚目标
run_or_die "POST_MAIN_ROTATION_BASELINE 备份" python3 -B atomic.py backup "$INGRESS_PAUSED_BASELINE" "$POST_MAIN_ROTATION_BASELINE"
run_or_die "POST_MAIN_ROTATION_BASELINE token 注入" python3 -B token_inject.py "$POST_MAIN_ROTATION_BASELINE" "$MAIN_BOT_TOKEN_FILE"
run_or_die "post-rotation validate" env OPENCLAW_CONFIG_PATH="$POST_MAIN_ROTATION_BASELINE" openclaw config validate   # 期望 Config valid
run_or_die "post-rotation projection" python3 -B projection.py "$POST_MAIN_ROTATION_BASELINE" --rotated-marker "$TOKEN_ROTATED_MARKER"
# 期望：main_token_rotated=true；telegram_enabled=false（保持暂停）；capture disabled；
#       vault_root basename=SourceNotes-test；bindings 含 notesvaulter（轮换前原状）

# 8) 原子发布 POST_MAIN_ROTATION_BASELINE（使新 main token 生效；ingress 仍暂停）+ reload + health
run_or_die "POST_MAIN_ROTATION_BASELINE 发布" python3 -B atomic.py write "$ACTIVE_CONFIG" "$POST_MAIN_ROTATION_BASELINE"
run_or_die "gateway restart" openclaw gateway restart
run_or_die "gateway validate/status/health" bash -c 'openclaw config validate && openclaw gateway status && openclaw gateway health'
```

- 失败边 **GA**：main revoke **前**失败 → 停止（`PRE_ROTATION_BACKUP` 仍有效）。
  main revoke 后 / 基线发布失败 → 恢复 `POST_MAIN_ROTATION_BASELINE`（§2.6），
  **不再触碰 `PRE_ROTATION_BACKUP`**。

#### Gate B — 预克隆指纹锁定 → 创建 canary 克隆（provenance-safe）→ CANARY_CANDIDATE 单一发布

`vault_fingerprint.py` 在 clone 前只读锁定正式 Vault（F-15）：记录 branch、完整
HEAD、`HEAD^{tree}`、index 文件 SHA-256、`git status --porcelain=v2 -z` 的
SHA-256 与条目数、`git ls-files -s -z` SHA-256；要求工作树 clean 且 HEAD 与批准
基线一致。ledger 为 0600 私有文件，只含 basename 与指纹值（无绝对路径）。保存为
`"$STATE_DIR/vault_fingerprint.py"`（0600）：

```python
#!/usr/bin/env python3
"""vault_fingerprint.py — pre-clone fingerprint lock for the official vault (Work Item safety closure, F-15).

Usage:
  python3 vault_fingerprint.py capture VAULT_ROOT LEDGER [EXPECTED_HEAD]
  python3 vault_fingerprint.py check   VAULT_ROOT LEDGER [CLONE_ROOT]
  python3 vault_fingerprint.py head    LEDGER

capture: read-only records branch / full HEAD / HEAD^{tree} / index SHA-256 /
  git status --porcelain=v2 -z SHA-256 + entry count / git ls-files -s -z SHA-256.
  Requires a clean worktree and (if given) HEAD == EXPECTED_HEAD. Writes the ledger
  as a 0600 private file containing ONLY the basename (never the absolute path).
check: recomputes all fields and compares them item-by-item with the ledger; any
  drift -> non-zero exit with FINGERPRINT_DRIFT=字段名; never modifies the vault.
  If CLONE_ROOT is given, also verifies clone HEAD and HEAD^{tree} equal the
  PRE-CLONE recorded values (clone provenance is NOT taken from a post-clone read
  of the source HEAD).
head: prints the recorded HEAD (for canary_provenance / clone comparison).

stdout: only fixed tokens / the head value — never the vault path.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys


class FingerprintError(Exception):
    pass


def _run(vault, args):
    return subprocess.run(
        ["git", "-C", vault] + args,
        capture_output=True, text=True, check=True,
    )


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _capture(vault):
    branch = _run(vault, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    head = _run(vault, ["rev-parse", "HEAD"]).stdout.strip()
    tree = _run(vault, ["rev-parse", "HEAD^{tree}"]).stdout.strip()
    status_raw = _run(vault, ["status", "--porcelain=v2", "-z"]).stdout.encode("utf-8")
    ls_raw = _run(vault, ["ls-files", "-s", "-z"]).stdout.encode("utf-8")
    index_path = os.path.join(vault, ".git", "index")
    return {
        "basename": os.path.basename(vault.rstrip("/")),
        "branch": branch,
        "head": head,
        "tree": tree,
        "index_sha256": _sha256_file(index_path),
        "status_sha256": _sha256_bytes(status_raw),
        "status_lines": 0 if not status_raw else status_raw.count(b"\0"),
        "ls_files_sha256": _sha256_bytes(ls_raw),
    }


def _write_ledger(ledger_path, data):
    """F-11: no-follow exclusive create via the parent dir fd (shared primitive)."""
    import pathlib as _pl
    parent = _pl.Path(ledger_path).resolve().parent
    pfd = os.open(str(parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        from secure_file import SecureFileError, create_exclusive
        try:
            create_exclusive(pfd, _pl.Path(ledger_path).name,
                             json.dumps(data, sort_keys=True).encode("utf-8"))
            os.fsync(pfd)
        except SecureFileError as exc:
            raise FingerprintError(str(exc))
    finally:
        os.close(pfd)


def _load_ledger(ledger_path):
    with open(ledger_path, "rb") as f:
        return json.loads(f.read().decode("utf-8"))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("op", choices=["capture", "check", "head"])
    ap.add_argument("vault")
    ap.add_argument("ledger")
    ap.add_argument("extra", nargs="?", default=None)
    args = ap.parse_args(argv)

    if args.op == "head":
        ledger = _load_ledger(args.ledger)
        print(ledger["head"])
        return 0

    vault = args.vault
    if not vault.startswith("/"):
        raise FingerprintError("vault path not absolute")
    if not os.path.isdir(vault):
        raise FingerprintError("vault path is not a directory")

    if args.op == "capture":
        fp = _capture(vault)
        if fp["status_lines"] != 0:
            raise FingerprintError("worktree not clean (%d status entries); refuse to lock"
                                   % fp["status_lines"])
        if args.extra:
            expected = args.extra
            if fp["head"] != expected:
                raise FingerprintError("HEAD %s != approved %s" % (fp["head"], expected))
        _write_ledger(args.ledger, fp)
        print("FINGERPRINT_CAPTURED=true basename=%s head=%s" % (fp["basename"], fp["head"]))
        return 0

    # check
    ledger = _load_ledger(args.ledger)
    fp = _capture(vault)
    for key in ("branch", "head", "tree", "index_sha256", "status_sha256",
                "status_lines", "ls_files_sha256"):
        if ledger.get(key) != fp[key]:
            raise FingerprintError("FINGERPRINT_DRIFT=%s" % key)
    if args.extra:
        clone = args.extra
        clone_head = _run(clone, ["rev-parse", "HEAD"]).stdout.strip()
        clone_tree = _run(clone, ["rev-parse", "HEAD^{tree}"]).stdout.strip()
        if clone_head != ledger["head"]:
            raise FingerprintError("FINGERPRINT_DRIFT=clone_head")
        if clone_tree != ledger["tree"]:
            raise FingerprintError("FINGERPRINT_DRIFT=clone_tree")
    print("FINGERPRINT_OK=true basename=%s" % ledger.get("basename"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except FingerprintError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001
        print("FINGERPRINT_ERROR=%s" % exc, file=sys.stderr)
        sys.exit(3)
```

`canary_provenance.py` 在克隆后写私有 marker 与 ledger（均 0600；marker 在克隆内但
不入 Git；内容 schema 仅 run_id、source fingerprints（source_head）、clone
realpath/dev/inode，**marker 与 ledger 两边完全匹配**），并 fail-closed 校验
STATE_DIR 0700、父目录为 `STATE_DIR/canary` 且 **lstat 非 symlink**（F-11）、
目标非 symlink、basename 形如 `SourceNotes-production-canary-${RUN_ID}-test`、
写入后 marker/ledger 均为常规文件（no-follow）0600 且 owner=当前 uid。
保存为 `"$STATE_DIR/canary_provenance.py"`（0600）：

```python
#!/usr/bin/env python3
"""canary_provenance.py — create provenance marker + ledger for a fresh canary clone (Work Item safety closure, repair round 1, F-11).

Usage:
  python3 canary_provenance.py init STATE_DIR CANARY_VAULT_ROOT RUN_ID SOURCE_HEAD

Fail-closed pre-checks:
  - CANARY_VAULT_ROOT absolute, not a symlink, realpath == itself
  - parent is NOT a symlink (lstat) and realpath(parent) == realpath(STATE_DIR/canary),
    parent mode 0700
  - target exists (clone created before init), is a directory, not a symlink
  - STATE_DIR mode 0700

Creates (after the caller clones), with NO-FOLLOW exclusive create:
  - $CANARY_VAULT_ROOT/.sourcenotes-canary.marker (0600, not tracked by git)
  - STATE_DIR/canary-ledger.json (0600)
  both containing IDENTICAL schema: run_id / source_head / realpath / dev / inode.
  Any pre-existing object at the target name (regular file, symlink, or dangling
  symlink) is REFUSED before any chmod/write; creation uses O_EXCL|O_NOFOLLOW via
  the parent directory fd, writes all bytes + fsync, then fstat-verifies regular /
  0600 / owner == current uid before recording provenance. On failure only the
  inode created by that call is removed.
stdout: CANARY_PROVENANCE_OK=true run_id=实际值 — never any secret.
"""
import argparse
import json
import os
import pathlib
import stat
import sys

MARKER_NAME = ".sourcenotes-canary.marker"
LEDGER_NAME = "canary-ledger.json"
CANARY_PARENT = "canary"


class ProvenanceError(Exception):
    pass


def _refuse(msg):
    raise ProvenanceError("PROVENANCE_REFUSED=" + msg)


def _mode(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


def _exclusive_write(parent_fd, name, data):
    """F-11: no-follow exclusive create via parent dir fd; fstat on the HELD fd.

    O_EXCL|O_NOFOLLOW|O_CREAT refuses ANY pre-existing object (regular, symlink,
    dangling symlink); os.write loop writes all bytes + fsync; fstat on the held
    fd (no path race) verifies regular, 0600, owner == current uid; on failure
    unlinks ONLY the inode created by this call.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(name, flags, 0o600, dir_fd=parent_fd)
    except OSError as exc:
        _refuse("cannot exclusively create %s (pre-existing or symlink): %s" % (name, exc))
    try:
        view = memoryview(data)
        written = 0
        while written < len(view):
            n = os.write(fd, view[written:])
            if n is None or n == 0:
                raise OSError("short write")
            written += n
        os.fsync(fd)
        st = os.fstat(fd)          # fstat on held fd — no path race
        if not stat.S_ISREG(st.st_mode):
            _refuse("%s not a regular file (no-follow)" % name)
        if (st.st_mode & 0o777) != 0o600:
            _refuse("%s mode %s != 0600" % (name, oct(st.st_mode & 0o777)))
        if st.st_uid != os.getuid():
            _refuse("%s owner != current uid" % name)
        return (st.st_dev, st.st_ino)
    except Exception:
        try:
            lst = os.lstat(name, dir_fd=parent_fd)
            if stat.S_ISREG(lst.st_mode):
                os.unlink(name, dir_fd=parent_fd)
        except OSError:
            pass
        raise


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("op", choices=["init"])
    ap.add_argument("state_dir")
    ap.add_argument("canary_path")
    ap.add_argument("run_id")
    ap.add_argument("source_head")
    args = ap.parse_args(argv)

    state_real = os.path.realpath(args.state_dir)
    if _mode(state_real) != 0o700:
        _refuse("STATE_DIR mode %s != 0700" % oct(_mode(state_real)))

    cp = args.canary_path
    if not cp.startswith("/"):
        _refuse("canary path not absolute")
    if os.path.islink(cp):
        _refuse("canary path is a symlink")
    if os.path.realpath(cp) != cp:
        _refuse("canary path realpath mismatch")

    parent = os.path.dirname(cp)
    if os.path.islink(parent):
        _refuse("canary parent is a symlink")
    parent_real = os.path.realpath(parent)
    expected_parent = os.path.join(state_real, CANARY_PARENT)
    if parent_real != os.path.realpath(expected_parent):
        _refuse("canary parent %s != STATE_DIR/canary %s" % (parent_real, expected_parent))
    if _mode(expected_parent) != 0o700:
        _refuse("canary parent mode %s != 0700" % oct(_mode(expected_parent)))
    base = os.path.basename(cp)
    if not base.endswith("-test"):
        _refuse("basename must end with -test")
    if not base.startswith("SourceNotes-production-canary-"):
        _refuse("basename must start with SourceNotes-production-canary-")
    if not os.path.isdir(cp) or os.path.islink(cp):
        _refuse("canary clone does not exist or is a symlink")

    st = os.stat(cp)
    payload = {
        "run_id": args.run_id,
        "source_head": args.source_head,
        "realpath": cp,
        "dev": st.st_dev,
        "inode": st.st_ino,
    }
    body = json.dumps(payload).encode("utf-8")
    oflags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    canary_fd = os.open(cp, oflags)
    state_fd = os.open(state_real, oflags)
    created = []   # 事务记录 (dir_fd, name, dev, inode)；失败时 reverse-order 回滚
    try:
        dev, ino = _exclusive_write(canary_fd, MARKER_NAME, body)
        created.append((canary_fd, MARKER_NAME, dev, ino))
        dev, ino = _exclusive_write(state_fd, LEDGER_NAME, body)
        created.append((state_fd, LEDGER_NAME, dev, ino))
    except Exception:
        for dfd, nm, dev, ino in reversed(created):
            try:
                lst = os.lstat(nm, dir_fd=dfd)   # no-follow 复核仍属本事务
                if (lst.st_dev, lst.st_ino) == (dev, ino) and stat.S_ISREG(lst.st_mode):
                    os.unlink(nm, dir_fd=dfd)
                    os.fsync(dfd)
            except OSError:
                pass
        raise
    finally:
        os.close(canary_fd)
        os.close(state_fd)
    print("CANARY_PROVENANCE_OK=true run_id=%s" % args.run_id)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except ProvenanceError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001
        print("PROVENANCE_ERROR=%s" % exc, file=sys.stderr)
        sys.exit(3)
```

```bash
# CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED
set -Eeuo pipefail
trap 'echo "GATE_B_FAILED=已停止；恢复 POST_MAIN_ROTATION_BASELINE（§2.6）" >&2; _safe_cleanup' ERR
# 0) 正式 Vault 预克隆指纹复核（F-15/F-19：Gate A 已 capture，此处 check 逐项等值）
run_or_die "预克隆指纹 check" python3 -B vault_fingerprint.py check "$PRODUCTION_VAULT_ROOT" "$VAULT_FINGERPRINT_LEDGER"
# 期望 stdout：FINGERPRINT_OK=true basename=SourceNotes

# 1) canary 父目录（0700、克隆前必须为空；lstat 非 symlink）+ 目标不存在
#    F-11：任何 chmod/mkdir 之前先 lstat 拒绝 symlink 与已存在文件对象；
#          目标用 -e 与 -L 双重拒绝（dangling symlink 的 -e 为假，必须 -L）
if [ -e "$STATE_DIR/canary" ] && [ -L "$STATE_DIR/canary" ]; then
  die "canary 父目录已存在且是 symlink"
fi
if [ -e "$STATE_DIR/canary" ] && [ ! -d "$STATE_DIR/canary" ]; then
  die "canary 父目录已存在但不是目录"
fi
run_or_die "mkdir canary 父目录" mkdir -p "$STATE_DIR/canary"
run_or_die "chmod canary 父目录" chmod 0700 "$STATE_DIR/canary"
[ "$(stat -c '%a' "$STATE_DIR/canary")" = "700" ] || die "canary 父目录 mode != 0700"
if [ -L "$STATE_DIR/canary" ]; then die "canary 父目录是 symlink"; fi
[ -z "$(ls -A "$STATE_DIR/canary")" ] || die "canary 父目录非空"
if [[ -e "$CANARY_VAULT_ROOT" || -L "$CANARY_VAULT_ROOT" ]]; then
  die "canary 目标已存在（含 dangling symlink）"
fi

# 2) 从正式 SourceNotes 创建本地完整克隆（不修改正式仓 .git/config 或 refs）
run_or_die "canary clone" git clone --no-hardlinks "$PRODUCTION_VAULT_ROOT" "$CANARY_VAULT_ROOT"

# 3) 克隆 provenance：用预克隆指纹验证（F-15：不允许 clone 后首次读取 source HEAD）
run_or_die "clone provenance check" python3 -B vault_fingerprint.py check "$PRODUCTION_VAULT_ROOT" "$VAULT_FINGERPRINT_LEDGER" "$CANARY_VAULT_ROOT"
# 期望 stdout：FINGERPRINT_OK=true basename=SourceNotes
# （source 与预克隆指纹逐项一致；clone HEAD/tree == 预克隆指纹记录值）
run_or_die "clone remote remove origin" git -C "$CANARY_VAULT_ROOT" remote remove origin       # push 禁用
if git -C "$CANARY_VAULT_ROOT" push >/dev/null 2>&1; then
  die "push 意外成功（应无 remote）"
else
  echo "GATE_B_PUSH_EXPECTED=push 按预期失败（无 remote，F-13 显式断言）"
fi
run_or_die "clone 后 source 指纹复核" python3 -B vault_fingerprint.py check "$PRODUCTION_VAULT_ROOT" "$VAULT_FINGERPRINT_LEDGER"
# 期望 stdout：FINGERPRINT_OK=true（源未被 clone 改动）

# 4) provenance marker + ledger（0600 私有；run_id/source fingerprints/realpath/dev/inode；
#    两边完全匹配，F-11）；source_head 取自预克隆指纹 ledger（F-15）
SOURCE_HEAD="$(run_or_die "指纹 ledger head 读取" python3 -B vault_fingerprint.py head "$VAULT_FINGERPRINT_LEDGER")"
[ -n "$SOURCE_HEAD" ] || die "SOURCE_HEAD 为空"
run_or_die "canary provenance init" python3 -B canary_provenance.py init "$STATE_DIR" "$CANARY_VAULT_ROOT" "$RUN_ID" "$SOURCE_HEAD"
# 期望 stdout：CANARY_PROVENANCE_OK=true run_id=实际值

# 5) 正式 Vault 复核（clone/init 前后指纹逐项等值，F-15）
run_or_die "init 后 source 指纹复核" python3 -B vault_fingerprint.py check "$PRODUCTION_VAULT_ROOT" "$VAULT_FINGERPRINT_LEDGER"

# 6) CANARY_CANDIDATE：基于 POST_MAIN_ROTATION_BASELINE（new main token、ingress 仍暂停）
#    + 单入口 + 三技能 + canary vault（F-04：channels.telegram.enabled=false 保持暂停）
run_or_die "canary transform" python3 -B transform.py "$POST_MAIN_ROTATION_BASELINE" "$CANARY_CANDIDATE" "$CANARY_VAULT_ROOT" --role canary
run_or_die "canary token 注入" python3 -B token_inject.py "$CANARY_CANDIDATE" "$MAIN_BOT_TOKEN_FILE"
run_or_die "ownership 记录 canary-candidate" record_owned "canary-candidate" "$CANARY_CANDIDATE"
run_or_die "canary candidate validate" env OPENCLAW_CONFIG_PATH="$CANARY_CANDIDATE" openclaw config validate            # 期望 Config valid
run_or_die "canary skills check" env OPENCLAW_CONFIG_PATH="$CANARY_CANDIDATE" openclaw skills check --agent notesvaulter
# 期望：vault-capture/vault-query/vault-maintenance 三技能 Eligible 且 Visible to model
run_or_die "canary skills info" env OPENCLAW_CONFIG_PATH="$CANARY_CANDIDATE" openclaw skills info vault-capture --agent notesvaulter  # ✓ Ready
run_or_die "canary projection" python3 -B projection.py "$CANARY_CANDIDATE" --rotated-marker "$TOKEN_ROTATED_MARKER"
# 期望：telegram_enabled=false（入口保持暂停）；vault_roots 三值 basename=SourceNotes-production-canary-${RUN_ID}-test；
#       bindings 仅 main→telegram:default；telegram_account_keys=["default"]；
#       notesvaulter_token_present=false；main_token_rotated=true

# 7) 唯一 canary publish/reload（canary 窗口内活动 Gateway 指向克隆；Telegram 不参与）
run_or_die "canary candidate 发布" python3 -B atomic.py write "$ACTIVE_CONFIG" "$CANARY_CANDIDATE"
run_or_die "gateway restart" openclaw gateway restart
run_or_die "gateway validate/status/health" bash -c 'openclaw config validate && openclaw gateway status && openclaw gateway health'
```

#### Gate C — 本地 main 会话委派 canary（Telegram 不参与；F-14：机器断言 bounded JSON）

`canary_assert.py` 对 `openclaw agent --json` 外层 envelope 与 inner bounded JSON 做
fail-closed 机器断言（F-14）。保存为 `"$STATE_DIR/canary_assert.py"`（0600）：

```python
#!/usr/bin/env python3
"""canary_assert.py — machine-validate the canary agent result (repair round 1, F-14).

Usage:
  python3 canary_assert.py OUTER_JSON CANARY_MARKER_STRING

Outer envelope (openclaw agent --json, Gateway-backed); any violation -> exit 2:
  - result.meta.aborted must be != true
  - result.meta.toolSummary.failures must be 0 (absent toolSummary -> refuse)
  - visible text must exist and be non-empty

Visible text extraction order (documented; refuse if none present):
  1. result.text
  2. result.payloads[0].text
  3. payloads[0].text

Inner schema (the prompt's exact contract), parsed from visible text as single-line
JSON; any violation -> exit 2:
  - ok: true
  - marker == CANARY_MARKER_STRING
  - capture: {ok:true, ingest_status:"ready", id non-empty, path relative,
    no "..", endswith ".md"}
  - query: {ok:true, count >= 1, ids contains capture.id, paths contains capture.path}
  - maintenance: {ok:true}

stdout: CANARY_JSON_OK=true marker=实际marker值  |  failure: stderr CANARY_JSON_FAILED=原因
"""
import argparse
import json
import os
import sys

OUTER_TEXT_PATHS = ("result.text", "result.payloads[0].text", "payloads[0].text")


class CanaryAssertError(Exception):
    pass


def _fail(msg):
    raise CanaryAssertError("CANARY_JSON_FAILED=" + msg)


def _get(obj, path):
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (IndexError, ValueError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _assert_outer(outer):
    meta = _get(outer, "result.meta")
    if not isinstance(meta, dict):
        _fail("outer result.meta missing")
    if meta.get("aborted") is True:
        _fail("outer result.meta.aborted is true")
    ts = meta.get("toolSummary")
    if not isinstance(ts, dict):
        _fail("outer result.meta.toolSummary missing")
    # F-14 strict: type(x) is int — bool(false/true) 一律拒绝
    if type(ts.get("failures")) is not int or ts["failures"] != 0:
        _fail("outer toolSummary.failures not int 0: %r" % ts.get("failures"))
    for path in OUTER_TEXT_PATHS:
        text = _get(outer, path)
        if isinstance(text, str) and text.strip():
            return text.strip()
    _fail("no visible text in outer envelope")


def _assert_inner(inner, marker):
    if not isinstance(inner, dict):
        _fail("inner not a JSON object")
    if inner.get("ok") is not True:
        _fail("inner ok != true")
    if inner.get("marker") != marker:
        _fail("inner marker %r != expected %r" % (inner.get("marker"), marker))
    cap = inner.get("capture")
    if not isinstance(cap, dict) or cap.get("ok") is not True:
        _fail("capture.ok != true")
    if cap.get("ingest_status") != "ready":
        _fail("capture.ingest_status != ready: %r" % cap.get("ingest_status"))
    cap_id = cap.get("id")
    cap_path = cap.get("path")
    if not isinstance(cap_id, str) or not cap_id:
        _fail("capture.id missing or empty")
    if not isinstance(cap_path, str) or not cap_path:
        _fail("capture.path missing")
    if cap_path.startswith("/") or ".." in cap_path.split("/"):
        _fail("capture.path not a safe relative path: %r" % cap_path)
    if not cap_path.endswith(".md"):
        _fail("capture.path does not end with .md: %r" % cap_path)
    q = inner.get("query")
    if not isinstance(q, dict) or q.get("ok") is not True:
        _fail("query.ok != true")
    # F-14 strict: type(x) is int — bool(false/true) 一律拒绝
    if type(q.get("count")) is not int or q["count"] < 1:
        _fail("query.count not int >= 1: %r" % q.get("count"))
    ids = q.get("ids")
    paths = q.get("paths")
    if not isinstance(ids, list) or cap_id not in ids:
        _fail("query.ids does not contain capture.id")
    if not isinstance(paths, list) or cap_path not in paths:
        _fail("query.paths does not contain capture.path")
    m = inner.get("maintenance")
    if not isinstance(m, dict) or m.get("ok") is not True:
        _fail("maintenance.ok != true")
    return cap_id, cap_path


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("outer_json")
    ap.add_argument("marker")
    args = ap.parse_args(argv)

    with open(args.outer_json, "rb") as f:
        raw = f.read()
    try:
        outer = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        _fail("outer JSON unparseable: %s" % exc)

    text = _assert_outer(outer)
    try:
        inner = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        _fail("visible text not parseable JSON: %s" % exc)
    cap_id, cap_path = _assert_inner(inner, args.marker)
    print("CANARY_JSON_OK=true marker=%s capture_id=%s capture_path=%s"
          % (args.marker, cap_id, cap_path))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except CanaryAssertError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001
        print("CANARY_JSON_ERROR=%s" % exc, file=sys.stderr)
        sys.exit(3)
```

`secure_capture.py` 在 STATE_DIR 私有 parent 中以 `mkstemp`/`O_EXCL|O_NOFOLLOW`
创建 0600 唯一 output 与独立 0600 stderr 文件，fstat 验证后以**精确获批 argv**
（`openclaw agent --agent main --session-key "$CANARY_SESSION_KEY" --message
"$CANARY_PROMPT" --json`，不新增业务 flags）运行，stdout 写 fd、stderr 写独立
0600 文件，`check=False` 显式报告 agent rc；失败保留私有诊断。保存为
`"$STATE_DIR/secure_capture.py"`（0600）：

```python
#!/usr/bin/env python3
"""secure_capture.py — secure outer-JSON capture for the canary agent run (final repair round, F-14).

Usage:
  python3 secure_capture.py STATE_DIR OUT_NAME ERR_NAME -- openclaw agent --agent main --session-key KEY --message PROMPT --json

- Creates OUT_NAME and ERR_NAME under STATE_DIR (0600) via mkstemp/O_EXCL|O_NOFOLLOW
  semantics: pre-lstat any existing object (regular/symlink/dangling) -> refuse,
  never follows symlinks, never chmods existing objects.
- Runs the EXACT argv after "--" with subprocess.run(check=False); stdout -> OUT fd,
  stderr -> ERR fd (separate 0600 files). No shell redirection is used.
- fstat-verifies both files (regular, 0600, owner == uid) before running.
- stdout: SECURE_CAPTURE_DONE=true out=OUT_NAME err=ERR_NAME agent_rc=N size=N
- On failure: refuses before running or reports AGENT_RC; private diagnostics are kept.
"""
import argparse
import os
import pathlib
import stat
import subprocess
import sys


class SecureCaptureError(Exception):
    pass


def _refuse(msg):
    raise SecureCaptureError("SECURE_CAPTURE_REFUSED=" + msg)


def _open_private(parent, name):
    """Exclusive no-follow 0600 create; returns (fd, (dev, ino))."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(name, flags, 0o600, dir_fd=parent)
    except OSError as exc:
        _refuse("cannot exclusively create %s (pre-existing or symlink?): %s" % (name, exc))
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or (st.st_mode & 0o777) != 0o600 or st.st_uid != os.getuid():
        os.close(fd)
        _refuse("%s fstat verification failed" % name)
    return fd, (st.st_dev, st.st_ino)


def main(argv):
    if "--" not in argv:
        raise SystemExit("usage: secure_capture.py STATE_DIR OUT_NAME ERR_NAME -- openclaw agent 及获批参数")
    idx = argv.index("--")
    head, cmd = argv[:idx], argv[idx + 1:]
    if len(head) != 3:
        raise SystemExit("usage: secure_capture.py STATE_DIR OUT_NAME ERR_NAME -- openclaw agent 及获批参数")
    state, out_name, err_name = head
    if not cmd or cmd[0] != "openclaw":
        _refuse("argv must start with the openclaw binary")
    if "--session-key" not in cmd or "--message" not in cmd or "--json" not in cmd:
        _refuse("argv missing approved flags (--agent/--session-key/--message/--json)")
    if any(f in cmd for f in ("--message-file", "--timeout")):
        _refuse("argv contains non-approved flags")

    if not state.startswith("/"):
        _refuse("state_dir not absolute")
    pfd = os.open(state, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        out_fd, _ = _open_private(pfd, out_name)
        err_fd, _ = _open_private(pfd, err_name)
        try:
            proc = subprocess.run(cmd, stdout=out_fd, stderr=err_fd, check=False)
        finally:
            os.close(out_fd)
            os.close(err_fd)
        out_size = os.path.getsize(os.path.join(state, out_name))
        err_size = os.path.getsize(os.path.join(state, err_name))
        print("SECURE_CAPTURE_DONE=true out=%s err=%s agent_rc=%d out_size=%d err_size=%d"
              % (out_name, err_name, proc.returncode, out_size, err_size))
        if proc.returncode != 0:
            _refuse("agent rc=%d (diagnostics kept in %s)" % (proc.returncode, err_name))
        return 0
    finally:
        os.close(pfd)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SecureCaptureError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001
        print("SECURE_CAPTURE_ERROR=%s" % exc, file=sys.stderr)
        sys.exit(3)
```

```bash
# CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED
set -Eeuo pipefail
trap 'echo "GATE_C_FAILED=已停止；恢复 POST_MAIN_ROTATION_BASELINE（§2.6）" >&2; _safe_cleanup' ERR
# 1) 本地委派会话（F-16：获批精确命令，无消息文件读取/无超时参数；
#    F-14：secure_capture 独占 0600 创建 output/stderr，无裸重定向）
run_or_die "canary 委派会话" python3 -B secure_capture.py "$STATE_DIR" \
  "$(basename "$CANARY_OUTPUT")" "canary-output-${RUN_ID}.err" -- \
  openclaw agent --agent main --session-key "$CANARY_SESSION_KEY" \
  --message "$CANARY_PROMPT" --json
[ -s "$CANARY_OUTPUT" ] || die "canary 输出为空"

# 2) 外层 envelope 机器断言（jq；F-14）
run_or_die "outer aborted 断言" jq -e '.result.meta.aborted != true' "$CANARY_OUTPUT" >/dev/null
run_or_die "outer tool failures 断言" jq -e '.result.meta.toolSummary.failures == 0' "$CANARY_OUTPUT" >/dev/null
run_or_die "outer visible text 断言" jq -e '((.result.text // .result.payloads[0].text // .payloads[0].text // "") | length) > 0' "$CANARY_OUTPUT" >/dev/null

# 3) inner bounded JSON 机器断言（ok/marker/capture/query/maintenance 全契约；任一失败不得进入 Gate D）
run_or_die "canary JSON 断言" python3 -B canary_assert.py "$CANARY_OUTPUT" "$CANARY_MARKER_STRING"
# 期望 stdout：CANARY_JSON_OK=true marker=sourcenotes-canary-${RUN_ID}
# 断言顺序（F-14）：capture ok/ready → staged path 为 canary 内 .md（相对、无 ..）→
# query count>=1 且 ids/paths 含同一 capture id/相对路径 → maintenance ok。
# canary 期间不得向正式 SourceNotes 发起任何写入；Telegram 不用于 canary。
# 注：provenance marker（.sourcenotes-canary.marker）仅作清理/删除绑定证据，不作为 query target。
```

#### Gate D — canary PASS → revoke NotesVaulter → POST_ROTATION_SAFE_ROLLBACK

```bash
# CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED
set -Eeuo pipefail
trap 'echo "GATE_D_FAILED=已停止；恢复 POST_ROTATION_SAFE_ROLLBACK（§2.6）" >&2; _safe_cleanup' ERR
# 0) 正式 Vault 指纹复核（canary 后，F-15）
run_or_die "canary 后 source 指纹复核" python3 -B vault_fingerprint.py check "$PRODUCTION_VAULT_ROOT" "$VAULT_FINGERPRINT_LEDGER"

# 1) Operator 在 BotFather 对 notesvaulter 旧 bot 执行 /revoke（旧 token 立即失效）。

# 2) POST_ROTATION_SAFE_ROLLBACK：new main token、移除 notesvaulter binding/account、
#    capture disabled、VAULT_ROOT=原测试库（maintenance-safe）、main Telegram enabled
run_or_die "safe-rollback transform" python3 -B transform.py "$POST_MAIN_ROTATION_BASELINE" "$POST_ROTATION_SAFE_ROLLBACK" "$TEST_VAULT_ROOT" --role safe-rollback
run_or_die "safe-rollback token 注入" python3 -B token_inject.py "$POST_ROTATION_SAFE_ROLLBACK" "$MAIN_BOT_TOKEN_FILE"
run_or_die "safe-rollback validate" env OPENCLAW_CONFIG_PATH="$POST_ROTATION_SAFE_ROLLBACK" openclaw config validate   # 期望 Config valid
run_or_die "safe-rollback projection" python3 -B projection.py "$POST_ROTATION_SAFE_ROLLBACK" --rotated-marker "$TOKEN_ROTATED_MARKER"
# 期望：main_token_rotated=true；notesvaulter_token_present=false；
#       vault-capture enabled=false；vault_root basename=SourceNotes-test；
#       telegram_enabled=true；bindings 仅 main→telegram:default

# 3) 不发布；该文件成为 NotesVaulter revoke 后唯一可用 rollback target（§2.6）。
```

- 失败边 **GD**：NotesVaulter revoke 后任何失败 → 恢复 `POST_ROTATION_SAFE_ROLLBACK`
  （§2.6），保证 main Telegram 仍可用；**禁止**恢复 `PRE_ROTATION_BACKUP`。

#### Gate E — PRODUCTION_CANDIDATE + ★唯一最终 production publish/reload（F-12）

```bash
# CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED
set -Eeuo pipefail
trap 'echo "GATE_E_FAILED=已停止；恢复 POST_ROTATION_SAFE_ROLLBACK（§2.6）" >&2; _safe_cleanup' ERR
# 0) 正式 Vault 指纹复核（production publish 前，F-15）
run_or_die "publish 前 source 指纹复核" python3 -B vault_fingerprint.py check "$PRODUCTION_VAULT_ROOT" "$VAULT_FINGERPRINT_LEDGER"

# 1) PRODUCTION_CANDIDATE：基于 POST_ROTATION_SAFE_ROLLBACK，只增加生产三技能/
#    production VAULT_ROOT 等最终字段
run_or_die "production transform" python3 -B transform.py "$POST_ROTATION_SAFE_ROLLBACK" "$PRODUCTION_CANDIDATE" "$PRODUCTION_VAULT_ROOT" --role production
run_or_die "production token 注入" python3 -B token_inject.py "$PRODUCTION_CANDIDATE" "$MAIN_BOT_TOKEN_FILE"
run_or_die "ownership 记录 production-candidate" record_owned "production-candidate" "$PRODUCTION_CANDIDATE"
run_or_die "production validate" env OPENCLAW_CONFIG_PATH="$PRODUCTION_CANDIDATE" openclaw config validate            # 期望 Config valid
run_or_die "production skills check" env OPENCLAW_CONFIG_PATH="$PRODUCTION_CANDIDATE" openclaw skills check --agent notesvaulter
# 期望：三 vault skill Eligible 且 Visible to model
run_or_die "production projection" python3 -B projection.py "$PRODUCTION_CANDIDATE" --rotated-marker "$TOKEN_ROTATED_MARKER"
# 期望：telegram_enabled=true（★唯一恢复 default main Telegram ingress 的点，F-04/F-12）；
#       vault_roots 三值 basename=SourceNotes；三技能 enabled=true；bindings 仅
#       main→telegram:default；accounts 仅 default；notesvaulter_token_present=false；
#       main_token_rotated=true

# 2) ★ 唯一最终 production 原子发布/reload（整个 cutover 只此一处）
run_or_die "★唯一 production 发布" python3 -B atomic.py write "$ACTIVE_CONFIG" "$PRODUCTION_CANDIDATE"
run_or_die "active config sha 记录" sha256sum "$ACTIVE_CONFIG"                # 记录新 SHA（与 PRODUCTION_CANDIDATE 一致）
run_or_die "gateway restart" openclaw gateway restart
run_or_die "gateway validate/status/health" bash -c 'openclaw config validate && openclaw gateway status && openclaw gateway health'

# 3) 收尾指纹复核（F-15）
run_or_die "收尾 source 指纹复核" python3 -B vault_fingerprint.py check "$PRODUCTION_VAULT_ROOT" "$VAULT_FINGERPRINT_LEDGER"
```

- 失败边 **GE**：最终发布失败 → 恢复 `POST_ROTATION_SAFE_ROLLBACK`（§2.6），
  main Telegram 仍可用；**不重复发布 production candidate**。

#### Gate F — Work Item 02 只读复核（不再 publish）

```bash
# CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED（以下命令全部只读）
set -Eeuo pipefail
trap 'echo "GATE_F_FAILED=已停止（只读复核失败，人工处置）" >&2; _safe_cleanup' ERR
run_or_die "config validate" openclaw config validate                        # 期望 Config valid
run_or_die "gateway status" openclaw gateway status                          # 期望 running、probe ok
run_or_die "gateway health" openclaw gateway health                          # 期望健康
run_or_die "skills check" openclaw skills check --agent notesvaulter         # 期望三 vault skill Visible、Missing requirements 0
run_or_die "running 检查" bash -c 'openclaw tasks list --status running | grep -q "0 running"'
run_or_die "queued 检查" bash -c 'openclaw tasks list --status queued | grep -q "0 queued"'
run_or_die "正式 Vault status" git -C "$PRODUCTION_VAULT_ROOT" status --short --branch   # 期望 clean（HEAD/index/工作树与预克隆指纹一致）
run_or_die "指纹复核" python3 -B vault_fingerprint.py check "$PRODUCTION_VAULT_ROOT" "$VAULT_FINGERPRINT_LEDGER"   # 期望 FINGERPRINT_OK=true
run_or_die "测试 Vault 只读确认" git -C "$TEST_VAULT_ROOT" status --short --branch          # 只读确认未被触碰
# 委派验证（生产态）：通过 main 新会话（default Telegram binding）要求 Steward 委派
# notesvaulter 执行只读 maintenance/query；期望委派成功且返回有界 JSON。
# 若委派失败 → 检查 agents.list 中 main 的 subagents.allowAgents 是否精确包含
# "notesvaulter"（禁止 *）。
# 首次 production capture 等待用户下一条真实输入；本 Gate 不写合成生产数据。
```

### 2.6 失败恢复矩阵（F-06：命名回滚点；禁止恢复含旧 token 文件）

```bash
# CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED
set -Eeuo pipefail
trap 'echo "RECOVERY_FAILED=已停止；不得继续自动处置" >&2; _safe_cleanup' ERR
# 通用恢复命令模板（TARGET ∈ POST_MAIN_ROTATION_BASELINE | POST_ROTATION_SAFE_ROLLBACK）：
run_or_die "恢复发布" python3 -B atomic.py write "$ACTIVE_CONFIG" "$TARGET"
run_or_die "恢复 sha 校验" sha256sum "$ACTIVE_CONFIG"                  # 必须等于 TARGET 记录 sha
run_or_die "gateway restart" openclaw gateway restart                    # 非破坏性重载
run_or_die "gateway validate/status/health" bash -c 'openclaw config validate && openclaw gateway status && openclaw gateway health'
run_or_die "指纹复核" python3 -B vault_fingerprint.py check "$PRODUCTION_VAULT_ROOT" "$VAULT_FINGERPRINT_LEDGER"  # 期望 FINGERPRINT_OK=true
run_or_die "正式 Vault status" git -C "$PRODUCTION_VAULT_ROOT" status --short --branch  # 确认 Vault 未被动过
# 禁止：git reset/clean、Vault 快照覆盖、删除浸泡期数据、恢复 PRE_ROTATION_BACKUP
```

| 阶段 | 失败点 | 恢复目标 | 附加动作 |
|---|---|---|---|
| Gate A 步骤 1–5 | main revoke 之前 | 停止（`PRE_ROTATION_BACKUP` 仍有效） | 无 |
| Gate A 步骤 6–8 | main revoke 之后 / 基线发布失败 | `POST_MAIN_ROTATION_BASELINE`（ingress paused） | 通用恢复模板；health 通过才继续 |
| Gate B/C | canary 候选发布或委派失败 | `POST_MAIN_ROTATION_BASELINE`（NotesVaulter token 未 revoke） | 先保存必要脱敏诊断，再经 `cleanup_canary.py` 删除克隆（见下） |
| Gate D 之后 | NotesVaulter revoke 后任何失败 | `POST_ROTATION_SAFE_ROLLBACK` | 通用恢复模板 |
| Gate E | 最终 production 发布失败 | `POST_ROTATION_SAFE_ROLLBACK` | 通用恢复模板；main Telegram 仍可用 |
| 任何阶段 | — | **禁止** `PRE_ROTATION_BACKUP` / 任何含旧 token 文件 | 见 §2.2 回滚纪律 |

canary 克隆删除只允许通过 fail-closed helper（F-11；验证父目录 lstat 非 symlink
且 realpath 精确等于 `STATE_DIR/canary`、精确 basename/run_id、marker 常规文件
（no-follow）0600 owner=当前 uid、dev/inode 与 ledger 一致、**marker 与 ledger
全字段（run_id/source_head/realpath/dev/inode）完全匹配**、ledger 常规文件
（no-follow）0600 owner=当前 uid、无运行中 canary 进程、与正式路径不相等；任一
不符拒绝并人工处置，**只报告不删除**）：

```python
#!/usr/bin/env python3
"""cleanup_canary.py — provenance-safe canary clone deletion (Work Item safety closure, F-11).

Usage:
  python3 cleanup_canary.py STATE_DIR CANARY_VAULT_ROOT --production-vault-root PROD_ROOT

Deletes a canary clone ONLY after re-verifying ALL of:
  - CANARY_VAULT_ROOT is absolute; not a symlink; realpath == itself
  - parent directory is NOT a symlink (lstat) and realpath(parent) ==
    realpath(STATE_DIR/canary) and mode 0700
  - basename matches SourceNotes-production-canary-${RUN_ID}-test (endswith -test)
  - target exists and is a directory (no follow)
  - marker $CANARY_VAULT_ROOT/.sourcenotes-canary.marker is a regular file (lstat, no-follow),
    mode 0600, owner == current uid, JSON with run_id / source_head / realpath /
    dev / inode matching target
  - ledger STATE_DIR/canary-ledger.json is a regular file (lstat, no-follow),
    mode 0600, owner == current uid, and every field (run_id / source_head /
    realpath / dev / inode) equals the marker
  - no running process has its cwd or an open fd under the canary realpath
  - canary realpath != production vault realpath (and not ancestor/descendant of it)

On success: rename to a tombstone in the same 0700 parent (re-verify inode), delete the
tombstone tree, fsync parent. stdout: CANARY_CLEANED=true. Refusal: non-zero exit with reason
and the clone is left untouched (report-only, no deletion).
Never uses bare `rm -rf` on the supplied path.
"""
import argparse
import json
import os
import pathlib
import shutil
import stat
import sys

MARKER_NAME = ".sourcenotes-canary.marker"
LEDGER_NAME = "canary-ledger.json"
CANARY_PARENT = "canary"
PROVENANCE_KEYS = ("run_id", "source_head", "realpath", "dev", "inode")


class CleanupRefused(Exception):
    pass


def _refuse(msg):
    raise CleanupRefused("CLEANUP_REFUSED=" + msg)


def _real(path):
    return os.path.realpath(path)


def _mode(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


def _dev_inode(path, follow=True):
    st = os.stat(path) if follow else os.lstat(path)
    return (st.st_dev, st.st_ino)


def _running_under(realpath):
    rp = realpath.rstrip("/")
    root = rp + "/"
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        base = "/proc/" + entry
        for sub in ("cwd", "root", "fd"):
            d = base + "/" + sub
            try:
                for name in os.listdir(d):
                    link = os.readlink(d + "/" + name) if sub == "fd" else os.readlink(d)
                    if link == rp or link.startswith(root):
                        return entry
            except OSError:
                continue
    return None


def _verify_private_file(path, what):
    """F-11: lstat no-follow regular file, not a symlink, 0600, owner == current uid."""
    try:
        lst = os.lstat(path)
    except OSError as exc:
        _refuse("%s missing: %s" % (what, exc))
    if not stat.S_ISREG(lst.st_mode):
        _refuse("%s not a regular file (no-follow)" % what)
    if os.path.islink(path):
        _refuse("%s is a symlink" % what)
    if (lst.st_mode & 0o777) != 0o600:
        _refuse("%s mode %s != 0600" % (what, oct(lst.st_mode & 0o777)))
    if lst.st_uid != os.getuid():
        _refuse("%s owner != current uid" % what)


def cleanup(state_dir, canary_path, production_root):
    if not isinstance(canary_path, str) or not canary_path.startswith("/"):
        _refuse("canary path not absolute")
    if os.path.islink(canary_path):
        _refuse("canary path is a symlink")
    if _real(canary_path) != canary_path:
        _refuse("canary path realpath mismatch")

    state_real = _real(state_dir)
    parent = os.path.dirname(canary_path)
    if os.path.islink(parent):
        _refuse("canary parent is a symlink")
    parent_real = _real(parent)
    expected_parent = os.path.join(state_real, CANARY_PARENT)
    if parent_real != _real(expected_parent):
        _refuse("canary parent %s != STATE_DIR/canary %s" % (parent_real, expected_parent))
    if _mode(expected_parent) != 0o700:
        _refuse("canary parent mode %s != 0700" % oct(_mode(expected_parent)))

    base = os.path.basename(canary_path)
    if not base.endswith("-test"):
        _refuse("basename must end with -test")
    prefix = "SourceNotes-production-canary-"
    if not base.startswith(prefix):
        _refuse("basename must start with %r" % prefix)
    run_id = base[len(prefix):-len("-test")]
    if not run_id:
        _refuse("cannot derive run_id from basename")

    if not os.path.isdir(canary_path):
        _refuse("canary target missing or not a directory")

    marker_path = os.path.join(canary_path, MARKER_NAME)
    _verify_private_file(marker_path, "marker")
    try:
        with open(marker_path, "rb") as f:
            marker = json.loads(f.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        _refuse("marker unreadable: %s" % exc)
    if marker.get("run_id") != run_id:
        _refuse("marker run_id %r != basename run_id %r" % (marker.get("run_id"), run_id))
    if marker.get("realpath") != canary_path:
        _refuse("marker realpath mismatch")
    m_dev, m_ino = marker.get("dev"), marker.get("inode")
    t_dev, t_ino = _dev_inode(canary_path, follow=False)
    if m_dev != t_dev or m_ino != t_ino:
        _refuse("marker dev/inode does not match target")

    ledger_path = os.path.join(state_real, LEDGER_NAME)
    _verify_private_file(ledger_path, "ledger")
    try:
        with open(ledger_path, "rb") as f:
            ledger = json.loads(f.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        _refuse("ledger unreadable: %s" % exc)
    l_dev, l_ino = ledger.get("dev"), ledger.get("inode")
    if l_dev != t_dev or l_ino != t_ino or ledger.get("run_id") != run_id:
        _refuse("ledger dev/inode/run_id does not match target")
    for key in PROVENANCE_KEYS:
        if marker.get(key) != ledger.get(key):
            _refuse("ledger/marker %s mismatch" % key)

    prod_real = _real(production_root)
    if canary_path == prod_real:
        _refuse("canary path equals production vault path")
    if canary_path.rstrip("/") + "/" in prod_real.rstrip("/") + "/":
        _refuse("canary path is ancestor of production vault path")
    if prod_real.rstrip("/") + "/" in canary_path.rstrip("/") + "/":
        _refuse("production vault path is ancestor of canary path")

    proc = _running_under(canary_path)
    if proc is not None:
        _refuse("running process %s still has cwd/fd under canary" % proc)

    tomb = os.path.join(expected_parent, ".sourcenotes-canary-%s-tombstone-%d" % (run_id, os.getpid()))
    os.rename(canary_path, tomb)
    t_dev2, t_ino2 = _dev_inode(tomb, follow=False)
    if (t_dev2, t_ino2) != (t_dev, t_ino):
        _refuse("tombstone inode changed after rename")
    shutil.rmtree(tomb)
    dfd = os.open(expected_parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    print("CANARY_CLEANED=true run_id=%s" % run_id)
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("state_dir")
    ap.add_argument("canary_path")
    ap.add_argument("--production-vault-root", required=True)
    args = ap.parse_args(argv)
    try:
        return cleanup(args.state_dir, args.canary_path, args.production_vault_root)
    except CleanupRefused as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print("CLEANUP_ERROR=%s" % exc, file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

```bash
# CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED
set -Eeuo pipefail
trap 'echo "CLEANUP_BLOCK_FAILED=已停止；不得继续自动处置" >&2; _safe_cleanup' ERR
# 删除前最后复核：正式 Vault 指纹（F-15）+ provenance-safe cleanup（F-11）
run_or_die "cleanup 前指纹复核" python3 -B vault_fingerprint.py check "$PRODUCTION_VAULT_ROOT" "$VAULT_FINGERPRINT_LEDGER"
run_or_die "provenance-safe cleanup" python3 -B cleanup_canary.py "$STATE_DIR" "$CANARY_VAULT_ROOT" --production-vault-root "$PRODUCTION_VAULT_ROOT"
# 期望 stdout：CANARY_CLEANED=true run_id=实际值；失败时 stderr=CLEANUP_REFUSED=原因 且克隆保留。
```

### 2.7 通过后记录 last_known_good 与 soak start

```bash
# CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED
set -Eeuo pipefail
trap 'echo "LKG_FAILED=已停止；不得继续自动处置" >&2; _safe_cleanup' ERR
run_or_die "指纹复核" python3 -B vault_fingerprint.py check "$PRODUCTION_VAULT_ROOT" "$VAULT_FINGERPRINT_LEDGER"   # 期望 FINGERPRINT_OK=true
run_or_die "last_known_good ledger" python3 scripts/sourcenotes_ops.py ledger \
  --dir "$STATE_DIR" --vault "$PRODUCTION_VAULT_ROOT" \
  add --type release \
  --data '{"blueprint_commit":"017c2ce1fb2ef00f4fdc4e6f872a9877c49890da","affected_path":"role=production-vault","disposition":"last_known_good; soak start 2026-08-17"}'
```

- `last_known_good` 精确记录 `017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`，soak
  自 2026-08-17 起一周或更长。
- 首次 production capture 等待**用户下一条真实输入**，不写合成生产数据。
- soak 期失败：按 §2.6 恢复矩阵恢复配置；Vault 数据时间线单调保留，不随软件回退删除。

---

## 3. 安全边界（本包自检，round 3 safety closure + repair round 1 + final repair round）

- 无 token/secret 值、无绝对 Vault 路径（仅 `"$PRODUCTION_VAULT_ROOT"` /
  `"$TEST_VAULT_ROOT"` 变量与 basename）、无正文、无逐项 URL、无尖括号占位符、
  无省略号占位形态（VAL-F05/F08 扫描）。
- **F-04（final）**：任何 token 读取/轮换前先构造、dry-run、原子发布并验证
  `INGRESS_PAUSED_BASELINE`（`channels.telegram.enabled=false`、capture 保持
  disabled）；暂停投影检查使用单一完整安全引用 pattern
  `grep -Eq '"telegram_enabled"[[:space:]]*:[[:space:]]*false' "$FILE"`
  （`false` 不会被解析为文件）；`POST_MAIN_ROTATION_BASELINE` 基于暂停基线且保持
  暂停；canary 只由 Operator 本地 `openclaw agent --agent main --session-key
  "$CANARY_SESSION_KEY" --message "$CANARY_PROMPT" --json` 触发；只有 Gate E 的
  production 候选恢复 default main Telegram ingress（VAL-F01）。
- **F-07**：§2.0 为 fail-closed preamble（`set -Eeuo pipefail` + 全部
  `: "${VAR:?}"` 定义检查）；`CANARY_VAULT_ROOT` 只由已验证 `STATE_DIR` + `RUN_ID`
  派生并验证 absolute/父目录/basename/初始不存在；无变量伪值/真实路径/尖括号占位符
  （VAL-S02）。
- **F-11（final）**：全部私有文件写入（fingerprint ledger、provenance marker/ledger、
  secure_capture output/stderr）共用 `secure_file.py` no-follow 原语——parent fd +
  `O_EXCL|O_NOFOLLOW`，目标预检查 lstat（regular/symlink/dangling 均拒绝）、
  持 fd `fstat` 验证 regular/0600/uid、全量写+fsync+parent fsync；多文件创建按
  `(dir_fd,name,dev,inode)` 事务记录，后续失败 reverse-order 仅回滚本事务 inode；
  shell 目标检查统一 `if [[ -e "$P" || -L "$P" ]]; then die; fi`（dangling 也拒绝）
  且先检查后 chmod（VAL-F02）。
- **F-13（final）**：`_safe_cleanup()` 首条可执行语句 `local rc=$?` 之后才
  `trap - ERR`，最终 `return "$rc"`，cleanup 错误只 stderr 报告不覆盖原 rc；
  candidate/temp 清理只认 `ownership-${RUN_ID}.manifest`（0600，含
  role/realpath/dev/inode/run_id），cleanup 前 no-follow 验证 dev/inode/parent/
  run_id，不匹配保留并报告；rm/unlink 失败显式报告；全部 bash 块 `set -Eeuo
  pipefail` + `run_or_die`/显式 `if` 包裹；预期失败显式 if/else（VAL-F03）。
- **F-14（final）**：Gate C 外层 JSON 经 `secure_capture.py` 独占 0600 创建
  output/stderr（无裸重定向、无 path-following），以精确获批 argv 运行并显式报告
  agent rc；`canary_assert.py` 对 failures/query.count 使用严格
  `type(x) is int`（bool 拒绝），布尔字段严格 `is True/False`；
  CANARY_PROMPT 要求 main 输出无 fence 单行 JSON；jq 外层断言 +
  inner 全契约机器断言，任一失败不得进入 Gate D（VAL-F04）。
- **F-15**：`vault_fingerprint.py capture` 在 Gate A（token 轮换前、clone 前，
  F-19）以 no-follow secure create 写入指纹 ledger；clone 后/canary 前后/cleanup
  前/production publish 前/收尾各 `check` 逐项等值；clone provenance 以预克隆
  指纹为准；漂移立即停止、恢复配置、不清理/修改正式 Vault（VAL-F08 回归）。
- **F-16（repair round 1）**：canary agent 命令精确为获批形式
  `openclaw agent --agent main --session-key "$CANARY_SESSION_KEY" --message "$CANARY_PROMPT" --json`，
  经 `secure_capture.py` 传递精确 argv，不新增业务 flags；全包零命中消息文件读取
  与超时参数（VAL-F04 静态扫描）。
- **F-17（final）**：Evidence 全量删除省略号/尖括号占位形态；每个 fixture 记录
  完整命令、cwd、exit、关键输出、fixture script SHA-256 与 package 同源提取 SHA
  及确定性提取命令（VAL-F05）。
- **F-18（final）**：全包 marker 统一精确 `sourcenotes-canary-${RUN_ID}`，旧多段式
  marker 形态零命中（VAL-F06）。
- **F-19（final）**：Gate A 在 ingress pause/token rotation 前运行
  `git -C "$PRODUCTION_VAULT_ROOT" status --porcelain=v2 -z`，严格断言输出长度 0
  （不只查 exit），并核验批准 full HEAD 与预克隆指纹；dirty/untracked/staged
  任一存在即 exit，token rotation sentinel 不执行（VAL-F07）。
- 所有真实写入命令均已标注 `CONTROLLED ACTION — OPERATOR ONLY — NOT EXECUTED`；
  配置写入一律原子（同目录唯一 temp → 0600 → flush/fsync → `os.replace` →
  parent fsync；VAL-F08 回归）。
- transformer/token injector/atomic helper 直接写 0600 私有文件；stdout 只输出
  固定布尔/哈希/projection，绝不输出配置正文或 token。
- 三技能均注入 `env.VAULT_ROOT`；结构缺失 fail-closed 且不写 candidate（VAL-F08 回归）。
- 轮换后回滚只使用 `POST_MAIN_ROTATION_BASELINE` / `POST_ROTATION_SAFE_ROLLBACK`，
  `PRE_ROTATION_BACKUP` 只审计（VAL-F01/F08 回归）。
- 唯一 production publish/reload 只在 Gate E（VAL-F01/F08 回归）。
- canary 克隆删除仅经 provenance-safe helper（VAL-F02/F08 回归）。
- 真实模型委派 canary：**NOT_RUN — OPERATOR CONTROLLED ACTION GATE**（见 §2.5
  顶部声明），本 Work Item 不执行、不自证。
- 蓝图产品代码、两个 Vault、活动配置、默认 Gateway 在本 Work Item 中一律未被
  修改（VAL-F09 前后指纹一致）。