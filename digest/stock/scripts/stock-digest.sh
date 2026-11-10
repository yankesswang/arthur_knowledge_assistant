#!/bin/bash
# Daily Stock Digest — run at 08:00 via LaunchAgent

set -e

# launchd 預設 C locale → bash 字串運算按位元組算，中文訊息截斷時會切壞多位元組
# 字元，Telegram 回 400「strings must be encoded in UTF-8」。強制 UTF-8 改以字元為單位。
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"

LOG_DIR="$HOME/Library/Logs/stock-digest"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$(date +%Y-%m-%d).log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

LINE_NOTIFY_SH="/Users/yankesswang/Projects/Arthur_App/scripts/lib/line_notify.sh"
[ -f "$LINE_NOTIFY_SH" ] && source "$LINE_NOTIFY_SH"

# ── 模式判斷 ──
# daily（預設，週一～五 07:00）：近 24h 日報
# weekly（週六 10:00）：整周復盤，回看 7 天（168h），確保涵蓋週五美股收盤
MODE="${1:-daily}"
if [ "$MODE" = "weekly" ]; then
    HORIZON_ARGS="--hours 168"
    DIGEST_LABEL="整周復盤"
    DIGEST_EMOJI="🗓️"
else
    HORIZON_ARGS=""
    DIGEST_LABEL="Stock Digest"
    DIGEST_EMOJI="📊"
