---
name: notebooklm
description: 將本地筆記或 URL 上傳到 NotebookLM，生成中文圖表（infographic / mind-map / data-table），下載並嵌入 Obsidian 筆記
---

# /notebooklm

給定一個 Obsidian 筆記路徑（或 URL），自動：
1. 建立 NotebookLM notebook 並加入來源
2. 設定輸出語言為繁體中文
3. 生成 infographic（landscape + portrait）+ mind-map + data-table
4. 等待生成完成，下載到 `assets/` 子資料夾
5. 將圖片嵌入原始筆記

## Usage

```
/notebooklm /path/to/note.md
/notebooklm /path/to/note.md --artifacts infographic,mind-map
/notebooklm https://example.com/article
/notebooklm --notebook <notebook_id>   # 使用已有 notebook，不新建
```

## 參數說明

| 參數 | 說明 | 預設 |
|------|------|------|
| `--artifacts` | 要生成的 artifact 類型，逗號分隔 | `infographic-landscape,infographic-portrait,mind-map,data-table` |
| `--notebook` | 指定已存在的 notebook ID（前綴即可），跳過建立步驟 | 無（自動建立） |
| `--no-embed` | 只下載，不修改筆記 | false |
| `--assets-dir` | 圖片儲存路徑 | 筆記所在資料夾的 `assets/` 子資料夾 |

## Vault Paths

- **圖片輸出**：`{note_dir}/assets/`（相對於目標筆記）
- **語言**：繁體中文（`zh_Hant`），為 global 設定，執行完後**不恢復**

---

## What You Must Do When Invoked

按順序執行，不可跳過或重排。

---

### Step 0 — 解析參數

從使用者輸入中提取：
- `NOTE_PATH`：筆記的絕對路徑（若輸入的是相對路徑，展開為絕對路徑）
- `SOURCE_URL`：若輸入的是 URL，則作為來源（不嵌入圖片）
- `NOTEBOOK_ID`：若有 `--notebook`，使用此 ID
- `ARTIFACTS`：要生成的類型清單（預設全部）
- `EMBED`：是否嵌入筆記（預設 true）

若輸入是筆記路徑，從 frontmatter 讀取 `title:` 欄位作為 notebook 名稱；若無 title，使用檔名（去除 `.md`）。

```bash
NOTE_PATH="<user input>"
NOTE_TITLE=$(python3 -c "
import re, sys
try:
    text = open('$NOTE_PATH').read()
    m = re.search(r'^title:\s*(.+)$', text, re.MULTILINE)
    print(m.group(1).strip().strip('\"').strip(\"'\") if m else '')
except:
    print('')
")
if [ -z "$NOTE_TITLE" ]; then
    NOTE_TITLE=$(basename "$NOTE_PATH" .md)
fi
NOTE_DIR=$(dirname "$NOTE_PATH")
ASSETS_DIR="$NOTE_DIR/assets"
mkdir -p "$ASSETS_DIR"
echo "Title: $NOTE_TITLE"
echo "Assets: $ASSETS_DIR"
```

---

### Step 1 — 確認 notebooklm CLI 可用

```bash
command -v notebooklm >/dev/null || { echo "ERROR: notebooklm not found. Run: pip install notebooklm-cli"; exit 1; }
notebooklm status 2>&1 | head -5
```

若 `status` 顯示未登入，告知使用者執行 `notebooklm login` 後重試。

---

### Step 2 — 建立 notebook 並加入來源

**若有 `--notebook` 參數**，直接 `notebooklm use <id>`，跳過建立。

**否則**：

```bash
# 建立新 notebook
NOTEBOOK_ID=$(notebooklm create "$NOTE_TITLE" 2>&1 | grep -oP '[0-9a-f-]{36}')
echo "Created: $NOTEBOOK_ID"

# 切換至該 notebook
notebooklm use "$NOTEBOOK_ID" 2>&1
```

加入來源：

```bash
# 若是本地檔案
notebooklm source add "$NOTE_PATH" 2>&1

# 若是 URL
# notebooklm source add "$SOURCE_URL" 2>&1
```

等待來源處理完成（大型檔案可能需要 10–30 秒）：

```bash
notebooklm source wait 2>&1 | tail -3
```

若 `source wait` 不存在，改用：

```bash
until notebooklm source list 2>&1 | grep -q "ready\|indexed\|completed"; do sleep 3; done
```

---

### Step 3 — 設定輸出語言為繁體中文

```bash
notebooklm language set zh_Hant 2>&1
```

> ⚠️ 這是 global 設定，會影響帳號下所有 notebook。執行完 skill 後不會自動還原。

---

### Step 4 — 生成 artifacts

根據 `ARTIFACTS` 清單依序觸發生成。預設生成：

