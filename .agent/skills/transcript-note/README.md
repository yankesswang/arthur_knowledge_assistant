# transcript-note

YouTube 影片 → Obsidian 筆記的自動化工作流。

---

## 使用方式

在 Claude Code 輸入：

```
/transcript-note https://www.youtube.com/watch?v=VIDEO_ID
```

或短網址：

```
/transcript-note https://youtu.be/VIDEO_ID
```

Claude 會自動完成：下載字幕 → 分析內容 → 產生 Obsidian 筆記 → 更新待看影片與Podcast清單 → 更新影片索引。

### 處理佇列

當佇列有待處理的影片時，直接說：

```
/transcript-note
（或）「幫我跑佇列」
```

---

## 頻道監控設定

### 新增監控頻道

編輯 `config/channels.json`，在 `channels` 陣列中加入一個物件：

```json
{
  "channels": [
    {
      "handle": "@ILTB_Podcast",
      "name": "Invest Like The Best",
      "limit": 5,
      "enabled": true
    },
    {
      "handle": "@DwarkeshPatel",
      "name": "Dwarkesh Podcast",
      "limit": 3,
      "enabled": true
    }
  ]
}
```

| 欄位 | 說明 |
|------|------|
| `handle` | YouTube 頻道的 `@xxx` handle（從頻道網址取得） |
| `name` | 自訂顯示名稱，用於 log |
| `limit` | 每次掃描最多抓幾部最新影片加入佇列 |
| `enabled` | `false` 可暫停這個頻道但保留設定 |

### 手動觸發頻道掃描

```bash
bash ~/.../transcript-note/scripts/check_channels.sh
```

執行後，新發現的影片 URL 會自動寫入 `data/queue.txt`。

### 自動排程（已設定）

LaunchAgent 每天早上 **8:30** 自動執行 `check_channels.sh`。  
Log 位置：`/tmp/transcript-note-check.log`

查看 log：
```bash
cat /tmp/transcript-note-check.log
```

---

## 檔案結構

```
transcript-note/
├── SKILL.md                    # Claude 的執行指令（勿手動編輯）
├── README.md                   # 本文件
│
├── config/
│   └── channels.json           # 監控頻道清單
│
├── data/
│   ├── queue.txt               # 待處理影片 URL（一行一條）
│   ├── processed_ids.txt       # 已處理的 video ID（防止重複）
│   └── transcripts/            # 每支影片的永久原始資料
│       └── VIDEO_ID/
│           ├── condensed.txt   # 壓縮逐字稿（60 秒一桶）
│           ├── info.json       # 標題、頻道、時長、章節
│           ├── analysis.json   # Claude 的分析結果
│           └── meta.json       # yt-dlp 原始 metadata
│
└── scripts/
    ├── setup.sh                # 下載字幕 + 解析 VTT
    ├── parse_vtt.py            # VTT → condensed.txt
    ├── finalize.sh             # 產生筆記 + 更新清單
    ├── generate_note.py        # 輸出 Obsidian .md
    ├── update_reading_list.py  # 更新待看影片與Podcast清單
    ├── update_index.py         # 更新 _INDEX.md
    ├── check_channels.sh       # 掃描頻道 → 寫入 queue.txt
    └── mark_processed.sh       # 標記已處理
```

---

## Obsidian 輸出位置

| 產出物 | 路徑 |
|--------|------|
| 影片筆記 | `arthurwang_DB/AI Knowledge/影片筆記/` |
| 影片總索引 | `arthurwang_DB/AI Knowledge/影片筆記/_INDEX.md` |
| 待看影片與Podcast清單 | `arthurwang_DB/待看影片與Podcast清單.md` |

### 筆記格式

每篇筆記包含：
- 影片封面縮圖
- TL;DR（核心主張、關鍵機制、重要結論、適用條件）
- 影片資訊表（頻道、時長、發布日、來源連結）
- 章節筆記（含 timestamp 連結）
- 關鍵洞見
- 關鍵數據速查表
- 同頻道影片（wikilink 連結）

---

## 整體流程

```
check_channels.sh（每天 8:30）
       ↓
新影片 URL → data/queue.txt
       ↓
/transcript-note（手動觸發）
       ↓
setup.sh：下載字幕 → data/transcripts/VIDEO_ID/
       ↓
Claude 分析：寫入 analysis.json
       ↓
finalize.sh：產生 .md + 更新清單 + 更新 _INDEX.md
       ↓
mark_processed.sh：VIDEO_ID 移入 processed_ids.txt
```

---

## 常見操作

### 查看目前佇列
```bash
cat data/queue.txt
```

### 查看已處理的影片
```bash
cat data/processed_ids.txt
```

### 手動加入單支影片到佇列
```bash
echo "https://www.youtube.com/watch?v=VIDEO_ID" >> data/queue.txt
```

### 暫停某個頻道的監控
在 `config/channels.json` 把該頻道的 `"enabled"` 改為 `false`。

### 查看原始逐字稿
```bash
cat data/transcripts/VIDEO_ID/condensed.txt
```
