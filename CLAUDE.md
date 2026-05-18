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

### 檔名規則

- **只有投資筆記**需要加日期前綴（`YYYY-MM-DD 標題.md`），規則詳見 `instructions/note-investment.md`
- **其他所有筆記**（論文、AI 講座、內容創作、工作流）直接用標題命名，不加日期

### 語言

- **所有輸出一律使用繁體中文**，無論原始資料語言
- 股票代碼、技術術語（LLM、KV cache、RLHF）、人名、公司名保留英文原文
- 數字帶單位（%、倍數、bytes、秒）

### 圖片判斷規則

**保留**（有資訊內容）：K 線圖、技術分析圖、季節性勝率表、產業鏈結構圖、財報截圖、任何有數字/標籤的圖

**刪除**（純裝飾）：文章封面橫幅、品牌 Logo、無數字的插圖

**圖片放置**：緊接在對應段落文字之後，不集中堆在文末

**本地附件格式**：`![[Pasted image xxx.png]]` → 直接保留

**外部 URL 圖片**（來自 Clippings、X/Twitter、網頁）：
- 格式為 `![Image](https://...)` → **必須保留在筆記中**，不得刪除
- 判斷依據相同：有資訊內容的保留，純裝飾的刪除
- 整理筆記時若重寫段落內容，**必須回頭確認對應圖片是否遺漏**，並補回到正確段落後

### 筆記完成後更新待閱讀清單

清單路徑：`/Users/yankesswang/Documents/arthurwang_DB/待閱讀清單.md`

#### 閱讀清單結構（時間分層）

```
## 🆕 本週新增（YYYY/MM/DD – MM/DD）
### AI Agent 工程
### LLM 技術 / 論文
### Claude Code / 開發工具
### 產業與策略
### 創業
### 投資
### 量化交易
### 知識創作

## 📅 [月份]中上旬（YYYY/MM/DD – MM/DD）
（同上子分區）

## ✅ 已讀
（同上子分區）
```

#### 操作 A：新增筆記到清單（整理新筆記後執行）

**執行前先驗證週別**：計算今天（`date.today()`）所在週的週一日期，與清單中 `🆕 本週新增（YYYY/MM/DD – MM/DD）` 的起始日比對：
- **符合**（同一週）：直接在該區塊下新增
- **不符合**（跨週）：
  1. 將現有 `## 🆕 本週新增（...）` 改為 `## 📅 上週（...）`
  2. 在它之前插入新的 `## 🆕 本週新增（本週 MM/DD – MM/DD）` 區塊

完成週別確認後：

1. 在 `🆕 本週新增` 區塊下，找到對應的**主題子分區**（AI Agent 工程 / LLM 技術 / 投資…）
2. 在子分區頂端新增一行：`- [ ] [[筆記標題]]`
3. 若清單中已有相同條目，**跳過**，不重複新增
4. 若對應子分區不存在，在 `🆕 本週新增` 下新建一個 `### 子分區名稱`

**主題子分區對應規則**：

| 筆記類型 | 對應子分區 |
|---------|-----------|
| Agent 工程、記憶架構、Harness | AI Agent 工程 |
| LLM 技術、論文、推論引擎、量化壓縮 | LLM 技術 / 論文 |
| Claude Code、Skill、MCP、開發工具 | Claude Code / 開發工具 |
| 產業趨勢、策略分析、商業模式 | 產業與策略 |
| 創業、自動化服務、工作流 | 創業 |
| 個股分析、財報、宏觀策略 | 投資 |
| Polymarket、量化策略、交易框架 | 量化交易 |
| 寫作、X 帳號、內容創作 | 知識創作 |

#### 操作 B：標記已讀（僅 Arthur 本人決定）

`[x]` 代表 Arthur 已讀過，**Claude 絕對不能自行標記 `[x]`**。
整理筆記 ≠ Arthur 讀過。整理完永遠只加 `- [ ]`，不改狀態。

### 摘要格式（TL;DR）

**所有筆記類型**（投資、論文、AI 講座、Claude Code、任何筆記）在 frontmatter 正下方一律寫列點式 TL;DR：

```markdown
## TL;DR

- **核心主張**：...
- **關鍵機制 / 問題**：...（可展開子列點）
- **重要結論或數字**：...
- **適用條件 / 限制**：...
```

- 段落式摘要禁止使用
- 每個列點帶粗體標籤 + 說明，子列點用於展開細節
- 投資筆記額外加：`- **操作建議**：時間點 + 動作`
- 論文筆記額外加：`- **核心數字**：關鍵指標的具體數字（如 Pass@3 從 X → Y）`
- 標題用 `## TL;DR`，不用 `## 摘要`

### 關鍵數據速查表格式

每篇筆記最後必須有速查表（有數字型內容時）：

```markdown
## 附：關鍵數據速查

| 指標 | 數值 | 備註 |
|------|------|------|
| ... | ... | ... |
```

### Vault 位置

- 主 Vault：`/Users/yankesswang/Documents/arthurwang_DB/`
- 投資筆記：`/Users/yankesswang/Documents/arthurwang_DB/投資/`
- AI Knowledge：`/Users/yankesswang/Documents/arthurwang_DB/AI Knowledge/`
- 文章輸出：`/Users/yankesswang/Documents/arthurwang_DB/Arthur_Blog/Posts/`
- 待閱讀清單：`/Users/yankesswang/Documents/arthurwang_DB/待閱讀清單.md`
- 操作建議總表（一般）：`/Users/yankesswang/Documents/arthurwang_DB/投資/投資操作建議總表.md`
- 操作建議總表（mimi）：`/Users/yankesswang/Documents/arthurwang_DB/投資/mimi操作建議總表.md`

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
