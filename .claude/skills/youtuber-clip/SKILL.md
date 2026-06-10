---
name: youtuber-clip
description: YouTube URL → 下載影片 → 字幕翻譯 → 人臉追蹤裁切 → 精華 supercut（9:16 Shorts）
tags: [youtube, clip, shorts, face-tracking, supercut, 剪輯]
allowed-tools: Bash, Read, Write
---

# /youtuber-clip

給一個 YouTube URL，自動完成：
1. yt-dlp 下載影片（1080p）+ 字幕
2. OpenAI API 翻譯字幕（繁體中文）
3. Claude 分析逐字稿 → 挑出 10 個最強爆點 + 精確時間碼
4. insightface 人臉偵測 → 動態裁切為 9:16 垂直格式
5. ffmpeg 合成 30 秒 supercut（zoom punch-in + 黃色置中大字卡 + 色彩增強）

**輸出**：`/home/trx50/video_transcript/<channel>-<video_id>/`
- `supercut.mp4` — 30 秒精華，1080×1920，直接可上傳 YouTube Shorts
- `clips/` — 10 個個別精華片段（橫版原始）
- `face/` — 10 個人臉追蹤裁切版（9:16，無字幕）

## Usage

```
/youtuber-clip https://www.youtube.com/watch?v=VIDEO_ID
/youtuber-clip https://youtu.be/VIDEO_ID
/youtuber-clip https://www.youtube.com/watch?v=VIDEO_ID --no-translate   # 跳過翻譯
```

## 依賴環境

| 工具 | 路徑 | 用途 |
|------|------|------|
| yt-dlp | `/home/trx50/.virtualenvs/chatbot/bin/yt-dlp` | 下載影片 + 字幕 |
| ffmpeg | `/usr/bin/ffmpeg` | 裁片、合成、drawtext |
| Python venv (face) | `/home/trx50/.virtualenvs/face/bin/python3` | insightface 人臉追蹤 |
| Python venv (chatbot) | `/home/trx50/.virtualenvs/chatbot/bin/python3` | openai SDK 翻譯 |
| OpenAI API key | `/home/trx50/gitlab/gigabyte_kg/.env` → `OPENAI_API_KEY` | gpt-4o-mini 翻譯 |
| Noto Sans CJK TC Black | `/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc` | 字卡字體 |

## Scripts

```
scripts/
├── 01_download.sh         # yt-dlp 下載影片 + 字幕
├── 02_parse_vtt.py        # VTT → srt_entries.json（6 秒合併）
├── 03_translate.py        # OpenAI gpt-4o-mini 批次翻譯
├── 04_face_track.py       # insightface + ffmpeg → 9:16 人臉追蹤版
└── 05_supercut.py         # 爆點裁切 + zoom/字卡/合成 supercut

data/
└── <VIDEO_ID>/
    ├── video.mp4          # 原始影片
    ├── subs.en.vtt        # 英文字幕
    ├── srt_entries.json   # 解析後含翻譯的字幕段落
    ├── meta.json          # 影片 metadata
    ├── clips/             # 橫版精華片段
    ├── face/              # 9:16 人臉追蹤片段
    └── supercut/          # 最終輸出
```

---

## What You Must Do When Invoked

**所有步驟全自動，除非遇到錯誤。**

---

### Step 0 — 解析輸入

從使用者訊息提取：
- `YT_URL`：完整 YouTube URL
- `SKIP_TRANSLATE`：若有 `--no-translate` 旗標則為 true

```bash
VIDEO_ID=$(python3 - "$YT_URL" << 'PYEOF'
import re, sys
url = sys.argv[1]
for p in [r'(?:v=)([A-Za-z0-9_-]{11})', r'youtu\.be/([A-Za-z0-9_-]{11})']:
    m = re.search(p, url)
    if m: print(m.group(1)); exit(0)
PYEOF
)

SKILL_DIR="/home/trx50/Project/arthur_knowledge_assistant/.agent/skills/youtuber-clip"
WORK_DIR="$SKILL_DIR/data/$VIDEO_ID"
mkdir -p "$WORK_DIR/clips" "$WORK_DIR/face" "$WORK_DIR/supercut"
echo "VIDEO_ID=$VIDEO_ID"
echo "WORK_DIR=$WORK_DIR"
```

