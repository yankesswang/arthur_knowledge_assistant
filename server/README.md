# Server — Podcast & YouTube 筆記生成後端

FastAPI 後端，負責 Podcast 和 YouTube 影片的下載、轉錄、AI 分析、Obsidian 筆記生成。

## 啟動

```bash
cd server
bash run.sh          # 自動停掉舊的 listener，在 :7654 重啟
```

預設 port `7654`，可用 `PORT=xxxx bash run.sh` 覆蓋。

---

## 筆記生成流程

### Podcast 流程

```
前端觸發下載
    │
    ▼
POST /api/download
    │  podcast_id + episode number
    ▼
podcast_jobs._run_download()
    │  bash download.sh {podcast_id} {episode}
    │  → 下載 audio.mp3 到 data/episodes/{podcast_id}_{ep}/
    │  → yt-dlp 轉錄 → transcript.txt（含時間戳）
    ▼
(transcription_settings.json mode)
    │
    ├── mode=local → bash local_whisper.sh → transcript.txt
    └── mode=remote → 呼叫遠端 Whisper API
    │
    ▼
POST /api/episodes/{episode_id}/analyze
    │  (使用者在 UI 點「生成筆記」)
    ▼
podcast_routes._run_analyze()
    │  python3.10 podcast-note/scripts/analyze.py {work_dir} --podcast {id}
    ▼
analyze.py
    │  1. strip_timestamps()：去掉 [MM:SS.ss] 時間戳（壓縮約 50%）
    │  2. build_prompt()：組出 system_prompt + user_prompt
    │     system_prompt = SKILL.md + note-investment.md + anchor_text 說明
    │     user_prompt   = 設定 + 完整逐字稿 + 執行步驟
    │  3. claude -p {user_prompt}
    │       --system-prompt {system_prompt}
    │       --model claude-haiku-4-5-20251001
    │       --dangerously-skip-permissions
    │       --add-dir {PROJECT_ROOT}
    │       --output-format stream-json
    │       --verbose
    ▼
Claude (Haiku) 執行工具
    │  Write tool → {work_dir}/analysis.json
    │  Bash tool  → python3.10 generate_note.py {work_dir}
    │  Bash tool  → python3.10 update_reading_list.py {work_dir}
    ▼
analyze.py（事後處理）
    │  backfill_timestamps()：用 anchor_text 模糊比對，補回 start_time
    │  再跑一次 generate_note.py，讓時間戳進 .md
    ▼
Obsidian 筆記（.md）輸出到 note_dir（投資筆記目錄）
待看影片與Podcast清單.md 更新
```

**工作目錄結構：**
```
podcast-note/data/episodes/{podcast_id}_{ep}/
├── audio.mp3          # 下載的音頻
├── transcript.txt     # 逐字稿（含時間戳）[MM:SS.ss] text
├── transcript.json    # yt-dlp 原始 JSON
├── analysis.json      # Claude 分析結果（sections, tldr, key_insights...）
├── meta.json          # yt-dlp metadata
├── env.sh             # 本集環境變數（EPISODE_MP3, WORK_DIR 等）
└── note_path.txt      # 生成的 .md 絕對路徑
```

---

### YouTube 流程

```
前端貼 YouTube URL
    │
    ▼
POST /api/youtube/videos  或  POST /api/youtube/queue
    │
    ▼
_ensure_yt_transcript()
    │
    ├── 已有 condensed.txt → 直接進 analyze
    │
    ├── bash setup.sh {url}          （yt-dlp 抓 CC 字幕）
    │   → condensed.txt（cc 來源）
    │
    └── 若無 CC → python3.10 transcribe_yt.py {work_dir}
        → Whisper medium（GPU auto）→ fallback small（CPU）
        → condensed.txt（whisper 來源）
    │
    ▼
POST /api/youtube/videos/{video_id}/analyze
    │  (使用者點「生成筆記」，或自動分析 worker 觸發)
    ▼
youtube_routes._run_yt_analyze()
    │  python3.10 .agent/skills/transcript-note/scripts/analyze.py {video_id}
    ▼
analyze.py（transcript-note）
    │  1. 讀 condensed.txt（最多 80,000 字元，超過截斷）
    │  2. build_prompt()
    │     system_prompt = SKILL.md + 執行步驟說明
    │     user_prompt   = 影片設定（id/title/channel/duration）+ 逐字稿
    │  3. claude -p {user_prompt}
    │       --system-prompt {system_prompt}
    │       --model claude-haiku-4-5-20251001
    │       --dangerously-skip-permissions
    │       --add-dir {PROJECT_ROOT}
    │       --output-format stream-json
    ▼
Claude (Haiku) 執行工具
    │  Write tool → {work_dir}/analysis.json
    │  Bash tool  → bash finalize.sh {video_id}
    ▼
Obsidian 筆記（.md）輸出到 影片筆記/{頻道名稱}/
待看影片與Podcast清單.md 更新
```

