#!/usr/bin/env bash
# test_capture_debug.sh — capture_debug.sh 的回归测试 (v2)
# 使用 mktemp 临时目录(内含 basename 以 -test 结尾的测试库)与 fake openclaw/fake python3，
# 绝不调用真实 OpenClaw。
# 覆盖(v1): 非测试库拒绝、重复 ID 误判、全新 idea、raw 通用契约。
# 覆盖(v2): fake python3 强校验 --vault、web 异步 yield 从唯一新增暂存恢复 ID、
#           --expect-status failed PASS、默认 ready 拒绝 failed、多候选不猜 ID 且 cleanup 安全、
#           wait 期新增 annotation/queue 后 cleanup 无残留。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS="$SCRIPT_DIR/capture_debug.sh"
OUT_DIR="$SCRIPT_DIR/out"

PASS_N=0; FAIL_N=0
pass() { PASS_N=$((PASS_N+1)); echo "PASS: $1"; }
fail() { FAIL_N=$((FAIL_N+1)); echo "FAIL: $1"; }

# 记录测试前 out/ 中已存在的文件，测试结束只清理本次新增的产物
PRE_OUT="$(cd "$OUT_DIR" && find . -maxdepth 1 -type f -printf '%f\n' 2>/dev/null || true)"

BASE="$(mktemp -d "${TMPDIR:-/tmp}/kv-harness-test.XXXXXX")"
trap 'rm -rf "$BASE"' EXIT
BIN="$BASE/bin"; mkdir -p "$BIN"

# ---- fake openclaw：按消息模式产出 NotesVaulter 风格 JSON；写入日志以便断言是否被调用 ----
cat > "$BIN/openclaw" <<'SCRIPT'
#!/usr/bin/env bash
echo "$*" >> "${FAKE_OPENCLAW_LOG:?}"
out=""; prev=""
for a in "$@"; do
  if [[ "$prev" == "--message" ]]; then out="$a"; fi
  prev="$a"
done
vault="${VAULT_ROOT:?}"
id="${FAKE_SRC_ID:-$(date +%Y%m%d-%H%M%S)-abcd}"
if [[ "$out" == "想法："* ]]; then
  # idea (v1)
  mkdir -p "$vault/notes/ideas"
  printf '# idea %s\n' "$id" > "$vault/notes/ideas/$id.md"
  git -C "$vault" add "notes/ideas/$id.md"
  cat <<JSON
{"status":"ok","result":{"meta":{"stopReason":"stop","aborted":false,"toolSummary":{"calls":4,"failures":0},"finalAssistantVisibleText":"已保存 Source ID: $id"}}}
JSON
  exit 0
fi
if [[ "$out" != *"收："* ]]; then
  # raw (v1)
  cat <<'JSON'
{"status":"ok","result":{"meta":{"stopReason":"stop","aborted":false,"toolSummary":{"calls":2,"failures":0},"finalAssistantVisibleText":"OK，收到。"}}}
JSON
  exit 0
fi
# web：envelope 由 FAKE_WEB_ENVELOPE 控制
env="${FAKE_WEB_ENVELOPE:-sync}"
case "$env" in
  sync)
    mkdir -p "$vault/notes/web"
    printf '# web %s\n' "$id" > "$vault/notes/web/$id.md"
    git -C "$vault" add "notes/web/$id.md"
    cat <<JSON
{"status":"ok","result":{"meta":{"stopReason":"stop","aborted":false,"toolSummary":{"calls":5,"failures":0},"finalAssistantVisibleText":"已暂存并启动后台抓取 job_created Source ID: $id"}}}
JSON
    ;;
  async)
    # 异步：end_turn + yielded + 空回复 + 唯一新增暂存
    mkdir -p "$vault/notes/web"
    printf '# web %s\n' "$id" > "$vault/notes/web/$id.md"
    git -C "$vault" add "notes/web/$id.md"
    cat <<JSON
{"status":"ok","result":{"meta":{"stopReason":"end_turn","yielded":true,"aborted":false,"toolSummary":{"calls":5,"failures":0},"payloads":[{"text":""}]}}}
JSON
    ;;
  async_multi)
    # 两个不同 ID 的新增暂存 → 歧义
    id2="${FAKE_SRC_ID2:-$(date +%Y%m%d-%H%M%S)-xyzw}"
    mkdir -p "$vault/notes/web"
    printf '# a %s\n' "$id" > "$vault/notes/web/$id.md"
    git -C "$vault" add "notes/web/$id.md"
    printf '# b %s\n' "$id2" > "$vault/notes/web/$id2.md"
    git -C "$vault" add "notes/web/$id2.md"
    cat <<JSON
{"status":"ok","result":{"meta":{"stopReason":"end_turn","yielded":true,"aborted":false,"toolSummary":{"calls":6,"failures":0},"payloads":[{"text":""}]}}}
JSON
    ;;