---

### Step 1 — 下載影片 + 字幕

```bash
bash "$SKILL_DIR/scripts/01_download.sh" "$YT_URL" "$WORK_DIR"
```

輸出：`$WORK_DIR/video.mp4`、`$WORK_DIR/subs.en.vtt`、`$WORK_DIR/meta.json`

---

### Step 2 — 解析 VTT → srt_entries.json

```bash
/home/trx50/.virtualenvs/chatbot/bin/python3 "$SKILL_DIR/scripts/02_parse_vtt.py" "$WORK_DIR"
```

輸出：`$WORK_DIR/srt_entries.json`（含 start/end/original 欄位，6 秒合併）

---

### Step 3 — 翻譯字幕（可跳過）

若 `SKIP_TRANSLATE=false`：

```bash
OPENAI_KEY=$(grep OPENAI_API_KEY /home/trx50/gitlab/gigabyte_kg/.env | head -1 | cut -d'"' -f2)
OPENAI_API_KEY="$OPENAI_KEY" \
  /home/trx50/.virtualenvs/chatbot/bin/python3 "$SKILL_DIR/scripts/03_translate.py" "$WORK_DIR"
```

翻譯完成後在 `srt_entries.json` 每筆加入 `translated` 欄位。

---

### Step 4 — Claude 分析逐字稿 → 挑出 10 個爆點

讀取 `$WORK_DIR/srt_entries.json` 和 `$WORK_DIR/meta.json`，**自行分析**（不呼叫外部工具），依以下標準挑出 10 個最強爆點：

**選取標準**（依優先順序）：
1. **反直覺數字**：具體數字 + 讓人意外的結論
2. **強烈對比**：「X 只要 Y，但 Z 卻要 W」
3. **新框架 / 新術語**：說話者現場定義新概念
4. **情感高點**：語氣激昂、使用強烈比喻
5. **主題多元**：10 個片段涵蓋不同面向，不重複

**每個爆點輸出**：
- `abs_start`：在原始影片的開始秒數
- `abs_end`：在原始影片的結束秒數（建議片段約 90 秒，含前後文）
- `slug`：英文短標題（`kebab-case`，含編號前綴如 `01-`）
- `moment_start`：片段內金句的開始秒（相對於 abs_start）
- `moment_dur`：金句持續秒數（2.5–4 秒）
- `label_line1`：字卡第一行（繁體中文，≤ 10 字）
- `label_line2`：字卡第二行（繁體中文，≤ 10 字，可留空）

用 Write 工具將結果寫入 `$WORK_DIR/moments.json`。

**格式參考 sample**（可直接讀取對照）：
`$SKILL_DIR/data/moments.sample.json`

```json
[
  {
    "abs_start": 0,        // 在原始影片的開始秒數
    "abs_end": 90,         // 在原始影片的結束秒數（片段含前後文，建議 60-120 秒）
    "slug": "01-example-slug",          // kebab-case，含兩位數字前綴
    "moment_start": 23.7,  // 金句在片段內的開始秒（相對於 abs_start）
    "moment_dur": 3.5,     // 金句持續秒數（2.5–4 秒）
    "label_line1": "第一行標題",   // ≤ 10 字
    "label_line2": "第二行標題"    // ≤ 10 字，可空字串 ""
  }
]
```

---

### Step 5 — 裁片（橫版原始）

```bash
/home/trx50/.virtualenvs/chatbot/bin/python3 "$SKILL_DIR/scripts/04a_cut_clips.py" "$WORK_DIR"
```

