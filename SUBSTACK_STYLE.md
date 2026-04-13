# Arthur Wang — Substack Writing Style Guide

> 這份文件是根據現有的 Substack 文章、LinkedIn post 和中文文章分析出的寫作風格 DNA。
> 未來只要提供原始資料（論文、研究、新聞、技術文章），就能按此風格生成文章。

---

## 一、文章類型與對應模板

### 類型 A：英文長文（Substack Technical Article）
**適用**：AI/ML 論文解析、技術深度分析、系統設計
**參考範例**：Context Engineering、BM25 vs Vector Search、SDPO vs GRPO

### 類型 B：英文短文（LinkedIn Post）
**適用**：研究亮點、工具介紹、個人觀點
**參考範例**：NemoClaw、AI Knowledge Base（Karpathy workflow）

### 類型 C：中文長文（Substack / Medium）
**適用**：AI 趨勢 × 人生哲學、科技概念 × 人文反思
**參考範例**：為什麼設定目標反而讓你離成功更遠

---

## 二、英文長文模板（類型 A）

### 2.1 標題公式

```
[主要觀點 / 核心概念]: [副標 — 說明方法或結論]

範例：
"The Essential Skill for Top AI Developers: A Practical Guide to Context Engineering"
"Why RL with Distillation Can Beat GRPO: Rich Feedback Changes Everything"
"When Vector Search Fails, BM25 Saves Your RAG"
```

**標題規律**：
- 主標：對比句型（When X fails, Y saves） / Why句型 / 核心技能句型
- 副標：點出「為什麼重要」或「結論是什麼」
- 避免：疑問句標題，避免「Introduction to X」

---

### 2.2 文章骨架

```markdown
[Title]

[One-line subtitle — punchy, specific]

---

[Opening Hook — 2~3 段]
- 從問題/矛盾/現象切入，不從定義開始
- 第一句就要抓住人
- 引出核心問題：「This paper centers on one question:」

---

## Part 1: The Problem — [問題描述]

### [子問題 1]
- 具體研究發現 + 數據
- 用 > blockquote 標記關鍵洞見

### [子問題 2]
...

### [分類框架，例如「Four Types of Context Failure」]
**1. [名稱]**
- Definition: ...
- Example: ...

**2. [名稱]**
...

---

## Part 2: The Solutions — [解法概述]

### Step 1: [解法名稱] — [副標]
- 定義 + 核心機制
- 具體實作方式（How to implement it:）
- Pro-Tip 或 Golden Rule

### Step 2: ...
...

---

### Conclusion: Welcome to the [X] Era

[2~3 段總結，不要重複前面的點，而是提升一個層次：
- 宣告一個新時代的到來
- 呼籲讀者行動：「Are you ready to level up?」]

---

Reference:
[URL list，非 markdown link，純文字]
```

---

### 2.3 寫作語調特徵

**開場不定義，先給痛點**
```
❌ "Context Engineering is a new concept in AI..."
✅ "In the past, our main way of interacting with LLMs centered on the 'prompt'... 
    However, a new concept quickly gained attention: Context Engineering."
```

**用類比讓技術概念可視化**
```
✅ "If we think of the LLM as a new operating system, the model itself is like the CPU, 
    while the 'context window' functions like RAM."

✅ "Think of it like the index at the back of a book."

✅ "GRPO is like a teacher who only marks your exam with a score—you can only improve 
    by guessing what you did wrong. SDPO is like a tutor sitting next to you, 
    reading your error logs line by line."
```

**數字一定要具體**
```
❌ "SDPO is faster and more efficient"
✅ "SDPO reaches GRPO's endpoint accuracy with 1/4 the generations, 
    while outputs are 7× shorter (48.8% vs 41.2% final accuracy)"
```

**Blockquote 用於最關鍵的 insight**
```
> **Golden Rule:** Put static text at the top, and variable user input at the bottom.

> "The Teacher isn't the source of answers; it's an error localizer—and that localizer 
   upgrades as the Student improves."
```