esac
SCRIPT
chmod +x "$BIN/openclaw"

# ---- fake python3：仅拦截 inspect；强校验 --vault 匹配预期根；按 FAKE_INSPECT_STATUS 返回 ----
cat > "$BIN/python3" <<'SCRIPT'
#!/usr/bin/env bash
echo "$*" >> "${FAKE_PY_LOG:-/dev/null}"
if [[ "$*" == *" inspect "* ]]; then
  vault=""; prev=""
  for a in "$@"; do
    if [[ "$prev" == "--vault" ]]; then vault="$a"; fi
    prev="$a"
  done
  if [[ "$vault" != "${FAKE_VAULT_ROOT:?}" ]]; then
    echo '{"ok":false,"error":"vault mismatch"}'
    exit 1
  fi
  id=""; prev=""
  for a in "$@"; do
    if [[ "$prev" == "inspect" ]]; then id="$a"; fi
    prev="$a"
  done
  # 模拟 wait 期间新建并暂存 annotation/queue 等 ID 相关产物
  if [[ "${FAKE_INSPECT_EXTRA:-0}" == "1" && -n "$id" ]]; then
    mkdir -p "$vault/notes/web" "$vault/.queue/vault-capture"
    printf 'ann %s\n' "$id" > "$vault/notes/web/$id.annotation.md"
    git -C "$vault" add "notes/web/$id.annotation.md"
    printf 'q %s\n' "$id" > "$vault/.queue/vault-capture/$id.json"
    git -C "$vault" add ".queue/vault-capture/$id.json"
  fi
  cat <<JSON
{"ok":true,"ingest_status":"${FAKE_INSPECT_STATUS:-ready}","title":"t"}
JSON
  exit 0
fi
exec /usr/bin/python3 "$@"
SCRIPT
chmod +x "$BIN/python3"

# 新建一个 basename 以 -test 结尾、已 git init 的测试库
make_test_vault() { # $1=名字(须以 -test 结尾)
  local base="$BASE/$1"
  mkdir -p "$base"
  git -C "$base" init -q
  echo "$base"
}

# ---------- A: 非测试库被拒绝，且未调用 openclaw ----------
run_A() {
  local vault="$BASE/NotTestVault" log="$BASE/openclaw_A.log"
  mkdir -p "$vault"; git -C "$vault" init -q
  local rc
  set +e
  PATH="$BIN:$PATH" FAKE_OPENCLAW_LOG="$log" VAULT_ROOT="$vault" \
    bash "$HARNESS" idea "想法：x" >"$BASE/A.out" 2>&1
  rc=$?
  set -e
  if [[ $rc -ne 0 ]] && grep -q "拒绝" "$BASE/A.out" && [[ ! -s "$log" ]]; then
    pass "A: 非测试库被拒绝且未调用 openclaw"
  else
    fail "A: 非测试库护栏 (rc=$rc)"
  fi
}

