#!/usr/bin/env bash
# download.sh — 從 RSS 下載指定集數的 Podcast MP3
# 用法：download.sh <podcast_id> <episode_number_or_latest>
# 範例：download.sh gooaye latest
#        download.sh gooaye 663
# 輸出：設定環境變數 EPISODE_MP3、EPISODE_TITLE、EPISODE_DATE、WORK_DIR

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$SKILL_DIR/config/podcasts.json"

PODCAST_ID="${1:-}"
EPISODE_ARG="${2:-latest}"

if [[ -z "$PODCAST_ID" ]]; then
  echo "ERROR: 缺少 podcast_id" >&2
  echo "用法：download.sh <podcast_id> [episode_number|latest]" >&2
  exit 1
fi

# 從 config 取得 RSS URL 和語言
RSS=$(python3 -c "
import json, sys
cfg = json.load(open('$CONFIG'))
pod = next((p for p in cfg['podcasts'] if p['id'] == '$PODCAST_ID'), None)
if not pod:
    print('ERROR: podcast_id 找不到', file=sys.stderr); sys.exit(1)
print(pod['rss'])
")

LANG=$(python3 -c "
import json
cfg = json.load(open('$CONFIG'))
pod = next(p for p in cfg['podcasts'] if p['id'] == '$PODCAST_ID')
print(pod.get('language', 'zh'))
")

echo "RSS: $RSS"
echo "集數: $EPISODE_ARG"

# 用 yt-dlp 抓集數列表，解析標題
if [[ "$EPISODE_ARG" == "latest" ]]; then
  PLAYLIST_ITEM="1"
else
  # 找對應集數（EP663 → 掃標題）
  PLAYLIST_ITEM=$(python3 - <<PYEOF
import subprocess, sys, re

result = subprocess.run(
    ["yt-dlp", "--flat-playlist", "--print", "%(playlist_index)s|%(title)s", "$RSS"],
    capture_output=True, text=True
)
target = "$EPISODE_ARG"
target_num = re.sub(r'[^0-9]', '', target)  # 只取數字部分

for line in result.stdout.strip().split("\n"):
    if "|" not in line:
        continue
    idx, title = line.split("|", 1)
    idx = idx.strip()
    # 精確匹配：EP663、663、或標題包含目標數字
    if target_num and (
        re.search(rf'\bEP0*{target_num}\b', title, re.IGNORECASE) or
        re.search(rf'\b0*{target_num}\b', title)
    ):
        print(idx)
        sys.exit(0)
    # 完整標題匹配（給標題型集數，如 MacroMicro）
    if target.strip() == title.strip():
        print(idx)
        sys.exit(0)

# fallback：只有純數字才當 playlist index，否則下最新集
if target_num and target_num.isdigit() and len(target_num) <= 4:
    print(target_num)
else:
    print("1")  # 找不到 → 下最新集
PYEOF
)
fi

echo "playlist-items: $PLAYLIST_ITEM"

# 建立工作目錄
WORK_DIR="$SKILL_DIR/data/episodes/${PODCAST_ID}_ep${EPISODE_ARG}"
mkdir -p "$WORK_DIR"

# 下載 MP3
# 取 metadata（不下載音頻）
yt-dlp \
  --playlist-items "$PLAYLIST_ITEM" \
  --dump-json \
  --no-download \
  "$RSS" > "$WORK_DIR/meta.json" 2>/dev/null || true

# 下載音頻（只跑一次，progress 才能正確顯示）
yt-dlp \
  --playlist-items "$PLAYLIST_ITEM" \
  -o "$WORK_DIR/audio.%(ext)s" \
  "$RSS" 2>&1

# 找到下載的音頻檔
AUDIO_FILE=$(find "$WORK_DIR" -name "audio.*" | head -1)
if [[ -z "$AUDIO_FILE" ]]; then
  echo "ERROR: 下載失敗，找不到音頻檔" >&2
  exit 1
fi

# 從 meta.json 取得標題和日期
EPISODE_TITLE=$(python3 -c "
import json, sys
try:
    d = json.load(open('$WORK_DIR/meta.json'))
    print(d.get('title', 'Unknown'))
except:
    print('Unknown')
")

EPISODE_DATE=$(python3 -c "
import json, sys
from datetime import date
try:
    d = json.load(open('$WORK_DIR/meta.json'))
    ud = d.get('upload_date', '')
    if ud and len(ud) == 8:
        print(f'{ud[:4]}-{ud[4:6]}-{ud[6:]}')
    else:
        print(date.today().isoformat())
except:
    print(date.today().isoformat())
")

echo "---"
echo "音頻檔：$AUDIO_FILE"
echo "標題：$EPISODE_TITLE"
echo "日期：$EPISODE_DATE"
echo "工作目錄：$WORK_DIR"

# 寫入環境檔，供後續步驟使用
cat > "$WORK_DIR/env.sh" << EOF
export EPISODE_MP3="$AUDIO_FILE"
export EPISODE_TITLE="$EPISODE_TITLE"
export EPISODE_DATE="$EPISODE_DATE"
export WORK_DIR="$WORK_DIR"
export PODCAST_ID="$PODCAST_ID"
export LANG_CODE="$LANG"
EOF

echo "環境檔已寫入：$WORK_DIR/env.sh"
