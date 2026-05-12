# 長文寫作規範（Substack / Medium）

適用：Substack 技術長文（英文）、中文深度文章（AI 趨勢 × 人文反思）。

> 聲音與人設、禁止寫作習慣、Hashtag 庫等通用規則，見 `write-social.md`。
> 本文只列長文特有的結構與語調要求。

---

## 全域輸出設定（強制）

- 預設語言：**繁體中文**。除非明確指定英文，否則一律中文完成全文
- 禁止先寫英文再翻譯；直接以中文思考寫作
- 預設風格：**數據先行 + 敘事包裝**（先給數字衝擊，再講解原因）

---

## 文章類型對照

| 類型 | 適用 | 參考範例 |
|------|------|---------|
| **A. 英文長文** | AI/ML 論文解析、技術深度分析、系統設計 | Context Engineering、BM25 vs Vector Search |
| **B. 英文短文** | 研究亮點、工具介紹、個人觀點（→ 改用 write-social.md） | — |
| **C. 中文長文** | AI 趨勢 × 人生哲學、科技概念 × 人文反思 | 為什麼設定目標反而讓你離成功更遠 |

文章長度：類型 A 1,500–2,500 字（8–12 分鐘）、類型 C 1,200–2,000 中文字（8–10 分鐘）

---

## 一、英文長文（類型 A）

### 1.1 標題公式

```
[主要觀點 / 核心概念]: [副標 — 說明方法或結論]

範例：
"The Essential Skill for Top AI Developers: A Practical Guide to Context Engineering"
"Why RL with Distillation Can Beat GRPO: Rich Feedback Changes Everything"
"When Vector Search Fails, BM25 Saves Your RAG"
```

- 主標：對比句型（When X fails, Y saves）/ Why 句型 / 核心技能句型
- 副標：點出「為什麼重要」或「結論是什麼」
- 避免：疑問句標題、「Introduction to X」

### 1.2 文章骨架

```markdown
[Title]
[One-line subtitle — punchy, specific（副標可省略，TurboQuant 無副標）]

---

[Opening Hook — 2~3 段]
三種有效開場模式（選一種）：
  A. 數字震撼：先給損失/倍率數字，再解釋為什麼（TurboQuant：-$143B）
  B. 誤解揭示：「很多人以為 X，但實際上 Y」（BM25：vector search 限制）
  C. 行業現象：描述一個正在發生的轉變，讀者可能沒察覺（Context Engineering）

引出核心問題：「This paper centers on one question:」

---

## Part 1: The Problem — [問題描述]

### [子問題 1]
具體研究發現 + 數據
用 > blockquote 標記關鍵洞見

### [分類框架，例如「Four Types of Context Failure」]
**1. [名稱]**
- Definition: ...
- Example: ...

---

## Part 2: The Solutions — [解法概述]

### Step 1: [解法名稱] — [副標]
定義 + 核心機制
具體實作方式（How to implement it:）
Pro-Tip 或 Golden Rule

---

### （選填）My take / Personal Perspective
技術爭議或主流觀點與你判斷不同時，加一段個人觀點：
「My take: [你的判斷] — because [具體理由]」
不需要每篇都有，但有時這是全文可信度最高的一段

---

### Conclusion
三種結尾模式（選一種，不要固定公式）：
  A. 時代宣告：「Welcome to the [X] Era... Are you ready to level up?」（適合宣示性主題）
  B. 開放問題：一個讓讀者思考的問題，不給答案（適合複雜議題，如 TurboQuant）
  C. 並列收尾：「Don't pick X—use both」「The answer isn't A or B, it's when」（適合對比型文章）

---

Reference:
[URL list，純文字，非 markdown link]
```

### 1.3 語調技巧

**開場不定義，先給痛點：**
```
❌ "Context Engineering is a new concept in AI..."
✅ "In the past, our main way of interacting with LLMs centered on the 'prompt'...
    However, a new concept quickly gained attention: Context Engineering."
```

**用類比讓技術概念可視化：**
```
✅ "If we think of the LLM as a new operating system, the model itself is like the CPU,
    while the 'context window' functions like RAM."
✅ "GRPO is like a teacher who only marks your exam with a score...
    SDPO is like a tutor sitting next to you, reading your error logs line by line."
```

