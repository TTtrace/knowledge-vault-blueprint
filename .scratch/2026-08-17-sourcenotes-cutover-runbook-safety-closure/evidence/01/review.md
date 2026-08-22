# Safety Closure Work Item Review Evidence

Role: Reviewer
Review round: 1
Date: 2026-08-17

Verdict: CHANGES_REQUESTED

## Findings

- **F-11 [major]**：marker/ledger 写入前未拒绝既有或 dangling symlink；`open(...,"wb")` 可跟随覆盖，Gate B 还在 symlink 检查前 chmod。
- **F-13 [major]**：多个 backup/clone/validate/reload/status 仍为裸命令；trap 只报告，没有对本次 candidate/clone 的安全 cleanup trap。`bash -n` 不证明 fail-fast 语义。
- **F-14 [major]**：Gate C 只判断 agent 命令退出码，未机器解析 bounded JSON，也未断言 `.md` 路径、同一 marker/note id、maintenance 与 errors。
- **F-16 [major]**：获批简报要求 `--message`，实际 package 改用 `--message-file` 并增加 `--timeout 600`，但 DEVIATIONS 写 none。修复应恢复获批精确命令，避免范围变化。
- **F-17 [major]**：Execution Evidence 的 VAL-S06 含 `eyJ…`、`<每个产物>` 等缩写/占位符，缺完整可复核命令。

## Acceptance matrix

- AC-S01: PASS
- AC-S02: PASS
- AC-S03: FAIL（F-11）
- AC-S04: FAIL（F-13）
- AC-S05: FAIL（F-14/F-16）
- AC-S06: PASS
- AC-S07: NOT_RUN（F-17）
- AC-S08: NOT_RUN

## Controlled Action gate

CLOSED。允许在现有路径内做第一个 CHANGES_REQUESTED 修复轮；不得执行生产动作。

---

## Review round 2

Date: 2026-08-17

Verdict: CHANGES_REQUESTED

### Findings

- **F-04 [major]**：Gate A 的 `grep` 引用错误，暂停验证通常会把 `false` 当文件名。
- **F-11 [major]**：fingerprint ledger 仍可能跟随 symlink；exclusive writer 写后用 path stat 而非 fstat，部分失败未回滚已创建 inode；dangling canary target 未以 `-L` 拒绝。
- **F-13 [major]**：ERR trap 在 `trap - ERR` 后才取 `$?`，丢失原始 rc；candidate cleanup 未证明归属本 RUN_ID，删除失败未报告。
- **F-14 [major]**：Gate C outer JSON 通过裸重定向写文件；类型检查把 bool 当 int，可能错误接受 `false/true`。
- **F-17 [major]**：Evidence 仍含 `<每个产物>`，fixture 命令缺脚本内容或 SHA/同源锚点。
- **F-18 [minor]**：marker 实际格式多出 `marker-`，与批准的 `sourcenotes-canary-${RUN_ID}` 不一致，DEVIATIONS 却为 none。
- **F-19 [major]**：Gate A token rotation 前只检查 `git status` 命令退出码，未断言正式 Vault clean。

### Acceptance matrix

- AC-S01: FAIL（F-04）
- AC-S02: PASS
- AC-S03: FAIL（F-11）
- AC-S04: FAIL（F-13）
- AC-S05: FAIL（F-14/F-18）
- AC-S06: NOT_RUN
- AC-S07: FAIL（F-17）
- AC-S08: NOT_RUN

### Controlled Action gate

CLOSED。允许第二个、最后一个自动修复轮；若下一次 Review 仍非 PASS，停止请求 Operator。

---

## Review round 3 — final

Date: 2026-08-17

Verdict: CHANGES_REQUESTED

### Findings

- **F-11 [major]**：secure-file 失败清理未比较创建 inode，可能删替换后的无关文件；成功路径 fd 未关闭。
- **F-13 [major]**：ownership manifest 可接受既有非 0600 文件，按路径读取；对象 mismatch/unlink 失败仍无条件删 manifest，可能丢失归属证据。
- **F-14 [major]**：secure_capture 只检查必要 flags 存在，未逐项强制唯一批准 argv、`--agent main`、参数值与无额外业务 flags。
- **F-17 [major]**：最终 Evidence 仍含多个尖括号占位符，FR.5 零命中声明与实际矛盾，提取命令不可直接复现。
- **F-18 [minor]**：历史 Evidence 仍含旧 marker 格式，FR.6 零命中声明不成立。

### Acceptance matrix

- AC-S01/S02/S06: PASS（静态）
- AC-S03: FAIL（F-11）
- AC-S04: FAIL（F-13）
- AC-S05: FAIL（F-14/F-18）
- AC-S07: FAIL（F-17/F-18）
- AC-S08: NOT_RUN

### Final gate

- Controlled Action gate CLOSED。
- 这是第三次 Review 且仍非 PASS；依 lifecycle 停止自动修复，Work Item 保持 claimed，Effort 未 VERIFIED，向 Operator 请求处置。
