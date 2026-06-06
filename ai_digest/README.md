# AI Digest

每日自動從 90 個技術部落格 RSS 抓取文章，Gemini AI 精選後寫入 Obsidian。

---

## 架構

```
launchd (com.golem.daily-digest) → digest-auto.sh → digest.ts → Obsidian + Telegram
```

- 觸發時間：每天 **07:03**（launchd plist）
- 主腳本：`ai_digest/scripts/digest-auto.sh`
- 摘要生成：`ai_digest/scripts/digest.ts`
- 輸出：`ai_digest/output/digest-YYYYMMDD.md`
- Obsidian：`AI Knowledge/Digest/digest-YYYYMMDD.md`

---

## 目前信息源

### RSS（唯一啟用的來源）

**90 個 Karpathy HN Popularity Contest 2025 推薦的個人技術部落格**，內容涵蓋：

| 類型 | 代表來源 | 佔比 |
|------|---------|------|
| AI/LLM | simonwillison.net、seangoedecke.com、minimaxir.com、geohot、gwern | ~15% |
| 資安 | krebsonsecurity.com、troyhunt.com、brutecat.com | ~15% |
| 一般工程 | matklad、overreacted.io、eli.thegreenplace.net、lucumr.pocoo.org | ~30% |
| 觀點/評論 | pluralistic.net、garymarcus.substack.com、wheresyoured.at | ~20% |
| 數學/硬體 | johndcook.com、righto.com（Ken Shirriff）、fabiensanglard.net | ~10% |
| 其他 | construction-physics.com、filfre.net、tedium.co | ~10% |

**已知問題**：信息源過廣，Top 3 選出來常混入資安新聞、HN meme、數學文章，並非都是 AI/工程相關。

---

## Horizon 各信息源抓取方式

### Hacker News
- **API**：`https://hacker-news.firebaseio.com/v0/topstories.json`（官方 Firebase API）
- **流程**：抓 Top N 則 story ID → 並發取每則 story 詳情 → 過濾 `min_score`（預設 100）→ 抓前 5 則留言
- **不需要任何 token**

### Reddit
- **API**：`https://www.reddit.com/r/{subreddit}/{sort}.json`（模擬瀏覽器 User-Agent）
- **流程**：直接打 Reddit JSON 端點，支援 hot/new/top/rising 排序，可選時間範圍（day/week/month）
- **也支援追蹤特定用戶**：`/user/{username}/submitted.json`
- **不需要任何 token**（有時會被 rate limit，有 retry 機制）

### Telegram
- **方式**：爬 `https://t.me/s/{channel}` 公開頻道網頁預覽，用 BeautifulSoup 解析 HTML
- **限制**：**只支援公開頻道**，私人頻道無法抓取
- **不需要 Bot token**

### RSS
- 標準 `feedparser` 解析，支援任意 RSS/Atom

### GitHub
- **user_events**：`https://api.github.com/users/{username}/events/public`，追蹤用戶的 star、push、PR、fork 等公開動態
- **repo_releases**：`https://api.github.com/repos/{owner}/{repo}/releases`，監聽新版本
- **不需要 token**，加 `GITHUB_TOKEN` 可提高 rate limit（未認證 60次/小時，認證 5000次/小時）

### Twitter/X
- **方式**：透過 Apify 的 `altimis/scweet` actor 抓推文
- **需要 Apify token**，免費方案 $5/月 ≈ 20,000 tweets
- 可追蹤指定用戶，可選是否抓回覆及最低按讚數過濾

### OSS Insight（GitHub Trending）
- **API**：`https://api.ossinsight.io/v1/trends/repos?period=past_24_hours`
- 從 GitHub WatchEvent 計算星星增長，無需任何 token

---

## 待整合信息源研究

### GitHub Trending

#### OSS Insight API（推薦）

從 GitHub WatchEvent 計算星星增長，無需 API key。

```
GET https://api.ossinsight.io/v1/trends/repos?period=past_24_hours&language=All&limit=50
```

**API 回傳欄位：**

| 欄位 | 說明 |
|------|------|
| `repo_name` | owner/repo |
| `primary_language` | 主要語言 |
| `description` | repo 描述（一行） |
| `stars` | 期間新增星星數 |
| `forks` | fork 數 |
| `pull_requests` | PR 數 |
| `pushes` | push 次數（活躍度指標） |
| `total_score` | OSS Insight 綜合評分 |
| `contributor_logins` | 貢獻者帳號（逗號分隔） |
| `collection_names` | 所屬分類（常為空） |

**Period 支援狀況（2026-06 測試）：**

| Period | 狀態 |
|--------|------|
| `past_24_hours` | ✅ 正常 |
| `past_7_days` | ❌ 500 error（upstream 壞掉） |
| `past_28_days` | ❌ 500 error |