**工作目錄結構：**
```
.agent/skills/transcript-note/data/transcripts/{video_id}/
├── condensed.txt          # 逐字稿（無時間戳，最多 80KB）
├── transcript_source.txt  # 來源：cc / whisper / description / none
├── info.json              # 影片 metadata（title, channel, duration）
├── analysis.json          # Claude 分析結果
└── note_path.txt          # 生成的 .md 絕對路徑
```

**自動分析 Worker：**
伺服器啟動時開一個背景 worker（`start_youtube_auto_transcript_worker`），定期掃已有逐字稿但尚未分析的影片，自動補跑 analyze，間隔由 `YT_AUTO_TRANSCRIPT_INTERVAL_SECONDS`（預設 3600 秒）控制。

---

## analysis.json 格式

Claude 輸出的中間格式，`generate_note.py` / `finalize.sh` 再把它渲染成 .md：

```json
{
  "title_zh": "筆記中文標題",
  "note_type": "investment",
  "topic": "主題標籤",
  "tags": ["標籤1", "標籤2"],
  "stocks": ["NVDA", "AAPL"],
  "tldr": {
    "核心主張": "...",
    "關鍵機制_問題": "...",
    "重要數字": "...",
    "操作建議": "..."
  },
  "sections": [
    {
      "title": "段落標題",
      "anchor_text": "開頭原文句子（供時間戳比對）",
      "start_time": "12:34",
      "content_points": ["- **要點**：說明"]
    }
  ],
  "key_insights": ["洞見1", "洞見2"],
  "investment_framework": {
    "短期（事件驅動，2-4 週）": { "觸發因素": "...", "操作": "..." },
    "中期（結構性，3-6 個月）": { "主要受益驅動": "..." }
  },
  "risks": ["風險1", "風險2"],
  "data_table": [
    { "指標": "...", "數值": "...", "備註": "..." }
  ],
  "reading_list_category": "投資"
}
```

---

## Claude CLI 優化

兩個 `analyze.py` 共用以下策略：

| 優化 | 說明 |
|------|------|
| system/user prompt 分離 | 靜態指令（SKILL.md + note-investment.md）放 `--system-prompt`，逐字稿放 `-p`；連續分析可命中 prompt cache |
| Haiku 模型 | `claude-haiku-4-5-20251001`，速度快 3-5x，成本約 1/10 |
| transcript-note 無 `--verbose` | 該腳本不需要 verbose 輸出，移除以降低 overhead |
| file lock | `claude_lock.py` 用 `fcntl.flock` 串行化並發 claude 呼叫，避免 API 競爭 |

---

## 並發控制

`server/claude_lock.py` 提供 `claude_cli_lock(label)` context manager：

- 鎖檔路徑：`server/data/claude_cli.lock`
- 同一時間只有一個 `claude -p` 在跑（podcast 和 YouTube 共用同一把鎖）
- 排隊中的 job 會在 UI 顯示「等待 Claude CLI 空檔」

---

## 主要路由

| 路由 | 說明 |
|------|------|
| `GET /api/podcasters` | 列出所有 podcast（合併本地 + 遠端集數）|
| `POST /api/podcasters` | 新增 podcast（RSS URL）|
| `POST /api/download` | 觸發 podcast 下載 + 轉錄 |
| `POST /api/episodes/{id}/analyze` | 觸發 AI 分析 → 生成筆記 |
| `GET /api/episodes/{id}/note` | 讀取 .md 筆記 |
| `GET /api/episodes/{id}/transcript` | 讀取逐字稿 |
| `GET /api/jobs` / `GET /api/jobs/{id}` | 查詢 job 狀態與進度 |
| `POST /api/youtube/videos` | 新增 YouTube 影片（觸發逐字稿抓取）|
| `POST /api/youtube/videos/{id}/analyze` | 觸發 YouTube AI 分析 → 生成筆記 |
| `GET /api/claude-usage` | 查詢今日 Claude CLI token 用量（via ccusage）|

---

## 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `PORT` | `7654` | 伺服器 port |
| `VAULT_ROOT` | `~/Documents/arthurwang_DB` | Obsidian Vault 根目錄 |
| `YT_NOTE_DIR` | `{VAULT_ROOT}/影片筆記` | YouTube 筆記輸出目錄 |
| `READING_LIST_PATH` | `{VAULT_ROOT}/待看影片與Podcast清單.md` | 閱讀清單路徑 |
| `YT_AUTO_TRANSCRIPT` | `1` | 是否啟用自動分析 worker |
| `YT_AUTO_TRANSCRIPT_INTERVAL_SECONDS` | `3600` | 自動 worker 掃描間隔（秒）|
