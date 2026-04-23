# Claude Code Guidelines — Arthur Knowledge Assistant

## 專案概覽

Arthur 的 Obsidian 知識管理 + 投資筆記 + 內容創作 AI 助理。
詳細 instruction 存放在 `instructions/`。接到任務時，**先判斷類型，再讀取對應檔案，再執行**。

---

## Instruction 索引

| 任務類型 | 觸發關鍵字 | 讀取路徑 |
|----------|-----------|---------|
| 投資筆記整理 | 投資筆記、podcast、訪談、財報、嘉賓 | `instructions/note-investment.md` |
| 月度整理（Finance Digest） | 月度整理、月底整理、月度總攬、幫我整理X月、FOMO SOC 整理 | `instructions/monthly-digest.md` |
| arXiv / 學術論文筆記 | 論文筆記、paper note、整理論文、論文摘要 | `instructions/note-paper.md` |
| AI 課程 / 講座筆記 | 技術筆記、課程筆記、整理筆記、tech note、LLM 評估、Agentic Framework | `instructions/note-ai-lecture.md` |
| LinkedIn / 短文寫作 | 寫貼文、LinkedIn、draft、short post、社群 | `instructions/write-social.md` |
| Substack / 長文寫作 | substack、長文、技術文章、按我的風格寫 | `instructions/write-longform.md` |
| 內容創作工作流 | 出個 Brief、找連結、每週連結、捕捉觀察 | `instructions/write-workflow.md` |

---

## 全域規範（所有任務共用，各 instruction 不重複）

### 語言

- **所有輸出一律使用繁體中文**，無論原始資料語言
- 股票代碼、技術術語（LLM、KV cache、RLHF）、人名、公司名保留英文原文
- 數字帶單位（%、倍數、bytes、秒）

### 圖片判斷規則

**保留**（有資訊內容）：K 線圖、技術分析圖、季節性勝率表、產業鏈結構圖、財報截圖、任何有數字/標籤的圖

**刪除**（純裝飾）：文章封面橫幅、品牌 Logo、無數字的插圖

**圖片放置**：緊接在對應段落文字之後，不集中堆在文末

**本地附件格式**：`![[Pasted image xxx.png]]` → 直接保留

### 關鍵數據速查表格式

每篇筆記最後必須有速查表（有數字型內容時）：

```markdown
## 附：關鍵數據速查

| 指標 | 數值 | 備註 |
|------|------|------|
| ... | ... | ... |
```

### Vault 位置

- 主 Vault：`/home/trx50/Documents/arthurwang_DB/`
- 投資筆記：`/home/trx50/Documents/arthurwang_DB/投資/`
- 文章輸出：`/home/trx50/Documents/arthurwang_DB/Arthur_Blog/Posts/`
- 所有路徑使用 Linux 格式（`/home/trx50/...`），不使用舊 macOS 路徑

---

## Instructions 資料夾結構

```
instructions/
├── note-investment.md    # 投資筆記（podcast/訪談/財報整理 + 操作建議總表更新）
├── monthly-digest.md     # 月度整理（Finance Digest/FOMO SOC 月度格式化 + 月度總攬生成）
├── note-paper.md         # 學術論文筆記（arXiv 為主，先直覺後背景）
├── note-ai-lecture.md    # AI 課程/講座筆記（課程型 A + 論文混合型 B/C）
├── write-linkedin.md     # LinkedIn/短文寫作（聲音、人設、貼文公式）
├── write-substack.md     # Substack 長文（英文技術文 + 中文敘事文）
└── write-workflow.md     # 內容創作工作流（每日捕捉、週連結、Content Brief）
```