**取得「本週」資料的方案：** 每天跑一次 `past_24_hours` 寫入累積 JSON，週報時合併去重即可。

**語言過濾：** 可加 `language=Python` / `language=TypeScript` 等參數，或 `language=All`。

**keyword 過濾：** OSS Insight API 本身沒有 keyword 過濾，需要在結果端自己 filter `description` 和 `repo_name`。

#### GitHub Search API（近似替代）

無法取得「本週新增星星數」，只有總星星數。可以用以下 query 作為近似：

```
GET https://api.github.com/search/repositories
  ?q=created:2026-05-30..2026-06-06+stars:>50+topic:ai
  &sort=stars&order=desc&per_page=20
```

邏輯：本週建立 + 已累積一定星數 = 快速竄升的新 repo。但精確度不如 OSS Insight。

不需要 API key（有 rate limit，加 token 可提高上限）。

#### GitHub Trending 頁面（週模式）

`https://github.com/trending?since=weekly` 有原生週 trending，但**沒有官方 API**，需爬 HTML。Horizon 沒有採用此方法。

#### Horizon ossinsight 設定參考

[Horizon](https://github.com/Thysrael/Horizon) 的 ossinsight scraper 設定格式：

```json
{
  "sources": {
    "ossinsight": {
      "enabled": true,
      "period": "past_24_hours",
      "languages": ["Python", "TypeScript", "All"],
      "keywords": ["llm", "agent", "claude", "ai"],
      "min_stars": 20,
      "max_items": 20
    }
  }
}
```

---

### Horizon 專案概覽

[Thysrael/Horizon](https://github.com/Thysrael/Horizon) — 支援多信息源的 AI 新聞雷達，可作為 `digest.ts` 的替代或補充。

**支援信息源：**

| 來源 | 需要什麼 | 說明 |
|------|---------|------|
| RSS | 無 | 任意 RSS feed |
| Hacker News | 無 | 含社群留言摘要 |
| Reddit | 無 | 指定 subreddits |
| Telegram | Bot token | 指定頻道 |
| Twitter/X | **Apify token** | 指定用戶帳號，免費 $5/月 |
| GitHub user_events | 無（token 提高限制） | 追蹤特定用戶動態 |
| GitHub repo_releases | 無 | 監聽 repo 新版本 |
| OSS Insight trending | 無 | GitHub trending repos |
| OpenBB | OpenBB SDK credentials | 財經新聞 |

**Twitter/X 設定範例：**
```json
{
  "sources": {
    "twitter": {
      "enabled": true,
      "users": ["karpathy", "sama", "ylecun"],
      "fetch_limit": 10,
      "fetch_reply_text": false
    }
  }
}
```
→ 需要 Apify token，免費額度約 20,000 tweets/月。

**GitHub user_events 設定範例：**
```json
{
  "sources": {
    "github": [
      { "type": "user_events", "username": "karpathy", "enabled": true },
      { "type": "repo_releases", "owner": "anthropics", "repo": "claude-code", "enabled": true }
    ]
  }
}
```

---

## 整合筆記強化的規劃

### 背景

Finance Digest 已有 `enhance-notes.sh` 流程：個別文章 → Claude 強化 → Obsidian 筆記 → 待閱讀清單 → Telegram 通知。

AI Digest 目前只輸出單一 `digest-YYYYMMDD.md`，不產生個別文章筆記，無法直接套用。

### 方向：只對高品質文章做筆記

Top 3（🥇🥈🥉）不可靠，常選到資安/meme/數學文章。建議改用以下篩選邏輯：

1. 分類為 `🤖 AI / ML` 或 `⚙️ 工程`
2. 標籤（`🏷️`）含 `ai`、`llm`、`agent`、`claude`、`architecture` 其中之一
3. 每天上限 3 篇

平均每天約 0–2 篇真正值得做筆記的文章，符合實際品質。

### 需要的工作

| 工作 | 說明 |
|------|------|
| 修改 `digest.ts` | 符合條件的文章另存個別 `.md`（frontmatter + 摘要） |
| 新 `enhance-ai-notes.sh` | 同 `enhance-notes.sh` 邏輯，但用 AI 技術筆記 prompt |
| AI 筆記格式規範 | TL;DR、技術原理、實際應用、與現有工作的連結 |
| 待閱讀清單路由 | 根據標籤插入對應分類（AI Agent 工程 / LLM 技術 / Claude Code） |

---

## 日誌

| 檔案 | 說明 |
|------|------|
| `~/.hn-daily-digest/digest.log` | 執行日誌 |
| `ai_digest/output/digest-YYYYMMDD.md` | 每日輸出 |

## Migration 備份

- `ai_digest/migration_backup/com.golem.daily-digest.plist.bak`
- `ai_digest/migration_backup/crontab.before.txt`
