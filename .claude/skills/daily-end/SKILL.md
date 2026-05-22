# Skill: Daily End

## 觸發方式
用戶輸入 `/daily-end` 或說「今天結束」、「收工了」、「記錄今天」

---

## 你的任務

讀取今天的 Daily Note，整理當天的決策、完成事項與有趣觀察，歸檔到 Decision Log，並讓明天的 `/daily-start` 有完整的接手資料。

---

## Vault 位置

- Daily Notes：`/home/trx50/Documents/arthurwang_DB/` 根目錄，格式 `YYYY-MM-DD.md`
- Decision Log：`/home/trx50/Documents/arthurwang_DB/AI Knowledge/知識創作/洞見/Decision Log.md`

---

## 執行步驟

### Step 1：讀取今天的 Daily Note

路徑：`/home/trx50/Documents/arthurwang_DB/YYYY-MM-DD.md`

若不存在，告知 Arthur「今天沒有 Daily Note，請先跑 /daily-start 或直接告訴我今天做了什麼」，等待輸入後繼續。

提取：
- 已勾選（`- [x]`）的項目 → 完成清單
- 未勾選（`- [ ]`）的項目 → 滾入明天
- `## 今日捕捉區` 的內容 → 有趣觀察
- `## 今日決策` 的內容 → 待歸檔到 Decision Log

### Step 2：歸檔決策到 Decision Log

路徑：`/home/trx50/Documents/arthurwang_DB/AI Knowledge/知識創作/洞見/Decision Log.md`

若檔案不存在，先建立：

```markdown
# Decision Log

記錄每一個影響未來方向的決定。日後查詢時，Claude 會讀這份 log 告訴你「過去的你已經想到了什麼」。

---
```

將今天 `## 今日決策` 的每一條，以以下格式追加到 Decision Log 頂端（最新在最前）：

```markdown
## YYYY-MM-DD — [決策標題，10 字以內]

**背景**：[當時的情境]
**選擇**：[做了什麼決定]
**理由**：[為什麼這樣決定]
**結果**：（待補）

---
```

若今天沒有任何決策記錄，跳過此步驟（不建立空白條目）。

### Step 3：更新今天的 Daily Note，補上 EOD 摘要

在今天的 Daily Note 底部追加：

```markdown

---

## EOD 摘要 HH:MM

**完成**：X 項（列出標題）
**滾入明天**：X 項（列出標題）
**今日生產力**：⭐⭐⭐⭐⭐（1–5 顆，由 Arthur 自評，預設不填）
**值得記住的一件事**：[從今日捕捉區挑一條最有價值的洞見或觀察]
```

### Step 4：在對話回報收工摘要

簡短告訴 Arthur：
1. 今天完成了幾項、滾入明天幾項
2. 有沒有歸檔決策（幾條）
3. 今日捕捉區裡最值得注意的一條觀察是什麼（你的判斷）
4. 明天建議第一優先做什麼（基於今天的未完成 + 重要性）

---

## 注意事項

- Decision Log 只記錄真正影響未來的決策，不記錄日常執行細節
- 「值得記住的一件事」要選你認為 Arthur 三個月後看到還會覺得有用的那條
- 不要問 Arthur 確認，直接執行並回報結果
- 若 Arthur 在對話中補充了沒有寫在 Daily Note 的內容，幫他寫進今天的捕捉區