**子章節 emoji 標頭（只在 section 內部）**
```
### ⚡ 4.1 Faster convergence: fewer generations for the same performance (4×)
### 📉 4.2 Less "padding": 7× shorter outputs
### 🪜 4.3 "Pulling yourself up by your bootstraps"
### 🧩 4.4 Hard-problem specialist
```

---

### 2.4 結論公式

```
Conclusion: Welcome to the [X] Era

We are at a turning point. [簡述舊思維] → [簡述新思維轉變]

[宣告新角色] Instead of being only a user issuing instructions, 
developers increasingly need to act as [新角色 metaphor].

Are you ready to level up?
```

---

### 2.5 格式規範

| 元素 | 用法 |
|------|------|
| `**Bold**` | 核心概念第一次出現，關鍵數字，重要術語 |
| `> blockquote` | 最重要的 insight，memorable one-liner |
| `---` | 大章節之間分隔 |
| `### Step N: Title` | 解法步驟 |
| `## Part N: Title` | 大章節 |
| Code block | JSON 範例、計算流程、結構示意 |
| Inline code | 技術術語、文件名、API 名稱 |
| `**N. Name**` | 分類框架的條目 |

---

## 三、英文短文模板（類型 B — LinkedIn/Short Post）

### 3.1 骨架

```
[Bold Hook — 1句，反直覺或令人意外的陳述]

[Personal context — 1~2句，說明為什麼你在讀這個]

[核心內容 — 用粗體數字 𝟭𝟮𝟯𝟰𝟱 分點]

**𝟭. [重點標題]**
[2~3句解釋，具體到可執行]

**𝟮. [重點標題]**
...

---

[Personal take — "This resonated because..." / "Here's where I disagree..."]

[Personal stack / recommendation — if applicable]
**Step 1: [Action]** — [brief reason]
👉 [resource/link]

**Step 2: [Action]** — [brief reason]
👉 [resource/link]

[Closing line — quote from source or forward-looking statement]

👇 [Original reference link]

#hashtag1 #hashtag2 ... [8~12 tags]
```

---

### 3.2 語調特徵

**個人聲音強，有立場**
```
✅ "I'll be honest — it's making me uncomfortable."
✅ "Here's where I disagree — whitelisting EVERYTHING is a usability nightmare."
✅ "This resonated so hard because I just went through this myself."
```

**Emoji 作為視覺結構，不是裝飾**
```
✅ 📁 File restrictions — [說明]
   🌐 Network restrictions — [說明]
   ⚙️ Process restrictions — [說明]
   
✅ ✅ Define a strict set of executable operations
   ✅ Lock down file permissions
```

**以「think about it」帶出核心論點**
```
✅ "Think about it — even if an agent reads a thousand poisoned documents, 
    if it can't EXECUTE dangerous actions, the damage stays at zero."
```

---

## 四、中文長文模板（類型 C）

### ⚠️ 最重要的原則：中文文章 ≠ 英文文章的翻譯

中文長文和英文長文是**完全不同的寫作任務**，不是翻譯關係。

英文文章 → 結構驅動：Part 1/Part 2、Step N、條列清單
中文文章 → **敘事驅動**：說書人語氣、故事帶技術、情緒帶觀點

如果生成的中文讀起來像「翻譯腔」或「報告體」，一定是錯的。

---

### 4.1 中文文章的核心語感：說書人，不是教授

**對比：**

```
❌ 教授語氣（太生硬）：
「KV Cache 是一種在推理過程中用於儲存中間計算結果的機制，
它的主要問題在於記憶體佔用過高，導致...」

✅ 說書人語氣（自然流動）：
「你跟 AI 聊越久，它就越慢——你有沒有這種感覺？
這不是你的網路問題，是 GPU 記憶體快撐不住了。
每一句對話，AI 都在默默記錄，把處理過的所有內容
全部存進一個叫做 KV Cache 的地方。
對話越長，這個地方就越擠。」
```

