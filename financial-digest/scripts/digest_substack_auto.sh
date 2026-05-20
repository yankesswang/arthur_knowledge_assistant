#!/usr/bin/env bash
# ============================================================
# Finance Substack Digest — 自動排程執行腳本 (無互動)
# 由 launchd 或 cron 觸發，不需要使用者手動操作
# ============================================================
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$HOME/.yt-digest/substack-digest.log"
VAULT_PATH="${OBSIDIAN_VAULT_PATH:-/Users/yankesswang/Documents/arthurwang_DB}"
GOLEM_ENV_MAIN="/Users/yankesswang/Desktop/Projects/Arthur_App/.env"
GOLEM_ENV_FALLBACK="/Users/yankesswang/openclaw_backup/.env"
GOLEM_ENV="${GOLEM_ENV:-$GOLEM_ENV_MAIN}"

if [ ! -f "$GOLEM_ENV" ] && [ -f "$GOLEM_ENV_FALLBACK" ]; then
  GOLEM_ENV="$GOLEM_ENV_FALLBACK"
fi

# 讀取 Golem .env 取得 Telegram 設定 & GEMINI_API_KEY
if [ -f "$GOLEM_ENV" ]; then
  TELEGRAM_TOKEN=$(grep '^TELEGRAM_TOKEN=' "$GOLEM_ENV" | cut -d= -f2- || true)
  TELEGRAM_ADMIN_ID=$(grep '^ADMIN_ID=' "$GOLEM_ENV" | cut -d= -f2- || true)
  GEMINI_FROM_ENV=$(grep '^GEMINI_API_KEY=' "$GOLEM_ENV" | cut -d= -f2- || true)
  GEMINI_KEYS_FROM_ENV=$(grep '^GEMINI_API_KEYS=' "$GOLEM_ENV" | cut -d= -f2- || true)
  GEMINI_FIRST_FROM_ENV="${GEMINI_KEYS_FROM_ENV%%,*}"
  export GEMINI_API_KEY="${GEMINI_API_KEY:-${GEMINI_FROM_ENV:-${GEMINI_FIRST_FROM_ENV:-}}}"
fi

mkdir -p "$HOME/.yt-digest"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

notify() {
  local title="$1" msg="$2" sound="${3:-Glass}"
  launchctl asuser "$(id -u)" osascript \
    -e "display notification \"$msg\" with title \"$title\" sound name \"$sound\"" \
    2>/dev/null || true
}

