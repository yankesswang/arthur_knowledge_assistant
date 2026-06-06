#!/usr/bin/env bash
# ============================================================
# AI Daily Digest — 自動排程執行腳本 (無互動)
# 由 launchd 或 cron 觸發，不需要使用者手動操作
# ============================================================
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="$HOME/.hn-daily-digest/config.json"
LOG_FILE="$HOME/.hn-daily-digest/digest.log"
OUTPUT_DIR="$SKILL_DIR/output"
IMAGE_PICKER_SCRIPT="${IMAGE_PICKER_SCRIPT:-/Users/yankesswang/Desktop/Projects/Arthur_App/scripts/select-digest-images.mjs}"
GOLEM_ENV_DEFAULT="$HOME/.hn-daily-digest/.env"
GOLEM_ENV_MAIN="/Users/yankesswang/Desktop/Projects/Arthur_App/.env"
GOLEM_ENV_FALLBACK="/Users/yankesswang/openclaw_backup/.env"
GOLEM_ENV="${GOLEM_ENV:-$GOLEM_ENV_DEFAULT}"

if [ ! -f "$GOLEM_ENV" ] && [ -f "$GOLEM_ENV_MAIN" ]; then
  GOLEM_ENV="$GOLEM_ENV_MAIN"
fi

if [ ! -f "$GOLEM_ENV" ] && [ -f "$GOLEM_ENV_FALLBACK" ]; then
  GOLEM_ENV="$GOLEM_ENV_FALLBACK"
fi

# 讀取 Golem .env 取得 Telegram 設定
if [ -f "$GOLEM_ENV" ]; then
  TELEGRAM_TOKEN=$(grep '^TELEGRAM_TOKEN=' "$GOLEM_ENV" | cut -d= -f2- || true)
  TELEGRAM_ADMIN_ID=$(grep '^ADMIN_ID=' "$GOLEM_ENV" | cut -d= -f2- || true)
fi

mkdir -p "$OUTPUT_DIR"
mkdir -p "$HOME/.hn-daily-digest"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }
notify() {
  local title="$1" msg="$2" sound="${3:-Glass}"
  launchctl asuser "$(id -u)" osascript -e "display notification \"$msg\" with title \"$title\" sound name \"$sound\"" 2>/dev/null || true
}

