#!/usr/bin/env bash
# Enhance Finance Digest article notes with Claude, following obsidian_claude/CLAUDE.md format.
# Usage: bash enhance-notes.sh note1.md note2.md ...
set -euo pipefail

CLAUDE_DIR="/Users/yankesswang/obsidian_claude"
CLAUDE_BIN="${CLAUDE_BIN:-/Users/yankesswang/.local/bin/claude}"
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GOLEM_ENV="${GOLEM_ENV:-$PROJECT_ROOT/.env}"
if [ ! -f "$GOLEM_ENV" ] && [ -f "/Users/yankesswang/openclaw_backup/.env" ]; then
  GOLEM_ENV="/Users/yankesswang/openclaw_backup/.env"
fi

if [ -f "$GOLEM_ENV" ]; then
  TELEGRAM_TOKEN=$(grep '^TELEGRAM_TOKEN=' "$GOLEM_ENV" | cut -d= -f2- || true)
  TELEGRAM_ADMIN_ID=$(grep '^ADMIN_ID=' "$GOLEM_ENV" | cut -d= -f2- || true)
fi

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [enhance] $*"; }

LINE_NOTIFY_SH="/Users/yankesswang/Projects/Arthur_App/scripts/lib/line_notify.sh"
[ -f "$LINE_NOTIFY_SH" ] && source "$LINE_NOTIFY_SH"

