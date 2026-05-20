#!/usr/bin/env bash
# Instagram 貼文下載工具
# 用法：
#   ig_download.sh <帳號> --count 10
#   ig_download.sh <帳號> --since 2026-01-01
#   ig_download.sh <帳號> --since 2026-01-01 --until 2026-05-01
#   ig_download.sh <帳號> --count 5 --output ~/Downloads/IG

set -e

# ── 載入 nvm ───────────────────────────────────────────
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# ── 預設值 ─────────────────────────────────────────────
USERNAME=""
COUNT=""
SINCE=""
UNTIL=""
OUTPUT_BASE="$HOME/Downloads/Instagram"
BROWSER="chrome"

# ── 解析參數 ───────────────────────────────────────────
usage() {
    echo "用法："
    echo "  $(basename $0) <帳號> [選項]"
    echo ""
    echo "選項："
    echo "  --count <數量>          下載最新 N 篇（例：--count 10）"
    echo "  --since <日期>          下載指定日期之後（例：--since 2026-01-01）"
    echo "  --until <日期>          下載指定日期之前（例：--until 2026-05-01）"
    echo "  --output <資料夾>       儲存位置（預設：~/Downloads/Instagram）"
    echo "  --browser <瀏覽器>      cookie 來源：chrome / firefox（預設：chrome）"
    echo ""
    echo "範例："
    echo "  $(basename $0) t40533 --count 10"
    echo "  $(basename $0) t40533 --since 2026-01-01"
    echo "  $(basename $0) t40533 --since 2026-01-01 --until 2026-05-01"
    echo "  $(basename $0) t40533 --count 5 --output ~/Desktop/IG"
    exit 1
}

[ $# -lt 1 ] && usage

USERNAME="$1"
shift

while [[ $# -gt 0 ]]; do
    case "$1" in
        --count)   COUNT="$2";   shift 2 ;;
        --since)   SINCE="$2";   shift 2 ;;
        --until)   UNTIL="$2";   shift 2 ;;
        --output)  OUTPUT_BASE="$2"; shift 2 ;;
        --browser) BROWSER="$2"; shift 2 ;;
        *) echo "❌ 未知參數：$1"; usage ;;
    esac
done

# ── 驗證參數 ───────────────────────────────────────────
if [ -z "$COUNT" ] && [ -z "$SINCE" ]; then
    echo "❌ 請指定 --count 或 --since"
    usage
fi

# ── 建立輸出目錄 ───────────────────────────────────────
OUTPUT_DIR="$OUTPUT_BASE/$USERNAME"
mkdir -p "$OUTPUT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📥 下載 @$USERNAME 的 Instagram 貼文"
echo "📁 儲存到：$OUTPUT_DIR"
[ -n "$COUNT" ] && echo "📊 數量：最新 $COUNT 篇"
[ -n "$SINCE" ] && echo "📅 起始：$SINCE"
[ -n "$UNTIL" ] && echo "📅 截止：$UNTIL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 組合 gallery-dl 參數 ───────────────────────────────
GALLERY_ARGS=(
    "--cookies-from-browser" "$BROWSER"
    "-o" "directory=[\"$USERNAME\", \"{post_shortcode}\"]"
    "-o" "base-directory=$OUTPUT_BASE"
    "--write-info-json"
)

# 數量模式
if [ -n "$COUNT" ]; then
    GALLERY_ARGS+=("--range" "1-$COUNT")
fi

# 日期過濾（gallery-dl 用 --filter）
DATE_FILTER=""
if [ -n "$SINCE" ] && [ -n "$UNTIL" ]; then
    DATE_FILTER="date >= datetime(${SINCE//-/,}) and date <= datetime(${UNTIL//-/,})"
elif [ -n "$SINCE" ]; then
    DATE_FILTER="date >= datetime(${SINCE//-/,})"
elif [ -n "$UNTIL" ]; then
    DATE_FILTER="date <= datetime(${UNTIL//-/,})"
fi

if [ -n "$DATE_FILTER" ]; then
    GALLERY_ARGS+=("--filter" "$DATE_FILTER")
fi

GALLERY_ARGS+=("https://www.instagram.com/$USERNAME/")

# ── 執行下載 ───────────────────────────────────────────
echo ""
echo "🚀 開始下載..."
gallery-dl "${GALLERY_ARGS[@]}" 2>&1 | grep -v "^\[cookies\]"

# ── 為每個 post 資料夾產生 caption.txt ────────────────
echo ""
echo "📝 整理 caption..."

python3 << PYEOF
import os, json, glob

base = "$OUTPUT_BASE/$USERNAME"
count = 0

for shortcode in sorted(os.listdir(base)):
    folder = os.path.join(base, shortcode)
    if not os.path.isdir(folder):
        continue

    caption_file = os.path.join(folder, "caption.txt")
    if os.path.exists(caption_file):
        continue  # 已有 caption，跳過

    info_files = glob.glob(f"{folder}/*.json")
    if not info_files:
        continue

    with open(info_files[0], encoding="utf-8") as f:
        try:
            info = json.load(f)
        except:
            continue

    caption   = info.get("description", "(無文字)")
    date      = str(info.get("date", ""))
    likes     = info.get("likes", 0)
    comments  = info.get("comments", 0)
    media_type = info.get("typename", info.get("type", ""))
    post_url  = f"https://www.instagram.com/p/{shortcode}/"

    media_files = [f for f in os.listdir(folder) if f.endswith((".jpg", ".mp4", ".png", ".jpeg"))]

    content  = f"URL: {post_url}\n"
    content += f"帳號: @$USERNAME\n"
    content += f"日期: {date}\n"
    content += f"類型: {media_type} | 媒體數: {len(media_files)}\n"
    content += f"讚數: {likes} | 留言數: {comments}\n"
    content += f"\n{caption}\n"

    with open(caption_file, "w", encoding="utf-8") as f:
        f.write(content)

    count += 1

print(f"✅ 已產生 {count} 個 caption.txt")
PYEOF

# ── 顯示結果摘要 ───────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 下載結果摘要"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for folder in "$OUTPUT_DIR"/*/; do
    shortcode=$(basename "$folder")
    media_count=$(find "$folder" -maxdepth 1 \( -name "*.jpg" -o -name "*.mp4" -o -name "*.png" \) | wc -l)
    has_caption=$([ -f "$folder/caption.txt" ] && echo "✅" || echo "❌")
    echo "  📁 $shortcode  |  媒體: $media_count  |  Caption: $has_caption"
done

total_folders=$(find "$OUTPUT_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)
echo ""
echo "✅ 完成！共 $total_folders 篇貼文存於 $OUTPUT_DIR"
