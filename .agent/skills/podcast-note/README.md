# podcast-note

Podcast 音頻 → faster-whisper 轉錄 → Claude 分析 → Obsidian 投資筆記。
附帶 FastAPI web server，提供 Podcast + YouTube 的統一瀏覽介面。

---

## 目錄結構

```
podcast-note/
├── SKILL.md                      # Claude Code skill 定義（/podcast-note 指令）
├── config/
│   └── podcasts.json             # Podcast 訂閱清單（id、RSS、語言）
├── data/
│   ├── episodes/                 # 每集工作目錄（音頻、逐字稿、analysis.json）
│   ├── inbox.json                # Server 收件匣（待整理條目）
│   └── server_cache.sqlite3      # YouTube 遠端快取（SQLite）
├── docs/
│   └── analyze-method-comparison.md  # 分析方法三版本比較與演進紀錄
├── scripts/                      # 批次處理 pipeline
│   ├── download.sh               # RSS → yt-dlp → audio.mp3 + env.sh
│   ├── transcribe.py             # MP3 → faster-whisper → transcript.txt / .json
│   ├── analyze.py                # transcript.txt → analysis.json（v3 架構）
│   ├── generate_note.py          # analysis.json → Obsidian 投資筆記
│   └── update_reading_list.py    # 更新待看影片與Podcast清單.md
└── server/                       # FastAPI web server
    ├── run.sh                    # 啟動腳本（自動清除佔用 port）
    ├── main.py                   # FastAPI 入口，掛載三組 router
    ├── settings.py               # 所有路徑與環境變數設定
    ├── state.py                  # 跨 module 共用狀態（jobs、快取）
    ├── cache_store.py            # SQLite 快取讀寫
    ├── config_store.py           # podcasts.json 讀寫
    ├── podcast_routes.py         # Podcast API（/api/podcasters, /api/jobs, ...）
    ├── podcast_services.py       # Podcast 業務邏輯（RSS、筆記解析）
    ├── podcast_jobs.py           # 下載 + 分析非同步 job
    ├── reading_routes.py         # 待看清單 API（/api/reading-list, /api/inbox）
    ├── remote.py                 # 啟動時背景預抓遠端清單
    ├── youtube_routes.py         # YouTube API（/api/youtube/channels, ...）
    └── youtube_services.py       # YouTube 業務邏輯（yt-dlp、transcript、avatar）
```

---

## 快速啟動（Web Server）

```bash
cd server
bash run.sh
# → http://localhost:7654
```

> Server 已搬到專案根目錄 `./server/`；`data/`、`config/`、`scripts/` 仍留在這個 skill 資料夾。

`run.sh` 會：
1. 自動載入 `.env`（專案根目錄或 server/ 目錄）
2. 檢查並釋放已佔用的 port
3. 執行 `python3.10 main.py`（uvicorn reload 模式）

---

## 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `PORT` | `7654` | Server 監聽 port |
| `HOST` | `0.0.0.0` | Server 監聽 host |
| `VAULT_ROOT` | `~/Documents/arthurwang_DB` | Obsidian vault 根目錄 |
| `YT_NOTE_DIR` | `$VAULT_ROOT/影片筆記` | YouTube 筆記存放目錄 |
| `READING_LIST_PATH` | `$VAULT_ROOT/待看影片與Podcast清單.md` | 待看清單路徑 |
| `YT_REMOTE_LIMIT` | `all` | 每個頻道抓取影片數（`all` 或正整數） |
| `YT_CACHE_TTL_SECONDS` | `86400` | YouTube 遠端快取有效期（秒） |
| `YT_AUTO_TRANSCRIPT` | `1` | 是否自動背景轉錄 YouTube 影片 |
| `YT_AUTO_TRANSCRIPT_INTERVAL_SECONDS` | `3600` | 自動轉錄輪詢間隔（秒） |

---

## Podcast 設定（config/podcasts.json）

```json
{
  "podcasts": [
    {
      "id": "gooaye",
      "name": "股癌 Gooaye",
      "rss": "https://feeds.soundon.fm/...",
      "language": "zh",
      "note_type": "investment",
      "note_dir": "/home/trx50/Documents/arthurwang_DB/投資",
      "reading_list_category": "投資"
    }
  ]
}
```

新增 Podcast 只需在陣列加一筆；server 啟動時會自動背景預抓遠端集數列表。

---

## 批次 Pipeline（/podcast-note 指令）

```
使用者輸入
 │
 ├─ Step 1  download.sh     RSS → yt-dlp → audio.mp3 + env.sh
 │          （或 --mp3 / --transcript 直接跳過）
 ├─ Step 2  transcribe.py   MP3 → faster-whisper（GPU auto, medium 模型）→ transcript.txt
 ├─ Step 3  analyze.py      transcript → 去時間戳 → Claude 分析 → analysis.json
 │          （+ difflib 模糊比對補回各段 start_time）
 ├─ Step 4  generate_note.py  analysis.json → Obsidian .md 投資筆記
 ├─ Step 5  update_reading_list.py  更新待看影片與Podcast清單.md
 └─ Step 6  報告（筆記路徑、章節數、轉錄耗時）
```

### 用法

