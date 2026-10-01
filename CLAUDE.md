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
| X 推文 / 短文剪報 | X 推文、Twitter、短貼文、社群剪報、觀點短文（非投資、非深度論文） | `instructions/note-clipping-x.md` |
| LinkedIn / 短文寫作 | 寫貼文、LinkedIn、draft、short post、社群 | `instructions/write-social.md` |
| Substack / 長文寫作 | substack、長文、技術文章、按我的風格寫 | `instructions/write-longform.md` |
| 內容創作工作流 | 出個 Brief、找連結、每週連結、捕捉觀察 | `instructions/write-workflow.md` |

---

## Git 規範

- commit message 不加 `Co-Authored-By` 行

---

## Clippings 整理規範

整理完 Clippings 內的筆記後，**不直接刪除原始檔案**，一律移動到：

```
/Users/yankesswang/Documents/arthurwang_DB/待檢查/
```

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

### 筆記完成後更新閱讀清單

> **重要：兩份清單用途不同，不可混用。**
>
> | 清單 | 路徑 | 用途 |
> |------|------|------|
> | `待閱讀清單.md` | `/home/trx50/Documents/arthurwang_DB/待閱讀清單.md` | **文章、筆記**（Clippings、Substack、論文、技術文章）|
> | `待看影片與Podcast清單.md` | `/home/trx50/Documents/arthurwang_DB/待看影片與Podcast清單.md` | **影片、Podcast 集數**（YouTube、股癌、曼報、財報狗等）|
>
> 整理 Clippings 或文章筆記後，一律加到 **`待閱讀清單.md`**，不加到待看影片清單。

清單路徑（文章用）：`/home/trx50/Documents/arthurwang_DB/待閱讀清單.md`

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
   - **投資子分區必須標記來源**，格式見下方「投資子分區來源標籤」
3. 若清單中已有相同條目，**跳過**，不重複新增
4. 若對應子分區不存在，在 `🆕 本週新增` 下新建一個 `### 子分區名稱`

#### 投資子分區來源標籤（僅 `### 投資` 適用）

投資條目一律在 checkbox 後、wikilink 前加上反引號包住的來源標籤：

```markdown
- [ ] `FOMO SOC` [[2026-09-16 UBER：Cybercab與Waymo的去中介化威脅]]
- [ ] `M報` [[2026-09-15 蘋果摺疊機首發、AI Agent雲端化競賽]]
- [ ] `mimi` [[2026-09-11 10年美債逼近5%空頭終局]]
- [ ] [[2026-09-09 解構中國權力變現機制]]          ← 自己整理的，不加標籤
```

**來源判斷**：讀筆記 frontmatter 的 `url` 或 `source` 欄位，對照下表；若 frontmatter 沒有，則看筆記所在資料夾路徑。

| frontmatter `url` / `source` 含 | 標籤 |
|--------------------------------|------|
| `fomosoc.com`、`FOMO SOC` | `FOMO SOC` |
| `mviewpoint.substack.com` | `M報` |
| `mimi`、`mimivsjames` | `mimi` |
| `vincentcwyu.substack.com` | `Vincent Yu` |
| `vickyho.substack.com` | `Vicky Ho` |

- 上表沒有的訂閱來源：用該來源的慣用簡稱，維持反引號格式
- **自己整理、非訂閱來源的筆記不加標籤** —— 留白本身就是區分
- 標籤只加在 `### 投資` 子分區，其他子分區維持原格式

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

### 正文條列化規範（所有筆記類型共用）

**核心原則：正文預設用條列式，不用段落式敘述。**

原始素材（Substack、podcast 逐字稿、論文、講座）幾乎都是連續段落。整理時**不是把段落搬過來翻譯**，而是要先拆出段落底下的邏輯結構，再用條列重建。

#### 四個必用手法

**1. 用粗體小標分出邏輯區塊**

每個子章節（`1-1`、`2-3`…）內部，先辨認它其實在講幾件事，各給一個粗體小標：

```markdown
### 1-1 為什麼 AAII 一度看不出世代進步

**發布時間點的訊號**

- Fable 5.1 發表**兩天後** OpenAI 就推出 GPT-6 Astra
- 暗示模型已接近可上線狀態，甚至可能是**被刺激而提前發布**

**矛盾現象**

- 上線第一天，AAII 顯示它與上一代**得分相同**
- 但這與官方數據、使用者體感**明顯不符**

**問題出在評測本身**

- 舊題目飽和 → 鑑別力下降，強弱模型都拿滿分
- 覆蓋不足 → 沒涵蓋新模型真正擅長的工作類型
```

小標是「這段在回答什麼問題」，不是原文的段落標題。

**2. 兩組以上的數字對比，一律抽成表格**

只要出現「A 是 X、B 是 Y」的比較，就不要留在句子裡：

```markdown
| 行為指標 | GPT-5.6 Sol | GPT-6 Astra | 變化 |
|---|---|---|---|
| 越權行為機率 | 48% | **0%** | 完全消除 |
| 幻覺率 | 9.4% | **2%** | 降至約 1/5 |
```

單一數字不必開表格，寫進列點並粗體即可。

**3. 因果鏈用 `→` 串接**

多步推導壓成一行，讓傳導路徑一眼可見：

```markdown
- 原本可能失業的司機 → 用累積資金買車成為車主 → 收入可能高於親自開車
  → 把**潛在反對者轉化為利益一致的參與者** → 降低地方政治阻力
```

**4. 情境分岔用並列列點**

「如果 A 就會…，如果 B 就會…」不要寫成一句長句：

```markdown
- **順利情境**（2–3 週無嚴重事故）→ 車隊很可能從 40 台**增加到 100 台以上**
- **事故情境**（發生重大安全事件）→ 擴張計畫**暫時卡關**
```

