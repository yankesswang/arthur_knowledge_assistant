---
name: twitter-save
description: 用戶提供 X/Twitter URL，自動判斷內容類型（推文 thread / 長文 article）並下載儲存到本地檔案。
tags: [twitter, x, download, save, article, thread]
allowed-tools: Bash
---

# Twitter Save — 下載 X/Twitter 內容到本地

用戶給一個 X/Twitter URL，你判斷類型、下載、存檔。

## 輸入

用戶提供的 URL，格式可能是：

| 類型 | URL 範例 |
|------|---------|
| 推文 / Thread | `https://x.com/<user>/status/<id>` |
| 長文 Article | `https://x.com/i/article/<id>` |
| 短網址 (t.co) | `https://t.co/xxxxxxx` |

## 流程

### Step 1：判斷 URL 類型

```bash
# 如果是 t.co 短網址，先解析真實 URL
curl -sI "https://t.co/xxxxxxx" | grep -i location
```

根據真實 URL 判斷：
- 含 `/i/article/` → **Article**
- 含 `/status/` → **Thread**（推文串）

### Step 2：下載內容

**Article（長文）：**
```bash
opencli twitter article "<url>"
```
> 若用戶給的是 status URL，article 指令會自動處理；若給的是 t.co，先解析再帶入。

**Thread（推文串）：**
```bash
opencli twitter thread "<url>"
```

### Step 3：決定輸出檔名

規則：`<author>_<type>_<id>.<ext>`

| 情況 | 副檔名 |
|------|--------|
| Article | `.yaml` |
| Thread | `.yaml` |

從 URL 提取 `<id>`（最後一段數字），從輸出第一行提取 `<author>`。

若無法自動提取作者，用 URL 的 `<user>` 欄位。

### Step 4：儲存

```bash
opencli twitter article "<url>" > <filename>
# 或
opencli twitter thread "<url>" > <filename>
```

確認存檔後回報：
- 儲存路徑（絕對路徑）
- 內容類型
- 作者
- 圖片數量（Article 才有）
- Thread 則回報推文數

## 執行環境注意

opencli 需要 Node.js v22+，透過 nvm 載入：

```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 22 --silent && opencli ...
```

先確認連線正常：
```bash
opencli doctor
```
若 Extension 未連線，提醒用戶開啟 Chrome 並載入 Browser Bridge extension。

## 範例

用戶：`https://x.com/intuitiveml/status/2043545596699750791`

1. 判斷：`/status/` → Thread，同時檢查是否為 Article tweet（tweet 內容是否含 t.co 連結）
2. 先嘗試 `opencli twitter article` → 若有 article 則優先儲存
3. 同時儲存 thread（回覆討論）
4. 輸出：
   - `article_intuitiveml_<id>.yaml`（文章本文 + 圖片）
   - `thread_intuitiveml_<id>.yaml`（推文串 + 回覆）
