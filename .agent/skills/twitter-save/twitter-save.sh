#!/usr/bin/env bash
# ============================================================
# twitter-save.sh — 下載 X/Twitter 內容到本地
# 用法：直接改下面的 URL 變數，然後執行這個腳本
# ============================================================

URL="https://x.com/intuitiveml/status/2043545596699750791"

# ============================================================
# 以下不需要修改
# ============================================================

set -e

export NVM_DIR="$HOME/.nvm"
# shellcheck disable=SC1091
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm use 22 --silent 2>/dev/null || true

OUT_DIR="$(cd "$(dirname "$0")" && pwd)/downloads"
mkdir -p "$OUT_DIR"

# 解析 t.co 短網址
if [[ "$URL" == https://t.co/* ]]; then
  RESOLVED=$(curl -sI "$URL" | grep -i '^location:' | tr -d '\r' | awk '{print $2}')
  echo "🔗 短網址解析 → $RESOLVED"
  URL="$RESOLVED"
fi

# 判斷類型
if [[ "$URL" == *"/i/article/"* ]]; then
  CONTENT_TYPE="article"
  ID=$(echo "$URL" | grep -oE '[0-9]+' | tail -1)
  # 解析文章對應的 status URL（article 指令接受 article URL，直接帶入即可）
  FETCH_URL="$URL"
elif [[ "$URL" == *"/status/"* ]]; then
  ID=$(echo "$URL" | grep -oE '/status/[0-9]+' | grep -oE '[0-9]+')
  AUTHOR=$(echo "$URL" | grep -oE 'x\.com/([^/]+)/status' | sed 's|x.com/||;s|/status||')

  # 先嘗試 article（tweet 可能附帶長文）
  echo "⏳ 嘗試抓取長文 article..."
  ARTICLE_RAW=$(opencli twitter article "$URL" 2>&1 || true)
  if echo "$ARTICLE_RAW" | grep -q "^- author:"; then
    CONTENT_TYPE="both"
  else
    CONTENT_TYPE="thread"
  fi
  FETCH_URL="$URL"
else
  echo "❌ 無法識別的 URL：$URL"
  echo "   支援格式：https://x.com/<user>/status/<id> 或 https://x.com/i/article/<id>"
  exit 1
fi

# 下載並儲存
case "$CONTENT_TYPE" in
  article)
    echo "⏳ 下載 Article..."
    RAW=$(opencli twitter article "$FETCH_URL" 2>&1)
    AUTHOR=$(echo "$RAW" | grep '^ *author:' | head -1 | awk '{print $2}')
    FILE="$OUT_DIR/article_${AUTHOR}_${ID}.yaml"
    echo "$RAW" > "$FILE"
    IMG_COUNT=$(grep -c '!\[' "$FILE" 2>/dev/null || echo 0)
    echo "✅ Article 已儲存"
    echo "   路徑：$FILE"
    echo "   作者：$AUTHOR"
    echo "   圖片：${IMG_COUNT} 張"
    ;;

  thread)
    echo "⏳ 下載 Thread..."
    RAW=$(opencli twitter thread "$FETCH_URL" 2>&1)
    AUTHOR=$(echo "$RAW" | grep '^ *author:' | head -1 | awk '{print $2}')
    FILE="$OUT_DIR/thread_${AUTHOR}_${ID}.yaml"
    echo "$RAW" > "$FILE"
    TWEET_COUNT=$(grep -c '^ *- id:' "$FILE" 2>/dev/null || echo 0)
    echo "✅ Thread 已儲存"
    echo "   路徑：$FILE"
    echo "   作者：$AUTHOR"
    echo "   推文數：${TWEET_COUNT} 則"
    ;;

  both)
    # Article
    ARTICLE_AUTHOR=$(echo "$ARTICLE_RAW" | grep -m1 'author:' | sed 's/.*author: *//')
    ARTICLE_FILE="$OUT_DIR/article_${ARTICLE_AUTHOR}_${ID}.yaml"
    echo "$ARTICLE_RAW" > "$ARTICLE_FILE"
    IMG_COUNT=$(grep -c '!\[' "$ARTICLE_FILE" 2>/dev/null || echo 0)

    # Thread
    echo "⏳ 下載 Thread 回覆..."
    THREAD_RAW=$(opencli twitter thread "$FETCH_URL" 2>&1)
    THREAD_FILE="$OUT_DIR/thread_${ARTICLE_AUTHOR}_${ID}.yaml"
    echo "$THREAD_RAW" > "$THREAD_FILE"
    TWEET_COUNT=$(grep -c '^ *- id:' "$THREAD_FILE" 2>/dev/null || echo 0)

    echo "✅ Article + Thread 已儲存"
    echo "   Article：$ARTICLE_FILE（圖片 ${IMG_COUNT} 張）"
    echo "   Thread ：$THREAD_FILE（推文 ${TWEET_COUNT} 則）"
    ;;
esac