**關鍵差異：**
- 先說「你感受到的現象」，再說「技術原因」
- 技術術語出現前，先用比喻建立畫面
- 每個概念用一個故事或場景帶出，不直接定義

---

### 4.2 句子節奏規則

中文讀者對節奏極敏感。長句 + 短句交錯，製造呼吸感：

```
✅ 好的節奏：
「這篇論文做到了一件聽起來不可能的事：
把 AI 的記憶壓縮六倍，速度快八倍，
準確率——一點都沒掉。

就是這個數字，讓記憶體產業在三天內蒸發了 900 億美元。」

❌ 壞的節奏（句子全部一樣長）：
「TurboQuant 將 KV Cache 的記憶體佔用壓縮了六倍，
並且將注意力運算速度提升了八倍，
同時在基準測試中實現了零精準度損失。」
```

**單句字數參考**：
- 衝擊句（金句）：8～15 字
- 解釋句：20～35 字
- 場景描述：15～25 字
- 避免超過 50 字的單一長句

---

### 4.3 骨架（敘事弧線，不是段落標題）

```
[開場：一個場景或衝擊事件]
用一個具體的畫面或數字開場，不解釋，製造懸念

[鋪陳：讀者需要知道的背景]
用比喻先建立畫面，再給術語
節奏：比喻 → 術語 → 所以什麼事情才會發生

[核心轉折：「但是」或「然後，事情變了」]
情節轉折點，不要用標題宣告，用語氣帶入

[深挖：一層一層揭開]
每揭一層，用一句話點出「這有什麼意義」
讀者不需要自己推理，你替他們推

[意外/反轉]
「更諷刺的是...」「但沒人預料到...」「然後有人在 GitHub 上做了一件事...」

[結語：提升到更大的意義]
不是總結，是啟示
結尾要讓人有東西帶走，不只是「原來如此」
```

---

### 4.4 禁止的中文寫作習慣

| 禁止 | 原因 | 改法 |
|------|------|------|
| `## 一、XXX：YYY說明` 結構標題 | 讀起來像論文或新聞稿 | 改用場景/問題開頭 |
| `首先...其次...最後...` | 太正式，像簡報 | 改用「接著」「然後」「但這裡有個問題」 |
| 條列三個以上重點 | 打斷敘事節奏 | 改用段落，把重點埋進故事裡 |
| 「值得注意的是」「不難發現」 | 翻譯腔 | 直接說結論 |
| 每段結尾都下結論 | 讀者會疲勞 | 讓一些段落留懸念，在下一段揭曉 |
| 直接翻譯英文 Part 1/Step 1 結構 | 不是中文的敘事邏輯 | 完全重寫，以故事為主軸 |

---

### 4.5 語調特徵

**說書人的轉場語**（用這些代替結構標題）：
```
「然後，事情開始變得有趣了。」
「但這裡有個問題，沒人說出來的那種。」
「更諷刺的是，...」
「就在這個時候，GitHub 上發生了一件事。」
「這一切都還說得過去，直到...」
「等等，我要先解釋一件事。」
「這就是問題所在。」
```

**技術概念的比喻公式**（先比喻，後術語）：
```
✅ 「就像你在開一個三小時的會議——
   到了第兩小時有人問你問題，
   你得回想前面說過的所有事。
   AI 也一樣，只是它記的東西叫做 KV Cache，
   而且它比你更不善忘，每一個字都存著。」

❌ 「KV Cache 是一種儲存機制，
   用於保存注意力機制計算過程中的 Key 和 Value 向量。」
```

**用讀者熟悉的 AI 概念解釋人生（適用人文反思類文章）**：
```
✅ Gradient Descent → 人生不要只走下坡（利用）
✅ AlphaGo 第 37 手 → 短期虧損換長期勝利
✅ Reward Hacking → 為了 KPI 犧牲真正的進步
```

**Blockquote 只放最衝擊的那句**：
```
> **一篇論文的「故事」和一篇論文的「貢獻」不是同一件事。**

> 「你無法預先串連這些點，只能在回頭看的時候才串起來。」
```

