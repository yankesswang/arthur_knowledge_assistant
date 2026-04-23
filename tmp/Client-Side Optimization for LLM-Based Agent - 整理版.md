---
title: AgentOpt：LLM Agent 的 Client-Side Optimization
date: 2026-04-07
source: arXiv
authors: Wenyue Hua et al.（Microsoft Research、Cornell University、Columbia University）
sector: LLM Agent 最佳化
tags:
  - AgentOpt
  - client-side optimization
  - LLM agents
  - black-box optimization
  - model selection
url: https://arxiv.org/abs/2604.06296
---

# AgentOpt：LLM Agent 的 Client-Side Optimization

> [!abstract]
> 這篇論文的核心結論是：多步 LLM agent 的最佳配置不是選最強單模型，而是做 role-specific 的模型組合最佳化；AgentOpt 用 combo-level 搜尋在 4 個 benchmark 上以比 brute-force 少 62%–76% 的評估預算，找到接近最佳的準確率與成本組合。

## 一、核心演算法直覺

### 1. 白話解釋

這篇論文的核心觀察很直接：做 agent 時，真正影響成本與效果的，常常不是「哪個模型最強」，而是「哪個模型該放在哪個角色」。同一個模型放在不同位置，行為可能完全不同，甚至會把整條 pipeline 帶偏。

作者拿 HotpotQA 當例子很有代表性。最強的 Claude Opus 4.6 如果放在 planner，常常會直接回答問題，不去叫 downstream solver 和 search tool，結果整體表現反而很差；相反地，最便宜的 Ministral 3 8B 當 planner，卻更願意遵守分工，把任務交給 solver，整體準確率更高。

所以這不是傳統的「每次呼叫挑一個模型」routing 問題，而是「整條工作流的模型陣容配置」問題。你不能只看單模型排行榜，因為 pipeline 裡存在很強的角色交互效應。

如果用生活化比喻，這更像排球隊先發陣容，而不是選 MVP。主攻、副攻、二傳各自需要不同能力；把最強球員塞到不對的位置，整隊反而更差。AgentOpt 做的事，就是在有限預算內，快速找出最合理的先發組合。

### 2. 演算法流程

```text
輸入：agent pipeline P、每個角色的候選模型集合 {M1...Mn}、帶標註的 eval set D
→ 定義 combo c = (m1...mn)                              （每個 role 指派一個模型，評估單位改成整組配置）
→ 用 selector 選下一個 combo                           （UCB-E、Arm Elimination、Bayesian Opt 等）
→ 執行完整 pipeline Pc                                  （不是只看單步呼叫，而是跑完整 trajectory）
→ 記錄 Perf(c)、Cost(c)、Latency(c)                    （以 end-to-end 指標評估實際效用）
→ 更新 selector 狀態                                     （保留高潛力組合、淘汰差組合、繼續探索）
→ 預算耗盡或收斂後輸出最佳 combo 與 Pareto frontier       （給開發者準確率/成本/延遲的折衷選擇）
```

### 3. 與舊方法最大的不同

| | 舊方法 | 本文方法 |
|--|--|--|
| 最佳化單位 | 單次呼叫選模型 | 整條 pipeline 的模型組合 |
| 問題假設 | 每一步可獨立決策 | 每一步會影響 downstream 行為與最終軌跡 |
| 工程介面 | 常需配合特定框架或 routing 邏輯 | 在 `httpx` transport 層攔截，對既有 agent 低侵入 |

## 二、具體數字範例

```text
兩角色 pipeline、每個角色 9 個候選模型：
  組合空間 = 9 × 9 = 81 種 combo

若用 brute-force 跑 HotpotQA：
  81 種 combo × 199 個樣本 ≈ 16,168 次 eval
  成本 = $51.90
  最佳準確率 = 74.27%

若用 Matrix UCB-E（budget fraction = 0.2）：
  只跑 3,234 次 eval
  成本 = $12.49
  準確率 = 73.54%

換句話說：
  少跑約 80% 的評估量
  省下 75.9% 成本
  準確率只少 0.73 個百分點
```

```text
HotpotQA 最關鍵的角色錯配例子：
  Opus 4.6 當 planner + Opus 4.6 當 solver = 31.71%
  Ministral 3 8B 當 planner + Opus 4.6 當 solver = 74.27%

同樣有 Opus 4.6，放錯位置時整體差距達 42.56 個百分點。
```

## 三、關鍵圖表解讀

### 圖 1（p.3）：AGENTOPT 整體架構圖

