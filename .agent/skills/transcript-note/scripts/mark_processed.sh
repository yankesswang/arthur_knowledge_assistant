#!/usr/bin/env bash
# Mark a video URL as processed: move from queue → processed_ids.txt
# Usage: mark_processed.sh <video_url_or_id>

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROCESSED="$SKILL_DIR/data/processed_ids.txt"
QUEUE="$SKILL_DIR/data/queue.txt"

INPUT="$1"
if [ -z "$INPUT" ]; then
    echo "Usage: mark_processed.sh <youtube_url_or_video_id>"
    exit 1
fi

# Extract video ID from URL or use directly
VIDEO_ID=$(python3 - "$INPUT" << 'PYEOF'
import re, sys
url = sys.argv[1]
for p in [r'(?:v=)([A-Za-z0-9_-]{11})', r'youtu\.be/([A-Za-z0-9_-]{11})']:
    m = re.search(p, url)
    if m: print(m.group(1)); import sys; sys.exit(0)
# If it looks like a raw ID
if re.match(r'^[A-Za-z0-9_-]{11}$', url):
    print(url)
else:
    print("")
PYEOF
)

if [ -z "$VIDEO_ID" ]; then
    echo "ERROR: 無法從輸入解析 video ID: $INPUT"
    exit 1
fi

# Add to processed list (deduplicated)
if grep -q "^$VIDEO_ID$" "$PROCESSED" 2>/dev/null; then
    echo "已在 processed 清單中：$VIDEO_ID"
else
    echo "$VIDEO_ID" >> "$PROCESSED"
    echo "已標記為已處理：$VIDEO_ID"
fi

# Remove all matching URLs from queue
URL="https://www.youtube.com/watch?v=$VIDEO_ID"
if [ -f "$QUEUE" ]; then
    TMP=$(mktemp)
    grep -v "^$URL$" "$QUEUE" > "$TMP" && mv "$TMP" "$QUEUE"
    echo "已從佇列移除：$URL"
fi
