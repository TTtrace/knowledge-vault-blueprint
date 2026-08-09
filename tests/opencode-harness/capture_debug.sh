#!/usr/bin/env bash
# capture_debug.sh — opencode 调试 vault-capture skill 的 harness
# 用法:
#   ./capture_debug.sh idea "想法：测试内容" [--assert] [--cleanup] [--session <key>] [--wait <秒>]
#   ./capture_debug.sh web  "收：https://..."   [--assert] [--cleanup] [--session <key>] [--wait <秒>] [--expect-status <s>]
#   ./capture_debug.sh raw  "任意消息"          [--assert] [--cleanup] [--session <key>] [--wait <秒>]
# --expect-status 仅允许 mode=web 且 --wait>0；取值 ready|failed|manual|terminal，默认 ready。
# 输出: 原始 JSON 存入 out/<timestamp>.json, 终端打印关键字段; --assert 时以退出码表示通过与否
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_DIR="$SCRIPT_DIR/out"
mkdir -p "$OUT_DIR"

MODE="${1:-}"; MSG="${2:-}"; shift 2 || true
ASSERT=0; CLEANUP=0; WAIT=0; SESSION_KEY="opencode-debug"
EXPECT_STATUS="ready"; EXPECT_SET=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --assert) ASSERT=1 ;;
    --cleanup) CLEANUP=1 ;;
    --wait) WAIT="${2:-}"; [[ "$WAIT" =~ ^[0-9]+$ ]] || { echo "!! --wait 需要秒数(正整数)" >&2; exit 2; }; shift ;;
    --session) SESSION_KEY="$2"; shift ;;
    --expect-status)
      EXPECT_SET=1; EXPECT_STATUS="${2:-}"
      case "$EXPECT_STATUS" in ready|failed|manual|terminal) ;; *)
        echo "!! --expect-status 需要 ready|failed|manual|terminal" >&2; exit 2 ;; esac
      shift ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
  shift
done

[[ -z "$MODE" || -z "$MSG" ]] && { echo "用法: $0 <idea|web|raw> <消息> [--assert] [--cleanup] [--session <key>] [--wait <秒>] [--expect-status ready|failed|manual|terminal]" >&2; exit 2; }
case "$MODE" in idea|web|raw) ;; *) echo "!! MODE 必须是 idea|web|raw" >&2; exit 2 ;; esac

VAULT_ROOT="${VAULT_ROOT:-/home/monottx/repos/SourceNotes-test}"
echo "==> VAULT_ROOT = $VAULT_ROOT"

# ---- STEP-01 前置护栏：必须在 openclaw 调用前完成 ----
# --expect-status 仅允许 mode=web 且 --wait>0
if [[ "$EXPECT_SET" == 1 && ( "$MODE" != "web" || "$WAIT" -eq 0 ) ]]; then
  echo "!! --expect-status 仅允许 mode=web 且 --wait>0" >&2; exit 2
fi
for dep in jq openclaw python3 git; do
  command -v "$dep" >/dev/null 2>&1 || { echo "!! 缺少依赖: $dep" >&2; exit 1; }
done
[[ -d "$VAULT_ROOT" ]] || { echo "!! VAULT_ROOT 不是目录: $VAULT_ROOT" >&2; exit 1; }
git -C "$VAULT_ROOT" rev-parse --git-dir >/dev/null 2>&1 || { echo "!! VAULT_ROOT 不是 Git 仓库: $VAULT_ROOT" >&2; exit 1; }
# 严格测试库护栏：basename 必须以 -test 结尾，否则在调用 openclaw 之前拒绝
if [[ "$(basename "$VAULT_ROOT")" != *"-test" ]]; then
  echo "!! 拒绝: VAULT_ROOT 必须以 -test 结尾(严格测试库护栏): $VAULT_ROOT" >&2
  exit 1
fi

# ---- STEP-02 调用前基线记录 ----
TMP="$(mktemp -d "${TMPDIR:-/tmp}/capture-debug.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
PRE_STAGED_FILE="$TMP/pre_staged"
POST_STAGED_FILE="$TMP/post_staged"
PRE_FILES_FILE="$TMP/pre_files"
POST_FILES_FILE="$TMP/post_files"
STAGED_NEW_ALL="$TMP/staged_new_all"   # 基线后新增的全部 staged 路径(NUL 分隔, 未按 ID 过滤)
STAGED_NEW="$TMP/staged_new"           # 基线后新增、含 SRC_ID 的暂存路径(NUL 分隔)
FILES_NEW="$TMP/files_new"             # 调用前不存在、当前仍存在、含 SRC_ID 的新建文件(NUL 分隔)
: > "$STAGED_NEW"; : > "$FILES_NEW"