```bash
# Claude Code 指令
/podcast-note gooaye          # 下載最新集
/podcast-note gooaye 663      # 下載指定集號
/podcast-note --mp3 /path/to/audio.mp3 --podcast gooaye
/podcast-note --transcript /path/to/transcript.txt --podcast gooaye
```

### 分析架構（v3，當前版本）

| 步驟 | 做法 |
|------|------|
| 壓縮 | 去除時間戳，82KB → ~60KB（節省 ~27%） |
| 送入 | 完整逐字稿一次送 Claude（不截斷、不分段） |
| 補時間戳 | 每段填 `anchor_text`，difflib 模糊比對原稿補回 `start_time` |

> 三版本詳細比較見 [docs/analyze-method-comparison.md](docs/analyze-method-comparison.md)。

---

## Web Server API

### Podcast

| Endpoint | 說明 |
|----------|------|
| `GET /api/podcasters` | 所有 podcaster + 集數列表（本地 + 遠端合併） |
| `GET /api/jobs` | 當前下載 / 分析 job 狀態 |
| `POST /api/download` | 觸發下載 + 分析 job |

### YouTube

| Endpoint | 說明 |
|----------|------|
| `GET /api/youtube/channels` | 所有訂閱頻道 + 影片列表 |
| `POST /api/youtube/transcript` | 觸發影片轉錄 job |
| `GET /api/youtube/queue` | 轉錄排隊狀態 |

### 待看清單 / Inbox

| Endpoint | 說明 |
|----------|------|
| `GET /api/reading-list` | 讀取 `待看影片與Podcast清單.md` |
| `GET /api/inbox` | 收件匣條目列表 |
| `POST /api/inbox/dismiss` | 標記條目已處理 |

---

## YouTube 新影片自動處理機制

### 流程

```
Server 啟動（+15 秒後）
    │
    └─ yt-auto worker 背景循環（每 YT_AUTO_TRANSCRIPT_INTERVAL_SECONDS，預設 3600 秒）
            │
            ├─ 1. enqueue：掃描每頻道 _remote_yt_cache 最新 N 支影片
            │       已有逐字稿 → 跳過
            │       尚無逐字稿 → 加入 queue.txt
            │
            └─ 2. process：對 queue.txt 每支影片
                    _run_yt_transcript_job()
                        └─ setup.sh（yt-dlp 抓 CC 字幕）→ condensed.txt
                           ✗ 不自動產生 Obsidian 筆記（需手動按「產生筆記」）
```

### 新影片上傳後的時間線

| 時間點 | 系統狀態 |
|--------|---------|
| 影片上傳 | yt-dlp cache 還沒有這支影片 |
| server 重啟 / 24h TTL 過期 | `_prefetch_all_remote` 刷新 cache，新影片進入 `_remote_yt_cache` |
| 下一次 worker 循環（最多 1 小時後）| 新影片加入 queue → 自動抓 CC 字幕 |
| 抓完字幕 | 前端顯示「逐字稿」badge，可手動按「產生筆記」 |

### 現有限制

| 限制 | 原因 |
|------|------|
| 新影片最多等 1 小時才被處理 | worker 間隔 `YT_AUTO_TRANSCRIPT_INTERVAL_SECONDS`（預設 3600s） |
| Cache 刷新前上傳的影片不會被偵測到 | worker 只讀 `_remote_yt_cache`，不主動呼叫 yt-dlp |
| Remote cache 只在啟動或 24h 後刷新 | `YT_CACHE_TTL_SECONDS`（預設 86400s） |
| 自動只抓字幕，不產生筆記 | `_run_yt_transcript_job` 不接 analyze → generate_note |
| 每頻道只看前 N 支（預設 5） | `channels.json` 的 `limit` 欄位，或 `YT_AUTO_TRANSCRIPT_LIMIT_PER_CHANNEL` env |

### 相關環境變數

| 變數 | 預設 | 說明 |
|------|------|------|
| `YT_AUTO_TRANSCRIPT` | `1` | `0` 可完全停用自動轉錄 |
| `YT_AUTO_TRANSCRIPT_START_DELAY_SECONDS` | `15` | 啟動後多久開始第一次掃描 |
| `YT_AUTO_TRANSCRIPT_INTERVAL_SECONDS` | `3600` | 每次掃描間隔（秒） |
| `YT_AUTO_TRANSCRIPT_LIMIT_PER_CHANNEL` | `channel` | `channel` = 讀 channels.json 的 `limit`；數字 = 全域上限 |
| `YT_CACHE_TTL_SECONDS` | `86400` | Remote cache 多久後強制刷新 |

### 手動觸發

不想等 worker 自動跑，可從前端直接操作：
- **抓字幕**：影片列表 → 點「抓逐字稿」按鈕 → 建立 `yt_setup` job
- **產生筆記**：有字幕後 → 點「產生筆記」→ 建立 `yt_analyze` job → 寫入 `影片筆記/<頻道>/`

---

## 依賴

- Python 3.10
- `fastapi`, `uvicorn` — web server
- `faster-whisper` — 本地 GPU 轉錄
- `yt-dlp` — 音頻下載
- GPU 建議 VRAM ≥ 3GB（medium 模型）；不足時自動降為 small / base