# ---------- B: 重复 ID——已有文件+已有暂存，idea --assert 应失败；--cleanup 后文件与暂存保留 ----------
run_B() {
  local vault; vault="$(make_test_vault "Repeat-test")"
  local id="20260808-000000-repea" log="$BASE/openclaw_B.log"
  mkdir -p "$vault/notes/ideas"
  printf '# old %s\n' "$id" > "$vault/notes/ideas/$id.md"
  git -C "$vault" add "notes/ideas/$id.md"   # 模拟上一次已暂存
  local rc
  set +e
  PATH="$BIN:$PATH" FAKE_OPENCLAW_LOG="$log" FAKE_SRC_ID="$id" VAULT_ROOT="$vault" \
    bash "$HARNESS" idea "想法：重复" --assert --cleanup >"$BASE/B.out" 2>&1
  rc=$?
  set -e
  if [[ $rc -eq 1 ]] && grep -q "FAIL: 本次产生了含 Source ID 的新增暂存" "$BASE/B.out"; then
    pass "B: 重复 ID 断言失败(无新增暂存)"
  else
    fail "B: 重复 ID 断言应失败 (rc=$rc)"
  fi
  if [[ -f "$vault/notes/ideas/$id.md" ]] && git -C "$vault" diff --cached --name-only | grep -q "$id"; then
    pass "B: 清理后既有文件与暂存保留"
  else
    fail "B: 清理不应删除/取消既有文件与暂存"
  fi
}

# ---------- C: 全新 idea 断言通过；--cleanup 后本次文件与新增暂存消失 ----------
run_C() {
  local vault; vault="$(make_test_vault "Fresh-test")"
  local log="$BASE/openclaw_C.log" rc
  set +e
  PATH="$BIN:$PATH" FAKE_OPENCLAW_LOG="$log" VAULT_ROOT="$vault" \
    bash "$HARNESS" idea "想法：全新" --assert --cleanup >"$BASE/C.out" 2>&1
  rc=$?
  set -e
  if [[ $rc -eq 0 ]] && grep -q "PASS: 本次产生了含 Source ID 的新增暂存" "$BASE/C.out"; then
    pass "C: 全新 idea 断言通过"
  else
    fail "C: 全新 idea 断言 (rc=$rc)"
  fi
  local staged files
  staged="$(git -C "$vault" diff --cached --name-only || true)"
  files="$(cd "$vault" && find notes -type f 2>/dev/null || true)"
  if [[ -z "$staged" ]] && [[ -z "$files" ]]; then
    pass "C: cleanup 清除本次文件与新增暂存"
  else
    fail "C: cleanup 应清除本次产物 (staged=[$staged] files=[$files])"
  fi
}

# ---------- D: web 同步 --wait 显式传 --vault 并 ready 通过；cleanup 清除 ----------
run_D() {
  local vault; vault="$(make_test_vault "Web-test")"
  local log="$BASE/openclaw_D.log" pylog="$BASE/py_D.log" rc
  set +e
  PATH="$BIN:$PATH" FAKE_OPENCLAW_LOG="$log" FAKE_WEB_ENVELOPE=sync \
    FAKE_VAULT_ROOT="$vault" FAKE_INSPECT_STATUS=ready FAKE_PY_LOG="$pylog" VAULT_ROOT="$vault" \
    bash "$HARNESS" web "收：https://example.com/a" --wait 2 --assert --cleanup >"$BASE/D.out" 2>&1
  rc=$?
  set -e
  if [[ $rc -eq 0 ]] && grep -q "PASS: 终态 == ready" "$BASE/D.out"; then
    pass "D: web 同步 --wait ready 通过"
  else
    fail "D: web 同步 --wait (rc=$rc)"
  fi
  # (a) fake python3 必须收到真实 --vault root
  if [[ -f "$pylog" ]] && grep -q -- "--vault $vault inspect" "$pylog"; then
    pass "(a) fake python3 收到 --vault 指向测试库"
  else
    fail "(a) fake python3 未收到正确 --vault"
  fi
  local files; files="$(cd "$vault" && find notes -type f 2>/dev/null || true)"
  if [[ -z "$files" ]]; then
    pass "D: cleanup 清除 web 文件"
  else
    fail "D: web cleanup 应清除文件"
  fi
}

# ---------- E: raw 无 Source ID 按通用契约通过 ----------
run_E() {
  local vault; vault="$(make_test_vault "Raw-test")"
  local log="$BASE/openclaw_E.log" rc
  set +e
  PATH="$BIN:$PATH" FAKE_OPENCLAW_LOG="$log" VAULT_ROOT="$vault" \
    bash "$HARNESS" raw "随便聊聊" --assert --cleanup >"$BASE/E.out" 2>&1
  rc=$?
  set -e
  if [[ $rc -eq 0 ]] && grep -q "PASS: stopReason == stop/end_turn" "$BASE/E.out"; then
    pass "E: raw 通用契约通过"
  else
    fail "E: raw 通用契约 (rc=$rc)"
  fi
}

