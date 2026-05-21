---
name: transcript-note
description: YouTube CC subtitle URL → yt-dlp transcript → Claude analysis → deep Obsidian note (AI lecture format)
---

# /transcript-note

給一個 YouTube URL，自動完成：
1. yt-dlp 下載字幕 + metadata（含 YouTube 章節）
2. 解析 VTT → 60 秒合併壓縮
3. Claude 直接分析（不呼叫外部 LLM）→ `note-ai-lecture.md` 格式
4. 輸出 Obsidian 筆記 + 更新待閱讀清單

不下載影片，不截圖。純字幕 → 結構化知識筆記。

## Usage

```
# 單支影片
/transcript-note https://youtu.be/VIDEO_ID
/transcript-note https://www.youtube.com/watch?v=VIDEO_ID
/transcript-note https://www.youtube.com/shorts/VIDEO_ID
/transcript-note https://www.youtube.com/live/VIDEO_ID
```

## Vault Paths

- **Notes**: `/Users/yankesswang/Documents/arthurwang_DB/AI Knowledge/影片筆記/`
- **Transcripts**: `<SKILL_DIR>/data/transcripts/<VIDEO_ID>/`（永久存放，不用 /tmp）
- **Reading list**: `/Users/yankesswang/Documents/arthurwang_DB/待閱讀清單.md`

## Scripts

```
scripts/
├── setup.sh               # Steps 1-3: URL解析 + yt-dlp下載 + VTT解析
├── parse_vtt.py           # (由 setup.sh 呼叫)
├── finalize.sh            # Steps 5-7: 產生筆記 + 更新清單 + 報告
├── generate_note.py       # (由 finalize.sh 呼叫)
├── update_reading_list.py # (由 finalize.sh 呼叫)
├── check_channels.sh      # 頻道監控：偵測新影片 → 寫入 data/queue.txt
└── mark_processed.sh      # 標記影片已處理：queue → processed_ids.txt

config/
└── channels.json          # 頻道清單設定

data/
├── queue.txt              # 待處理影片 URL（一行一條）
├── processed_ids.txt      # 已處理的 video ID（防止重複）
└── transcripts/           # 每支影片的永久原始資料
    └── <VIDEO_ID>/
        ├── condensed.txt  # 壓縮逐字稿
        ├── info.json      # 標題、頻道、章節
        ├── analysis.json  # Claude 分析結果
        └── meta.json      # yt-dlp 原始 metadata
```

---

## What You Must Do When Invoked

**所有步驟全自動，不需要使用者確認。**

---

### 模式判斷

**若使用者提供 YouTube URL** → 直接執行 Action 1-3（單支影片模式）

**若使用者說「處理佇列」或未提供 URL** → 先執行佇列模式：

```bash
SKILL_DIR="/Users/yankesswang/Desktop/Projects/Arthur_App/arthur_knowledge_assistant/.agent/skills/transcript-note"
cat "$SKILL_DIR/data/queue.txt"
```

若佇列不為空，逐一取出第一條 URL，執行 Action 1-3，完成後執行：
```bash
bash "$SKILL_DIR/scripts/mark_processed.sh" "<VIDEO_URL>"
```
然後繼續處理下一條，直到佇列清空。

---

### Action 1 — Setup + 下載 + 解析字幕

```bash
SKILL_DIR="/Users/yankesswang/Desktop/Projects/Arthur_App/arthur_knowledge_assistant/.agent/skills/transcript-note"
bash "$SKILL_DIR/scripts/setup.sh" "<user-provided URL>"
```

輸出：
- `<SKILL_DIR>/data/transcripts/<VIDEO_ID>/condensed.txt` — 壓縮後逐字稿
- `<SKILL_DIR>/data/transcripts/<VIDEO_ID>/info.json` — 標題、頻道、時長、章節

---

### Action 2 — Claude 分析（自我分析，不呼叫外部工具）

讀取 `condensed.txt` 和 `info.json`，依照以下格式分析，將結果**直接用 Write 工具**寫入 `<SKILL_DIR>/data/transcripts/<VIDEO_ID>/analysis.json`。

```json
{
  "title_zh": "影片中文標題（保留英文專有名詞）",
  "note_type": "A",
  "topic": "技術主題",
  "tags": ["核心技術1", "核心技術2"],
  "tldr": {
    "核心主張": "這份筆記在講什麼（一句話）",
    "關鍵機制_問題": "核心問題是什麼，為什麼重要",
    "重要結論": "最重要的洞見或結論（帶具體數字）",
    "適用條件_限制": "什麼情況下這些結論成立"
  },
  "sections": [
    {
      "title": "章節標題（繁體中文，5-20字）",
      "start_time": "MM:SS",
      "content_points": [
        "- **概念名稱**：一句話定義",
        "    - **子觀點**：說明內容（保留推理過程）"
      ]
    }
  ],
  "key_insights": ["洞見1（不超過40字）", "洞見2", "洞見3"],
  "data_table": [{"指標": "...", "數值": "...", "備註": "..."}],
  "reading_list_category": "AI Agent 工程 | LLM 技術 / 論文 | Claude Code / 開發工具 | 產業與策略 | 創業 | 投資 | 量化交易 | 知識創作"
}
```

**分析品質要求：**
- `sections`：有 YouTube 章節則跟章節走，否則自行推斷 5-8 個邏輯段落
- `content_points`：每節 5-12 bullet，用巢狀結構 `- **概念**: ...` → `    - **子觀點**: ...`
- 保留推理鏈：寫清楚「為什麼 A 導致 B」，不只寫「A 導致 B」
- 保留所有具體數字、百分比、benchmark
- 長逐字稿（>15K 字）：分 timestamp 區段分析，最後合併

---

### Action 3 — 產生筆記 + 更新清單 + 報告

```bash
SKILL_DIR="/Users/yankesswang/Desktop/Projects/Arthur_App/arthur_knowledge_assistant/.agent/skills/transcript-note"
VIDEO_ID="<從 setup.sh 輸出取得的 VIDEO_ID>"
bash "$SKILL_DIR/scripts/finalize.sh" "$VIDEO_ID"
```

---

## Edge Cases

| 情況 | 處理方式 |
| --- | --- |
| 無 CC 字幕 | 改用影片描述（最多 4000 字）；frontmatter 標記 |
| 有手動 CC | 優先於自動生成字幕 |
| 有 YouTube 章節 | 作為 sections 的分段依據 |
| 逐字稿超過 15K 字 | 按 timestamp 分段分析後合併 |
| 筆記檔名已存在 | 附加 ` - {video_id}` 避免覆蓋 |
| 清單子分區不存在 | 在「🆕 本週新增」下新建 `### 子分區` |

## Architecture

```
YouTube URL
 │
 ├─ scripts/setup.sh
 │   ├─ Step 1: 解析 URL → VIDEO_ID
 │   ├─ Step 2: yt-dlp → meta.json + VTT 字幕
 │   └─ Step 3: parse_vtt.py → condensed.txt + info.json
 │
 ├─ Claude 分析 → Write analysis.json
 │
 └─ scripts/finalize.sh
     ├─ Step 5: generate_note.py → Obsidian .md
     ├─ Step 6: update_reading_list.py → 待閱讀清單
     └─ Step 7: 報告
```
