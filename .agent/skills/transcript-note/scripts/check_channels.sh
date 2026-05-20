#!/usr/bin/env bash
# Check all configured channels for new videos → append to queue.txt
# Usage: check_channels.sh
# Run via LaunchAgent or manually before processing

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$SKILL_DIR/config/channels.json"
PROCESSED="$SKILL_DIR/data/processed_ids.txt"
QUEUE="$SKILL_DIR/data/queue.txt"

command -v opencli >/dev/null || { echo "ERROR: opencli not found"; exit 1; }
command -v python3  >/dev/null || { echo "ERROR: python3 not found"; exit 1; }

# Ensure processed list exists
touch "$PROCESSED" "$QUEUE"

# Read channels from config
CHANNELS=$(python3 -c "
import json
with open('$CONFIG') as f:
    data = json.load(f)
for ch in data['channels']:
    if ch.get('enabled', True):
        print(ch['handle'] + '|' + str(ch.get('limit', 5)) + '|' + ch['name'])
")

NEW_COUNT=0

while IFS='|' read -r handle limit name; do
    echo "── Checking: $name ($handle) ──"

    RAW=$(opencli youtube channel "$handle" --limit "$limit" 2>/dev/null)

    # Extract video URLs and IDs using Python
    NEW_VIDEOS=$(python3 << PYEOF
import re

raw = """$RAW"""
# Find all YouTube watch URLs in the output
urls = re.findall(r'https://www\.youtube\.com/watch\?v=([A-Za-z0-9_-]{11})', raw)

# Read already-processed IDs
try:
    with open('$PROCESSED') as f:
        processed = set(line.strip() for line in f if line.strip())
except:
    processed = set()

# Read existing queue to avoid duplicates
try:
    with open('$QUEUE') as f:
        queued_urls = set(line.strip() for line in f if line.strip())
except:
    queued_urls = set()

new = []
for vid_id in urls:
    url = f"https://www.youtube.com/watch?v={vid_id}"
    if vid_id not in processed and url not in queued_urls:
        new.append(url)

print('\n'.join(new))
PYEOF
)

    if [ -n "$NEW_VIDEOS" ]; then
        COUNT=$(echo "$NEW_VIDEOS" | grep -c .)
        echo "  → $COUNT 部新影片加入佇列"
        echo "$NEW_VIDEOS" >> "$QUEUE"
        NEW_COUNT=$((NEW_COUNT + COUNT))
    else
        echo "  → 無新影片"
    fi
done <<< "$CHANNELS"

echo ""
echo "══════════════════════════════"
echo "共新增 $NEW_COUNT 部影片到佇列"
echo "佇列檔案：$QUEUE"

# Show current queue
TOTAL_QUEUED=$(grep -c . "$QUEUE" 2>/dev/null || echo 0)
if [ "$TOTAL_QUEUED" -gt 0 ]; then
    echo ""
    echo "待處理佇列（共 $TOTAL_QUEUED 部）："
    cat "$QUEUE"
fi
