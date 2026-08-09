#!/usr/bin/env bash
# ============================================================
# AI Daily Digest — horizon 版 (無互動)
# 由 launchd 或 cron 觸發，不需要使用者手動操作
# ============================================================
set -euo pipefail

# launchd 預設 C locale → bash 的 ${#msg} / ${msg:0:N} 會按「位元組」算，
# 中文報告超過 4000 bytes 時 telegram_send 的截斷會把多位元組字切一半，
# 導致 Telegram 回 400「strings must be encoded in UTF-8」。強制 UTF-8 locale
# 讓字串運算改以「字元」為單位（截斷也落在字元邊界）。
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"

HORIZON_DIR="/Users/yankesswang/Desktop/Projects/Arthur_App/arthur_knowledge_assistant/digest/ai/horizon"
LOG_DIR="$HOME/Library/Logs/ai-digest"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$(date +%Y-%m-%d).log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

LINE_NOTIFY_SH="/Users/yankesswang/Projects/Arthur_App/scripts/lib/line_notify.sh"
[ -f "$LINE_NOTIFY_SH" ] && source "$LINE_NOTIFY_SH"

# ── 讀取 Telegram 憑證
GOLEM_ENV="$HOME/.config/digest/.env"
[ ! -f "$GOLEM_ENV" ] && GOLEM_ENV="/Users/yankesswang/Desktop/Projects/Arthur_App/.env"
TELEGRAM_TOKEN=""
TELEGRAM_ADMIN_ID=""
if [ -f "$GOLEM_ENV" ]; then
    TELEGRAM_TOKEN=$(grep '^TELEGRAM_TOKEN=' "$GOLEM_ENV" | cut -d= -f2- || true)
    TELEGRAM_ADMIN_ID=$(grep '^ADMIN_ID=' "$GOLEM_ENV" | cut -d= -f2- || true)
fi

telegram_send() {
    local msg="$1"
    local kind="${2:-general}"
    local telegram_msg="$msg"
    if [ -z "${TELEGRAM_TOKEN:-}" ] || [ -z "${TELEGRAM_ADMIN_ID:-}" ]; then
        log "Telegram 通知略過：未設定 token"
    else
        if [ ${#telegram_msg} -gt 4000 ]; then telegram_msg="${telegram_msg:0:4000}…"; fi
        local tmp http_code
        tmp="$(mktemp)"
        http_code=$(curl -sS -o "$tmp" -w "%{http_code}" \
            -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
            --data-urlencode "chat_id=${TELEGRAM_ADMIN_ID}" \
            --data-urlencode "text=${telegram_msg}" \
            2>> "$LOG" || true)
        if [ "$http_code" = "200" ]; then
            log "✅ Telegram 發送成功"
        else
            log "⚠️  Telegram 失敗 HTTP ${http_code}: $(cut -c1-200 "$tmp")"
        fi
        rm -f "$tmp"
    fi
    declare -F line_notify_text >/dev/null 2>&1 && line_notify_text "$msg" "$kind"
}

log "========== AI Digest Start =========="

cd "$HORIZON_DIR"

if ! /Users/yankesswang/.local/bin/uv run horizon >> "$LOG" 2>&1; then
    log "ERROR: horizon pipeline 執行失敗"
    telegram_send "❌ AI Digest 失敗（$(date '+%Y-%m-%d %H:%M')）
請查看 log：$LOG"
    exit 1
fi

TODAY=$(date +%Y-%m-%d)
# horizon 用 UTC 時間命名，找最新輸出避免時區差
HORIZON_DATE=$(ls -t "$HORIZON_DIR/data/summaries/" 2>/dev/null | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' | head -1 || echo "$TODAY")
SRC_DIR="$HORIZON_DIR/data/summaries/$HORIZON_DATE"
SRC_FLAT=$(ls -t "$HORIZON_DIR/data/summaries/horizon-"*"-zh-tw.md" 2>/dev/null | head -1 || true)
DST_DIGEST="/Users/yankesswang/Documents/arthurwang_DB/Digest/ai/$TODAY/"
DST_OBSIDIAN="/Users/yankesswang/Documents/arthurwang_DB/AI Knowledge/Digest/$TODAY/"

if [ -d "$SRC_DIR" ] || [ -f "$SRC_FLAT" ]; then
    mkdir -p "$DST_DIGEST" "$DST_OBSIDIAN"
    # cp + retry (NOT python shutil) — writing ~/Documents under launchd hits
    # intermittent EDEADLK "Resource deadlock avoided"; cp with retries is stable.
    sync_ok=1
    for DST in "$DST_DIGEST" "$DST_OBSIDIAN"; do
        mkdir -p "$DST"
        if [ -d "$SRC_DIR" ]; then
            for f in "$SRC_DIR"/*; do
                [ -f "$f" ] || continue
                base=$(basename "$f")
                copied=0
                for attempt in 1 2 3 4 5; do
                    if cp -f "$f" "$DST$base" 2>>"$LOG"; then copied=1; break; fi
                    sleep 1
                done
                [ "$copied" = 1 ] || { sync_ok=0; log "WARNING: 複製失敗 $base → $DST"; }
            done
        elif [ -f "$SRC_FLAT" ]; then
            base=$(basename "$SRC_FLAT")
            copied=0
            for attempt in 1 2 3 4 5; do
                if cp -f "$SRC_FLAT" "$DST$base" 2>>"$LOG"; then copied=1; break; fi
                sleep 1
            done
            [ "$copied" = 1 ] || sync_ok=0
        fi
    done
    [ "$sync_ok" = 1 ] && log "✅ Synced → Digest/ai/$TODAY & AI Knowledge/Digest/$TODAY" || log "WARNING: sync 部分失敗"
else
    log "WARNING: 找不到今日輸出（$SRC_DIR 或 $SRC_FLAT），跳過 sync"
fi

# ── 整理成「可直讀摘要報」：跨分類彙整 Top 8，每篇 2~3 句中文摘要 ──
# 來源優先用資料夾（含各分類 .md），退回 flat file。報告由 python 切成
# ≤Telegram 上限的數個 chunk，逐則發送，使用者不必點進文章就讀得懂。
REPORT_SRC="$SRC_DIR"
[ -d "$REPORT_SRC" ] || REPORT_SRC="$SRC_FLAT"

CHUNK_FILES=$(python3 "$HOME/Library/Scripts/ai-digest-report.py" "$REPORT_SRC" "$TODAY" 8 2>>"$LOG" || true)

log "========== AI Digest Done =========="

if [ -n "$CHUNK_FILES" ]; then
    sent=0
    while IFS= read -r cf; do
        [ -f "$cf" ] || continue
        telegram_send "$(cat "$cf")" report
        rm -f "$cf"
        sent=$((sent + 1))
        sleep 1
    done <<< "$CHUNK_FILES"
    log "✅ 已發送摘要報 ${sent} 則"
else
    log "WARNING: 報告萃取失敗，改發簡訊版"
    telegram_send "📰 AI Digest — ${TODAY}
（今日報告萃取失敗，請改看 Obsidian）
📂 AI Knowledge/Digest/${TODAY}/" report
fi