# 调用前：记录已暂存路径与全部文件存在性(相对路径, NUL 分隔以正确容纳空格/Unicode/换行)
git -C "$VAULT_ROOT" diff --cached --name-only -z > "$PRE_STAGED_FILE" 2>/dev/null || true
(cd "$VAULT_ROOT" && find . -type f -not -path './.git/*' -print0) > "$PRE_FILES_FILE" 2>/dev/null || true

# 相对调用前基线，重算本次新增暂存/新建文件(均含 SRC_ID)。$1=post staged 文件, $2=post files 文件。
recompute_new() {
  : > "$STAGED_NEW"; : > "$FILES_NEW"
  NEW_STAGED_CNT=0; NEW_FILES_CNT=0
  if [[ -n "$SRC_ID" ]]; then
    sort -z -u "$PRE_STAGED_FILE" -o "$TMP/sorted_pre_staged" 2>/dev/null || true
    sort -z -u "$1" -o "$TMP/sorted_post_staged" 2>/dev/null || true
    comm -z -13 "$TMP/sorted_pre_staged" "$TMP/sorted_post_staged" 2>/dev/null > "$STAGED_NEW" || true
    grep -z -F -- "$SRC_ID" "$STAGED_NEW" > "$TMP/_sn" 2>/dev/null || true; mv "$TMP/_sn" "$STAGED_NEW"
    sort -z -u "$PRE_FILES_FILE" -o "$TMP/sorted_pre_files" 2>/dev/null || true
    sort -z -u "$2" -o "$TMP/sorted_post_files" 2>/dev/null || true
    comm -z -13 "$TMP/sorted_pre_files" "$TMP/sorted_post_files" 2>/dev/null > "$FILES_NEW" || true
    grep -z -F -- "$SRC_ID" "$FILES_NEW" > "$TMP/_fn" 2>/dev/null || true; mv "$TMP/_fn" "$FILES_NEW"
    # 只保留当前仍存在的文件
    : > "$TMP/_fn_exist"
    while IFS= read -r -d '' p; do
      [[ -n "$p" && -e "$VAULT_ROOT/$p" ]] && printf '%s\0' "$p" >> "$TMP/_fn_exist"
    done < "$FILES_NEW"
    mv "$TMP/_fn_exist" "$FILES_NEW"
    NEW_STAGED_CNT="$(tr -d -c '\0' < "$STAGED_NEW" | wc -c)"
    NEW_FILES_CNT="$(tr -d -c '\0' < "$FILES_NEW" | wc -c)"
  fi
}

TS="$(date +%Y%m%d-%H%M%S)"
OUT_JSON="$OUT_DIR/${TS}-${MODE}.json"

echo "==> 调用 NotesVaulter (mode=$MODE, session=$SESSION_KEY)"
openclaw agent --agent notesvaulter --session-key "$SESSION_KEY" --message "$MSG" --json > "$OUT_JSON" 2>"$OUT_JSON.err" || {
  echo "!! openclaw 调用失败, stderr:"; cat "$OUT_JSON.err"; exit 1;
}

# ---- STEP-02b 调用后快照与 ID 确定 ----
git -C "$VAULT_ROOT" diff --cached --name-only -z > "$POST_STAGED_FILE" 2>/dev/null || true
(cd "$VAULT_ROOT" && find . -type f -not -path './.git/*' -print0) > "$POST_FILES_FILE" 2>/dev/null || true

TEXT="$(jq -r '.result.meta.finalAssistantVisibleText // .result.payloads[0].text // empty' "$OUT_JSON")"
STOP="$(jq -r '.result.meta.stopReason // empty' "$OUT_JSON")"
FAILS="$(jq -r '.result.meta.toolSummary.failures // empty' "$OUT_JSON")"
CALLS="$(jq -r '.result.meta.toolSummary.calls // 0' "$OUT_JSON")"
ABORTED="$(jq -r 'if (.result.meta.aborted // false) == true then "true" else "false" end' "$OUT_JSON")"
YIELDED="$(jq -r '.result.meta.yielded // empty' "$OUT_JSON")"

# 基线后新增的全部 staged 路径(未按 ID 过滤)，用于 web 无 ID 时恢复
sort -z -u "$PRE_STAGED_FILE" -o "$TMP/sorted_pre_staged" 2>/dev/null || true
sort -z -u "$POST_STAGED_FILE" -o "$TMP/sorted_post_staged" 2>/dev/null || true
comm -z -13 "$TMP/sorted_pre_staged" "$TMP/sorted_post_staged" 2>/dev/null > "$STAGED_NEW_ALL" || true