**結語必備元素**：
- 把全文概念收束到一個更大的意義，不要只是總結
- 留餘韻，不說教，不下命令
- 最後一句要夠重，讀者讀完會停下來想一下

---

## 五、通用寫作原則（跨語言）

### 5.1 研究引用規範

```
✅ 具體說出研究來源：
   "According to the 'Context Rot' report by Chroma..."
   "A DeepMind paper counters this with a brute-force experiment..."
   "Anthropic notes that this approach can improve output quality by as much as 90.2%"

✅ 數字必須帶單位/比較基準：
   不能說「快很多」，要說「4× faster」或「需要 1/4 的 generation 次數」

❌ 不要說「studies show」「researchers found」這種模糊引用
```

### 5.2 禁止的寫作習慣

| 禁止 | 原因 |
|------|------|
| 「Introduction to X」開場 | 太教科書，讀者會跳過 |
| 「In this article, I will...」 | 浪費空間，直接寫就好 |
| 結論只是重複前面的點 | 要提升一個層次或給行動建議 |
| Passive voice 氾濫 | Arthur 偏好主動語態 |
| 過多的 hedging（「might」「could」「perhaps」） | 要有明確立場 |
| 定義先於問題 | 先給痛點，再給解法 |

### 5.3 結構信號詞

**英文**：
- 「The real X is...」（提出核心洞見）
- 「Think about it —」（帶出反直覺論點）
- 「Here's where I disagree」（明確表態）
- 「The key isn't X. It's Y.」（否定假設，建立新框架）
- 「In one sentence:」（後面跟最重要的定義）

**中文**：
- 「但這裡有個問題：」
- 「更諷刺的是，」
- 「這看起來是...的繞路吧？但...」
- 「這兩個故事告訴我們同一個真理：」
- 「正是因為...，才...」（強調因果的踏腳石邏輯）

---

## 六、生成文章的 Prompt 模板

使用此風格生成文章時，提供以下資訊：

```
【文章類型】類型 A / B / C
【語言】英文 / 中文 / 雙語
【原始素材】[貼入論文摘要、研究報告、新聞、技術文章]
【核心論點】[你希望文章論證的主要觀點，如果有的話]
【目標讀者】[AI 工程師 / 一般科技讀者 / 投資人 / 通用]
【發布平台】Substack / LinkedIn / Medium
```

生成時必須遵守：
1. 類型 A：完整骨架，Part 1/Part 2 結構，Step N 格式，結尾 Conclusion
2. 類型 B：Bold hook + 𝟭𝟮𝟯 數字分點 + Personal take + #hashtags
3. 類型 C：開場問題 + Case Studies + AI 概念類比 + 正向收尾
4. 所有類型：具體數字、類比、有立場的觀點

---

## 七、Hashtag 庫

**AI/ML 技術**：
`#AI #LLM #MachineLearning #MLOps #GenAI #AIEngineering #DeepLearning #NLP`

**RAG / 搜尋**：
`#RAG #VectorSearch #BM25 #HybridSearch #InformationRetrieval #Search`

**Agent / 安全**：
`#AIAgent #AgentSecurity #PromptInjection #CyberSecurity #InfoSec`

**知識管理**：
`#KnowledgeManagement #Obsidian #PersonalKnowledgeBase #AIWorkflow`

**開發工具**：
`#ClaudeCode #OpenSource #BuildInPublic #DeveloperTools`

**一般科技**：
`#Tech #Innovation #FutureOfWork #Startup`

---

## 八、文章長度參考

| 類型 | 字數（英文）| 閱讀時間 |
|------|------------|----------|
| 類型 A（Substack 長文）| 1,500 ~ 2,500 字 | 8~12 分鐘 |
| 類型 B（LinkedIn 短文）| 300 ~ 600 字 | 2~3 分鐘 |
| 類型 C（中文長文）| 1,200 ~ 2,000 中文字 | 8~10 分鐘 |