telegram_notify() {
  local msg="$1"
  local telegram_msg="$msg"
  if [ -z "${TELEGRAM_TOKEN:-}" ] || [ -z "${TELEGRAM_ADMIN_ID:-}" ]; then
    log "Telegram 通知略過：未設定 token/id"
    declare -F line_notify_text >/dev/null 2>&1 && line_notify_text "$msg"
    return 0
  fi
  [ ${#telegram_msg} -gt 3500 ] && telegram_msg="${telegram_msg:0:3500}…"
  curl -sS -o /dev/null \
    -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_ADMIN_ID}" \
    --data-urlencode "text=${telegram_msg}" \
    --data-urlencode "parse_mode=HTML" \
    --data-urlencode "disable_web_page_preview=true" \
    2>/dev/null || true
  declare -F line_notify_text >/dev/null 2>&1 && line_notify_text "$msg"
}

if ! command -v "$CLAUDE_BIN" &>/dev/null && [ ! -x "$CLAUDE_BIN" ]; then
  log "ERROR: claude CLI not found at $CLAUDE_BIN — skipping note enhancement"
  exit 0
fi

if [ ! -d "$CLAUDE_DIR" ]; then
  log "ERROR: obsidian_claude dir not found: $CLAUDE_DIR — skipping"
  exit 0
fi

if [ $# -eq 0 ]; then
  log "No note files provided."
  exit 0
fi

READING_LIST="${OBSIDIAN_VAULT_PATH:-/Users/yankesswang/Documents/arthurwang_DB}/待閱讀清單.md"

ENHANCED=0
FAILED=0
ENHANCED_NOTES=()

for note_file in "$@"; do
  if [ ! -f "$note_file" ]; then
    log "Skipping (not found): $note_file"
    continue
  fi

  note_name="$(basename "$note_file")"
  log "Enhancing: $note_name"

  CONTENT="$(cat "$note_file")"
  PROMPT="將以下從 Substack 擷取的財經文章，按照 CLAUDE.md 格式規範輸出完整 Obsidian 投資筆記。

【重要規則】
- frontmatter 之後緊接 ## TL;DR 區塊，用 3–5 個 bullet 點整理核心論點與投資行動
- 不需要寫作者背景章節
- 原文提到的每一個論點、數字、公司、機制都必須保留並展開，不得壓縮或略過
- 每個章節要有足夠的分析深度，用 callout（quote/tip/warning/info/note）標注關鍵洞見
- 在原文事實基礎上補充投資含義（[!tip]），不只是複述原文
- 保留 frontmatter 的 url、source、date，title 改為中文，補充 speaker、sector、tags、stocks
- 直接輸出完整 Markdown，不要有任何說明文字，不要用 \`\`\`markdown 包裝

【原文內容】
${CONTENT}"

  RESULT=$(printf '%s' "$PROMPT" | "$CLAUDE_BIN" -p --system-prompt-file "$CLAUDE_DIR/CLAUDE.md" 2>/dev/null || true)

  if [ -n "$RESULT" ]; then
    note_dir="$(dirname "$note_file")"
    note_stem="${note_name%.md}"

    # 從強化結果的 frontmatter 取得日期
    NOTE_DATE=$(printf '%s' "$RESULT" | grep '^date:' | head -1 | sed 's/^date: *//' | tr -d '"')
    NOTE_DATE="${NOTE_DATE:-$(date '+%Y-%m-%d')}"

    # 去掉 stem 開頭的既有日期（避免 2026-01-01 2026-01-01 Article_筆記）
    note_stem_clean=$(echo "$note_stem" | sed 's/^[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\} //')
    enhanced_name="${NOTE_DATE} ${note_stem_clean}_筆記.md"
    enhanced_file="${note_dir}/${enhanced_name}"
    printf '%s\n' "$RESULT" > "$enhanced_file"
    log "✅ Enhanced → $enhanced_name"

    # --- 原文移到 raw/ ---
    raw_dir="${note_dir}/raw"
    mkdir -p "$raw_dir"
    mv "$note_file" "${raw_dir}/${note_name}"
    log "📦 原文移至 raw/ → $note_name"

    # --- 加入待閱讀清單 ---
    if [ -f "$READING_LIST" ]; then
      NOTE_TITLE=$(grep '^title:' "$enhanced_file" | head -1 | sed 's/^title: *//' | tr -d '"')
      WIKI_LINK="${NOTE_DATE} ${note_stem_clean}_筆記${NOTE_TITLE:+|${NOTE_DATE} ${NOTE_TITLE}}"
      GEN_DATE="$(date '+%Y-%m-%d')"
      READING_LIST="$READING_LIST" WIKI_LINK="$WIKI_LINK" GEN_DATE="$GEN_DATE" node -e "
const fs = require('fs');
const f = process.env.READING_LIST;
const wikiLink = process.env.WIKI_LINK;
const dateStr = process.env.GEN_DATE || new Date().toISOString().slice(0, 10);

// Calculate Mon–Sun week for the note generation date
function weekHeader(ds) {
  const d = new Date(ds + 'T00:00:00');
  const day = d.getDay();
  const diffToMon = day === 0 ? -6 : 1 - day;
  const mon = new Date(d); mon.setDate(d.getDate() + diffToMon);
  const sun = new Date(mon); sun.setDate(mon.getDate() + 6);
  const p = n => String(n).padStart(2, '0');
  return '## 🆕 本週新增（' + mon.getFullYear() + '/' + p(mon.getMonth()+1) + '/' + p(mon.getDate()) + ' – ' + p(sun.getMonth()+1) + '/' + p(sun.getDate()) + '）';
}

const header = weekHeader(dateStr);
const entry = '- [ ] [[' + wikiLink + ']]\n';
let c = fs.readFileSync(f, 'utf8');

// Skip if already present
if (c.includes('[[' + wikiLink.split('|')[0])) process.exit(0);

const weekIdx = c.indexOf(header);
const INVEST_HEADING = '\n### 投資\n';

if (weekIdx !== -1) {
  // Find the end of this week section (next ## or EOF)
  const nextSection = c.indexOf('\n## ', weekIdx + header.length);
  const sectionEnd = nextSection === -1 ? c.length : nextSection;
  const sectionSlice = c.slice(weekIdx, sectionEnd);
  const investOff = sectionSlice.indexOf(INVEST_HEADING);
  if (investOff !== -1) {
    const insertAt = weekIdx + investOff + INVEST_HEADING.length;
    c = c.slice(0, insertAt) + entry + c.slice(insertAt);
  } else {
    // Add ### 投資 subsection at end of this week block
    c = c.slice(0, sectionEnd) + '\n### 投資\n' + entry + c.slice(sectionEnd);
  }
} else {
  // Create new week section right after the opening ---\n\n
  const insertAfter = c.indexOf('\n---\n');
  const insertAt = insertAfter !== -1 ? c.indexOf('\n', insertAfter + 5) + 1 : c.indexOf('# 待閱讀清單\n') + '# 待閱讀清單\n'.length;
  const newSection = '\n' + header + '\n\n### 投資\n' + entry;
  c = c.slice(0, insertAt) + newSection + c.slice(insertAt);
}

fs.writeFileSync(f, c);
" 2>/dev/null && log "📋 加入待閱讀清單（${GEN_DATE}）：$NOTE_TITLE" || log "WARNING: 無法寫入待閱讀清單"
    fi

    # 提取摘要與投資重點供 Telegram 通知
    NOTE_BLURB=$(NOTE_FILE="$enhanced_file" NOTE_TITLE="${NOTE_TITLE:-$note_stem_clean}" NOTE_DATE="$NOTE_DATE" node -e "
const fs = require('fs');
const content = fs.readFileSync(process.env.NOTE_FILE, 'utf8');
const lines = content.split('\n');
const title = process.env.NOTE_TITLE;
const date = process.env.NOTE_DATE;

// Extract ## TL;DR bullets — handles both '- ' and '> - ' (inside callout)
const tldr = [];
let inTldr = false;
for (const line of lines) {
  if (/^## TL;DR/.test(line)) { inTldr = true; continue; }
  if (inTldr && /^## /.test(line)) break;
  if (inTldr) {
    const bare = line.match(/^- (.+)/);
    const callout = line.match(/^> - (.+)/);
    const m = bare || callout;
    if (m) tldr.push('• ' + m[1].replace(/\*\*/g, ''));
  }
}

// Fallback: [!abstract] one-liner
let abstract = '';
if (!tldr.length) {
  let inAbstract = false;
  for (const line of lines) {
    if (/\[!abstract\]/i.test(line)) { inAbstract = true; continue; }
    if (inAbstract && /^>\s+\S/.test(line)) { abstract = line.replace(/^>\s*/, '').trim(); break; }
    if (inAbstract && !/^>/.test(line)) break;
  }
}

// Extract [!tip] first content line from each block (top 4)
const tips = [];
let inTip = false;
for (const line of lines) {
  if (/\[!tip\]/i.test(line)) { inTip = true; continue; }
  if (inTip && /^>\s+\S/.test(line)) {
    tips.push('💡 ' + line.replace(/^>\s*/, '').replace(/\*\*/g, '').trim());
    inTip = false;
  } else if (!/^>/.test(line)) inTip = false;
  if (tips.length >= 4) break;
}

// Extract stocks
const stockLines = [];
let inStocks = false;
for (const line of lines) {
  if (/^stocks:/.test(line)) { inStocks = true; continue; }
  if (inStocks && /^  - /.test(line)) stockLines.push(line.replace(/^  - /, '').trim());
  else if (inStocks) break;
}

let msg = '<b>' + date + ' ' + title + '</b>\n\n';
if (tldr.length) msg += '📌 TL;DR\n' + tldr.join('\n');
else if (abstract) msg += abstract;
if (tips.length) msg += '\n\n' + tips.join('\n');
if (stockLines.length) msg += '\n\n🏷 ' + stockLines.join(', ');
process.stdout.write(msg);
" 2>/dev/null || true)
    [ -n "$NOTE_BLURB" ] && ENHANCED_NOTES+=("$NOTE_BLURB")
    ENHANCED=$((ENHANCED + 1))
  else
    log "❌ Failed (empty output): $note_name"
    FAILED=$((FAILED + 1))
  fi
done

log "Enhancement done — ${ENHANCED} enhanced, ${FAILED} failed"

# --- Telegram 通知（每篇筆記各發一則）---
for note_blurb in "${ENHANCED_NOTES[@]+"${ENHANCED_NOTES[@]}"}"; do
  telegram_notify "$note_blurb"
done
