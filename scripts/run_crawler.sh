#!/bin/zsh
# AI 爬蟲排程入口，由 cron 呼叫

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$SCRIPT_DIR/../.venv/bin/python3"
LOG="$SCRIPT_DIR/crawler.log"

echo "\n$(date '+%Y-%m-%d %H:%M:%S')  ── 排程啟動 ──" >> "$LOG"
"$PYTHON" "$SCRIPT_DIR/ai_crawler.py" >> "$LOG" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S')  ── 排程結束 ──" >> "$LOG"