# ID 确定：先尝试从 TEXT 提取（Source ID / 记录 ID / 反引号 / 路径 均覆盖）
SRC_ID="$(printf '%s' "$TEXT" | grep -oP '[0-9]{8}-[0-9]{6}-[a-z0-9]{4}' | head -1 || true)"
ID_SRC="none"
if [[ -n "$SRC_ID" ]]; then
  ID_SRC="text"
elif [[ "$MODE" == "web" ]]; then
  # web 无 ID 时从基线后新增 staged 路径中提取唯一 Source ID；零/多候选视为 none/ambiguous
  declare -A _IDS=()
  while IFS= read -r -d '' p; do
    [[ -n "$p" ]] || continue
    local_id="$(printf '%s' "$(basename "$p")" | grep -oP '[0-9]{8}-[0-9]{6}-[a-z0-9]{4}' | head -1 || true)"
    [[ -n "$local_id" ]] && _IDS["$local_id"]=1
  done < "$STAGED_NEW_ALL"
  if [[ "${#_IDS[@]}" -eq 1 ]]; then
    SRC_ID="${!_IDS[@]}"; ID_SRC="staged"
  elif [[ "${#_IDS[@]}" -gt 1 ]]; then
    ID_SRC="ambiguous"
  else
    ID_SRC="none"
  fi
  unset _IDS
fi

recompute_new "$POST_STAGED_FILE" "$POST_FILES_FILE"

echo "--- agent 回复 ---"
printf '%s\n' "$TEXT"
echo "--- 元信息 ---"
echo "stopReason=$STOP  aborted=$ABORTED  yielded=${YIELDED:-<缺省>}  toolCalls=$CALLS  toolFailures=${FAILS:-<缺省>}  sourceId=${SRC_ID:-<none>}  (ID来源=$ID_SRC)"
echo "本次新增暂存路径(含ID)=${NEW_STAGED_CNT}  本次新建文件(含ID)=${NEW_FILES_CNT}  expect-status=$EXPECT_STATUS"
echo "原始 JSON: $OUT_JSON"

# ---- STEP-04 --wait 轮询：显式传 --vault，不依赖环境变量 ----
INSPECT_SCRIPT="$REPO_ROOT/skills/vault-capture/scripts/vault_capture.py"
FINAL_STATUS=""
if [[ "$WAIT" -gt 0 && -n "$SRC_ID" ]]; then
  echo "--- 等待终态 (id=$SRC_ID, timeout=${WAIT}s, expect=$EXPECT_STATUS) ---"
  deadline=$(( $(date +%s) + WAIT ))
  while :; do
    INSP="$(python3 "$INSPECT_SCRIPT" --vault "$VAULT_ROOT" inspect "$SRC_ID" 2>/dev/null || true)"
    FINAL_STATUS="$(printf '%s' "$INSP" | jq -r '.ingest_status // empty' 2>/dev/null || true)"
    if [[ "$FINAL_STATUS" == "ready" || "$FINAL_STATUS" == "failed" || "$FINAL_STATUS" == "manual" ]]; then
      echo "终态: $FINAL_STATUS"
      break
    fi
    if [[ "$(date +%s)" -ge "$deadline" ]]; then
      echo "!! 轮询超时(${WAIT}s)，最近状态: ${FINAL_STATUS:-<未知>}"
      FINAL_STATUS="timeout"
      break
    fi
    sleep 2
  done
fi

# ---- STEP-03 断言(移除 eval，显式比较) ----
PASS=0
check() { # $1=标签  $2=1 通过 / 0 失败
  if [[ "$2" == "1" ]]; then echo "PASS: $1"; else echo "FAIL: $1"; PASS=1; fi
}