![[Pasted image 20260422172125.png]]

**看什麼**：左半部定義 combo = 每個 pipeline role 各選一個模型；右半部畫出 selector 反覆選 combo、執行 pipeline、量測 performance/cost/latency、再更新搜尋器的迭代流程。  
**關鍵發現**：本文把 agent optimization 的基本單位，從 per-call routing 升級成 combo-level optimization。  
**數字**：兩角色且每角色 9 個模型時，組合空間就是 81；角色數再增加時會指數成長。

### 表 1：四個 benchmark 的 brute-force 最佳組合

![[Pasted image 20260422172054.png]]

**看什麼**：比較單角色任務與雙角色任務中，最佳組合、最佳準確率與 brute-force 成本。  
**關鍵發現**：反直覺最佳解主要出現在多角色 pipeline；單模型最強不等於多角色最佳。  
**數字**：HotpotQA 最佳組合是 `Ministral 3 8B + Claude Opus 4.6`，準確率 74.27%；MathQA 最佳組合是 `Claude Opus 4.6 + Claude Haiku 4.5`，準確率 98.84%。

### 表 2：各 benchmark 的代表性結果

![[Pasted image 20260422172148.png]]

**看什麼**：不同任務下，最佳組合是否符合直覺，以及 cost/performance trade-off 長什麼樣。  
**關鍵發現**：GPQA 比較像單模型能力排序問題；HotpotQA 與 BFCL 則高度依賴角色與 workflow 結構。  
**數字**：BFCL 中 Opus 4.6 與 Qwen3 Next 都到 70.00%，但 Qwen3 Next 成本低 32×。

### 表 3：HotpotQA 最差的 11 個組合

![[Pasted image 20260422172204.png]]

**看什麼**：哪些組合持續落在排名底部，以及失敗模式是否集中。  
**關鍵發現**：幾乎都是 Opus 4.6 當 planner，表示問題出在上游角色行為，而不是 solver 單獨太弱。  
**數字**：最差區間大致落在 31%–33% 準確率。

## 四、研究背景與動機

- 既有 agent efficiency 研究多做 server-side optimization，優化的是 provider 基礎設施，不是開發者自己的應用目標函數。
- 傳統 LLM routing 假設每次呼叫可獨立選模型，但多步 agent pipeline 裡每一階段都會影響後續狀態。
- 多角色 workflow 的組合空間會隨角色數指數成長，直接 brute-force 搜尋很快變得昂貴。
- 缺少一個 framework-agnostic、低侵入式的工具，能直接對現有 agent pipeline 做模型組合最佳化。

> [!tip]
> 這篇論文真正回答的是開發者視角的問題：不是「供應商怎麼把 agent serving 做便宜」，而是「我自己這條 agent workflow 該怎麼配模型，才能在可接受品質下把成本壓低」。

## 五、方法細節

### 1. 問題定義

作者把一個組合定義為 `c = (m1, ..., mN)`，其中每個 `mi` 是某個 pipeline role 所選的模型。  
效用函數寫成 `J(c) = U(Perf(τ(c)), Latency(τ(c)), Cost(τ(c)))`。  
白話就是：你不能只看單一步驟，而是要看整條軌跡 `τ(c)` 跑完後，準確率、延遲、成本綜合起來值不值得。

### 2. 系統設計

- 在 `httpx` transport layer 攔截 LLM 呼叫，用 `contextvars` 標記當前 datapoint 與 combo。
- 不要求重寫 agent framework，因此能套在既有 LangGraph workflow 上。
- 內建 HTTP-level caching、bounded parallel evaluation、CSV/YAML 匯出與 Pareto frontier 輸出。

### 3. 搜尋演算法

本文實作 10 種搜尋法，包含：

- Brute-force
- Random Search
- Matrix UCB-E
- Matrix UCB-E-LRF
- Arm Elimination
- Epsilon-LUCB
- Threshold Successive Elimination
- Hill Climbing
- Bayesian Optimization
- LM Proposal

其中最重要的是 **Matrix UCB-E**。  
白話來說，它把「combo × datapoint」看成一個大矩陣，優先把評估預算投到看起來最可能成為最佳解的組合，而不是平均地把所有組合都跑完。

### 4. 實驗設計

| Benchmark | 樣本數 | Pipeline | 組合數 | 指標 |
|--|--:|--|--:|--|
| HotpotQA | 199 | planner-solver | 81 | exact-match accuracy |
| GPQA Diamond | 198 | 單模型回答 | 9 | multiple-choice accuracy |
| MathQA | 200 | answerer-critic | 81 | exact-match accuracy |
| BFCL v3 Multi-Turn | 200 | 單模型 agent | 9 | end-to-end tool correctness |

