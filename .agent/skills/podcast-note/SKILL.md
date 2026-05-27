---
name: podcast-note
description: Podcast 音頻 → faster-whisper 轉錄 → Claude 分析 → 投資筆記（note-investment.md 格式）+ 更新待看影片與Podcast清單。支援從 RSS 下載、本地 MP3、或已有逐字稿直接分析。
---

# /podcast-note

給一個 Podcast 節目名稱（或 RSS + 集號），自動完成：
1. RSS → yt-dlp 下載 MP3（或接受本地音頻 / 逐字稿）
2. faster-whisper（GPU 優先）轉錄 → transcript.txt
3. Claude 直接分析（不呼叫外部 LLM）→ `note-investment.md` 格式
4. 輸出 Obsidian 投資筆記 + 更新待看影片與Podcast清單

## Usage

```
# 下載最新集並整理
/podcast-note gooaye

# 下載指定集號
/podcast-note gooaye 663

# 直接使用本地 MP3（跳過下載）
/podcast-note --mp3 /path/to/episode.mp3 --podcast gooaye

# 直接使用已有逐字稿（跳過下載 + 轉錄）
/podcast-note --transcript /tmp/transcripts/EP663_transcript.txt --podcast gooaye
```

## Vault Paths

- **投資筆記**：`/home/trx50/Documents/arthurwang_DB/投資/`
- **工作目錄**：`<PROJECT_ROOT>/podcast-note/data/episodes/<podcast_id>_ep<episode>/`
- **待看影片與Podcast清單**：`/home/trx50/Documents/arthurwang_DB/待看影片與Podcast清單.md`

## Config

`podcast-note/config/podcasts.json` 管理訂閱清單，目前已設定：
- `gooaye`：股癌 Gooaye（RSS: soundon.fm，語言: zh，格式: investment）

新增 Podcast 只需在 `podcasts` 陣列加一筆：

```json
{
  "id": "your_id",
  "name": "節目名稱",
  "rss": "https://...",
  "language": "zh",
  "note_type": "investment",
  "note_dir": "/home/trx50/Documents/arthurwang_DB/投資",
  "reading_list_category": "投資"
}
```

## Scripts

```
podcast-note/scripts/
├── download.sh           # RSS → yt-dlp 下載 MP3 → 寫 env.sh
├── transcribe.py         # MP3 → faster-whisper → transcript.txt + .json
├── generate_note.py      # analysis.json → Obsidian 筆記
└── update_reading_list.py # 更新待看影片與Podcast清單
```

---

## What You Must Do When Invoked

執行步驟依序如下，若使用者提供 `--transcript` 則跳到 Step 3，提供 `--mp3` 則跳到 Step 2。

---

### Step 1 — 解析參數，下載 MP3

判斷呼叫模式：
- `--transcript <path>`：直接跳到 Step 3，設定 `TRANSCRIPT_PATH`
- `--mp3 <path>`：直接跳到 Step 2，設定 `EPISODE_MP3`
- `<podcast_id> [episode]`：執行下載

**下載模式**：

```bash
SKILL_DIR="$(dirname "$(realpath "$0")")"  # SKILL.md 所在目錄
PROJECT_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
PODCAST_ROOT="$PROJECT_ROOT/podcast-note"

# 確認 podcast_id 在 config
PODCAST_ID="<user_input>"  # e.g. gooaye
EPISODE="${episode_arg:-latest}"

bash "$PODCAST_ROOT/scripts/download.sh" "$PODCAST_ID" "$EPISODE"
source "$PODCAST_ROOT/data/episodes/${PODCAST_ID}_ep${EPISODE}/env.sh"
```

`env.sh` 會設定：`EPISODE_MP3`、`EPISODE_TITLE`、`EPISODE_DATE`、`WORK_DIR`、`PODCAST_ID`、`LANG_CODE`

若使用者提供本地路徑（`--mp3`），手動設定：
```bash
export EPISODE_MP3="<user_provided_path>"
export PODCAST_ID="<podcast_id>"
export WORK_DIR="$PODCAST_ROOT/data/episodes/${PODCAST_ID}_manual_$(date +%Y%m%d)"
mkdir -p "$WORK_DIR"
cp "$EPISODE_MP3" "$WORK_DIR/audio.mp3"
```

---

### Step 2 — 轉錄音頻

```bash
# 取得集數標籤（從 info.json 或 EPISODE_TITLE 環境變數萃取）
EPISODE_LABEL=$(python3 -c "
import json, os, re
title = os.environ.get('EPISODE_TITLE', '')
m = re.search(r'EP\d+', title)
print(m.group(0) if m else title[:20])
" 2>/dev/null || echo "unknown")

# faster-whisper 轉錄（GPU 優先，medium 模型）
# 逐字稿同時存到 work_dir（供分析）和 Obsidian Podcast/<podcaster>/transcripts/（永久）
python3.10 "$PODCAST_ROOT/scripts/transcribe.py" "$WORK_DIR" \
  --lang "${LANG_CODE:-zh}" \
  --model medium \
  --device auto \
  --episode "$EPISODE_LABEL"

# 輸出：$WORK_DIR/transcript.txt, $WORK_DIR/transcript.json
```

**GPU 記憶體注意**：若 GPU 空閒記憶體 < 3GB，改用 `--model small`；若 < 1.5GB，改用 `--model base`。
先用 `nvidia-smi --query-gpu=memory.free --format=csv,noheader` 確認。

---

### Step 3 — Claude 分析逐字稿

**DO NOT 呼叫外部 LLM。直接用自己的能力分析。**

