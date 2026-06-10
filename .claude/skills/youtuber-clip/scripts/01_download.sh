#!/usr/bin/env bash
# Step 1: 下載影片（1080p）+ 字幕 + metadata
YT_URL="$1"
WORK_DIR="$2"
if [ -z "$YT_URL" ] || [ -z "$WORK_DIR" ]; then
  echo "Usage: 01_download.sh <youtube_url> <work_dir>"; exit 1
fi

YT_DLP=""
for c in /home/trx50/.virtualenvs/chatbot/bin/yt-dlp "$HOME/.local/bin/yt-dlp" "$(which yt-dlp 2>/dev/null)"; do
  [ -x "$c" ] && YT_DLP="$c" && break
done
[ -z "$YT_DLP" ] && { echo "ERROR: yt-dlp not found"; exit 1; }

# Metadata
"$YT_DLP" --dump-json --no-playlist "$YT_URL" 2>/dev/null > "$WORK_DIR/meta.json" || true

# 影片（1080p）
if [ ! -s "$WORK_DIR/video.mp4" ]; then
  "$YT_DLP" \
    -f "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best" \
    --merge-output-format mp4 --no-playlist \
    -o "$WORK_DIR/video.%(ext)s" "$YT_URL" 2>&1 | tail -3
fi

VIDEO_FILE=$(ls "$WORK_DIR"/video.mp4 2>/dev/null | head -1)
[ -z "$VIDEO_FILE" ] && { echo "ERROR: 影片下載失敗"; exit 1; }
echo "Video: $VIDEO_FILE ($(du -sh "$VIDEO_FILE" | cut -f1))"

# 字幕（手動優先 → auto en fallback）
VTT_FILE=""
for args in \
  "--write-subs --no-write-auto-subs --sub-lang en,en-US" \
  "--write-auto-subs --no-write-subs --sub-lang en,en-US"
do
  "$YT_DLP" --skip-download $args --sub-format vtt --no-playlist \
    -o "$WORK_DIR/subs.%(ext)s" "$YT_URL" 2>/dev/null || true
  VTT_FILE=$(ls "$WORK_DIR"/subs.*.vtt 2>/dev/null | head -1)
  [ -n "$VTT_FILE" ] && break
done

if [ -n "$VTT_FILE" ]; then
  # 統一命名
  [ "$VTT_FILE" != "$WORK_DIR/subs.en.vtt" ] && mv "$VTT_FILE" "$WORK_DIR/subs.en.vtt"
  echo "Subs: $WORK_DIR/subs.en.vtt ($(wc -l < "$WORK_DIR/subs.en.vtt") lines)"
else
  echo "WARNING: 無法下載字幕"
fi
