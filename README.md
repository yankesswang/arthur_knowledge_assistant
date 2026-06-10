# arthur_knowledge_assistant

Arthur 的 Obsidian 知識管理 + 投資筆記 + 內容創作 AI 助理。

這個 repo 是個人工作區，整合 Claude Code skills、Obsidian 插件、爬蟲腳本與工作流文件。

---

## 目錄結構

```
arthur_knowledge_assistant/
├── CLAUDE.md                    # 主規範：instruction 索引、格式規則、vault 路徑
├── agent.md                     # Agent 入口（轉發器，指向 CLAUDE.md）
│
├── instructions/                # 各任務類型的詳細操作規範
│   ├── note-investment.md       # 投資筆記（podcast / 財報 / 訪談）
│   ├── monthly-digest.md        # 月度整理（Finance Digest / FOMO SOC）
│   ├── note-paper.md            # 學術論文筆記（arXiv）
│   ├── note-ai-lecture.md       # AI 課程 / 講座筆記
│   ├── write-linkedin.md        # LinkedIn / 短文寫作
│   ├── write-substack.md        # Substack / 長文寫作
│   └── write-workflow.md        # 內容創作工作流
│
├── .agent/skills/               # Claude Code 啟用的 skills（19 個）
├── .claude/                     # Claude Code 設定（settings.json、hooks）
│
├── scripts/                     # 工具腳本
│   ├── check_reading_list.py    # 掃描待閱讀清單的 wikilink 斷連
│   ├── check_reading_list_doc.md
│   ├── ig_download.sh
│   ├── ai_crawler.py            # AI 內容爬蟲
│   └── run_crawler.sh
│
├── workflow-docs/               # 工作流文件與已編譯的 Obsidian 插件
│   ├── substack-in-obsidian-guide.md
│   ├── x-article-in-obsidian-guide.md
│   ├── twitter-cli.md
│   ├── x-automation-tools.md
│   ├── substack-in-obsidian/    # 編譯版插件
│   └── x-article-in-obsidian/  # 編譯版插件
│
├── substack-in-obsidian/        # Obsidian 插件源碼（TypeScript）
├── x-article-in-obsidian/       # Obsidian 插件源碼（TypeScript）
│
├── digest/                      # Digest 輸出（ai / finance / stock）
├── graphify/                    # graphify 工具（cloned from safishamsi/graphify）
├── graphify-out/                # graphify 圖譜分析輸出
├── docs/                        # 參考文件
├── OpenCLI/                     # CLI 工具集
├── native-host/                 # Chrome native messaging host
├── chrome-extension/            # 瀏覽器擴充功能
├── skills/                      # Skills 規格與模板
├── systemd/                     # 系統服務設定
└── zhihu-articles/              # 知乎文章存檔
```

---

## 任務觸發方式

接到任務時，Claude 依 `CLAUDE.md` 的索引表判斷類型，再讀取 `instructions/` 的對應規範執行。

| 任務類型 | 觸發關鍵字 |
|----------|-----------|
| 投資筆記 | 投資筆記、podcast、財報、嘉賓 |
| 月度整理 | 月度整理、幫我整理X月、FOMO SOC |
| 論文筆記 | 論文筆記、paper note、arXiv |
| AI 講座筆記 | 技術筆記、課程筆記、LLM、Agentic |
| 短文寫作 | 寫貼文、LinkedIn、short post |
| 長文寫作 | substack、長文、技術文章 |
| 內容工作流 | 出個 Brief、每週連結、捕捉觀察 |

---

## 常用腳本

```bash
# 掃描待閱讀清單斷連 wikilink
python3 scripts/check_reading_list.py

# 含 Spotlight 二次比對（~1 分鐘）
python3 scripts/check_reading_list.py --check-urls

# 查單一 URL 是否已在 vault
python3 scripts/check_reading_list.py --url "https://..."

# AI 內容爬蟲
bash scripts/run_crawler.sh
```

---

## Vault 路徑

| 用途 | 路徑 |
|------|------|
| 主 Vault | `/Users/yankesswang/Documents/arthurwang_DB/` |
| 投資筆記 | `arthurwang_DB/投資/` |
| AI Knowledge | `arthurwang_DB/AI Knowledge/` |
| 影片筆記 | `arthurwang_DB/影片筆記/<頻道名稱>/` |
| 文章輸出 | `arthurwang_DB/Arthur_Blog/Posts/` |