**數字一定要具體：**
```
❌ "SDPO is faster and more efficient"
✅ "SDPO reaches GRPO's endpoint accuracy with 1/4 the generations,
    while outputs are 7× shorter (48.8% vs 41.2% final accuracy)"
```

**Blockquote 用於最關鍵的 insight：**
```
> **Golden Rule:** Put static text at the top, and variable user input at the bottom.
```

**子章節 emoji 標頭（只在 section 內部）：**
```
### ⚡ 4.1 Faster convergence: 4× fewer generations
### 📉 4.2 Less "padding": 7× shorter outputs
```

### 1.4 爭議處理原則

當主題有公開爭議（社群批評、反駁論文、不同 benchmark 結果），**不要迴避，直接正面處理**：

```
Addressing the Controversy:
[說明爭議是什麼 — 誰提出、基於什麼]
[說明你對爭議的判斷 — 是否有道理、在什麼條件下成立]
[給出你的結論立場]
```

這樣做的目的：讀者知道你讀過反面意見，信任度比「只講優點」高。

### 1.5 結論模式（三選一）

```
A. 時代宣告型（適合宣示性主題）：
Conclusion: Welcome to the [X] Era
We are at a turning point. [簡述舊思維 → 新思維轉變]
Instead of being only a user, developers need to act as [新角色 metaphor].
Are you ready to level up?

B. 開放問題型（適合複雜或不確定議題）：
[用一個高層次問題收尾，不給答案]
「Is [X] moat eroding faster than we think?」
「The question is no longer whether—it's when.」

C. 並列收尾型（適合對比型、工具選擇型文章）：
[兩種工具/方法都有價值，最後一句整合]
「Don't pick one — use both.」
「The answer isn't A or B. It's understanding when each applies.」
```

### 1.5 格式規範

| 元素 | 用法 |
|------|------|
| `**Bold**` | 核心概念第一次出現、關鍵數字、重要術語 |
| `> blockquote` | 最重要的 insight，memorable one-liner |
| `---` | 大章節之間分隔 |
| `### Step N: Title` | 解法步驟 |
| `## Part N: Title` | 大章節 |
| Code block | JSON 範例、計算流程、結構示意 |

---

## 二、中文長文（類型 C）

### ⚠️ 最重要原則：中文長文 ≠ 英文長文的翻譯

英文文章 → **結構驅動**：Part 1/Part 2、Step N、條列清單
中文文章 → **敘事驅動**：說書人語氣、故事帶技術、情緒帶觀點

如果生成的中文讀起來像「翻譯腔」或「報告體」，一定是錯的。

### 2.1 核心語感：說書人，不是教授

```
❌ 教授語氣：
「KV Cache 是一種在推理過程中用於儲存中間計算結果的機制，
它的主要問題在於記憶體佔用過高，導致...」

✅ 說書人語氣：
「你跟 AI 聊越久，它就越慢——你有沒有這種感覺？
這不是你的網路問題，是 GPU 記憶體快撐不住了。
每一句對話，AI 都在默默記錄，把處理過的所有內容
全部存進一個叫做 KV Cache 的地方。
對話越長，這個地方就越擠。」
```

關鍵差異：先說「你感受到的現象」，再說「技術原因」；技術術語出現前先用比喻建立畫面。

### 2.2 句子節奏規則

長句 + 短句交錯，製造呼吸感：

```
✅ 好的節奏：
「這篇論文做到了一件聽起來不可能的事：
把 AI 的記憶壓縮六倍，速度快八倍，
準確率——一點都沒掉。

就是這個數字，讓記憶體產業在三天內蒸發了 900 億美元。」
```

**單句字數參考**：金句 8–15 字、解釋句 20–35 字、場景描述 15–25 字、避免超過 50 字單句。

**數據出場節奏**：

- **技術分析型**（AI 論文、效能對比、產品評測）：
  - 開頭 120 字內至少 1 個硬數字（%、倍數、金額、時間）
  - 每 2–3 段至少 1 個硬數字，不可連續 4 段都沒數字
  - 每篇至少 5 個可記憶數字，其中至少 2 個對比數字（如 `55.4% → 38.4%`）

