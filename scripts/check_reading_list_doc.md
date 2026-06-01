# check_reading_list.py 使用說明

掃描 `待閱讀清單.md` 中的所有 `[[wikilink]]`，檢查 Obsidian vault 內是否有對應筆記，並輸出斷連報告。

---

## 安裝需求

- Python 3.10+
- macOS（`--check-urls` 和 `--url` 模式需要 Spotlight，即 `mdfind` 指令）

---

## 快速開始

```bash
python3 ~/Desktop/Projects/Arthur_App/arthur_knowledge_assistant/scripts/check_reading_list.py
```

執行後：
1. 終端顯示斷連摘要
2. 自動覆寫 `/arthurwang_DB/待閱讀清單斷連筆記.md`

---

## 三種模式

### 模式一：預設掃描（快，~0.1 秒）

```bash
python3 check_reading_list.py
```

只比對**檔名**。清單中的 `[[筆記標題]]` 若在 vault 找不到同名 `.md` 檔，就標記為斷連。

適合：日常定期執行，快速掌握清單健康狀況。

---

### 模式二：含 URL 二次比對（~1 分鐘）

```bash
python3 check_reading_list.py --check-urls
```

對每個斷連項目，額外用 Spotlight 搜尋 vault 內容，找出「**檔名不同但內容對應**」的筆記。

輸出兩類結果：
- `❌ 真正缺失`：vault 完全找不到對應筆記，需補建或從清單刪除
- `⚠️ 檔名不符`：vault 有內容相關的筆記，但檔名不同（可能是中英文版本、改過名等）

適合：清理清單前做完整審查。

**範例輸出：**
```
⚠️ 檔名不符（URL 有對應）

【量化交易】
  [ ] 準確率超過 85%：網球 AI 交易生產系統完整架構
       → 投資/量化交易/準確率超過 85%：網球人工智慧交易生產系統.md
```

---

### 模式三：查詢單一 URL（~0.2 秒）

```bash
python3 check_reading_list.py --url "https://x.com/user/status/123456"
```

直接貼上文章 URL，確認 vault 是否已有對應筆記（透過 frontmatter `source:` 欄位比對）。

適合：剪存新文章前，先確認有沒有重複。

**範例：**
```bash
python3 check_reading_list.py --url "https://x.com/sarvagya_kul/status/2055620873294581955"
# ✓ 找到對應筆記：待檢查/How I'd get a job in 7 days.md

python3 check_reading_list.py --url "https://example.com/article-not-yet-saved"
# ✗ 找不到 source URL 為 https://... 的筆記
```

---

## 附加選項

### `--dry-run`：只印終端，不寫報告

```bash
python3 check_reading_list.py --dry-run
python3 check_reading_list.py --check-urls --dry-run
```

---

## 輸出說明

### 終端摘要

```
Vault 共 3604 個 .md 檔案
唯一 wikilink：448 個
檔名比對後缺失：19 個
真正缺失：13 筆 | 檔名不符：6 筆
```

### 報告檔案

自動寫入：`/arthurwang_DB/待閱讀清單斷連筆記.md`

每次執行都會**覆寫**，日期自動更新。

---

## 設定

腳本頂部三個路徑可依需求修改：

```python
VAULT_ROOT   = Path("/Users/yankesswang/Documents/arthurwang_DB")
READING_LIST = VAULT_ROOT / "待閱讀清單.md"
OUTPUT_FILE  = VAULT_ROOT / "待閱讀清單斷連筆記.md"
```

---

## 常見問題

**Q：`--check-urls` 要跑很久？**
A：vault 在 iCloud Drive 時，Spotlight 每次搜尋約 3 秒，19 個斷連 × 3 秒 ≈ 1 分鐘。這是正常的。

**Q：`--check-urls` 的「檔名不符」判斷準確嗎？**
A：用 Spotlight 關鍵字搜尋，可能有誤判（關鍵字碰巧出現在無關筆記中）。建議看到「檔名不符」結果時，手動確認一下對應路徑是否真的是同一篇文章。

**Q：`--url` 找不到，但我確定有這篇筆記？**
A：確認筆記 frontmatter 有 `source:` 欄位，且 URL 與查詢 URL 相符。Clippings 自動剪存的筆記通常都有；手動建立的筆記可能沒有。
