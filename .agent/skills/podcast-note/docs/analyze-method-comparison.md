# Podcast 分析方法比較

`analyze.py` 負責在下載 + 轉錄完成後，呼叫 `claude -p` 分析逐字稿並產生 Obsidian 筆記。
本文記錄三個演化版本的設計、優缺點與實測結果。

測試集數：**股癌 EP658**（2026-04-30，約 50 分鐘，逐字稿 1999 行 / 82KB）

---

## 版本一：一次全塞（截斷）

**Archive**：`Podcast/Gooaye 股癌/notes/archive/EP658_v1_一次全塞截斷.md`

### 做法

```
逐字稿（截斷至 80K chars）
+ SKILL.md 全文
→ 單一超長字串送進 claude -p
```

### 優點

- 結構連貫：Claude 一次看完所有 instruction + 逐字稿，輸出格式最一致
- 實作最簡單

### 缺點

- **逐字稿截斷**：EP658 原始 82KB，截到 80K chars 後約遺漏後 20-30% 內容（Q&A 段、記憶體股討論、邊緣運算等）
- 沒有帶入 `note-investment.md` 格式規範，投資框架格式不符標準

### 實測品質

- 章節數：7
- 時間戳：有（逐字稿帶入時保留）
- 後段內容：**遺漏**（記憶體股討論、邊緣運算前景等未進筆記）

---

## 版本二：分段 Read tool

**Archive**：`Podcast/Gooaye 股癌/notes/archive/EP658_v2_分段Read.md`

### 做法

```
prompt 只帶路徑 + SKILL.md + note-investment.md
→ claude -p 用 Read tool 自行分批讀逐字稿（每次 400-500 行）
→ 各段摘要後合成完整分析
```

### 優點

- 逐字稿完整不截斷
- 帶入 `note-investment.md` 規範，投資框架格式正確

### 缺點

- **連貫性差**：Claude 分批讀取，需自行在腦中拼接，各段之間有時不一致
- 分析深度比版本一淺，因為 Claude 需要耗費 context 在「拼接」而非「分析」
- 實際測試品質反而不如版本一

### 實測品質

- 章節數：9
- 時間戳：有（Read tool 讀到時間戳）
- 內容完整度：高，但論點深度偏淺

---

## 版本三：去時間戳完整送入 + 事後補回（當前版本 ✅）

**保留**：`Podcast/Gooaye 股癌/notes/2026-05-02 股癌 EP658｜AI時代軟體股存活術與台積電先進封裝佈局 - EP658.md`

### 做法

```
Step 1：transcript.txt → 去除時間戳 → 純文字（82KB → 60KB，壓縮 27%）
Step 2：純文字（完整不截斷）+ SKILL.md + note-investment.md → 一次送進 claude -p
Step 3：Claude 在每個 section 填 anchor_text（該段開頭句，字面接近原文）
Step 4：analyze.py 用 difflib 模糊比對 anchor_text vs 原始逐字稿 → 補回 start_time
Step 5：重跑 generate_note.py 讓時間戳進筆記
```

### 優點

- **完整不截斷**：去時間戳後塞得進去，後段內容不遺漏
- **結構連貫**：一次全看，品質接近版本一但覆蓋率更高
- **時間戳自動補回**：6/6 段全部命中，精度高（difflib cutoff=0.35）
- 帶入 `note-investment.md` 規範，格式正確

### 缺點

- `anchor_text` 比對偶爾會因 Whisper 轉錄誤字而命中偏移（約 ±5 秒），通常可接受
- 比版本一多一個後處理步驟（backfill + 重跑 generate_note）

### 實測品質

- 章節數：6
- 時間戳：**6/6 全補回**
- 內容完整度：**完整**（包含後段 Q&A、記憶體股、邊緣運算）

---

## 比較總表

| 面向 | v1 一次全塞截斷 | v2 分段 Read | v3 去時間戳完整（當前）|
|------|:--------------:|:------------:|:---------------------:|
| 逐字稿完整 | ✗ 截斷後 20-30% | ✓ | ✓ |
| 結構連貫性 | ✓ | ✗ | ✓ |
| 時間戳 | ✓（保留在稿中） | ✓ | ✓（事後比對補回） |
| note-investment.md 規範 | ✗ | ✓ | ✓ |
| 實作複雜度 | 低 | 中 | 中 |
| 整體品質 | 中（缺後段） | 中（連貫性差） | **高** |

---

## 相關檔案

| 檔案 | 說明 |
|------|------|
| `scripts/analyze.py` | 當前版本（v3）實作 |
| `scripts/transcribe.py` | faster-whisper 轉錄 |
| `scripts/generate_note.py` | analysis.json → Obsidian 筆記 |
| `scripts/update_reading_list.py` | 更新待閱讀清單 |
| `docs/analyze-method-comparison.md` | 本文件 |