telegram_notify() {
  local msg="$1"
  if [ -z "${TELEGRAM_TOKEN:-}" ] || [ -z "${TELEGRAM_ADMIN_ID:-}" ]; then
    return 0
  fi

  if [ ${#msg} -gt 3500 ]; then
    msg="${msg:0:3500}…"
  fi

  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_ADMIN_ID}" \
    --data-urlencode "text=${msg}" \
    > /dev/null 2>&1 \
    && log "Telegram 通知已發送" \
    || log "WARNING: Telegram 通知發送失敗"
}

log "========== Substack Digest Start =========="

# --- 確認 API Key ---
if [ -z "${GEMINI_API_KEY:-}" ]; then
  log "ERROR: 未設定 GEMINI_API_KEY（環境變數或 .env 均未找到）"
  notify "Finance Digest ❌" "未設定 GEMINI_API_KEY" "Basso"
  telegram_notify "📊 Finance Digest ❌ $(date '+%Y-%m-%d')\n未設定 GEMINI_API_KEY，任務終止。"
  exit 1
fi

# --- 參數（可透過環境變數覆蓋）---
HOURS="${DIGEST_HOURS:-168}"       # 預設 7 天
TOP_N="${DIGEST_TOP_N:-10}"
LANG="${DIGEST_LANG:-zh}"
SCRAPE_FLAG=""
[ "${DIGEST_NO_SCRAPE:-0}" = "1" ] && SCRAPE_FLAG="--no-scrape"

DATE=$(date +%Y-%m-%d)
DIGEST_FILE="$VAULT_PATH/Finance Digest/${DATE} digest.md"

RUN_MARK="$(mktemp)"
touch "$RUN_MARK"

log "參數：hours=$HOURS, topN=$TOP_N, lang=$LANG${SCRAPE_FLAG:+, no-scrape}"
log "Vault：$VAULT_PATH"
log "Digest 輸出：$DIGEST_FILE"

# --- 執行爬取 + 生成摘要 ---
if ! bun "$SKILL_DIR/digest-substack.ts" \
    --hours "$HOURS" \
    --top-n "$TOP_N" \
    --lang  "$LANG" \
    ${SCRAPE_FLAG:+"$SCRAPE_FLAG"} \
    >> "$LOG_FILE" 2>&1; then
  log "ERROR: digest-substack.ts 執行失敗，請查看 $LOG_FILE"
  notify "Finance Digest ❌" "摘要生成失敗，請查看日誌" "Basso"
  telegram_notify "📊 Finance Digest ❌ $(date '+%Y-%m-%d')\ndigest-substack.ts 執行失敗\n日誌：$LOG_FILE"
  exit 1
fi

ACTUAL_DIGEST_FILE=$(find "$VAULT_PATH/Finance Digest" -maxdepth 1 -name "* digest.md" -newer "$RUN_MARK" -print 2>/dev/null | sort | tail -n 1 || true)
if [ -n "$ACTUAL_DIGEST_FILE" ]; then
  DIGEST_FILE="$ACTUAL_DIGEST_FILE"
  DATE="$(basename "$DIGEST_FILE" " digest.md")"
fi

if [ ! -f "$DIGEST_FILE" ]; then
  log "ERROR: 找不到 digest 檔案：$DIGEST_FILE"
  notify "Finance Digest ❌" "找不到 digest 檔案，請查看日誌" "Basso"
  telegram_notify "📊 Finance Digest ❌ $(date '+%Y-%m-%d')\n找不到 digest 檔案\n預期：$DIGEST_FILE\n日誌：$LOG_FILE"
  exit 1
fi

log "摘要已生成：$DIGEST_FILE"

# --- 統計存入 Obsidian 的筆記數 ---
NOTES_COUNT=$(find "$VAULT_PATH/Finance Digest" -name "*.md" -newer "$RUN_MARK" 2>/dev/null | wc -l | tr -d ' ')
ARTICLE_COUNT=$(grep -c "^### " "$DIGEST_FILE" 2>/dev/null || echo "?")

log "完成！精選 $ARTICLE_COUNT 篇，新增筆記 $NOTES_COUNT 個"
log "========== Substack Digest End =========="

# --- 提取 Top 3（供通知使用）---
TOP3_SUMMARY=$(DIGEST_FILE="$DIGEST_FILE" node -e "
const fs = require('fs');
let content;
try { content = fs.readFileSync(process.env.DIGEST_FILE, 'utf8'); } catch(e) { process.exit(0); }

const lines = content.split(/\\r?\\n/);
const medals = ['🥇', '🥈', '🥉'];
const results = [];

for (const medal of medals) {
  const start = lines.findIndex((l) => l.includes(medal));
  if (start === -1) continue;

  const windowText = lines.slice(start, start + 14).join('\\n');
  const titleMatch = windowText.match(/\\*\\*(.+?)\\*\\*/);
  const title = titleMatch ? titleMatch[1].trim() : '';

  const summaryMatch = windowText.match(/^>\\s*(.+)$/m);
  let summary = summaryMatch ? summaryMatch[1].trim() : '';
  if (summary.length > 100) summary = summary.slice(0, 100) + '…';

  if (title) {
    results.push(medal + ' ' + title + (summary ? '\\n' + summary : ''));
  }
}

process.stdout.write(results.join('\\n\\n'));
" 2>/dev/null || true)


# --- macOS 通知 ---
notify "📊 Finance Digest ✅" "精選 $ARTICLE_COUNT 篇 | 筆記 $NOTES_COUNT 個已存入 Obsidian" "Glass"

# --- Telegram 通知（重點摘要）---
TG_MSG="📊 財經電子報精選 — $(date '+%Y-%m-%d')

🏆 今日必讀 Top 3
${TOP3_SUMMARY:-（摘要提取失敗）}

📚 精選 ${ARTICLE_COUNT} 篇 | 新增筆記 ${NOTES_COUNT} 個
📁 Obsidian: Finance Digest/${DATE} digest"
telegram_notify "$TG_MSG"

# --- 終端機輸出 ---
echo ""
echo "✅ Finance Substack Digest 完成"
echo "   📄 摘要：$DIGEST_FILE"
echo "   📚 新增筆記：$NOTES_COUNT 個"
echo "   📊 精選文章：$ARTICLE_COUNT 篇"
echo "   📋 日誌：$LOG_FILE"
rm -f "$RUN_MARK"