if [[ "$ASSERT" == 1 ]]; then
  echo "--- 断言 ---"
  if [[ "$MODE" == "idea" ]]; then
    check "stopReason == stop"        "$([[ "$STOP" == "stop" ]] && echo 1 || echo 0)"
    check "未被 abort"                 "$([[ "$ABORTED" != "true" ]] && echo 1 || echo 0)"
    check "toolFailures 存在且==0"     "$([[ "$FAILS" == "0" ]] && echo 1 || echo 0)"
    check "回复非空"                   "$([[ -n "$TEXT" ]] && echo 1 || echo 0)"
    check "拿到 Source ID"             "$([[ -n "$SRC_ID" ]] && echo 1 || echo 0)"
    check "已落盘 (saved/ready/created)" "$(printf '%s' "$TEXT" | grep -qE '已保存|ready|created|已落盘' && echo 1 || echo 0)"
    if [[ -n "$SRC_ID" ]]; then
      if compgen -G "$VAULT_ROOT/notes/ideas/*${SRC_ID}*" >/dev/null; then
        check "文件存在于 notes/ideas" 1
      else
        check "文件存在于 notes/ideas" 0
      fi
      check "本次产生了含 Source ID 的新增暂存" "$([[ "$NEW_STAGED_CNT" -gt 0 ]] && echo 1 || echo 0)"
    fi
  elif [[ "$MODE" == "web" ]]; then
    # 同步/异步两种 envelope 共同要求
    check "未被 abort"                 "$([[ "$ABORTED" != "true" ]] && echo 1 || echo 0)"
    check "toolFailures 存在且==0"     "$([[ "$FAILS" == "0" ]] && echo 1 || echo 0)"
    if [[ "$STOP" == "stop" ]]; then
      # 同步 envelope：stop + 非空回复 + ID
      check "web 同步: stop + 回复非空" "$([[ -n "$TEXT" ]] && echo 1 || echo 0)"
      check "拿到 Source ID"            "$([[ -n "$SRC_ID" ]] && echo 1 || echo 0)"
      check "已暂存或启动后台抓取"       "$(printf '%s' "$TEXT" | grep -qE '暂存|后台|抓取|staged|job' && echo 1 || echo 0)"
    elif [[ "$STOP" == "end_turn" ]]; then
      # 异步 envelope：end_turn + yielded==true + 从唯一新增 staged 路径恢复 ID
      check "web 异步: yielded==true"   "$([[ "$YIELDED" == "true" ]] && echo 1 || echo 0)"
      check "web 异步: 从唯一新增暂存恢复 ID" "$([[ "$ID_SRC" == "staged" && -n "$SRC_ID" ]] && echo 1 || echo 0)"
    else
      check "web stopReason 合法(stop/end_turn)" 0
    fi
    if [[ -n "$SRC_ID" ]]; then
      check "本次产生了含 Source ID 的新增暂存" "$([[ "$NEW_STAGED_CNT" -gt 0 ]] && echo 1 || echo 0)"
    fi
    if [[ "$WAIT" -gt 0 ]]; then
      if [[ "$EXPECT_STATUS" == "terminal" ]]; then
        check "终态为终态(ready/failed/manual)" "$([[ "$FINAL_STATUS" == "ready" || "$FINAL_STATUS" == "failed" || "$FINAL_STATUS" == "manual" ]] && echo 1 || echo 0)"
      else
        check "终态 == $EXPECT_STATUS" "$([[ "$FINAL_STATUS" == "$EXPECT_STATUS" ]] && echo 1 || echo 0)"
      fi
    fi
  else # raw：仅通用健康检查
    check "stopReason == stop/end_turn" "$([[ "$STOP" == "stop" || "$STOP" == "end_turn" ]] && echo 1 || echo 0)"
    check "未被 abort"                  "$([[ "$ABORTED" != "true" ]] && echo 1 || echo 0)"
    check "toolFailures 存在且==0"      "$([[ "$FAILS" == "0" ]] && echo 1 || echo 0)"
    check "回复非空"                    "$([[ -n "$TEXT" ]] && echo 1 || echo 0)"
  fi
fi

# ---- STEP-05 cleanup：相对调用前基线重算，仅处理基线后新增内容 ----
if [[ "$CLEANUP" == 1 ]]; then
  echo "--- 清理(仅本次新增暂存与新建文件, 相对调用前基线重算) ---"
  if [[ -n "$SRC_ID" && "$ID_SRC" != "ambiguous" ]]; then
    # 重算当前差异，纳入 wait 期间新建/暂存的 annotation/assets/queue
    git -C "$VAULT_ROOT" diff --cached --name-only -z > "$POST_STAGED_FILE" 2>/dev/null || true
    (cd "$VAULT_ROOT" && find . -type f -not -path './.git/*' -print0) > "$POST_FILES_FILE" 2>/dev/null || true
    recompute_new "$POST_STAGED_FILE" "$POST_FILES_FILE"
    # 只 unstage 基线后新增、含 SRC_ID 的 staged path；用 `git reset -- <path>`(无 HEAD commit 也安全)
    while IFS= read -r -d '' p; do
      [[ -n "$p" ]] && git -C "$VAULT_ROOT" reset -q -- "$p" || true
    done < "$STAGED_NEW"
    # 只删除调用前不存在、当前仍存在、含 SRC_ID 的新建文件
    while IFS= read -r -d '' p; do
      [[ -n "$p" ]] && rm -f -- "$VAULT_ROOT/$p" || true
    done < "$FILES_NEW"
    echo "已清理: 新增暂存=$NEW_STAGED_CNT, 新建文件=$NEW_FILES_CNT"
  else
    echo "(SRC_ID 缺失或歧义, 跳过清理, 不碰任何候选)"
  fi
fi

[[ "$ASSERT" == 1 && "$PASS" == 1 ]] && exit 1
exit 0
