# twitter-cli 使用指南

X/Twitter 終端機工具，**不需要 API Key**，透過瀏覽器 Cookie 認證，支援讀取與發文。

---

## 一、安裝與啟動

### 本地專案（目前的設置）

```bash
cd /Users/yankesswang/Desktop/Projects/Arthur_App/twitter-cli
uv run twitter <指令>
```

### 全域安裝（安裝後可直接用 `twitter`）

```bash
uv tool install /Users/yankesswang/Desktop/Projects/Arthur_App/twitter-cli
# 之後直接執行：
twitter feed
```

### 升級

```bash
uv tool upgrade twitter-cli
```

---

## 二、認證

**不需要手動設定**，CLI 會自動從瀏覽器提取 Cookie（Arc / Chrome / Firefox / Brave / Edge）。前提：要先在瀏覽器登入 x.com。

```bash
# 驗證目前登入狀態
twitter status
twitter whoami

# 指定瀏覽器
TWITTER_BROWSER=chrome uv run twitter feed

# Chrome 多 Profile
TWITTER_CHROME_PROFILE="Profile 2" uv run twitter feed

# 手動設定（不推薦）
TWITTER_AUTH_TOKEN=xxx TWITTER_CT0=yyy uv run twitter feed
```

如果出現 `Unable to get key for cookie decryption` 錯誤（macOS Keychain）：

```bash
security unlock-keychain ~/Library/Keychains/login.keychain-db
```

---

## 三、所有可用指令

### 讀取類

| 指令 | 功能 |
|---|---|
| `feed` | 首頁時間線（For You / Following）|
| `search "關鍵字"` | 搜尋推文 |
| `tweet <id>` | 查看單則推文 + 回覆 |
| `show <N>` | 開啟上次列表的第 N 則 |
| `bookmarks` | 查看書籤 |
| `article <id>` | 讀取 Twitter Article（長文）|
| `list <id>` | 讀取 Twitter List 時間線 |
| `user <username>` | 查看用戶資料 |
| `user-posts <username>` | 查看用戶發文 |
| `likes <username>` | 查看用戶按讚（僅自己）|
| `followers <username>` | 粉絲列表 |
| `following <username>` | 追蹤列表 |
| `whoami` | 目前登入的帳號 |
| `status` | 確認登入狀態 |

### 寫入類

| 指令 | 功能 |
|---|---|
| `post "內容"` | 發推文 |
| `reply <id> "內容"` | 回覆推文 |
| `quote <id> "評論"` | 引用推文 |
| `delete <id>` | 刪除推文 |
| `like <id>` | 按讚 |
| `unlike <id>` | 取消按讚 |
| `retweet <id>` | 轉推 |
| `unretweet <id>` | 取消轉推 |
| `bookmark <id>` | 加書籤 |
| `unbookmark <id>` | 取消書籤 |
| `follow <username>` | 追蹤用戶 |
| `unfollow <username>` | 取消追蹤 |

---

## 四、常用操作範例

### 讀取

```bash
# 首頁時間線
twitter feed
twitter feed -t following          # Following 頁
twitter feed --max 30              # 限制筆數
twitter feed --filter              # 依互動分數排序
twitter feed --full-text           # 不截斷推文

# 搜尋
twitter search "Claude Code"
twitter search "AI agent" -t Latest --max 50
twitter search "topic" --from elonmusk --since 2026-01-01
twitter search "AI" --yaml         # 結構化輸出

# 查看推文與回覆
twitter tweet 1234567890
twitter show 3                     # 上次列表第 3 則

# 用戶
twitter user elonmusk
twitter user-posts elonmusk --max 20

# Article（只能讀，不能發）
twitter article 1234567890 --markdown
twitter article 1234567890 --output article.md
```

### 發文

```bash
# 基本發文
twitter post "Hello world"

# 帶圖片（最多 4 張）
twitter post "附圖" -i photo.jpg
twitter post "多圖" -i a.png -i b.jpg -i c.webp

# 回覆
twitter post "回覆內容" --reply-to 1234567890
twitter reply 1234567890 "回覆"

# 引用推文
twitter quote 1234567890 "我的評論"

# 確認發文結果
twitter post "Hello!" --json
```

---

## 五、輸出模式

| 模式 | 用途 |
|---|---|
| 預設（rich table）| 終端機閱覽 |
| `--full-text` | 顯示完整推文，不截斷 |
| `--yaml` | 結構化輸出，適合 AI / 腳本 |
| `--json` | JSON 輸出 |
| `-c` / `--compact` | 精簡輸出，省 token |
| `-o results.json` | 儲存到檔案 |

```bash
# 儲存到檔案後再讀取
twitter feed --json > tweets.json
twitter feed --input tweets.json
```

---

## 六、代理設定（推薦）

```bash
export TWITTER_PROXY=http://127.0.0.1:7890   # HTTP
export TWITTER_PROXY=socks5://127.0.0.1:1080  # SOCKS5
```

---

## 七、設定檔（config.yaml）

路徑：`/Users/yankesswang/Desktop/Projects/Arthur_App/twitter-cli/config.yaml`

```yaml
fetch:
  count: 50              # 預設每次拉幾則

filter:
  mode: "topN"           # topN / score / all
  topN: 20               # 保留前幾則
  minScore: 50
  weights:
    likes: 1.0
    retweets: 3.0
    replies: 2.0
    bookmarks: 5.0
    views_log: 0.5

rateLimit:
  requestDelay: 1.5      # 請求間隔（秒）
  maxRetries: 3
  maxCount: 200          # 單次最大上限
```

排分公式：
```
score = likes×1.0 + retweets×3.0 + replies×2.0 + bookmarks×5.0 + log10(views)×0.5
```

---

## 八、防風控建議

- 使用代理（`TWITTER_PROXY`）
- `--max` 控制在 50 以內，不要用 `--max 500`
- 不要頻繁重啟（每次啟動都會訪問 x.com 初始化）
- 寫操作有內建隨機延遲 1.5–4 秒，這是正常的

---

## 九、常見錯誤排查

| 錯誤 | 原因 | 解法 |
|---|---|---|
| `No Twitter cookies found` | 瀏覽器未登入 | 在支援的瀏覽器登入 x.com |
| `Cookie expired (401/403)` | Cookie 過期 | 重新登入 x.com |
| `Unable to get key for cookie decryption` | macOS Keychain 鎖定 | 執行 `security unlock-keychain ~/Library/Keychains/login.keychain-db` |
| `Twitter API error 404` | GraphQL queryId 輪換 | 重試，有自動 fallback |
| `daily limit for sending Tweets (344)` | 達到當日發文上限 | 等隔天再試 |

---

## 十、不支援的操作

- **發布 Twitter Article（長文）**：平台無公開 API，僅能讀取，無法程式化發布
- **私訊（DM）**：不支援

---

## 專案路徑

```
/Users/yankesswang/Desktop/Projects/Arthur_App/twitter-cli/
├── twitter_cli/        # 核心程式碼
├── config.yaml         # 設定檔
├── README.md           # 完整英文文件
└── SKILL.md            # AI Agent Skill 說明
```