讀取 `$WORK_DIR/transcript.txt`（若是 `--transcript` 模式則讀使用者提供的路徑）。

**分析品質要求**（依 `note-investment.md` 規範）：
- 每個投資觀點的「為什麼」必須完整保留因果推論
- 具體數字、指標、時間點一律保留，不得省略
- 操作建議必須具體：時間點 + 動作 + 條件
- 風險分析要說明傳導機制（為什麼 → 如何影響股價）

**長逐字稿（> 15K chars）**：分段讀取，先摘各段重點，再合成完整分析。

產生 JSON 並寫入 `$WORK_DIR/analysis.json`：

```json
{
  "title_zh": "YYYY-MM-DD 股癌 EP663｜[核心主題]（10-20字，提煉核心論點）",
  "note_type": "investment",
  "topic": "台股投資 / [具體主題]",
  "tags": ["主題1", "主題2"],
  "stocks": ["TICKER1"],
  "tldr": {
    "核心主張": "這集在說什麼（一句話）",
    "關鍵機制_問題": "核心邏輯為什麼成立",
    "重要數字": "具體指標、漲幅、時間點",
    "風險_限制": "什麼條件下論點會失效",
    "操作建議": "時間點 + 動作（如：等供需缺口確認後分批布局，注意擴產訊號）"
  },
  "sections": [
    {
      "title": "段落標題（繁體中文，5-20字）",
      "start_time": "MM:SS",
      "content_points": [
        "- **核心概念**：定義 + 為什麼重要",
        "    - **子觀點**：具體說明、數字、邏輯鏈",
        "    - **投資含義**：對應到哪個標的或操作",
        "    - **風險**：什麼情況下這個邏輯不成立"
      ]
    }
  ],
  "key_insights": [
    "洞見1（不超過50字，要有觀點，不只是事實）",
    "洞見2"
  ],
  "investment_framework": {
    "短期（事件驅動）": {
      "觸發因素": "...",
      "跟蹤指標": "...",
      "操作": "..."
    },
    "中期（結構性 6-18 個月）": {
      "主要受益驅動": "...",
      "關鍵里程碑": "..."
    },
    "長期（主題性）": {
      "核心主線": "...",
      "基礎假設": "..."
    }
  },
  "risks": [
    "風險1：傳導機制說明",
    "風險2：傳導機制說明"
  ],
  "data_table": [
    {"指標": "...", "數值": "...", "備註": "..."}
  ],
  "reading_list_category": "投資"
}
```

**Podcast 特有的分析重點**：
- 廣告段落（前 1-2 分鐘的贊助商廣告）跳過，不納入分析
- 閒聊、個人生活分享（減重、育兒等）：若有投資觀點連結則保留，否則簡短帶過
- Q&A 段落：只整理有投資價值的問答，其他略過
- 市場情緒/盤感：主持人的「直覺」和「體感」有時比新聞更早，要保留

寫入 analysis.json 後，同步寫入 `$WORK_DIR/info.json`（若尚未存在）：

```json
{
  "title": "原始集數標題",
  "channel": "股癌 Gooaye",
  "episode": "EP663",
  "duration": "33:14",
  "upload_date": "2026-05-20",
  "rss": "https://feeds.soundon.fm/..."
}
```

---

### Step 4 — 產生 Obsidian 筆記

```bash
export PODCAST_ID="gooaye"  # 確保環境變數已設定
python3.10 "$PODCAST_ROOT/scripts/generate_note.py" "$WORK_DIR"

# 筆記路徑記錄在 $WORK_DIR/note_path.txt
NOTE_PATH=$(cat "$WORK_DIR/note_path.txt")
echo "筆記：$NOTE_PATH"
```

**檔名格式**：`YYYY-MM-DD [核心主題].md`（與 `title_zh` 相同，去掉非法字符）

---

### Step 5 — 更新待看影片與Podcast清單

```bash
python3.10 "$PODCAST_ROOT/scripts/update_reading_list.py" "$WORK_DIR"
```

---

### Step 6 — 報告

輸出：
- 筆記路徑
- 章節數、洞見數
- 轉錄耗時（若有執行轉錄）
- 待看影片與Podcast清單更新狀態

---

## Edge Cases

| 情況 | 處理方式 |
|------|---------|
| GPU OOM（large-v3）| 自動降為 medium，再不行降 small |
| 廣告段落 | 跳過前 2 分鐘或依內容判斷，不整理進筆記 |
| 長逐字稿（>15K chars） | 分段分析，各段摘要後合成 |
| 無具體股票代碼 | `stocks` 留空陣列 `[]` |
| 純閒聊集 | 仍整理，但 `投資框架` 區塊可省略 |
| 集號已存在（note_path 衝突） | 自動加 `-ep{N}` suffix |
| RSS 下載失敗 | 提示使用者直接提供 MP3 路徑（`--mp3` 模式）|

## Architecture

```
用戶輸入（podcast_id + 集號 / MP3 / 逐字稿）
 │
 ├─ Step 1: 下載 (download.sh) ← RSS → yt-dlp → audio.mp3
 │           或接受本地 MP3 / transcript 直接跳過
 ├─ Step 2: 轉錄 (transcribe.py) ← faster-whisper GPU
 │           cuDNN 9 symlink 自動處理
 ├─ Step 3: Claude 分析 ← 直接讀 transcript.txt
 │           note-investment.md 格式（TL;DR + 章節 + 框架 + 風險）
 ├─ Step 4: 生成筆記 (generate_note.py) → 投資/ 目錄
 ├─ Step 5: 更新待看影片與Podcast清單 (update_reading_list.py)
 └─ Step 6: 報告
```