- **人文反思型**（AI 概念 × 人生哲學、思維模式類）：
  - 數字密度規則放寬；可無 benchmark 數字
  - 改用「可感知的場景數字」錨定（如「你每天做 37 個決策」）
  - 核心論述靠敘事、類比、反轉邏輯驅動，不強求數據

### 2.3 骨架（敘事弧線，不是段落標題）

```
[開場：一個場景或衝擊事件]
用具體畫面或數字開場，不解釋，製造懸念

[鋪陳：讀者需要知道的背景]
比喻 → 術語 → 所以什麼事情才會發生

[核心轉折：「但是」或「然後，事情變了」]
情節轉折點，不要用標題宣告，用語氣帶入

[深挖：一層一層揭開]
每揭一層，用一句話點出「這有什麼意義」

[意外/反轉]
「更諷刺的是...」「但沒人預料到...」

[結語：提升到更大的意義]
不是總結，是啟示。結尾要讓人有東西帶走
```

### 2.4 禁止的中文寫作習慣

| 禁止 | 原因 | 改法 |
|------|------|------|
| `## 一、XXX：YYY說明` 結構標題 | 讀起來像論文或新聞稿 | 改用場景/問題開頭 |
| `首先...其次...最後...` | 太正式，像簡報 | 改用「接著」「然後」「但這裡有個問題」 |
| 條列三個以上重點 | 打斷敘事節奏 | 改用段落，把重點埋進故事裡 |
| 「值得注意的是」「不難發現」 | 翻譯腔 | 直接說結論 |
| 每段結尾都下結論 | 讀者疲勞 | 讓一些段落留懸念，下一段揭曉 |

### 2.5 個人觀點段落（「我的判斷」）

技術文章可在分析末段加入個人立場，格式：

```
我的判斷：[你的結論]
理由：[1-2 句具體依據]
如果 [條件 X] 出現，我會改變這個看法。
```

**何時加、何時不加**：
- 主流觀點有明顯盲點時：加
- 你的判斷與作者 / 業界有差異時：加
- 純粹介紹技術機制（無爭議）：不加
- 人文反思型文章：用「踏腳石理論」式比喻帶出洞見，不用「我的判斷」格式

### 2.7 轉場語（用來代替結構標題）

```
「然後，事情開始變得有趣了。」
「但這裡有個問題，沒人說出來的那種。」
「更諷刺的是，...」
「就在這個時候，GitHub 上發生了一件事。」
「這一切都還說得過去，直到...」
「等等，我要先解釋一件事。」
```

### 2.8 技術比喻公式（先比喻，後術語）

```
✅「就像你在開一個三小時的會議——
   到了第兩小時有人問你問題，
   你得回想前面說過的所有事。
   AI 也一樣，只是它記的東西叫做 KV Cache，
   而且它比你更不善忘，每一個字都存著。」

❌「KV Cache 是一種儲存機制，
   用於保存注意力機制計算過程中的 Key 和 Value 向量。」
```

**用 AI 概念解釋人生（適用人文反思類）**：
```
✅ Gradient Descent → 人生不要只走下坡
✅ AlphaGo 第 37 手 → 短期虧損換長期勝利
✅ Reward Hacking → 為了 KPI 犧牲真正的進步
```

### 2.9 高吸引力數據寫法（技術型適用）

先給可感知損益，再講方法細節：
```
「不是小幅下降，是從 A 直接掉到 B（-X 個百分點）。」
「三天蒸發 900 億美元，不是情緒，是定價重算。」
「你以為拿到外掛，其實只拿到 1/3 的有效增益。」
```

**數據句型模板**：
- 損失型：`從 A 到 B，少了 X（絕對差）/ 少了 Y%（相對差）`
- 倍率型：`在相同結果下，成本只要 1/N；或速度提升 N×`
- 回收型：`經過 [方法] 後，從 A 回升到 B，救回 X 個點`
- 反直覺型：`高載入率 ≠ 高成功率（A% loading, B% pass）`

---

## 三、通用寫作原則

### 研究引用規範

```
✅ 具體說出研究來源：
   "According to the 'Context Rot' report by Chroma..."
   "A DeepMind paper counters this with a brute-force experiment..."

✅ 數字必須帶單位/比較基準：
   不能說「快很多」，要說「4× faster」

❌ 不要說「studies show」「researchers found」這種模糊引用
```

### 數據密度發布前檢查清單