> [!note]
> 所有 agent 都用 LangGraph 實作；對不支援 native function-calling 的模型，BFCL 採用 text-based prompting fallback。

## 六、實驗結果

### 1. 主要結果總表

| 任務 | Brute-force 最佳準確率 | 代表性高效搜尋結果 | 成本/預算節省 |
|--|--:|--|--|
| HotpotQA | 74.27% | Matrix UCB-E (0.2) = 73.54% | $51.90 → $12.49，省 75.9% |
| MathQA | 98.84% | Matrix UCB-E (0.2) = 98.37% | $123.87 → $35.18，省 71.6% |
| GPQA | 74.75% | Matrix UCB-E (0.5) = 74.75% | 同分下用較少評估預算 |
| BFCL | 70.00% | Matrix UCB-E (0.5) = 70.00% | 同分下避免 brute-force |

> 重點：Matrix UCB-E 在四個 benchmark 上都給出最穩定的 accuracy-efficiency trade-off，幾乎是全文最實用的結論。

### 2. 最重要的定性觀察

- **最佳單模型不等於最佳組合**：HotpotQA 最佳組合是 `Ministral 3 8B（planner）+ Opus 4.6（solver）`。
- **角色交互非常強**：MathQA 中若 answerer 已經很強，critic 換誰差距不大；HotpotQA 則 planner 決定生死。
- **成本差距可能遠大於準確率差距**：BFCL 中 Qwen3 Next 與 Opus 同為 70.00%，但前者便宜 32×。
- **不是所有任務都需要複雜組合搜尋**：GPQA 這類單角色任務，模型能力排序大致就能預測最佳解。

### 3. 近似消融觀察

- **Matrix UCB-E-LRF 不如 plain Matrix UCB-E**：低秩假設在這批任務上不夠穩，還增加額外擬合成本。
- **Hill Climbing 對 landscape 很敏感**：在結構平滑的任務還行，但在 HotpotQA 這種反直覺地形下容易卡局部最優。
- **LM Proposal 不可靠**：在 GPQA 還能猜中，但在 HotpotQA/BFCL 這種角色互動重的任務明顯失靈。

### 4. 附錄表格

#### Table 4：GPQA selector comparison

![[Pasted image 20260422172237.png]]

**看什麼**：不同 selector 在 GPQA 上能否快速找到最佳單模型。  
**關鍵發現**：這類單角色任務的搜尋難度相對低，合理的 prior 或 bandit 方法都能接近 brute-force。  
**數字**：Matrix UCB-E、Matrix UCB-E-LRF、LM Proposal 都能到 74.75%。

#### Table 5：BFCL selector comparison

![[Pasted image 20260422172252.png]]

**看什麼**：比較各 selector 在 BFCL 上的 accuracy 與 cost。  
**關鍵發現**：系統化探索方法能用更低成本接近最優；LM Proposal 在 agentic setting 明顯不穩。  
**數字**：Brute-force 為 70.00%、$84.80；Matrix UCB-E (0.2) 為 69.90%、$26.14；LM Proposal 只有 44.03%。

#### Table 6：HotpotQA selector comparison

![[Pasted image 20260422172306.png]]

**看什麼**：最困難、最反直覺的 HotpotQA 上，各搜尋法的效率與效果。  
**關鍵發現**：Matrix UCB-E 幾乎保住最佳準確率，同時把成本壓到 brute-force 的約四分之一。  
**數字**：Brute-force 74.27%、$51.90；Matrix UCB-E (0.2) 73.54%、$12.49；LM Proposal 34.13%。

#### Table 7：MathQA selector comparison

![[Pasted image 20260422172324.png]]

**看什麼**：各搜尋法在 MathQA 的表現與成本。  
**關鍵發現**：這個 benchmark 的 landscape 相對平滑，許多方法都能接近最佳，但方法穩定性仍有差別。  
**數字**：Brute-force 98.84%、$123.87；Matrix UCB-E (0.2) 98.37%、$35.18；Threshold SE 掉到 74.52%。

#### Table 8：GPQA brute-force results

![[Pasted image 20260422172344.png]]

**看什麼**：9 個單模型在 GPQA 的完整排名。  
**關鍵發現**：GPQA 基本上仍接近單模型能力排序問題。  
**數字**：Claude Opus 4.6 第一，74.75%。

#### Table 9：BFCL brute-force results

