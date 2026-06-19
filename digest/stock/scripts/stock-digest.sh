#!/bin/bash
# Daily Stock Digest — run at 08:00 via LaunchAgent

set -e

LOG_DIR="$HOME/Library/Logs/stock-digest"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$(date +%Y-%m-%d).log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

# ── 讀取 Telegram 憑證
GOLEM_ENV="$HOME/.config/digest/.env"
[ ! -f "$GOLEM_ENV" ] && GOLEM_ENV="/Users/yankesswang/Desktop/Projects/Arthur_App/.env"
TELEGRAM_TOKEN=""
ADMIN_ID=""
if [ -f "$GOLEM_ENV" ]; then
    TELEGRAM_TOKEN=$(grep '^TELEGRAM_TOKEN=' "$GOLEM_ENV" | cut -d= -f2- || true)
    ADMIN_ID=$(grep '^ADMIN_ID=' "$GOLEM_ENV" | cut -d= -f2- || true)
fi

telegram_send() {
    local msg="$1"
    if [ -z "${TELEGRAM_TOKEN:-}" ] || [ -z "${ADMIN_ID:-}" ]; then
        log "Telegram 通知略過：未設定 token"
        return 0
    fi
    if [ ${#msg} -gt 4000 ]; then msg="${msg:0:4000}…"; fi
    local tmp http_code
    tmp="$(mktemp)"
    http_code=$(curl -sS -o "$tmp" -w "%{http_code}" \
        -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${ADMIN_ID}" \
        --data-urlencode "text=${msg}" \
        2>> "$LOG" || true)
    if [ "$http_code" = "200" ]; then
        log "✅ Telegram 發送成功"
    else
        log "⚠️  Telegram 失敗 HTTP ${http_code}: $(cat "$tmp" | cut -c1-200)"
    fi
    rm -f "$tmp"
}

# 從 md 檔案萃取指定 section 的內容（到下一個頂層 --- 或同層 ## 為止）
extract_section() {
    local file="$1" pattern="$2" lines="${3:-8}"
    awk -v pat="$pattern" -v n="$lines" '
        $0 ~ pat { found=1; count=0; depth=0; next }
        found && /^---$/ { exit }
        found && /^# / { exit }
        found && count >= n { exit }
        found {
            if ($0 !~ /^[[:space:]]*$/ && $0 !~ /^\|[-|]+\|/) {
                print; count++
            }
        }
    ' "$file" 2>/dev/null || true
}

# ── 主流程 ──
log "========== Stock Digest Start =========="

cd /Users/yankesswang/Desktop/Projects/Arthur_App/arthur_knowledge_assistant/digest/stock/horizon

if ! /Users/yankesswang/.local/bin/uv run horizon >> "$LOG" 2>&1; then
    log "ERROR: horizon pipeline 執行失敗"
    telegram_send "❌ *Stock Digest 失敗*（$(date '+%Y-%m-%d %H:%M')）
請查看 log：$LOG"
    exit 1
fi

# Sync to Digest
TODAY=$(date +%Y-%m-%d)
# horizon 用 UTC 時間命名，找最新輸出避免時區差
STOCK_HORIZON_SUMMARIES="/Users/yankesswang/Desktop/Projects/Arthur_App/arthur_knowledge_assistant/digest/stock/horizon/data/summaries"
HORIZON_DATE=$(ls -t "$STOCK_HORIZON_SUMMARIES/" 2>/dev/null | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' | head -1 || echo "$TODAY")
SRC="$STOCK_HORIZON_SUMMARIES/$HORIZON_DATE/"
DST="/Users/yankesswang/Documents/arthurwang_DB/Digest/stock/$HORIZON_DATE/"

if [ -d "$SRC" ]; then
    mkdir -p "$DST"
    # 用 cp + 重試（Python/Node 寫 ~/Documents 在 launchd 下會機率性 EDEADLK；cp 較穩，重試保底）
    sync_ok=1
    for f in "$SRC"*; do
        [ -f "$f" ] || continue
        base=$(basename "$f")
        copied=0
        for attempt in 1 2 3 4 5; do
            if cp -f "$f" "$DST$base" 2>>"$LOG"; then copied=1; break; fi
            sleep 1
        done
        [ "$copied" = 1 ] || { sync_ok=0; log "WARNING: 複製失敗 $base"; }
    done
    [ "$sync_ok" = 1 ] && log "✅ Synced to Digest/stock/$HORIZON_DATE" || log "WARNING: sync 部分失敗"
fi

# ── 從報告萃取重點 ──
REPORT="${SRC}📊 今日市場報告.md"
PORTFOLIO="${SRC}📊 Portfolio.md"

ONE_LINER=""
MACRO_SECTION=""
EARNINGS_TABLE=""
SEMI_SECTION=""
ACTION_LIST=""

if [ -f "$REPORT" ]; then
    ONE_LINER=$(grep -A2 "▌今日一句話" "$REPORT" 2>/dev/null \
        | grep -v "▌今日一句話" | head -1 | sed 's/^[[:space:]]*//')

    # Macro：取前 6 行非空內容
    MACRO_SECTION=$(extract_section "$REPORT" "Macro / 總經 — 完整分析" 6)

    # 財報表格：取表頭+前5行資料
    EARNINGS_TABLE=$(awk '/💰 財報.*摘要/{found=1} found && /\|/{print; count++} count>6{exit}' "$REPORT" 2>/dev/null | head -8 || true)

    # AI/半導體摘要：取前 5 行
    SEMI_SECTION=$(extract_section "$REPORT" "🤖 AI / 半導體摘要" 5)

    # 行動清單
    ACTION_LIST=$(extract_section "$REPORT" "💡 今日行動清單" 6)
fi

# ── 持倉今日漲跌（從 Portfolio 總表撈，按漲跌排序）──
MOVERS=""
if [ -f "$PORTFOLIO" ]; then
    # 格式：| TICKER | 持股 | 均價 | 現價 | 今日漲跌 | ...
    MOVERS=$(grep -E "^\| [A-Z]{2,5} " "$PORTFOLIO" \
        | awk -F'|' '{
            ticker=$2; price=$5; chg=$6
            gsub(/ /,"",ticker); gsub(/ /,"",price); gsub(/ /,"",chg)
            if (chg ~ /[+-][0-9]/) print chg "\t" ticker "\t" price
        }' \
        | sort -t'%' -k1 -n \
        | awk '{printf "  %-6s %-10s %s\n", $2, $3, $1}' \
        | head -12 2>/dev/null || true)
fi

# ── Token 使用量 ──
TOKENS=$(grep "Token usage this run" "$LOG" | tail -1 | grep -oE '[0-9,]+ tokens' | head -1 || echo "")

# ── 組合訊息（分段，保持可讀性）──
MSG="📊 *Stock Digest — ${TODAY}*

${ONE_LINER:+▌ ${ONE_LINER}
}"

if [ -n "$MACRO_SECTION" ]; then
MSG="${MSG}
━━━━━━━━━━━━
📊 *Macro*
${MACRO_SECTION}"
fi

if [ -n "$EARNINGS_TABLE" ]; then
MSG="${MSG}
━━━━━━━━━━━━
💰 *財報摘要*
${EARNINGS_TABLE}"
fi

if [ -n "$SEMI_SECTION" ]; then
MSG="${MSG}
━━━━━━━━━━━━
🤖 *AI / 半導體*
${SEMI_SECTION}"
fi

if [ -n "$MOVERS" ]; then
MSG="${MSG}
━━━━━━━━━━━━
📉 *持倉今日漲跌*
${MOVERS}"
fi

if [ -n "$ACTION_LIST" ]; then
MSG="${MSG}
━━━━━━━━━━━━
💡 *行動清單*
${ACTION_LIST}"
fi

MSG="${MSG}
━━━━━━━━━━━━
📂 投資/Stock Digest/${TODAY}/
${TOKENS:+🧮 ${TOKENS}}"

log "========== Stock Digest Done =========="
telegram_send "$MSG"