telegram_notify() {
  local msg="$1"
  if [ -z "${TELEGRAM_TOKEN:-}" ] || [ -z "${TELEGRAM_ADMIN_ID:-}" ]; then
    log "Telegram 通知略過：未設定 TELEGRAM_TOKEN 或 ADMIN_ID（env=$GOLEM_ENV）"
    return 0
  fi

  if [ ${#msg} -gt 3500 ]; then
    msg="${msg:0:3500}…"
  fi

  local tmp_resp http_code
  tmp_resp="$(mktemp)"
  http_code=$(curl -sS -o "$tmp_resp" -w "%{http_code}" \
    -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_ADMIN_ID}" \
    --data-urlencode "text=${msg}" \
    2>> "$LOG_FILE" || true)

  if [ "$http_code" = "200" ]; then
    log "Telegram 通知已發送"
  else
    local body
    body="$(tr '\n' ' ' < "$tmp_resp" | cut -c1-500)"
    log "WARNING: Telegram 通知發送失敗（HTTP ${http_code:-unknown}）：$body"
  fi
  rm -f "$tmp_resp"
}

telegram_notify_photo() {
  local photo_url="$1" msg="$2"
  if [ -z "$photo_url" ]; then
    telegram_notify "$msg"
    return 0
  fi
  if [ -z "${TELEGRAM_TOKEN:-}" ] || [ -z "${TELEGRAM_ADMIN_ID:-}" ]; then
    telegram_notify "$msg"
    return 0
  fi

  local caption="$msg"
  if [ ${#caption} -gt 900 ]; then
    caption="${caption:0:900}…"
  fi

  local tmp_resp http_code
  tmp_resp="$(mktemp)"
  http_code=$(curl -sS -o "$tmp_resp" -w "%{http_code}" \
    -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendPhoto" \
    --data-urlencode "chat_id=${TELEGRAM_ADMIN_ID}" \
    --data-urlencode "photo=${photo_url}" \
    --data-urlencode "caption=${caption}" \
    2>> "$LOG_FILE" || true)

  if [ "$http_code" = "200" ]; then
    log "Telegram 圖片通知已發送：$photo_url"
  else
    local body
    body="$(tr '\n' ' ' < "$tmp_resp" | cut -c1-500)"
    log "WARNING: Telegram 圖片通知失敗（HTTP ${http_code:-unknown}）：$body"
    log "改用純文字 Telegram 通知"
    telegram_notify "$msg"
  fi
  rm -f "$tmp_resp"
}

telegram_notify_album() {
  local photos="$1" msg="$2"
  if [ -z "$photos" ]; then
    telegram_notify "$msg"
    return 0
  fi
  if [ -z "${TELEGRAM_TOKEN:-}" ] || [ -z "${TELEGRAM_ADMIN_ID:-}" ]; then
    telegram_notify "$msg"
    return 0
  fi

  local photo_count first_photo
  photo_count=$(printf '%s\n' "$photos" | sed '/^[[:space:]]*$/d' | wc -l | tr -d ' ')
  first_photo=$(printf '%s\n' "$photos" | sed '/^[[:space:]]*$/d' | head -n 1)

  if [ "$photo_count" -lt 2 ]; then
    telegram_notify_photo "$first_photo" "$msg"
    return 0
  fi

  local media_json tmp_resp http_code
  media_json=$(PHOTOS="$photos" CAPTION="$msg" node -e "
const photos = (process.env.PHOTOS || '').split(/\\n+/).map(s => s.trim()).filter(Boolean).slice(0, 10);
let caption = process.env.CAPTION || '';
if (caption.length > 900) caption = caption.slice(0, 900) + '…';
const media = photos.map((url, index) => ({
  type: 'photo',
  media: url,
  ...(index === 0 ? { caption } : {}),
}));
process.stdout.write(JSON.stringify(media));
")

  tmp_resp="$(mktemp)"
  http_code=$(curl -sS -o "$tmp_resp" -w "%{http_code}" \
    -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMediaGroup" \
    --data-urlencode "chat_id=${TELEGRAM_ADMIN_ID}" \
    --data-urlencode "media=${media_json}" \
    2>> "$LOG_FILE" || true)

  if [ "$http_code" = "200" ]; then
    log "Telegram 相簿通知已發送：${photo_count} 張"
  else
    local body
    body="$(tr '\n' ' ' < "$tmp_resp" | cut -c1-500)"
    log "WARNING: Telegram 相簿通知失敗（HTTP ${http_code:-unknown}）：$body"
    log "改用單張圖片 Telegram 通知"
    telegram_notify_photo "$first_photo" "$msg"
  fi
  rm -f "$tmp_resp"
}

obsidian_open_link() {
  local note_path="$1"
  local vault_path="${OBSIDIAN_VAULT_PATH:-${VAULT_PATH_CFG:-/Users/yankesswang/Documents/arthurwang_DB}}"
  local vault_name="${OBSIDIAN_VAULT_NAME:-$(basename "$vault_path")}"
  VAULT_NAME="$vault_name" NOTE_PATH="$note_path" node -e "
const vault = encodeURIComponent(process.env.VAULT_NAME || '');
const file = encodeURIComponent(process.env.NOTE_PATH || '');
process.stdout.write('https://obsidianopen.com/?vault=' + vault + '&file=' + file);
"
}

log "========== Auto Digest Start =========="

# --- 讀取設定 ---
if [ ! -f "$CONFIG_FILE" ]; then
  log "ERROR: 找不到設定檔 $CONFIG_FILE，請先執行 /digest 完成初始設定"
  notify "AI Daily Digest ❌" "找不到設定檔，請先執行 /digest 完成初始設定" "Basso"
  telegram_notify "AI Daily Digest 失敗 — 找不到設定檔：$CONFIG_FILE"
  exit 1
fi

GEMINI_API_KEY=$(node -e "const c=require('$CONFIG_FILE');process.stdout.write(c.geminiApiKey||'')" 2>/dev/null)
HOURS=$(node -e "const c=require('$CONFIG_FILE');process.stdout.write(String(c.timeRange||48))" 2>/dev/null)
TOP_N=$(node -e "const c=require('$CONFIG_FILE');process.stdout.write(String(c.topN||15))" 2>/dev/null)
LANG=$(node -e "const c=require('$CONFIG_FILE');process.stdout.write(c.language||'zh')" 2>/dev/null)
VAULT_PATH_CFG=$(node -e "const c=require('$CONFIG_FILE');process.stdout.write(c.obsidianVaultPath||'')" 2>/dev/null)

if [ -z "$GEMINI_API_KEY" ]; then
  log "ERROR: 設定檔中沒有 GEMINI_API_KEY，請先執行 /digest 設定 API Key"
  notify "AI Daily Digest ❌" "未設定 API Key，請先執行 /digest" "Basso"
  telegram_notify "AI Daily Digest 失敗 — 未設定 GEMINI_API_KEY，請先執行 /digest"
  exit 1
fi

DATE=$(date +%Y%m%d)
OUTPUT_FILE="$OUTPUT_DIR/digest-$DATE.md"

log "參數：hours=$HOURS, topN=$TOP_N, lang=$LANG"
log "輸出：$OUTPUT_FILE"

export GEMINI_API_KEY

# --- 執行摘要生成 ---
if ! npx -y bun "$SKILL_DIR/scripts/digest.ts" \
    --hours "$HOURS" \
    --top-n "$TOP_N" \
    --lang "$LANG" \
    --output "$OUTPUT_FILE" >> "$LOG_FILE" 2>&1; then
  log "ERROR: digest.ts 執行失敗，請查看日誌 $LOG_FILE"
  notify "AI Daily Digest ❌" "摘要生成失敗，請查看日誌" "Basso"
  telegram_notify "AI Daily Digest 失敗 — digest.ts 執行失敗。日誌：$LOG_FILE"
  exit 1
fi

log "摘要已生成：$OUTPUT_FILE"

# --- 寫入 Obsidian ---
OBSIDIAN_RESULT=""
VAULT_PATH="${OBSIDIAN_VAULT_PATH:-${VAULT_PATH_CFG:-/Users/yankesswang/Documents/arthurwang_DB}}"

if [ -d "$VAULT_PATH" ]; then
  OBSIDIAN_FOLDER="$VAULT_PATH/AI Knowledge/Digest"
  OBSIDIAN_NOTE="$OBSIDIAN_FOLDER/digest-$DATE.md"
  mkdir -p "$OBSIDIAN_FOLDER"
  cp "$OUTPUT_FILE" "$OBSIDIAN_NOTE"
  log "Obsidian 副本已寫入：$OBSIDIAN_NOTE"
  OBSIDIAN_RESULT="✅ Obsidian: AI Knowledge/Digest/digest-$DATE"
else
  log "WARNING: 找不到 Obsidian vault，跳過寫入"
  OBSIDIAN_RESULT="⚠️ Obsidian 未可用"
fi

# --- 更新 lastUsed ---
node -e "
  const fs=require('fs');
  const c=JSON.parse(fs.readFileSync('$CONFIG_FILE','utf8'));
  c.lastUsed=new Date().toISOString();
  fs.writeFileSync('$CONFIG_FILE',JSON.stringify(c,null,2));
" 2>/dev/null || true

# --- 提取摘要統計 ---
ARTICLE_COUNT=$(grep -Ec "^### [0-9]+\\. " "$OUTPUT_FILE" 2>/dev/null || true)

# --- 提取 Top 3 完整摘要 (供 Telegram 通知) ---
TOP3_SUMMARY=$(node -e "
const fs = require('fs');
const content = fs.readFileSync('$OUTPUT_FILE', 'utf8');

// 找到今日必讀區塊
const start = content.indexOf('## 🏆 今日必讀');
let section = start >= 0 ? content.slice(start) : content;
const endMatch = section.match(/\n---\n/);
if (endMatch && typeof endMatch.index === 'number') {
  section = section.slice(0, endMatch.index);
}
const medals = ['🥇', '🥈', '🥉'];
const results = [];

medals.forEach((medal, i) => {
  const idx = section.indexOf(medal);
  if (idx === -1) return;

  // 提取中文標題 (medal 後的 **粗體** 文字)
  const titleMatch = section.slice(idx).match(/\*\*(.+?)\*\*/);
  const title = titleMatch ? titleMatch[1] : '';

  // 提取摘要 (> 開頭的 blockquote，取前 80 字)
  const summaryMatch = section.slice(idx).match(/^> (.+)/m);
  const summary = summaryMatch ? summaryMatch[1].slice(0, 80) + (summaryMatch[1].length > 80 ? '…' : '') : '';

  if (title) results.push(medal + ' ' + title + '\n' + summary);
  const linkMatch = section.slice(idx).match(/\]\((https?:\/\/[^)]+)\)/);
  if (title && linkMatch) {
    results[results.length - 1] += '\n網頁原文: ' + linkMatch[1].trim();
  }
});

process.stdout.write(results.join('\n\n'));
" 2>/dev/null || echo "")

# --- 抓候選圖片並用 LLM 挑選最適合 Telegram 通知的圖片；失敗時會在腳本內 fallback ---
PHOTO_URLS=$(OUTPUT_FILE="$OUTPUT_FILE" node "$IMAGE_PICKER_SCRIPT" --digest "$OUTPUT_FILE" --limit 3 2>> "$LOG_FILE" || true)

log "完成！共精選 $ARTICLE_COUNT 篇文章"
log "========== Auto Digest End =========="

# --- macOS 通知 ---
NOTIFY_MSG="今日精選 $ARTICLE_COUNT 篇 | $OBSIDIAN_RESULT"
notify "📰 AI Daily Digest ✅" "$NOTIFY_MSG" "Glass"

# --- Telegram 通知 ---
OBSIDIAN_NOTE_PATH="AI Knowledge/Digest/digest-$DATE"
OBSIDIAN_OPEN_URL="$(obsidian_open_link "$OBSIDIAN_NOTE_PATH")"
TG_MSG="今日 AI 精選 — $(date '+%Y-%m-%d')

今日必讀 Top 3

${TOP3_SUMMARY}

共精選 ${ARTICLE_COUNT} 篇 | ${OBSIDIAN_RESULT}
手機開啟: ${OBSIDIAN_OPEN_URL}"
telegram_notify_album "$PHOTO_URLS" "$TG_MSG"

# --- 在終端機輸出報告路徑（供 cron 日誌查閱）---
echo ""
echo "✅ AI Daily Digest 完成"
echo "   📄 報告：$OUTPUT_FILE"
echo "   📒 $OBSIDIAN_RESULT"
echo "   📊 精選文章：$ARTICLE_COUNT 篇"
if [ -n "${TOP3_SUMMARY:-}" ]; then
  echo "   🏆 Top 3：已產生（詳見通知）"
fi
echo "   📋 日誌：$LOG_FILE"
