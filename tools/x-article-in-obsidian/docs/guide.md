# X Article in Obsidian — 完整使用指南

> 本指南涵蓋從零開始安裝到每日使用的完整流程，以及常見問題排查。

---

## 目錄

1. [環境需求](#1-環境需求)
2. [安裝插件](#2-安裝插件)
3. [取得 Playwright Token](#3-取得-playwright-token)
4. [插件設定](#4-插件設定)
5. [開啟預覽](#5-開啟預覽)
6. [Frontmatter 格式](#6-frontmatter-格式)
7. [上傳草稿到 X Article](#7-上傳草稿到-x-article)
8. [在新機器上設定（macOS / Ubuntu）](#8-在新機器上設定macos--ubuntu)
9. [常見問題排查](#9-常見問題排查)

---

## 1. 環境需求

在使用上傳功能前，需要完成以下準備：

| 項目 | 說明 |
|------|------|
| **Obsidian** | 版本 1.6.0 以上，桌面版（Desktop only） |
| **Node.js** | v18 以上，安裝後確認 `node`、`npm`、`npx` 可在終端機執行 |
| **Chrome 瀏覽器** | 用於 Playwright MCP Bridge |
| **Playwright MCP Bridge 擴充功能** | 從 Chrome Web Store 安裝，提供 `PLAYWRIGHT_MCP_EXTENSION_TOKEN` |

> 純預覽功能不需要 Node.js 或 Chrome 擴充功能。

---

## 2. 安裝插件

### 方式一：直接複製構建檔（最快）

```bash
cd /path/to/x-article-in-obsidian
npm install
npm run build
```

將以下三個檔案複製到 Vault 的插件資料夾：

```
<Vault>/.obsidian/plugins/x-article-in-obsidian/
├── main.js
├── manifest.json
└── styles.css
```

重新載入 Obsidian，在 **設定 → 第三方插件** 中啟用 `X Article in Obsidian`。

### 方式二：從 GitHub Release 下載

1. 前往 [GitHub Releases](https://github.com/Icy-Cat/x-article-in-obsidian/releases/latest)
2. 下載 zip，解壓縮後得到 `main.js`、`manifest.json`、`styles.css`
3. 複製到上方路徑，重載 Obsidian 後啟用

---

## 3. 取得 Playwright Token

1. 在 Chrome 中安裝 **Playwright MCP Bridge** 擴充功能
2. 點擊工具列上的擴充功能圖示，進入設定
3. 找到 `PLAYWRIGHT_MCP_EXTENSION_TOKEN`，複製**等號後面的值**

> **重要**：只貼 Token 本身的值，不要包含 `PLAYWRIGHT_MCP_EXTENSION_TOKEN=` 這段前綴。
>
> 正確範例：`PR8AL4E7QEHgLG7CLXosOV_Q3K9KUDpJ0KakRAmR-1I`
>
> 錯誤範例：`PLAYWRIGHT_MCP_EXTENSION_TOKEN=PR8AL4E7QEHgLG7CLXosOV_Q3K9KUDpJ0KakRAmR-1I`

Token 是**每台機器獨立產生的**，Vault 跨機器同步時 `data.json` 裡的 Token 不會自動更新，需要在每台機器上重新填入。

---

## 4. 插件設定

前往 **設定 → X Article in Obsidian**：

### 草稿箱上傳

| 設定項 | 說明 |
|--------|------|
| **Playwright Token** | 貼入 Token 值（見上方說明） |
| **自動檢測** | 掃描本機可用 Token 並自動填入 |

### 預覽

| 設定項 | 預設值 | 說明 |
|--------|--------|------|
| 自動刷新 | 開啟 | 切換或編輯筆記時自動更新預覽 |
| 隱藏 Frontmatter | 開啟 | 預覽中不顯示 YAML 區塊 |
| 文件名補標題 | 開啟 | 沒有 `# 標題` 時用檔案名稱代替 |
| 顯示草稿提示 | 開啟 | 正文上方顯示「草稿預覽」提示條 |

### Debug

| 設定項 | 說明 |
|--------|------|
| 啟用 Debug Log | 將發布事件寫入 `logs/publish.log`，排查上傳失敗時很有用 |

---

## 5. 開啟預覽

啟用插件後，以下任一方式開啟預覽面板：

- 點擊左側功能區的**報紙圖示**
- `Cmd+P`（macOS）或 `Ctrl+P`（Windows/Linux）→ 搜尋 **Open preview**（英文）或 **打开预览**（簡中）

預覽面板功能：

- 自動跟隨當前編輯中的筆記
- 滾動同步（編輯器滾動，預覽同步）
- 顯示封面圖、標題、摘要
- 支援 X / Twitter 連結富預覽
- 顯示草稿提示標籤

---

## 6. Frontmatter 格式

插件優先讀取 `formatter.title` 和 `formatter.cover`，向下兼容舊格式的頂層 `title` / `cover`。

### 推薦格式（新）

```yaml
---
formatter:
  title: 我的 X 長文標題
  cover: ![[cover.png]]
---
```

### 向下兼容格式（舊）

```yaml
---
title: 我的 X 長文標題
cover: ![[cover.png]]
---
```

### 欄位說明

| 欄位 | 說明 |
|------|------|
| `formatter.title` / `title` | 文章標題，覆蓋第一個 `# 標題` 或檔案名稱 |
| `formatter.cover` / `cover` | 封面圖，支援 `![[image.png]]`（Vault 內部連結）或外部 URL |

> 在預覽面板點擊 **添加 formatter** 按鈕，可自動為當前筆記補充 `formatter.title` 和 `formatter.cover` 欄位。

---

## 7. 上傳草稿到 X Article

插件會自動填入 X Article 編輯器並**儲存為草稿**，不會點擊最終發布，由你在瀏覽器中確認後手動發布。

### 方式一：從預覽面板上傳（推薦）

1. 打開一篇筆記，確認預覽內容正確
2. 點擊預覽面板右上角的 **上傳到草稿箱**
3. 等待完成後，在瀏覽器的 X Article 草稿中確認內容
4. 確認無誤後，在 X 網頁手動點擊發布

### 方式二：命令面板上傳

`Cmd+P` → **通过浏览器上传到草稿箱**（簡中）或 **Upload article to draft through browser**（英文）

### 方式三：複製上傳腳本（手動執行）

1. `Cmd+P` → **复制 X 草稿上传脚本**
2. 在瀏覽器開啟 X Article 編輯器
3. 按 `F12` 開啟開發者工具 → Console
4. 貼上腳本並執行

---

## 8. 在新機器上設定（macOS / Ubuntu）

Vault 透過 iCloud / Syncthing 等服務同步時，插件的 `data.json`（設定）也會同步，**但 Token 必須在每台機器上重新設定**，因為 Playwright Token 是每台機器的 Chrome 獨立生成的。

### macOS（Homebrew 環境）

```bash
# 安裝 Node.js
brew install node

# 確認安裝成功
node -v
npx -v
```

安裝 Playwright MCP Bridge Chrome 擴充功能，取得新機器的 Token 後填入 Obsidian 插件設定。

### Ubuntu / Linux

```bash
# 安裝 Node.js（用 nvm，避免 sudo 權限問題）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install --lts

# 確認安裝
node -v && npx -v

# 安裝 Chrome（Ubuntu）
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update && sudo apt install -y google-chrome-stable
```

在 Chrome 安裝 Playwright MCP Bridge，取得 Token 填入設定。

> Ubuntu 使用 Obsidian AppImage / Flatpak 時，Electron GUI 程序的 PATH 可能不包含 `~/.nvm/versions/node/...`，如出現 `spawn npx ENOENT` 錯誤，將 `npx` 做符號連結到 `/usr/local/bin`：
>
> ```bash
> sudo ln -sf $(which npx) /usr/local/bin/npx
> sudo ln -sf $(which node) /usr/local/bin/node
> ```

---

## 9. 常見問題排查

### `spawn npx ENOENT` / MCP 啟動失敗

**原因**：Obsidian（Electron）以 GUI 方式啟動，不繼承 Shell 的 PATH，找不到 `npx`。

**解法**：
- macOS：確認 `/opt/homebrew/bin/npx` 存在（`which npx`）。插件已自動延伸搜尋路徑。
- Ubuntu：將 `npx` 做符號連結到 `/usr/local/bin/npx`（見上方 Ubuntu 設定）。

### `invalid token provided` / Token 驗證失敗

**原因**：Token 格式不正確，貼入了 `PLAYWRIGHT_MCP_EXTENSION_TOKEN=Xxx...` 整段。

**解法**：只貼等號後面的值，例如 `PR8AL4E7QEH...`。

### 圖片放錯位置、被刪除、標題亂跑

**原因**：筆記 Frontmatter 或正文中存在 `MPH_MARKER_N`（或 `MPH\_MARKER\_N`）字串，與插件的內部標記衝突。

**解法**：在筆記中搜尋並刪除所有 `MPH_MARKER` 字樣。插件已在解析時自動清除，舊版本需手動清理。

### Token 在新機器失效

**原因**：Playwright Token 是每台機器 Chrome 獨立生成的，不能跨機器共用。

**解法**：在新機器的 Chrome 擴充功能設定中取得該機器的 Token，在 Obsidian 插件設定中更新。

### 上傳後 X Article 顯示空白

**原因**：可能是 Playwright MCP 尚未連接，或 Chrome 未登入 X 帳號。

**解法**：
1. 確認 Chrome 已登入 X
2. 確認 Playwright MCP Bridge 擴充功能處於啟用狀態
3. 啟用 Debug Log（設定 → Debug → 啟用 Debug Log），重新上傳後查看 `logs/publish.log`

### 如何查看 Debug Log

```
<Vault>/.obsidian/plugins/x-article-in-obsidian/logs/publish.log
```

每次上傳操作都會追加記錄，包含 MCP 啟動、工具呼叫、錯誤詳情。

---

## 快速參考

| 動作 | 方法 |
|------|------|
| 開啟預覽 | 報紙圖示 / `Cmd+P` → Open preview |
| 上傳到草稿 | 預覽面板 → Upload draft / `Cmd+P` → 通过浏览器上传到草稿箱 |
| 複製發布腳本 | `Cmd+P` → 复制 X 草稿上传脚本 |
| 查看使用指南 | `Cmd+P` → 打开快速使用指南 |
| 查看 Debug Log | `<Vault>/.obsidian/plugins/x-article-in-obsidian/logs/publish.log` |
