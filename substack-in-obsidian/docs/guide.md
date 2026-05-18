# Substack in Obsidian — 完整使用指南

> 本指南涵蓋從零開始安裝到每日使用的完整流程，以及常見問題排查。

---

## 目錄

1. [環境需求](#1-環境需求)
2. [安裝插件](#2-安裝插件)
3. [取得 Playwright Token](#3-取得-playwright-token)
4. [插件設定](#4-插件設定)
5. [開啟預覽](#5-開啟預覽)
6. [Frontmatter 格式](#6-frontmatter-格式)
7. [上傳草稿到 Substack](#7-上傳草稿到-substack)
8. [在新機器上設定（macOS / Ubuntu）](#8-在新機器上設定macos--ubuntu)
9. [常見問題排查](#9-常見問題排查)

---

## 1. 環境需求

| 項目 | 說明 |
|------|------|
| **Obsidian** | 版本 1.6.0 以上，桌面版（Desktop only） |
| **Node.js** | v18 以上，安裝後確認 `node`、`npm`、`npx` 可在終端機執行 |
| **Chrome 瀏覽器** | 需登入 Substack，用於 Playwright MCP Bridge |
| **Playwright MCP Bridge 擴充功能** | 從 Chrome Web Store 安裝，提供 `PLAYWRIGHT_MCP_EXTENSION_TOKEN` |

> 純預覽功能不需要 Node.js 或 Chrome 擴充功能。

---

## 2. 安裝插件

### 從源碼構建

```bash
cd /path/to/substack-in-obsidian
npm install
npm run build
```

將以下三個檔案複製到 Vault 的插件資料夾：

```
<Vault>/.obsidian/plugins/substack-in-obsidian/
├── main.js
├── manifest.json
└── styles.css
```

重新載入 Obsidian，在 **設定 → 第三方插件** 中啟用 `Substack in Obsidian`。

---

## 3. 取得 Playwright Token

1. 在 Chrome 中安裝 **Playwright MCP Bridge** 擴充功能
2. 點擊工具列上的擴充功能圖示，進入設定
3. 找到 `PLAYWRIGHT_MCP_EXTENSION_TOKEN`，複製**等號後面的值**

> **重要**：只貼 Token 本身的值，不要包含前綴。
>
> 正確：`PR8AL4E7QEHgLG7CLXosOV_Q3K9KUDpJ0KakRAmR-1I`
>
> 錯誤：`PLAYWRIGHT_MCP_EXTENSION_TOKEN=PR8AL4E7QEHgLG7CLXosOV_Q3K9KUDpJ0KakRAmR-1I`

Token 是**每台機器獨立產生的**，在新機器上需要重新填入。

---

## 4. 插件設定

前往 **設定 → Substack in Obsidian**：

| 設定項 | 說明 | 範例 |
|--------|------|------|
| **Substack publication URL** | 你的 Substack 網址 | `https://yourname.substack.com` |
| **Playwright MCP token** | Playwright Token 值（見上方說明） | `PR8AL4E7QEH...` |

### 預覽設定

| 設定項 | 預設值 | 說明 |
|--------|--------|------|
| Auto refresh | 開啟 | 切換或編輯筆記時自動更新預覽 |
| Hide frontmatter | 開啟 | 預覽中不顯示 YAML 區塊 |
| Use filename as title | 開啟 | 沒有 `# 標題` 時用檔案名稱代替 |

### Debug 設定

| 設定項 | 說明 |
|--------|------|
| Enable debug log | 將發布事件寫入 `logs/publish.log`，排查上傳失敗時很有用 |

---

## 5. 開啟預覽

啟用插件後，以下任一方式開啟預覽面板：

- 點擊左側功能區的**報紙圖示**
- `Cmd+P`（macOS）或 `Ctrl+P`（Windows/Linux）→ 搜尋 **Open preview**

預覽面板功能：

- 自動跟隨當前編輯中的筆記
- 滾動同步（編輯器滾動，預覽同步）
- 顯示封面圖（Hero card）、標題、摘要
- 顯示「Draft preview — not published」提示標籤
- 點擊 **Upload draft** 按鈕直接上傳

---

## 6. Frontmatter 格式

### 基本格式

```yaml
---
title: "文章標題"
description: "文章摘要（會成為 Substack 的 subtitle）"
cover: ![[cover.png]]
---

# 也可以在正文用 H1 當標題
```

### 欄位說明

| 欄位 | 說明 |
|------|------|
| `title` | 文章標題。如果不設，插件會從正文第一個 `# 標題` 提取；再不行則用檔案名稱 |
| `description` / `subtitle` | 文章副標題（Subtitle）。顯示在預覽的摘要區域，並填入 Substack 的 subtitle 欄位 |
| `cover` | 封面圖，支援 `![[image.png]]`（Vault 內部連結）或外部 URL |

### 標題提取優先順序

1. Frontmatter `title`
2. 正文第一個 `# 標題`（提取後從正文移除，避免重複）
3. 檔案名稱（需開啟「Use filename as title」設定）

---

## 7. 上傳草稿到 Substack

插件會自動開啟 Substack 編輯器，填入標題、副標題與正文，並**儲存為草稿**，不會點擊最終發布。你可以在 Substack 網頁確認內容後再手動發布。

### 方式一：從預覽面板上傳（推薦）

1. 打開一篇筆記，預覽面板確認內容正確
2. 點擊預覽面板右上角的 **Upload draft**
3. 等待上傳完成（進度會顯示在通知欄）
4. 在瀏覽器的 Substack 草稿中確認內容，手動發布

### 方式二：命令面板上傳

`Cmd+P` → **Upload draft to Substack**

### 上傳流程細節

1. 插件啟動 Playwright MCP，透過 Chrome 擴充功能控制瀏覽器
2. 導航到你的 Substack 寫作介面（`https://yourname.substack.com/publish/post/new`）
3. 填入標題 → 副標題 → 貼上正文（透過 clipboard）
4. 儲存草稿

> 上傳前確認 Chrome 已登入你的 Substack 帳號。

---

## 8. 在新機器上設定（macOS / Ubuntu）

Vault 同步時 `data.json`（插件設定）也會同步，**但 Token 必須在每台機器上重新設定**。

### macOS（Homebrew 環境）

```bash
# 安裝 Node.js
brew install node

# 確認安裝
node -v && npx -v
```

1. 在 Chrome 安裝 Playwright MCP Bridge
2. 取得該機器的 Token
3. 在 Obsidian 插件設定中填入新 Token 和 Substack URL

### Ubuntu / Linux

```bash
# 安裝 Node.js（用 nvm）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install --lts

# 確認安裝
node -v && npx -v

# 安裝 Chrome
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update && sudo apt install -y google-chrome-stable
```

> 若出現 `spawn npx ENOENT`，將 npx 連結到 `/usr/local/bin`：
> ```bash
> sudo ln -sf $(which npx) /usr/local/bin/npx
> sudo ln -sf $(which node) /usr/local/bin/node
> ```

---

## 9. 常見問題排查

### `spawn npx ENOENT` / MCP 啟動失敗

**原因**：Obsidian（Electron）GUI 方式啟動，不繼承 Shell 的 PATH，找不到 `npx`。

**解法**：
- macOS：確認 `/opt/homebrew/bin/npx` 存在（`which npx`）。插件會自動搜尋此路徑。
- Ubuntu：`sudo ln -sf $(which npx) /usr/local/bin/npx`

### `invalid token provided` / Token 驗證失敗

**原因**：貼入了完整的 `PLAYWRIGHT_MCP_EXTENSION_TOKEN=...` 字串。

**解法**：只貼等號後面的值。插件會自動去除前綴，但建議手動確認設定中只有 Token 值。

### 上傳後 Substack 顯示空白或正文遺失

**解法**：
1. 確認 Chrome 已登入 Substack 帳號
2. 確認插件設定中的 `Substack publication URL` 只是 `https://yourname.substack.com`，不含路徑或 `utm_source` 參數
3. 啟用 Debug Log，重新上傳後查看 `logs/publish.log`

### Substack URL 設定格式錯誤

**正確**：`https://yourname.substack.com`

**錯誤**：
- `https://yourname.substack.com/` （多了結尾斜線，插件會自動修正）
- `https://yourname.substack.com/p/post-title?utm_source=...` （不應填文章頁面）

### Token 在新機器失效

Playwright Token 是每台機器 Chrome 獨立生成的，不能跨機器共用。在新機器的 Chrome 取得 Token 後，更新插件設定即可。

### 如何查看 Debug Log

```
<Vault>/.obsidian/plugins/substack-in-obsidian/logs/publish.log
```

---

## 快速參考

| 動作 | 方法 |
|------|------|
| 開啟預覽 | 報紙圖示 / `Cmd+P` → Open preview |
| 上傳到草稿 | 預覽面板 → Upload draft / `Cmd+P` → Upload draft to Substack |
| 查看 Debug Log | `<Vault>/.obsidian/plugins/substack-in-obsidian/logs/publish.log` |
