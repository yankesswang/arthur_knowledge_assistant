# Skill: Daily Start

## 觸發方式
用戶輸入 `/daily-start` 或說「開始今天」、「早安 brief」、「今天要做什麼」

---

## 你的任務

讀取昨天的 Daily Note，找出未完成事項，結合近期 vault 狀態，生成今日的行動 brief。

---

## Vault 位置

- Daily Notes：`/home/trx50/Documents/arthurwang_DB/` 根目錄，格式 `YYYY-MM-DD.md`
- Decision Log：`/home/trx50/Documents/arthurwang_DB/AI Knowledge/知識創作/洞見/Decision Log.md`（若不存在則跳過）
- 待閱讀清單：`/home/trx50/Documents/arthurwang_DB/待閱讀清單.md`

---

## 執行步驟

### Step 1：確認日期

取得今天日期（`date +%Y-%m-%d`）與昨天日期（`date -d yesterday +%Y-%m-%d`）。

### Step 2：讀取昨天的 Daily Note

路徑：`/home/trx50/Documents/arthurwang_DB/YYYY-MM-DD.md`（昨天日期）

若昨天的 note 不存在，往前找最近一天存在的 Daily Note（最多往前 7 天）。

從中提取：
- `## TODO` 或 `## 任務` 區塊中未勾選（`- [ ]`）的項目
- `## 停滯` 或 `## 卡住` 區塊的內容（如有）
- 任何標有 `#follow-up` 的段落

若沒有上述結構，掃描全文找出動詞開頭的句子作為潛在待辦。

### Step 3：掃描近期 vault 活動

用 `find /home/trx50/Documents/arthurwang_DB/ -name "*.md" -mtime -3 -not -path "*/.obsidian/*" -not -path "*/_Archive/*" -not -path "*/附件/*"` 找出過去 3 天修改的筆記。

列出筆記標題，判斷哪些可能需要後續行動（例如：草稿、未整理的 Clipping、投資筆記未更新操作建議）。

### Step 4：生成今日 Daily Note

建立檔案：`/home/trx50/Documents/arthurwang_DB/YYYY-MM-DD.md`（今天日期，若已存在則跳過建立，直接在對話回報 brief）

格式如下：

```markdown
---
date: YYYY-MM-DD
type: daily
---

## 今日優先（最多 3 項）

- [ ] （從昨天未完成 + 判斷重要性排序）
- [ ] 
- [ ] 

## 滾入項目（昨天未完成，今天繼續）

- [ ] （昨天的未勾選項目）

## 停滯警示

（若有超過 3 天未動的任務或 backlog，在此標記）

## 今日捕捉區

（隨時記錄：想法、決策、有趣觀察）

## 今日決策

（任何影響未來方向的決定記錄在此，晚上 /daily-end 會歸檔到 Decision Log）
```

### Step 5：在對話回報 brief

簡短告訴 Arthur：
1. 昨天有幾個未完成項目（若有）
2. 今日建議優先事項（最多 3 項，說明選擇理由）
3. 有沒有停滯超過 3 天的任務需要注意
4. 今日 Daily Note 已建立在 `YYYY-MM-DD.md`

---

## 注意事項

- 若今天的 Daily Note 已存在，不覆蓋，只在對話回報 brief
- 優先事項的選擇依據：未完成天數 > 有明確 deadline > 創作輸出類優先於資料收集類
- 不要問 Arthur 確認，直接執行並回報結果
