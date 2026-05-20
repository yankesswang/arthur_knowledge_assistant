#!/usr/bin/env bash
# Steps 1-3: parse URL → download metadata + CC → parse VTT → condensed.txt + info.json

YT_URL="$1"
if [ -z "$YT_URL" ]; then echo "Usage: setup.sh <youtube_url>"; exit 1; fi

# ── Step 1: Extract video ID ────────────────────────────────────────────────
VIDEO_ID=$(python3 - "$YT_URL" << 'PYEOF'
import re, sys
url = sys.argv[1]
for p in [
    r'(?:v=)([A-Za-z0-9_-]{11})',
    r'youtu\.be/([A-Za-z0-9_-]{11})',
    r'youtube\.com/(?:shorts|embed|live)/([A-Za-z0-9_-]{11})',
]:
    m = re.search(p, url)
    if m: print(m.group(1)); import sys; sys.exit(0)
print("")
PYEOF
)
if [ -z "$VIDEO_ID" ]; then echo "ERROR: Cannot extract video ID from URL"; exit 1; fi

WORK_DIR="/tmp/transcript_note/$VIDEO_ID"
NOTE_DIR="/Users/yankesswang/Documents/arthurwang_DB/AI Knowledge/影片筆記"
mkdir -p "$WORK_DIR" "$NOTE_DIR"
echo "VIDEO_ID=$VIDEO_ID"
echo "WORK_DIR=$WORK_DIR"

command -v yt-dlp >/dev/null || { echo "ERROR: yt-dlp not found. Run: pip install yt-dlp"; exit 1; }

# ── Step 2: Download metadata ───────────────────────────────────────────────
yt-dlp --dump-json --no-playlist "$YT_URL" 2>/dev/null > "$WORK_DIR/meta.json" || true
if [ ! -s "$WORK_DIR/meta.json" ]; then
  echo '{"title":"Unknown","channel":"Unknown","duration":0,"description":"","chapters":[]}' > "$WORK_DIR/meta.json"
fi

# ── Step 2b: Download subtitles (priority: manual zh → auto zh → auto en) ──
VTT_FILE=""

# Try manual subs (zh-TW → zh-Hant → zh → en)
yt-dlp --skip-download \
  --write-subs \
  --sub-lang "zh-TW,zh-Hant,zh,en" \
  --sub-format "vtt" \
  -o "$WORK_DIR/transcript_manual.%(ext)s" \
  "$YT_URL" 2>/dev/null || true
VTT_FILE=$(ls "$WORK_DIR"/transcript_manual.*.vtt 2>/dev/null | head -1)

# Try auto subs zh family
if [ -z "$VTT_FILE" ]; then
  yt-dlp --skip-download \
    --write-auto-subs \
    --sub-lang "zh-TW,zh-Hant,zh" \
    --sub-format "vtt" \
    -o "$WORK_DIR/transcript_auto_zh.%(ext)s" \
    "$YT_URL" 2>/dev/null || true
  VTT_FILE=$(ls "$WORK_DIR"/transcript_auto_zh.*.vtt 2>/dev/null | head -1)
fi

# Try auto subs English (fallback for English-language videos)
if [ -z "$VTT_FILE" ]; then
  yt-dlp --skip-download \
    --write-auto-subs \
    --sub-lang "en" \
    --sub-format "vtt" \
    -o "$WORK_DIR/transcript_auto_en.%(ext)s" \
    "$YT_URL" 2>/dev/null || true
  VTT_FILE=$(ls "$WORK_DIR"/transcript_auto_en.*.vtt 2>/dev/null | head -1)
fi

python3 -c "
import json
d=json.load(open('$WORK_DIR/meta.json'))
ch=d.get('chapters') or []
print('Meta:', d.get('title','?')[:60], '| dur:', d.get('duration',0),'s | chapters:', len(ch))
" 2>/dev/null || true
echo "VTT:  ${VTT_FILE:-NONE (will use description)}"

# ── Step 3: Parse VTT → condensed.txt + info.json ───────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VTT_FILE="$VTT_FILE" WORK_DIR="$WORK_DIR" python3 "$SCRIPT_DIR/parse_vtt.py"

echo "---"
echo "Setup complete. Work dir: $WORK_DIR"
echo "Next: read $WORK_DIR/condensed.txt and $WORK_DIR/info.json, write analysis.json"
