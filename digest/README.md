# Digest 系統總覽

Arthur 的三套自動化每日摘要系統，統一存放在此目錄。

```
digest/
├── ai/       AI 科技日報      — 每天 07:03 自動
├── stock/    美股財經日報      — 每天 08:00 自動
└── finance/  Finance Substack — 手動觸發
```

---

## ai/ — AI 科技日報

**定位**：從 90 個技術部落格 RSS 精選當日最值得讀的 AI / 工程文章。

### 架構

```
LaunchAgent (07:03)
  → ~/Library/Scripts/ai-digest.sh
    → bun digest/ai/scripts/digest.ts   ← Gemini 2.5 Flash 精選
      → ~/Library/ai-digest-output/digest-YYYYMMDD.md
        → Obsidian: AI Knowledge/Digest/
        → Telegram 通知（Top 3 + 統計）
```

### 關鍵設定

| 項目 | 值 |
|------|-----|
| 觸發時間 | 每天 **07:03** |
| LaunchAgent | `~/Library/LaunchAgents/com.golem.daily-digest.plist` |
| 執行腳本 | `~/Library/Scripts/ai-digest.sh` |
| AI 模型 | Gemini 2.5 Flash |
| 來源數 | 90 個技術 RSS |
| 輸出 | Obsidian `AI Knowledge/Digest/digest-YYYYMMDD.md` |
| Log | `~/.hn-daily-digest/digest.log` |

### 手動執行

```bash
launchctl start com.golem.daily-digest
# 或直接執行 script
bash ~/Library/Scripts/ai-digest.sh
```

---

## stock/ — 美股財經日報

**定位**：從 50 個財經 RSS + Reddit + Finnhub 即時數據，生成個人化美股日報，對照持倉與 Watchlist。

### 架構

```
LaunchAgent (08:00)
  → ~/Library/Scripts/stock-digest.sh
    → digest/stock/horizon (uv run horizon)
      ├── 抓取：RSS (50個) + Reddit (6個)
      ├── AI 評分：GPT-4o-mini（一般 ≥6.0，持倉 ticker ≥4.0）
      ├── Finnhub：即時股價 + 財報預告 + 分析師評級
      └── 生成 3 個 md：
            📊 今日市場報告.md
            📋 個股與產業.md
            📊 Portfolio.md
        → Obsidian: 投資/Stock Digest/YYYY-MM-DD/
        → Telegram 通知（一句話 + Macro + 財報 + 持倉漲跌 + 行動清單）
```

### 關鍵設定

| 項目 | 值 |
|------|-----|
| 觸發時間 | 每天 **08:00** |
| LaunchAgent | `~/Library/LaunchAgents/com.arthurwang.stock-digest.plist` |
| 執行腳本 | `~/Library/Scripts/stock-digest.sh` |
| AI 模型 | GPT-4o-mini |
| 財務數據 | Finnhub（60 req/min）+ Alpha Vantage（25 req/day）|
| 持倉來源 | `stock-radar/backend/stock_valuation.db` |
| 輸出 | Obsidian `投資/Stock Digest/YYYY-MM-DD/` |
| Log | `~/Library/Logs/stock-digest/YYYY-MM-DD.log` |

### 手動執行

```bash
launchctl start com.arthurwang.stock-digest
# 或直接執行
bash ~/Library/Scripts/stock-digest.sh
# 或指定時間窗
cd digest/stock/horizon && uv run horizon --hours 48
```

### API Keys（存於 digest/stock/horizon/.env）

```
OPENAI_API_KEY=...
FINNHUB_API_KEY=...
ALPHAVANTAGE_API_KEY=...  # 25 req/day，需節省使用
GOOGLE_API_KEY=...
```

---

## finance/ — Finance Substack Digest

**定位**：爬取訂閱的 Finance Substack（FOMO SOC、M報、Vicky Ho 等），整理成 Obsidian 月度筆記。

### 架構

```
手動執行
  → digest/finance/scripts/digest_substack_auto.sh
    → bun finance/scripts/digest-substack.ts   ← Gemini 整理
      → Obsidian: Finance Digest/YYYY-MM-DD digest.md
      → Telegram 通知
```

### 關鍵設定

| 項目 | 值 |
|------|-----|
| 觸發方式 | **手動**（不定期，通常每週或每月） |
| AI 模型 | Gemini |
| 輸出 | Obsidian `Finance Digest/YYYY-MM-DD digest.md` |
| Log | `~/.yt-digest/substack-digest.log` |

### 手動執行

```bash
bash digest/finance/scripts/digest_substack_auto.sh
```

---

## 共用設定

### Telegram

三套系統共用同一個 Telegram Bot，token 存在：

```
/Users/yankesswang/Desktop/Projects/Arthur_App/.env
  TELEGRAM_TOKEN=...
  ADMIN_ID=...
```

### Obsidian Vault

```
/Users/yankesswang/Documents/arthurwang_DB/
  ├── AI Knowledge/Digest/          ← ai/ 輸出
  ├── 投資/Stock Digest/YYYY-MM-DD/ ← stock/ 輸出
  └── Finance Digest/               ← finance/ 輸出
```

### LaunchAgent 管理

```bash
# 查看狀態
launchctl list | grep digest

# 重新載入
launchctl unload ~/Library/LaunchAgents/com.golem.daily-digest.plist
launchctl load   ~/Library/LaunchAgents/com.golem.daily-digest.plist

launchctl unload ~/Library/LaunchAgents/com.arthurwang.stock-digest.plist
launchctl load   ~/Library/LaunchAgents/com.arthurwang.stock-digest.plist
```

> ⚠️ LaunchAgent 需要 macOS 登入狀態才觸發。若常關機，考慮改用雲端排程。

---

## 常見問題

**Q: Telegram 沒收到通知？**
檢查 log 最後幾行，確認 `TELEGRAM_TOKEN` / `ADMIN_ID` 是否讀到。

**Q: Stock Digest 的 Alpha Vantage 額度用完？**
免費 25 req/day，次日自動恢復。當日 sentiment score 欄位會顯示「額度耗盡」。

**Q: AI Digest 的文章數變少？**
RSS 來源中有些部落格更新頻率低，`--hours 48` 可拉長時間窗。

**Q: Stock Digest 某支持倉沒出現在個股動態？**
表示今天沒有任何文章 match 到該 ticker（Google News RSS 無新文章），持倉總表仍會顯示 Finnhub 即時報價。