- [ ] 開場 120 字內出現至少 1 個硬數字？
- [ ] 至少提供 2 組 `A → B` 對比？
- [ ] 至少 1 次明確寫出「絕對差（pp）」或「相對變化（%）」？
- [ ] 至少 1 次指出反直覺結果？
- [ ] 若刪掉所有形容詞，文章還能靠數據說服嗎？

---

## 四、生成 Prompt 模板

> **進入前提**：`write-workflow.md` 的 Writer Context Packet 必須已填完。
> `thesis` → 核心論點、`reader` → 目標讀者、`proof` → 關鍵數字、`angle` → 開場模式，直接帶入下方模板對應欄位。

```
【文章類型】類型 A / C
【語言】中文（預設，除非另行指定）
【原始素材】[貼入論文摘要、研究報告、新聞、技術文章]
【原始圖片】[若有圖表/截圖，提供檔名或路徑；若無則填「無」]
【核心論點】[你希望文章論證的主要觀點，如果有的話]
【關鍵數字】[至少 5 個：含 2 組對比數字 + 1 個反直覺數字]
【目標讀者】[AI 工程師 / 一般科技讀者 / 投資人 / 通用]
【發布平台】Substack / LinkedIn / Medium
```

生成時必須遵守：
1. 類型 A：完整骨架，Part 1/Part 2 結構，Step N 格式，結尾 Conclusion
2. 類型 C：開場場景 + 敘事弧線 + AI 概念類比 + 啟示性收尾
3. 所有類型：具體數字、類比、有立場的觀點
4. 若原始資料數據不足：先明確標註「可用數據不足」，再避免過度推論
5. 若原始素材含圖片：正文嵌入對應圖片並加一行圖說
6. **必須同時產出英文版 + 繁體中文版各一**（英文主稿 `post_en.md`，中文版 `post_zh.md`）
   - 中文版不是英文版的逐字翻譯，改用說書人語氣重寫（見 2.1 節）
   - 人文反思型文章若原始為中文，改寫英文版時改用類型 A 結構

---

## 五、LinkedIn 衍生版（選填，長文完成後執行）

長文草稿確認後，問自己一句：**這篇的核心洞見能不能在 3 秒內說清楚？** 能的話就出 LinkedIn 版。

### 衍生原則

- 不是長文的摘要，是長文的**最強單點**——只取一個論點，不壓縮全文
- 用 `proof`（Writer Context Packet 的數字/案例）當 hook 開場
- 結尾加「完整分析在 Substack，連結在留言」

### 衍生 Prompt

```text
以下是一篇已完成的長文（Substack）：
[貼入 post_en.md 或 post_zh.md]

從這篇文章提取**最強的單一洞見**，寫一則 LinkedIn 貼文。
規格：依照 write-linkedin.md 的格式規範。
不要總結全文，只攻一個論點。
結尾加一行：「完整分析在 Substack，連結在留言。」
```

> 衍生完成後，依 `write-linkedin.md` 的儲存規範另存。

---

## 六、輸出存儲規範

每次生成文章，建立新資料夾存放：

**路徑**：`/home/trx50/Documents/arthurwang_DB/Arthur_Blog/Posts/`

**資料夾命名**：`YYYY-MM-DD_文章標題-slug`（當日同名加序號 `_02`）

**檔案**：
- 英文主稿：`post_en.md`
- 繁體中文版：`post_zh.md`（說書人語氣改寫，非逐字翻譯）
- LinkedIn 衍生版：`post_linkedin.md`（若執行五、）
- 若有參考資料：`sources.md`
- 若有圖片：`assets/figure-01.png`（格式：`![圖說](./assets/figure-01.png)`）
- 若原始素材提到圖片但缺失：文中標註 `（原始圖檔缺失，待補）`

---

## 七、可選：NotebookLM 視覺補充

文章草稿完成後，若文章結構適合圖像化（有框架對比、多階段流程、數據密集段落），執行：

```
/notebooklm <post_path>
```

**分塊建議**（Substack 長文通常按論點切）：
- 引言 + 核心論點 → 一塊
- 主要論證 / 案例 → 一塊（若有多組對比可再細分）
- 結論 + 行動建議 → 一塊

生成的 infographic 放入文章的 `assets/` 資料夾，嵌入對應段落（英文版和中文版都加）。