# ---------- (a2) fake python3 强校验 --vault：根不匹配必须失败 ----------
run_py_strict() {
  local rc
  set +e
  PATH="$BIN:$PATH" FAKE_VAULT_ROOT="/wrong/root" FAKE_PY_LOG="/dev/null" \
    bash "$BIN/python3" --vault /right/root inspect 20260808-000000-aaaa >"$BASE/PY.out" 2>&1
  rc=$?
  set -e
  if [[ $rc -eq 1 ]] && grep -q "vault mismatch" "$BASE/PY.out"; then
    pass "(a) fake python3 强校验 --vault 根"
  else
    fail "(a) fake python3 未强校验 --vault (rc=$rc)"
  fi
}

# ---------- (b) web 异步 yield：从唯一新增暂存恢复 ID，断言通过且 cleanup 清除 ----------
run_b_async() {
  local vault; vault="$(make_test_vault "Async-test")"
  local log="$BASE/openclaw_b.log" rc
  set +e
  PATH="$BIN:$PATH" FAKE_OPENCLAW_LOG="$log" FAKE_WEB_ENVELOPE=async \
    FAKE_VAULT_ROOT="$vault" FAKE_INSPECT_STATUS=ready VAULT_ROOT="$vault" \
    bash "$HARNESS" web "收：https://e.com/b" --wait 2 --assert --cleanup >"$BASE/b.out" 2>&1
  rc=$?
  set -e
  if [[ $rc -eq 0 ]] && grep -q "PASS: web 异步: yielded==true" "$BASE/b.out" \
     && grep -q "PASS: web 异步: 从唯一新增暂存恢复 ID" "$BASE/b.out" \
     && grep -q "(ID来源=staged)" "$BASE/b.out"; then
    pass "(b) web 异步从唯一新增暂存恢复 ID 且通过"
  else
    fail "(b) web 异步恢复 ID (rc=$rc)"
  fi
  local files; files="$(cd "$vault" && find notes -type f 2>/dev/null || true)"
  if [[ -z "$files" ]]; then
    pass "(b) cleanup 清除 web 异步产物"
  else
    fail "(b) web 异步 cleanup 应清除"
  fi
}

# ---------- (c) inspect=failed + --expect-status failed → PASS 并 cleanup ----------
run_c_failed_expected() {
  local vault; vault="$(make_test_vault "Fail-test")"
  local log="$BASE/openclaw_c.log" rc
  set +e
  PATH="$BIN:$PATH" FAKE_OPENCLAW_LOG="$log" FAKE_WEB_ENVELOPE=sync \
    FAKE_VAULT_ROOT="$vault" FAKE_INSPECT_STATUS=failed VAULT_ROOT="$vault" \
    bash "$HARNESS" web "收：https://e.com/c" --wait 2 --expect-status failed --assert --cleanup >"$BASE/c.out" 2>&1
  rc=$?
  set -e
  if [[ $rc -eq 0 ]] && grep -q "PASS: 终态 == failed" "$BASE/c.out"; then
    pass "(c) --expect-status failed 通过并 cleanup"
  else
    fail "(c) --expect-status failed (rc=$rc)"
  fi
  local files; files="$(cd "$vault" && find notes -type f 2>/dev/null || true)"
  if [[ -z "$files" ]]; then
    pass "(c) cleanup 清除 failed 产物"
  else
    fail "(c) failed cleanup 应清除"
  fi
}

# ---------- (d) inspect=failed + 默认 ready → FAIL ----------
run_d_default_ready_rejects() {
  local vault; vault="$(make_test_vault "Reject-test")"
  local log="$BASE/openclaw_d.log" rc
  set +e
  PATH="$BIN:$PATH" FAKE_OPENCLAW_LOG="$log" FAKE_WEB_ENVELOPE=sync \
    FAKE_VAULT_ROOT="$vault" FAKE_INSPECT_STATUS=failed VAULT_ROOT="$vault" \
    bash "$HARNESS" web "收：https://e.com/d" --wait 2 --assert --cleanup >"$BASE/d.out" 2>&1
  rc=$?
  set -e
  if [[ $rc -eq 1 ]] && grep -q "FAIL: 终态 == ready" "$BASE/d.out"; then
    pass "(d) 默认 ready 不接受 failed"
  else
    fail "(d) 默认 ready 应拒绝 failed (rc=$rc)"
  fi
}

