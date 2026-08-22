# Controlled Action Runbook — Operator execution sequence

Effort: `.scratch/2026-08-17-sourcenotes-simple-cutover/`
Date: 2026-08-18
Status: APPROVED for Operator execution (token rotation confirmed by Operator)

> 本文件是生产切换的精确命令序列。除标注「只读/验证」外，均为 **Controlled Action**，必须由 Operator 手动执行。Executor/Reviewer 不执行、不授权这些写/重启动作；它们只做执行前后的只读复核。

## 0. 关键变量

- 活动配置：`~/.openclaw/openclaw.json`（OpenClaw 原生原子写）
- 私有状态目录：`~/.local/state/sourcenotes-simple-cutover/2026-08-17/`（0700）
- 凭据/路径注入：`~/.openclaw/.env`（0600）
- 正式 Vault：`/home/monottx/repos/SourceNotes`
- canary clone：`/home/monottx/repos/SourceNotes-production-canary-20260818-test`（**保留，不删除**）
- Gateway 服务：`openclaw-gateway`（systemd user）

## 阶段 A — 备份与基线

```bash
mkdir -p ~/.local/state/sourcenotes-simple-cutover/2026-08-17
chmod 700 ~/.local/state/sourcenotes-simple-cutover/2026-08-17

cp ~/.openclaw/openclaw.json ~/.local/state/sourcenotes-simple-cutover/2026-08-17/openclaw.json.bak
chmod 600 ~/.local/state/sourcenotes-simple-cutover/2026-08-17/openclaw.json.bak
sha256sum ~/.openclaw/openclaw.json ~/.local/state/sourcenotes-simple-cutover/2026-08-17/openclaw.json.bak

# 若 ~/.openclaw/.env 已存在则备份；预期首次不存在
[ -f ~/.openclaw/.env ] && cp -a ~/.openclaw/.env ~/.local/state/sourcenotes-simple-cutover/2026-08-17/env.bak

# 确认无运行中任务（应 0）
openclaw tasks list --status running --status queued

# 正式 Vault checkpoint（应 clean，porcelain 字节数 0）
git -C /home/monottx/repos/SourceNotes rev-parse HEAD
git -C /home/monottx/repos/SourceNotes status --porcelain=v2 -z | wc -c
```

## 阶段 B — 写入 .env（secret，勿让 token 进 shell history / 聊天）

用编辑器创建 `~/.openclaw/.env`（不要用 `echo`/`printf` 明文回显 token），内容两行：

```
OPENCLAW_TELEGRAM_BOT_TOKEN=<新轮换的 token>
OPENCLAW_VAULT_ROOT=/home/monottx/repos/SourceNotes-production-canary-20260818-test
```

```bash
chmod 600 ~/.openclaw/.env
```

> canary 阶段 `OPENCLAW_VAULT_ROOT` 指向 clone；production 阶段改为正式 Vault 路径。token 全程只存在于 `.env`，不进 `openclaw.json`。

## 阶段 C — 创建 canary clone（保留不删除）

```bash
git clone --no-hardlinks /home/monottx/repos/SourceNotes /home/monottx/repos/SourceNotes-production-canary-20260818-test
git -C /home/monottx/repos/SourceNotes-production-canary-20260818-test remote remove origin
git -C /home/monottx/repos/SourceNotes-production-canary-20260818-test remote -v        # 应为空（push 禁用）
# 校验一致
git -C /home/monottx/repos/SourceNotes-production-canary-20260818-test rev-parse HEAD
git -C /home/monottx/repos/SourceNotes rev-parse HEAD
```

## 阶段 D — canary 配置（先 dry-run 再应用）

将 `canary-patch.json5`（内容见 cutover-package.md §3.1）写到私有目录，然后：

```bash
cd ~/.local/state/sourcenotes-simple-cutover/2026-08-17

# D1 dry-run
openclaw config patch --file canary-patch.json5 --replace-path bindings --dry-run
openclaw config set 'agents.list[0].name' 'Steward' --dry-run
openclaw config set 'agents.list[0].subagents.allowAgents' '["notesvaulter"]' --strict-json --dry-run
openclaw config set 'agents.list[1].skills' '["vault-capture","vault-query","vault-maintenance"]' --strict-json --replace --dry-run

# D2 应用（原生原子写）
openclaw config patch --file canary-patch.json5 --replace-path bindings
openclaw config set 'agents.list[0].name' 'Steward'
openclaw config set 'agents.list[0].subagents.allowAgents' '["notesvaulter"]' --strict-json
openclaw config set 'agents.list[1].skills' '["vault-capture","vault-query","vault-maintenance"]' --strict-json --replace
```

## 阶段 E — 重启 Gateway 并验证 canary

```bash
systemctl --user restart openclaw-gateway
openclaw gateway status                       # running, healthy
openclaw config validate                      # Config valid
openclaw config get channels.telegram.enabled   # false
openclaw config get channels.telegram.accounts  # 仅 default
openclaw config get bindings                    # 仅 main→telegram:default
openclaw skills check --agent notesvaulter      # 三 skill eligible
```

## 阶段 F — 真实模型 canary E2E（写 canary clone，非正式 Vault）

```bash
openclaw agent --agent main --session-key canary-20260818 --json --message \
  '请委派 notesvaulter 做一次自检并只输出单行 JSON：先捕获一条想法（正文含 "sourcenotes-canary-20260818"），再 query 搜索该字符串，再执行 maintenance report。最终只回一行：{"ok":true,"capture_id":"<id>","query_count":1,"maintenance_ok":true}；任一步失败输出 {"ok":false,"error":"..."}。'
```

断言：捕获文件落在 canary clone 的 `notes/ideas/` 下、query 命中同一 id、maintenance ok；正式 Vault 无任何变化。

## 阶段 G — production 切换

```bash
# G1 改 .env：OPENCLAW_VAULT_ROOT 改为 /home/monottx/repos/SourceNotes（编辑器改，不 echo）
# G2 应用 production patch（仅重新开启 telegram）
cd ~/.local/state/sourcenotes-simple-cutover/2026-08-17
openclaw config patch --file production-patch.json5 --dry-run
openclaw config patch --file production-patch.json5
# G3 重启使 .env 的正式 Vault 路径生效
systemctl --user restart openclaw-gateway
# G4 验证
openclaw gateway status
openclaw config validate
openclaw config get channels.telegram.enabled    # true
openclaw config get 'skills.entries.vault-capture.env.VAULT_ROOT'   # ${OPENCLAW_VAULT_ROOT}
```

## 阶段 H — last_known_good 与 soak 起点

在私有 ledger 记录：`last_known_good=017c2ce1fb2ef00f4fdc4e6f872a9877c49890da`，soak 开始。首次 production Capture 等待用户下一条真实输入。

## 回滚（任意阶段失败，只恢复配置、不倒退 Vault 数据）

```bash
cp ~/.local/state/sourcenotes-simple-cutover/2026-08-17/openclaw.json.bak ~/.openclaw/openclaw.json
chmod 600 ~/.openclaw/openclaw.json
# 恢复 .env（有备份则 cp 回，无则删除本次新增）
[ -f ~/.local/state/sourcenotes-simple-cutover/2026-08-17/env.bak ] && \
  cp ~/.local/state/sourcenotes-simple-cutover/2026-08-17/env.bak ~/.openclaw/.env || \
  rm -f ~/.openclaw/.env
systemctl --user restart openclaw-gateway
openclaw config validate
```

canary clone 保留不删除；清理由后续单独决定。
