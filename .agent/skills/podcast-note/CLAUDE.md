# podcast-note — Claude Code 開發指南

## 跨平台注意事項（macOS / Linux）

| 項目 | macOS | Linux |
|------|-------|-------|
| Bash 版本 | 3.2（不支援 `mapfile`） | 4.x+ |
| GPU | 無（通常）| NVIDIA CUDA |
| Python | `python3.10` via Homebrew | `python3.10` via apt/pyenv |
| `lsof` | 內建 | 需安裝 `lsof` 或用 `ss` |
| `ffprobe` | via `brew install ffmpeg` | via `apt install ffmpeg` |

**Shell 腳本規則**：
- 禁止使用 `mapfile`（bash 3.2 不支援）→ 用 `while IFS= read -r` 替代
- 禁止使用 `declare -A`（關聯陣列）→ bash 3.2 不支援
- `{1..N}` brace expansion 在 bash 3.2 OK；`for ((i=0; i<N; i++))` 也 OK
- `process substitution <()` 在 bash 3.2 OK

---

## 啟動 Server

> Server 已搬到專案根目錄 `./server/`（v1.3+）。`data/`、`config/`、`scripts/` 仍留在這個 skill 資料夾。

從專案根目錄執行：

```bash
cd server
bash run.sh              # 自動清 port → 啟動，跨平台安全
```

或直接：
```bash
cd server
VAULT_ROOT=/path/to/arthurwang_DB python3.10 main.py
```

預設 port：**7654**，可用 `PORT=8000 bash run.sh` 覆蓋。

`.env` 載入順序（第一個存在的即使用）：
1. `server/../.env`（專案根目錄）
2. `server/.env`

---

## 環境變數

| 變數 | 必填 | 預設 | 說明 |
|------|------|------|------|
| `VAULT_ROOT` | ✓ | `~/Documents/arthurwang_DB` | Obsidian vault 根目錄 |
| `PORT` | | `7654` | Server port |
| `HOST` | | `0.0.0.0` | Bind host |
| `YT_NOTE_DIR` | | `$VAULT_ROOT/影片筆記` | YouTube 筆記存放 |
| `READING_LIST_PATH` | | `$VAULT_ROOT/待看影片與Podcast清單.md` | 待看清單 |
| `YT_CACHE_TTL_SECONDS` | | `86400` | YouTube 遠端快取 TTL（秒） |
| `YT_AUTO_TRANSCRIPT` | | `1` | 是否自動背景轉錄 |
| `YT_REMOTE_LIMIT` | | `all` | 每頻道抓取影片數 |

---

## YouTube 快取行為

**快取位置**：`data/server_cache.sqlite3`（SQLite，跟隨 skill 目錄）

**啟動流程**：
1. `preload_yt_db_cache()` ← 同步，把 DB 資料載入記憶體，第一個 request 立即有資料
2. `_prefetch_all_remote()` ← 背景執行，若 TTL 過期則呼叫 yt-dlp 刷新

**第一次啟動（DB 空）**：
- 前端顯示空的 YouTube 頁面，每 5 秒 poll 一次
- 背景 yt-dlp 抓所有頻道（21 個頻道，4 個平行，可能需要 2-5 分鐘）
- 完成後 DB 有資料，後續重啟 ≤ 1 秒即有資料

**TTL 過期（> 24h）**：
- 顯示舊快取資料（立即），同時背景刷新
- 前端 `dates_ready` 仍為 True，不會出現 loading 狀態

---

## Job 進度設計

| phase 值 | 說明 |
|---------|------|
| `準備中` | Job 建立、尚未執行 |
| `解析中` | RSS / yt-dlp 解析集數資訊 |
| `下載中` | yt-dlp 下載音頻（progress 0-100 為真實百分比）|
| `轉錄中` | faster-whisper 轉錄（progress 依音頻時長估算）|
| `分析中` | Claude 分析逐字稿（progress: 5→15→30→70→95）|
| `完成` | Done |
| `*失敗` | Error |

**Job type 值**：

| type | 顯示名稱 | 來源 |
|------|---------|------|
| `pod_download` | 下載 + 轉錄 | `/api/download` |
| `pod_analyze` | 產生筆記 | `/api/episodes/{id}/analyze` |
| `yt_analyze` | 產生筆記 | `/api/youtube/videos/{id}/analyze` |
| `yt_setup` | 抓逐字稿 | YouTube transcript setup |
| `yt_auto_transcript` | 自動逐字稿 | 背景自動轉錄 |

---

## Scripts pipeline

```
download.sh   →  transcribe.py  →  analyze.py  →  generate_note.py  →  update_reading_list.py
 (yt-dlp)       (faster-whisper)   (claude -p)    (analysis.json→.md)   (待看清單)
```

**analyze.py 進度協定**（`PROGRESS:<n>:<phase>` 格式，由 `podcast_routes.py` 解析）：
- `PROGRESS:5:啟動中`
- `PROGRESS:15:分析逐字稿中`
- `PROGRESS:30:分析中`（tokens 開始後只報一次，避免跳進）
- `PROGRESS:70:寫入 analysis.json`
- `PROGRESS:{75-90}:執行後處理腳本`
- `PROGRESS:95:Claude 完成`

**GPU 模型選擇**（transcribe.py / podcast_jobs.py）：

| 可用 VRAM | 模型 |
|-----------|------|
| ≥ 3 GB | `medium` |
| ≥ 1.5 GB | `small` |
| < 1.5 GB 或無 GPU | `base` |

macOS 通常無 NVIDIA GPU → 固定用 `base` 或 `small`（速度慢但可運作）。

---

## 常見問題

**`run.sh: mapfile: command not found`**
→ macOS bash 3.2 不支援，run.sh 已改用 `while IFS= read -r` 相容寫法。

**`[Errno 48] Address already in use`**
→ 舊 server 未結束，`run.sh` 會自動清除；若用 `python3.10 main.py` 直接啟動，先手動 `lsof -tiTCP:7654 -sTCP:LISTEN | xargs kill`。

**YouTube 第一次很慢**
→ DB 空，背景抓 21 個頻道需要幾分鐘，完成後 DB 快取生效，後續重啟 < 1 秒。

**GPU OOM / 轉錄失敗**
→ 自動降模型；或手動 `--model small` 傳給 transcribe.py。