```bash
# Infographic（landscape — 適合概覽圖）
notebooklm generate infographic --orientation landscape 2>&1
ARTIFACT_LANDSCAPE=$(notebooklm artifact list 2>&1 | grep "Infographic" | head -1 | grep -oP '[0-9a-f-]{8}')

# Infographic（portrait — 適合詳細流程圖）
notebooklm generate infographic --orientation portrait 2>&1
ARTIFACT_PORTRAIT=$(notebooklm artifact list 2>&1 | grep "Infographic" | head -2 | tail -1 | grep -oP '[0-9a-f-]{8}')

# Mind Map
notebooklm generate mind-map 2>&1

# Data Table（依筆記主題客製化 prompt）
notebooklm generate data-table "關鍵指標與數據整理" 2>&1
```

記下所有觸發的 artifact ID（從 `Started: <uuid>` 取得）。

---

### Step 5 — 等待所有 artifacts 完成

```bash
notebooklm artifact wait 2>&1
```

若 `artifact wait` 失敗，改用 poll loop：

```bash
until notebooklm artifact list 2>&1 | grep -v "generating\|pending" | grep -qE "infographic|mind.map|data.table"; do
    sleep 5
done
notebooklm artifact list 2>&1
```

確認所有 artifact Status 為 `completed`，若有 `failed` 告知使用者並繼續下載其他成功的。

---

### Step 6 — 下載 artifacts

從 `artifact list` 取得各 artifact 的 ID（使用前 8 碼前綴即可）。

```bash
# 下載 landscape infographic
notebooklm download infographic -a <landscape_id> "$ASSETS_DIR/infographic_landscape.png" --force 2>&1

# 下載 portrait infographic
notebooklm download infographic -a <portrait_id> "$ASSETS_DIR/infographic_portrait.png" --force 2>&1

# 下載 mind-map
notebooklm download mind-map "$ASSETS_DIR/mindmap.json" 2>&1

# 下載 data-table
notebooklm download data-table "$ASSETS_DIR/data_table.csv" 2>&1
```

用 Read tool 讀取兩張 PNG 確認是繁體中文且有實質內容，若仍是英文，重新執行 Step 3 並再次生成。

---

### Step 7 — 嵌入筆記（若 `--no-embed` 未設定）

在筆記的**第一段落文字之後**（frontmatter 結束後的第一個段落末尾）插入圖片：

```markdown
![[assets/infographic_landscape.png]]
> *圖：{筆記標題}——整體架構概覽*

![[assets/infographic_portrait.png]]
> *圖：{筆記標題}——核心概念與詳細結構*
```

**插入位置規則**：
- 找到 frontmatter（`---` 之間）結束後的第一個非空段落
- 在該段落的**末尾**（不是開頭）插入，保持閱讀流暢
- 若筆記已有 `![[assets/infographic` 開頭的圖片，**替換**舊有圖片，不重複插入

用 Edit tool 執行插入，不要用 bash。

---

### Step 8 — 報告結果

```
✓ Notebook:     {title} ({notebook_id})
✓ Source:       {note_path or url}
✓ Language:     zh_Hant（繁體中文）
✓ Artifacts:    {N} 個已生成
  - infographic_landscape.png  ({size}KB)
  - infographic_portrait.png   ({size}KB)
  - mindmap.json
  - data_table.csv
✓ Embedded:     {note_path}（在第一段落後）

NotebookLM Notebook ID: {notebook_id}
（下次可用 --notebook {notebook_id_prefix} 重用此 notebook）
```

---

## Edge Cases

| 狀況 | 處理方式 |
|------|---------|
| 來源檔案太大（> 500KB） | notebooklm 會自動截斷；`source wait` 後確認 indexed 狀態 |
| 輸出仍是英文 | 確認 `notebooklm language get` 回傳 `zh_Hant`；重新執行 Step 3 再生成 |
| artifact 生成失敗 | `artifact list` 顯示 `failed`；跳過該類型，下載其他成功的 |
| `artifact wait` 命令不存在 | 改用 Step 5 的 poll loop |
| 筆記路徑含空格或特殊字元 | 用雙引號包住路徑 |
| `--notebook` 指定舊 notebook | 直接 `use`，跳過建立，從 Step 3 開始 |
| 來源是 URL | `source add <url>` 後等待抓取完成（可能需 30s–2min） |
| 圖片已存在 | `--force` 覆蓋；若不想覆蓋改用 `--no-clobber` |
| 筆記無 frontmatter title | 使用檔名（去除 `.md`）作為 notebook 名稱 |
| 筆記已有舊版圖片 | Step 7 偵測到 `![[assets/infographic` 時替換，不新增 |

---

## Architecture

```
輸入（筆記路徑 / URL）
 │
 ├─ Step 0: 解析參數（title, assets dir）
 ├─ Step 1: 確認 CLI 可用 + 登入狀態
 ├─ Step 2: 建立 notebook → source add → wait indexed
 ├─ Step 3: language set zh_Hant（global）
 ├─ Step 4: generate infographic×2 + mind-map + data-table
 ├─ Step 5: artifact wait（poll until all completed）
 ├─ Step 6: download → assets/ 子資料夾
 ├─ Step 7: Edit tool 插入圖片到筆記第一段落後
 └─ Step 8: 報告 notebook ID + artifact 清單
```
