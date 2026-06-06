#!/usr/bin/env bash
# Horizon AI Digest — 每日自動執行
set -euo pipefail

HORIZON_DIR="/Users/yankesswang/Desktop/Projects/Arthur_App/ai_digest/horizon"
LOG_FILE="/Users/yankesswang/.hn-daily-digest/digest.log"
OBSIDIAN_DIR="/Users/yankesswang/Documents/arthurwang_DB/AI Knowledge/Digest"
UV_BIN="${UV_BIN:-/Library/Frameworks/Python.framework/Versions/3.10/bin/uv}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

log "========== Horizon Digest Start =========="

if [ ! -d "$HORIZON_DIR" ]; then
  log "ERROR: Horizon dir not found: $HORIZON_DIR"
  exit 1
fi

cd "$HORIZON_DIR"

if ! "$UV_BIN" run python -m src.main --hours 48 >> "$LOG_FILE" 2>&1; then
  log "ERROR: Horizon run failed"
  exit 1
fi

# 取今日日期
TODAY=$(date '+%Y-%m-%d')

# 複製 per-category folder 到 Obsidian
if [ -d "data/summaries/$TODAY" ]; then
  rm -rf "$OBSIDIAN_DIR/$TODAY"
  cp -r "data/summaries/$TODAY" "$OBSIDIAN_DIR/$TODAY"
  log "📁 Copied $TODAY folder to Obsidian"
fi

# 複製合併版 summary 到 Obsidian（備用）
SUMMARY="data/summaries/horizon-${TODAY}-zh-tw.md"
if [ -f "$SUMMARY" ]; then
  cp "$SUMMARY" "$OBSIDIAN_DIR/horizon-${TODAY}.md"
  log "📄 Copied horizon-${TODAY}.md to Obsidian"
fi

log "========== Horizon Digest End =========="