# ---------- (e) 两个新增 staged ID：不猜 ID、断言失败、cleanup 不删/unstage 二者 ----------
run_e_ambiguous() {
  local vault; vault="$(make_test_vault "Ambig-test")"
  local id1="20260809-000001-aaaa" id2="20260809-000002-bbbb" log="$BASE/openclaw_e.log" rc
  set +e
  PATH="$BIN:$PATH" FAKE_OPENCLAW_LOG="$log" FAKE_WEB_ENVELOPE=async_multi \
    FAKE_SRC_ID="$id1" FAKE_SRC_ID2="$id2" \
    FAKE_VAULT_ROOT="$vault" FAKE_INSPECT_STATUS=ready VAULT_ROOT="$vault" \
    bash "$HARNESS" web "收：https://e.com/e" --wait 2 --assert --cleanup >"$BASE/e.out" 2>&1
  rc=$?
  set -e
  if [[ $rc -eq 1 ]] && grep -q "ID来源=ambiguous" "$BASE/e.out" && grep -q "FAIL" "$BASE/e.out"; then
    pass "(e) 多候选不猜 ID 且断言失败"
  else
    fail "(e) 多候选应断言失败 (rc=$rc)"
  fi
  if [[ -f "$vault/notes/web/$id1.md" && -f "$vault/notes/web/$id2.md" ]] \
     && git -C "$vault" diff --cached --name-only | grep -q "$id1" \
     && git -C "$vault" diff --cached --name-only | grep -q "$id2"; then
    pass "(e) cleanup 未删除/取消暂存二者"
  else
    fail "(e) cleanup 不应碰歧义候选"
  fi
  # 测试自身清除临时 repo 里的歧义产物
  rm -f "$vault/notes/web/$id1.md" "$vault/notes/web/$id2.md"
}

# ---------- (f) wait 期新增 annotation/queue；cleanup 后无残留且无新增 cached ----------
run_f_extra() {
  local vault; vault="$(make_test_vault "Extra-test")"
  local log="$BASE/openclaw_f.log" rc
  set +e
  PATH="$BIN:$PATH" FAKE_OPENCLAW_LOG="$log" FAKE_WEB_ENVELOPE=sync \
    FAKE_VAULT_ROOT="$vault" FAKE_INSPECT_STATUS=ready FAKE_INSPECT_EXTRA=1 VAULT_ROOT="$vault" \
    bash "$HARNESS" web "收：https://e.com/f" --wait 2 --assert --cleanup >"$BASE/f.out" 2>&1
  rc=$?
  set -e
  if [[ $rc -eq 0 ]] && grep -q "PASS: 终态 == ready" "$BASE/f.out"; then
    pass "(f) wait 期新增 annotation/queue 后断言通过"
  else
    fail "(f) wait 期新增产物断言 (rc=$rc)"
  fi
  local staged files
  staged="$(git -C "$vault" diff --cached --name-only || true)"
  files="$(cd "$vault" && find notes .queue -type f 2>/dev/null || true)"
  if [[ -z "$staged" ]] && [[ -z "$files" ]]; then
    pass "(f) cleanup 清除 annotation/queue 且无新增 cached"
  else
    fail "(f) cleanup 残留 (staged=[$staged] files=[$files])"
  fi
}

run_A
run_B
run_C
run_D
run_E
run_py_strict
run_b_async
run_c_failed_expected
run_d_default_ready_rejects
run_e_ambiguous
run_f_extra

# 清理本测试在 out/ 下新增的文件(保留测试前已存在的)
(cd "$OUT_DIR" && for f in *.json *.json.err; do
  [[ -f "$f" ]] || continue
  if ! grep -qxF "$f" <<<"$PRE_OUT" 2>/dev/null; then rm -f -- "$f"; fi
done) 2>/dev/null || true

echo "----------------------------"
echo "通过 $PASS_N 项，失败 $FAIL_N 项"
[[ "$FAIL_N" -eq 0 ]]