從 `moments.json` 讀取時間碼，用 ffmpeg 從 `video.mp4` 裁出各片段，存入 `$WORK_DIR/clips/`。

---

### Step 6 — 人臉追蹤 → 9:16 裁切

```bash
/home/trx50/.virtualenvs/face/bin/python3 "$SKILL_DIR/scripts/04b_face_track.py" "$WORK_DIR"
```

對每個 clip：
- insightface `buffalo_sc` 每 15 幀偵測最大臉，取水平中心點
- 線性插值 + EMA 平滑（α=0.08）
- ffmpeg sendcmd 動態 crop（607×1080）→ scale（1080×1920）
- 輸出存入 `$WORK_DIR/face/`

---

### Step 7 — 合成 Supercut

```bash
/home/trx50/.virtualenvs/face/bin/python3 "$SKILL_DIR/scripts/05_supercut.py" "$WORK_DIR"
```

對每個金句片段（`moment_start` + `moment_dur`）：
- **zoom punch-in**：前 9 幀 1.05x → 1.0x（zoompan）
- **色彩增強**：saturation 1.3, contrast 1.06
- **置中大字卡**：黃色 `#FFE033`，Noto Sans CJK TC Black，72px，黑描邊 5px + 陰影，全程顯示
- concat 所有片段，輸出 `$WORK_DIR/supercut/supercut.mp4`

同時把 supercut 複製到 `/home/trx50/video_transcript/<slug>/supercut.mp4`。

---

### Step 8 — 報告

輸出摘要：
```
=== youtuber-clip 完成 ===
影片    : <標題>
頻道    : <頻道名>
爆點數  : 10
Supercut: /home/trx50/video_transcript/<slug>/supercut.mp4
          31.5 秒 | 20.6 MB | 1080×1920
個別片段: /home/trx50/video_transcript/<slug>/face/
```

---

## Edge Cases

| 情況 | 處理方式 |
|------|---------|
| 無英文字幕 | 嘗試 auto-generated；若無任何字幕，跳過翻譯步驟，Claude 從描述分析 |
| OpenAI key 不存在 | 跳過翻譯，Claude 直接從英文逐字稿分析 |
| 某幀無法偵測到臉 | 插值補齊；若整段無臉，改用水平置中裁切 |
| 影片超過 2 小時 | 下載前警告磁碟空間（預估 2–4 GB），詢問是否繼續 |
| 金句時間點超出片段範圍 | clamp 到片段最後 2 秒 |
| ffmpeg zoompan 錯誤 | fallback 移除 zoompan，直接裁切 |

## Architecture

```
YouTube URL
 │
 ├─ 01_download.sh       → video.mp4 + subs.en.vtt + meta.json
 ├─ 02_parse_vtt.py      → srt_entries.json
 ├─ 03_translate.py      → srt_entries.json（+translated）
 ├─ Claude 分析           → moments.json（10 個爆點時間碼）
 ├─ 04a_cut_clips.py     → clips/*.mp4（橫版）
 ├─ 04b_face_track.py    → face/*.mp4（9:16 無字幕）
 └─ 05_supercut.py       → supercut/supercut.mp4（30s Shorts）
```

## 參數說明

| 參數 | 預設 | 說明 |
|------|------|------|
| 輸出解析度 | 1080×1920 | YouTube Shorts 標準 |
| 裁切框寬度 | 607px（SRC_H × 9/16） | 來源 1080p 的 9:16 裁切 |
| EMA 平滑係數 | 0.08 | 越小越平滑，防止畫面抖動 |
| 人臉偵測頻率 | 每 15 幀 | ~2fps，平衡速度與精度 |
| 字卡字體大小 | 72px | 1080×1920 最佳可讀性 |
| zoom punch-in | 1.05x → 1.0x | 前 9 幀（0.3 秒） |
| 色彩飽和度 | 1.3 | 視覺衝擊增強 |