fi

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
    local telegram_msg="$msg"
    if [ -z "${TELEGRAM_TOKEN:-}" ] || [ -z "${ADMIN_ID:-}" ]; then
        log "Telegram 通知略過：未設定 token"
    else
        if [ ${#telegram_msg} -gt 4000 ]; then telegram_msg="${telegram_msg:0:4000}…"; fi
        local tmp http_code
        tmp="$(mktemp)"
        http_code=$(curl -sS -o "$tmp" -w "%{http_code}" \
            -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
            --data-urlencode "chat_id=${ADMIN_ID}" \
            --data-urlencode "text=${telegram_msg}" \
            2>> "$LOG" || true)
        if [ "$http_code" = "200" ]; then
            log "✅ Telegram 發送成功"
        else
            log "⚠️  Telegram 失敗 HTTP ${http_code}: $(cat "$tmp" | cut -c1-200)"
        fi
        rm -f "$tmp"
    fi
    declare -F line_notify_text >/dev/null 2>&1 && line_notify_text "$msg"
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

# ── 確保 stock-radar 當天持倉快照已生成 ──
# digest 讀 portfolio_snapshots 的 MAX(snapshot_date)；若當天快照還沒寫，
# 會抓到前一天的持倉。這裡先觸發 stock-radar 每日報告並等它寫完當天快照。
SR_HEALTH="http://127.0.0.1:6000/api/health"
SR_REPORT="http://127.0.0.1:6000/api/scheduler/report/run"
SR_MIMI_SYNC="http://127.0.0.1:6000/api/mimi/sync"
SR_DB="/Users/yankesswang/Desktop/Projects/Arthur_App/stock-radar/backend/stock_valuation.db"

ensure_stockradar_snapshot() {
    local today; today=$(date +%Y-%m-%d)

    if ! curl -sf -o /dev/null --max-time 5 "$SR_HEALTH" 2>/dev/null; then
        log "⚠️  stock-radar backend 未啟動（:6000），跳過快照刷新，digest 使用既有最新快照"
        return 0
    fi

    # ── 同步 mimi 操作建議總表 → DB（重跑 parser、含新格式報酬率/燈號）──
    log "🔄 同步 mimi 操作建議總表 → stock-radar DB…"
    local sync_resp
    sync_resp=$(curl -sf -X POST --max-time 90 "$SR_MIMI_SYNC" 2>/dev/null || echo "")
    if [ -n "$sync_resp" ]; then
        log "✅ mimi sync 完成：$sync_resp"
    else
        log "⚠️  mimi sync 失敗或逾時（不阻斷 digest）"
    fi

    local cur
    cur=$(sqlite3 "$SR_DB" "SELECT MAX(snapshot_date) FROM portfolio_snapshots;" 2>/dev/null || echo "")
    if [ "$cur" = "$today" ]; then
        log "✅ stock-radar 當天快照已存在（$today），略過刷新"
        return 0
    fi

    log "📸 觸發 stock-radar 每日報告（產生 $today 快照）…"
    curl -sf -X POST --max-time 10 "$SR_REPORT" >> "$LOG" 2>&1 || true

    # 報告為背景非阻塞執行，輪詢直到當天快照出現（最多 ~180s）
    local i
    for i in $(seq 1 60); do
        sleep 3
        cur=$(sqlite3 "$SR_DB" "SELECT MAX(snapshot_date) FROM portfolio_snapshots;" 2>/dev/null || echo "")
        if [ "$cur" = "$today" ]; then
            log "✅ stock-radar 快照已更新到 $today（等待 $((i*3))s）"
            return 0
        fi
    done
    log "⚠️  等待 stock-radar 快照逾時，digest 改用既有最新快照（$cur）"
}

# ── 主流程 ──
log "========== Stock Digest Start（mode=$MODE）=========="

ensure_stockradar_snapshot

cd /Users/yankesswang/Desktop/Projects/Arthur_App/arthur_knowledge_assistant/digest/stock/horizon

if ! /Users/yankesswang/.local/bin/uv run horizon $HORIZON_ARGS >> "$LOG" 2>&1; then
    log "ERROR: horizon pipeline 執行失敗"
    telegram_send "❌ *${DIGEST_LABEL} 失敗*（$(date '+%Y-%m-%d %H:%M')）
請查看 log：$LOG"
    exit 1
fi

# Sync to Digest
TODAY=$(date +%Y-%m-%d)
# 整周復盤的涵蓋區間（週六往回：週一 ~ 週五）
WEEK_START=$(date -v-5d +%Y-%m-%d 2>/dev/null || echo "$TODAY")
WEEK_END=$(date -v-1d +%Y-%m-%d 2>/dev/null || echo "$TODAY")
# horizon 用 UTC 時間命名，找最新輸出避免時區差
STOCK_HORIZON_SUMMARIES="/Users/yankesswang/Desktop/Projects/Arthur_App/arthur_knowledge_assistant/digest/stock/horizon/data/summaries"
HORIZON_DATE=$(ls -t "$STOCK_HORIZON_SUMMARIES/" 2>/dev/null | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' | head -1 || echo "$TODAY")
SRC="$STOCK_HORIZON_SUMMARIES/$HORIZON_DATE/"
DST="/Users/yankesswang/Documents/arthurwang_DB/Digest/stock/$HORIZON_DATE/"
# 非保護鏡像：stock-radar 後端讀這裡，而非 ~/Documents。launchd 啟動的服務
# 無法讀 ~/Documents（macOS TCC，表現為 OSError Errno 11 EDEADLK），故另存一份。
MIRROR="$HOME/.arthur-digest/stock/$HORIZON_DATE/"

if [ -d "$SRC" ]; then
    mkdir -p "$DST" "$MIRROR"
    # 用 cp + 重試（Python/Node 寫 ~/Documents 在 launchd 下會機率性 EDEADLK；cp 較穩，重試保底）
    sync_ok=1
    for f in "$SRC"*; do
        [ -f "$f" ] || continue
        base=$(basename "$f")
        # 鏡像：來源/目的都在非保護區，直接複製即可
        cp -f "$f" "$MIRROR$base" 2>>"$LOG" || log "WARNING: 鏡像複製失敗 $base"
        copied=0
        for attempt in 1 2 3 4 5; do
            if cp -f "$f" "$DST$base" 2>>"$LOG"; then copied=1; break; fi
            sleep 1
        done
        [ "$copied" = 1 ] || { sync_ok=0; log "WARNING: 複製失敗 $base"; }
    done
    [ "$sync_ok" = 1 ] && log "✅ Synced to Digest/stock/$HORIZON_DATE" || log "WARNING: sync 部分失敗"
    log "✅ Mirrored to ~/.arthur-digest/stock/$HORIZON_DATE"
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
if [ "$MODE" = "weekly" ]; then
    MSG_HEADER="${DIGEST_EMOJI} *${DIGEST_LABEL} — ${WEEK_START} ~ ${WEEK_END}*"
else
    MSG_HEADER="${DIGEST_EMOJI} *${DIGEST_LABEL} — ${TODAY}*"
fi

MSG="${MSG_HEADER}

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