#### 什麼情況「不要」條列化

條列化是為了讓結構浮現，不是把所有東西切碎。以下維持原樣：

- **連續推理鏈**：一段論證前後緊扣、拆開會斷掉因果關係的，保留成段落，改用 `→` 或 code block 呈現流程
- **已經是結構化的區塊**：callout（`[!tip]`/`[!warning]`/`[!info]`）、code block、投資框架三個時間維度、章節開頭的核心數據表 —— 這些原本就有結構，條列化反而打散
- **定義與背景說明**：一兩句話講完的概念定義，不需要拆成列點

> **判準**：拆完之後如果讀者更快看懂邏輯 → 拆；如果只是把一句話斷成三行 → 不拆。

#### 與深度標準的關係

條列化**不等於**縮短篇幅。`4d 深度標準`（因果推論完整、對比分析完整重現、支撐論據都要納入）仍然全部適用 —— 條列化只改變**呈現方式**，不減少**資訊量**。改寫後的內容密度應與原文相當。

---

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
- 待看影片與Podcast清單：`/Users/yankesswang/Documents/arthurwang_DB/待看影片與Podcast清單.md`
- 操作建議總表（一般）：`/Users/yankesswang/Documents/arthurwang_DB/投資/投資操作建議總表.md`
- 操作建議總表（mimi）：`/Users/yankesswang/Documents/arthurwang_DB/投資/mimi操作建議總表.md`
- **影片筆記**：`/Users/yankesswang/Documents/arthurwang_DB/影片筆記/<頻道名稱>/`

### 影片筆記存放規則

影片筆記一律存到 **`/Users/yankesswang/Documents/arthurwang_DB/影片筆記/<頻道名稱>/`**，以頻道名稱建子資料夾：

```
影片筆記/
├── Invest Like The Best/
├── Dwarkesh Patel/
├── The Diary Of A CEO/
├── 硅谷101/
└── <其他頻道>/
```

- 頻道名稱從 `info.json` 的 `channel` 欄位取得
- 頻道名稱做為資料夾名稱時，移除 `/\:*?"<>|` 等非法字元
- 無頻道資訊時，放到 `影片筆記/未分類/`
- 檔名格式：`<中文標題>.md`，衝突時加 ` - <video_id>` suffix

---

## 決策捕捉（Decision Capture）

對話過程中，若 Arthur 說了任何**影響未來方向的決定**，Claude 應主動詢問是否要記錄到 Decision Log。

### 判斷標準：以下情況主動詢問

- Arthur 說「決定用 X」、「改用 Y」、「從今天起 Z」、「不再做 A」
- Arthur 確認了某個策略方向（如：「好，就照這個方向走」、「那就先做 X 再做 Y」）
- Arthur 明確放棄某個選項（如：「那個方案不考慮了」）

### 不需詢問的情況

- 日常執行指令（「幫我整理這篇筆記」、「繼續」）
- 純粹提問或資訊查詢
- Arthur 只是在表達偏好，沒有做出決定

### 詢問方式

在回應末尾簡短問一句：

> 這算是一個決策，要記到 Decision Log 嗎？

若 Arthur 說「要」或「好」，立即用以下格式寫入：

路徑：`/Users/yankesswang/Documents/arthurwang_DB/AI Knowledge/知識創作/洞見/Decision Log.md`

格式（追加到檔案頂端，header 之後）：

```markdown
## YYYY-MM-DD — [決策標題，10字以內]

**背景**：[當時情境，一句話]
**選擇**：[做了什麼決定，一句話]
**理由**：[為什麼，一句話；若對話中沒提到則寫「—」]
**結果**：（待補）

---
```

若 Arthur 說「不用」則跳過，不再提。

---

## Scripts 索引

| 腳本 | 觸發關鍵字 | 功能 |
|------|-----------|------|
| `scripts/check_reading_list.py` | 斷連、清單檢查、wikilink 壞掉、找筆記、URL 查詢 | 掃描 `待閱讀清單.md` 的 wikilink，找出 vault 內缺失的筆記 |

### check_reading_list.py

**三種用法：**

```bash
# 快速掃描（~0.1 秒）— 只比對檔名
python3 scripts/check_reading_list.py

# 含 Spotlight 二次比對（~1 分鐘）— 找出改過名但內容對應的筆記
python3 scripts/check_reading_list.py --check-urls

# 查單一 URL（~0.2 秒）— 確認 vault 是否已有這篇文章
python3 scripts/check_reading_list.py --url "https://..."

# 只印終端，不寫檔
python3 scripts/check_reading_list.py --dry-run
```

**輸出：** 自動覆寫 `待閱讀清單斷連筆記.md`（vault 根目錄）

**詳細說明：** `scripts/check_reading_list_doc.md`

---

## Instructions 資料夾結構

```
instructions/
├── note-investment.md    # 投資筆記（podcast/訪談/財報整理 + 操作建議總表更新）
├── monthly-digest.md     # 月度整理（Finance Digest/FOMO SOC 月度格式化 + 月度總攬生成）
├── note-paper.md         # 學術論文筆記（arXiv 為主，先直覺後背景）
├── note-ai-lecture.md    # AI 課程/講座筆記（課程型 A + 論文混合型 B/C）
├── note-clipping-x.md    # X 推文/短文剪報（濃縮條列、不複述原文）
├── write-linkedin.md     # LinkedIn/短文寫作（聲音、人設、貼文公式）
├── write-substack.md     # Substack 長文（英文技術文 + 中文敘事文）
└── write-workflow.md     # 內容創作工作流（每日捕捉、週連結、Content Brief）
```