![[Pasted image 20260422172356.png]]

**看什麼**：9 個單模型在 BFCL 的完整排名。  
**關鍵發現**：accuracy 打平時，成本差異才是實務部署的主要決策點。  
**數字**：前三名都為 70.00%，但成本差距很大。

## 七、侷限與風險

> [!warning]
> 第一，本文目前只驗證了 4 個 benchmark，涵蓋面比一般單一任務論文廣，但離真實世界 agent workflow 的多樣性還有距離。
>
> [!warning]
> 第二，這套方法目前主要優化的是模型組合；對 tool routing、memory policy、scheduler policy 等其他 client-side 決策還沒有完整展開。
>
> [!warning]
> 第三，最佳 combo 依賴小型 labeled eval set。如果離線評估資料的分布和真實部署不同，選出的最佳解可能不穩。
>
> [!warning]
> 第四，部分搜尋法帶有強結構假設，例如 LRF 依賴低秩、Hill Climbing 依賴良好的鄰域拓撲；假設不成立時表現會快速退化。

## 八、延伸應用

### 短期

- 把現有 LangGraph / AutoGen workflow 的多角色模型配置，直接拿 AgentOpt 做離線搜尋。
- 在相同準確率前提下找更便宜的部署組合，而不是預設整條流程都用最強模型。

### 中期

- 把搜尋空間從「模型組合」擴展成「模型 + 工具 + prompt policy + memory policy」的聯合最佳化。
- 接到實際產品監控資料後，把 utility function 改成更貼近業務的 quality-cost-latency 權重。

### 長期

- 從 offline combo search 走向 online adaptive routing，讓 agent 依任務型態動態切換角色配置。
- 把 combo abstraction 延伸到 sub-agent、tool-use、retrieval、memory write/read policy 的整體 pipeline 設計。

> [!tip]
> 對你自己的知識助理或檢索型 agent，這篇最值得帶走的不是某個 selector 細節，而是「角色分工本身就是優化對象」。planner、retriever、reader、critic 不能只挑單點最強，而要看整體配合。

## 九、個人判讀

- 這篇論文的 framing 很強，因為它把工程上早就存在、但經常被忽略的問題正式化了。
- 真正有價值的不是「又做了一個 search benchmark」，而是它證明了多角色 agent 的 failure mode 常來自上游角色行為失配。
- 若未來作者能把 model selection 擴展到 tool 與 memory policy，這條線有機會從技術報告變成很實用的 agent optimization toolbox。

## 附：關鍵數據速查

| 指標 | 數值 |
|------|------|
| 論文 | AgentOpt v0.1 Technical Report: Client-Side Optimization for LLM-Based Agent |
| arXiv 編號 | 2604.06296 |
| 首次提交日期 | 2026-04-07 |
| 最新版本日期 | 2026-04-15 |
| 作者 | Wenyue Hua et al. |
| 機構 | Microsoft Research、Cornell University、Columbia University |
| Benchmark 數量 | 4 |
| 候選模型數 | 9 |
| HotpotQA 樣本數 | 199 |
| GPQA Diamond 樣本數 | 198 |
| MathQA 樣本數 | 200 |
| BFCL v3 Multi-Turn 樣本數 | 200 |
| HotpotQA / MathQA 組合數 | 81 |
| GPQA / BFCL 組合數 | 9 |
| HotpotQA 最佳組合 | Ministral 3 8B（planner）+ Claude Opus 4.6（solver） |
| HotpotQA 最佳準確率 | 74.27% |
| Opus+Opus 在 HotpotQA | 31.71% |
| MathQA 最佳組合 | Claude Opus 4.6 + Claude Haiku 4.5 |
| MathQA 最佳準確率 | 98.84% |
| GPQA 最佳準確率 | 74.75% |
| BFCL 最佳準確率 | 70.00% |
| BFCL 成本差距 | 在相同準確率下最佳與最差可差到 32× |
| 匹配準確率時的成本差距 | 13×–32× |
| UCB-E 相對 brute-force 節省 | 62%–76% 評估預算 |
| HotpotQA brute-force 成本 | $51.90 |
| HotpotQA Matrix UCB-E 成本 | $12.49 |
| MathQA brute-force 成本 | $123.87 |
| MathQA Matrix UCB-E 成本 | $35.18 |
| DOI | 10.48550/arXiv.2604.06296 |
| 專案頁 | https://agentoptimizer.github.io/agentopt/ |
| GitHub | https://github.com/AgentOptimizer/agentopt |
