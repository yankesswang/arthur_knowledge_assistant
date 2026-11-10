# Stock Digest（美股財經日報）完整流程文件

> 本文件由程式碼還原，補上官方 `horizon/README_zh.md`、`docs/scoring.md` 未涵蓋的**美股客製化**部分（持倉對照、Finnhub 即時數據、市場/Portfolio 報告、繁中分類）。
>
> 底層引擎是開源專案 **Horizon**（`digest/stock/horizon/`），本流程在其 pipeline 的「總結生成」階段插入大量客製邏輯。

---

## 1. 一句話定位

**週一～五 07:00**（近 24h 日報）＋**週六 10:00**（整周復盤，回看 7 天）從 **50 個 RSS + 6 個 Reddit** 抓內容 → GPT-4o-mini 評分過濾 → 對照 `stock-radar` 持倉/watchlist + Finnhub 即時數據 → 生成三份繁中報告，rsync 到 Obsidian。週日不跑。

---

## 2. 觸發與排程

```
LaunchAgent 週一～五 07:00              LaunchAgent 週六 10:00
  com.arthurwang.stock-digest.plist      com.arthurwang.stock-digest-weekly.plist
    → ~/Library/Scripts/stock-digest.sh    → ~/Library/Scripts/stock-digest.sh weekly
        （MODE=daily，無參數）                  （MODE=weekly，第 1 參數 = "weekly"）
        → ensure_stockradar_snapshot      ← 先確保 stock-radar 當天持倉快照存在（見 §9）
        → uv run horizon [$HORIZON_ARGS]  ← daily 預設 24h；weekly 帶 --hours 168（回看 7 天）
            → HorizonOrchestrator.run()
        → cp（5 次重試）data/summaries/<最新>/ → Obsidian「Digest/stock/<日期>/」
        → telegram_send（從報告萃取重點推播，weekly 標題為「🗓️ 整周復盤 — 週一~週五」，見 §7）
```

> **為什麼週六 10:00 跑整周復盤？** 週五美股收盤 = 週六 04:00（台），盤後/財報數據要更晚才齊。
> 週六 10:00 跑、回看 168h，確保**週五當天**的盤後動態完整納入——這是日報（週一～五 07:00）涵蓋不到的。
> 週日不跑（無新交易日）。

> ⚠️ **真正在跑的是 `~/Library/Scripts/stock-digest.sh`，不在這個 repo 裡。**
> repo 內的 `horizon/run_daily.sh` 與 `digest/stock/scripts/stock-digest-auto.sh` 是**過時副本**
> （同步到舊路徑 `投資/Stock Digest/`、無 Telegram），實際已停用。詳見 §8。

| 項目 | 值 |
|------|-----|
| 觸發時間 | 日報 **週一～五 07:00**；整周復盤 **週六 10:00**（週日不跑） |
| LaunchAgent（日報） | `~/Library/LaunchAgents/com.arthurwang.stock-digest.plist`（`StartCalendarInterval` array：Weekday 1–5 @ 07:00） |
| LaunchAgent（週報） | `~/Library/LaunchAgents/com.arthurwang.stock-digest-weekly.plist`（Weekday 6 @ 10:00，傳第 1 參數 `weekly`） |
| **實際入口腳本** | **`~/Library/Scripts/stock-digest.sh [weekly]`**（repo 外，含 Telegram + sync；無參數=daily 24h，`weekly`=回看 168h） |
| WorkingDirectory | `…/Desktop/Projects/Arthur_App/…/horizon`（Desktop 是 symlink → repo） |
| 引擎指令 | `uv run horizon`（= `horizon/src/main.py`，預設 24h 視窗） |
| 核心管線 | `horizon/src/orchestrator.py` → `HorizonOrchestrator.run()` |
| AI 模型 | GPT-4o-mini（`data/config.json` → `ai.model`） |
| 過濾門檻 | 一般 ≥ **6.0**；個股 ticker feed ≥ **4.0** |
| 輸出語言 | 繁體中文（`zh-tw`） |
| 同步目的地 | `~/Documents/arthurwang_DB/Digest/stock/<日期>/` |
| Telegram | `~/.config/digest/.env` 或 repo `.env` 的 `TELEGRAM_TOKEN` / `ADMIN_ID` |
| Log | `~/Library/Logs/stock-digest/YYYY-MM-DD.log`（+ `launchd-std{out,err}.log`） |

手動執行：

```bash
launchctl start com.arthurwang.stock-digest          # 日報（24h）
launchctl start com.arthurwang.stock-digest-weekly   # 整周復盤（168h）
# 或直接跑腳本
~/Library/Scripts/stock-digest.sh                    # daily
~/Library/Scripts/stock-digest.sh weekly             # weekly（整周復盤）
# 或只跑引擎
cd digest/stock/horizon && uv run horizon            # 預設 24h
cd digest/stock/horizon && uv run horizon --hours 168 # 整周復盤視窗
```

---

## 3. 資料源：一層一層的架構

資料源全部定義在 [`horizon/data/config.json`](horizon/data/config.json) 的 `sources` 區塊，由 `orchestrator.fetch_all_sources()` 並發抓取。**目前實際啟用的只有 RSS + Reddit 兩大類**（hackernews / telegram / twitter / openbb / ossinsight / github 皆 disabled）。

```
資料源 (sources)
│
├── 📡 RSS（50 個 feed，scrapers/rss.py）
│   │
│   ├── [macro-official] 總經官方  ……………… 2 個
│   │     ├── Federal Reserve（press_all）
│   │     └── Fed Speeches（speeches）
│   │
│   ├── [semiconductor] 半導體產業  …………… 2 個
│   │     ├── The Next Platform
│   │     └── DigiTimes
│   │
│   ├── [valuation] 估值方法  ………………………… 1 個
│   │     └── Damodaran Blog
│   │
│   ├── [market-view] 市場觀點  …………………… 1 個
│   │     └── A Wealth of Common Sense
│   │
│   ├── [market-charts] 市場圖表  ……………… 1 個
│   │     └── Charlie Bilello
│   │
│   ├── [ir-releases] 公司 IR  ……………………… 1 個
│   │     └── AMD IR
│   │
│   └── [stock-news] 個股新聞（Google News RSS）… 42 個
│         每檔股票一個 feed，帶 keywords 過濾、max_items=5：
│         NVDA AMD AVGO TSM AAPL MSFT GOOGL AMZN META TSLA
│         PLTR ARM SMCI VRT ANET MU INTC LLY RDW IBM
│         VIAV SWKS NVTS OUST NVDL PDYN BKSY DJT WOLF ACMR
│         CRM ASX LTRX TXN FCEL SOFI QCOM SMH SE JBL
│         SANM VT
│
├── 💬 Reddit（6 個 subreddit，scrapers/reddit.py）
│         每個 sub 設獨立的 sort / min_score / fetch_limit：
│     ├── r/stocks            hot  min_score=100  limit=15
│     ├── r/investing         hot  min_score=100  limit=15
│     ├── r/options           hot  min_score=50   limit=10
│     ├── r/thetagang         hot  min_score=30   limit=10
│     ├── r/SecurityAnalysis  hot  min_score=20   limit=10  (time=week)
│     └── r/wallstreetbets    hot  min_score=500  limit=10
│         （fetch_comments=3：每篇抓前 3 則留言）
│
└── 🚫 未啟用：hackernews / telegram / twitter / openbb / ossinsight / github
      （程式碼支援，config 中 enabled=false）

────────────────────────────────────────────────
個人化資料層（非 sources，總結階段才讀取）
│
├── 🗄️ stock-radar DB（sqlite，持倉/watchlist 真實資料）
│     stock-radar/backend/stock_valuation.db
│     讀取的表：holding_snapshots / holdings / mimi_watchlist
│     提供：我的持倉（Main / Mom）、watchlist ticker、thesis
│
└── 📡 Finnhub API（即時行情，summarizer._load_finnhub_context）
      ├── /quote               即時股價 + 當日高低 + 漲跌幅
      ├── /calendar/earnings   未來 30 天財報日曆（濾持倉）
      └── /stock/recommendation 分析師 Buy/Hold/Sell 評級
          （key tickers：NVDA AVGO TSM AMD ARM AAPL META MSFT）
```

---

## 4. Pipeline 階段（`orchestrator.run()`）

| # | 階段 | 函式 / 位置 | 說明 |
|---|------|------------|------|
| 1 | **抓取** | `fetch_all_sources()` `orchestrator.py:293` | 並發抓所有啟用來源，產出 `ContentItem` list |
| 2 | **跨源去重** | `merge_cross_source_duplicates()` `:403` | 同 URL（正規化後）合併，保留內容最豐富的，併入其他來源的留言/metadata |
| 3 | **AI 評分** | `_analyze_content()` → `ContentAnalyzer` `:600` | GPT-4o-mini 給每篇 0-10 分 + reason + summary + tags（批次、失敗重試 3 次） |
| 4 | **門檻過濾** | inline `_passes()` `:96` | 一般 ≥ `ai_score_threshold`(6.0)；**個股 ticker feed（feed 名以 " News" 結尾）放寬到 ≥4.0**，確保持倉冷門新聞進得來 |
| 5 | **語意去重** | `merge_topic_duplicates()` `:459` | AI 判斷同主題，只留分數最高者，併入其餘留言 |
| 5.6 | Twitter 留言展開 | `_expand_twitter_discussion()` `:532` | 僅當 twitter 啟用（目前停用） |
| 6 | **內容 enrich** | `_enrich_important_items()` → `ContentEnricher` `:582` | 第二次 AI pass：抽概念 → DuckDuckGo 查背景 → 補 whats_new / why_it_matters / background |
| 7 | **生成報告**（zh-tw 客製） | `:146`–`:200` | 見下節，本流程的精華 |
| 8 | **分發** | `:198`–`:255` | 寫 `data/summaries/`、複製 GitHub Pages、Email、Webhook（Telegram 若有設定） |

### 7. 報告生成細節（`DailySummarizer`，僅 zh-tw）

`orchestrator.py:152` 起，只有 `zh-tw` 語言會跑客製報告：

1. **載入持倉/watchlist** — `_load_watchlist(db_path)` 從 `stock_valuation.db` 讀 `holding_snapshots` / `mimi_watchlist`
2. **載入 Finnhub 即時數據** — `_load_finnhub_context(tickers)`：即時股價、30 天內財報、分析師評級 → 併入 `watchlist_ctx`
3. **分類報告** — `save_category_folder()` 依 `📊 Macro / 總經`、半導體、選擇權/情緒 等分類整理 → 產出 `📋 個股與產業.md`
4. **市場報告** — `generate_market_report()` 綜合各分類 → 產出 `📊 今日市場報告.md`
5. **Portfolio 報告** — `generate_portfolio_report()` 用 Finnhub quotes + 持倉表 → 產出 `📊 Portfolio.md`

---

## 5. 輸出結構

每天在 `horizon/data/summaries/<YYYY-MM-DD>/` 產出一個資料夾：

| 檔案 | 生成函式 | 內容 |
|------|---------|------|
| `📊 今日市場報告.md` | `generate_market_report` | 今日一句話 + Macro 完整分析 + 財報表 + 半導體摘要 + 持倉更新（Main/Mom）+ 行動清單 |
| `📋 個股與產業.md` | `save_category_folder` | 各分類個股與產業動態（含被過濾掉的低分項摘要） |
| `📊 Portfolio.md` | `generate_portfolio_report` | 持倉總表 + 每檔個股深度動態（含 Finnhub 即時報價） |

另外 `data/summaries/horizon-<日期>-zh-tw.md` 是 Horizon 原生的單檔日報（GitHub Pages 用）。

**同步到 Obsidian**（實際運行腳本 `~/Library/Scripts/stock-digest.sh`）：

```bash
# horizon 用 UTC 命名，取 summaries/ 下最新日期資料夾
# 逐檔 cp -f，失敗重試 5 次（launchd 下 Python/Node 寫 ~/Documents 會機率性 EDEADLK）
for f in data/summaries/<最新>/*; do
  cp -f "$f" ~/Documents/arthurwang_DB/Digest/stock/<日期>/   # 重試保底
done
```

> 注意目的地是 **`Digest/stock/`**，不是舊文件寫的 `投資/Stock Digest/`。
> repo 內過時腳本仍用 `rsync … 投資/Stock Digest/`，已不是現行行為。

---

## 6. 設定與金鑰

| 設定檔 | 路徑 | 內容 |
|--------|------|------|
| 來源/模型/門檻 | `horizon/data/config.json` | `sources` / `ai` / `filtering` |
| API 金鑰 | `horizon/.env` | `OPENAI_API_KEY`、`FINNHUB_API_KEY`、`ALPHAVANTAGE_API_KEY`、`GOOGLE_API_KEY` |

`filtering`：`{ "ai_score_threshold": 6.0, "time_window_hours": 24 }`

財務數據限制：Finnhub 60 req/min；Alpha Vantage 25 req/day（需節省使用）。

---

## 7. Telegram 通知

**不是**透過 Horizon 的 `config.json` webhook（那欄目前為空 `{}`），而是由 wrapper 腳本
`~/Library/Scripts/stock-digest.sh` 在 pipeline 跑完後，用 `awk` / `grep` 從報告萃取重點、
組訊息、`curl` 打 `api.telegram.org/.../sendMessage`：

- 憑證：`~/.config/digest/.env`（或退回 repo `.env`）的 `TELEGRAM_TOKEN` / `ADMIN_ID`
- 訊息分段（從 `📊 今日市場報告.md` + `📊 Portfolio.md` 萃取）：
  1. `▌今日一句話`
  2. `📊 Macro`（前 6 行）
  3. `💰 財報摘要`（表格前 5 行）
  4. `🤖 AI / 半導體`（前 5 行）
  5. `📉 持倉今日漲跌`（從 Portfolio 總表撈，按漲跌排序，前 12 檔）
  6. `💡 行動清單`（前 6 行）
  7. token 使用量
- 失敗時（pipeline 非 0）也發一則 `❌ Stock Digest 失敗` 並附 log 路徑。

---

## 8. ⚠️ 已知問題 / 注意事項

1. **「Desktop vs Projects 路徑不一致」其實不是問題 ✅**
   - `/Users/yankesswang/Desktop/Projects/Arthur_App` 是 **symlink → `/Users/yankesswang/Projects/Arthur_App`**。
   - 所有寫死 `Desktop/...` 的路徑（腳本、`orchestrator.py:156` 的 `db_path`）都正確解析到本 repo，**無需修改**。

2. **腳本版控（已整理 ✅）**
   - 實際運行腳本已納入版控：`digest/stock/scripts/stock-digest.sh`（與 `~/Library/Scripts/stock-digest.sh` 內容一致）。
   - 三支過時副本已刪除：`horizon/run_daily.sh`、`digest/stock/scripts/stock-digest-auto.sh`、`financial_digest/scripts/stock/stock-digest-auto.sh`。
   - **部署流程**：改腳本時編輯 repo 版 → 複製覆蓋運行版：
     ```bash
     cp digest/stock/scripts/stock-digest.sh ~/Library/Scripts/stock-digest.sh
     ```
     （LaunchAgent 載入的是 `~/Library/Scripts/` 那份，repo 版為 source of truth）

3. **持倉快照 race（已處理 ✅）**
   - digest 讀 `portfolio_snapshots` 的 `MAX(snapshot_date)`；過去與 stock-radar 的 `stocks-daily-report` 同在 08:00 跑、無依賴順序，偶爾會讀到前一天快照。
   - 現行腳本開頭新增 `ensure_stockradar_snapshot()`：先 health check `:6000` → 查 DB 是否已有當天快照 → 沒有就 `POST /api/scheduler/report/run` 並輪詢（每 3s，最多 ~180s）直到當天快照寫入，才開始跑 digest。
   - backend 未啟動或逾時 → 記 log 並 fallback 用既有最新快照，digest 不中斷。
   - 即時報價仍走 Finnhub（與快照無關）。

4. **launchd 下寫 ~/Documents 會 EDEADLK**
   - log 出現 `[Errno 11] Resource deadlock avoided`（Python `shutil` 寫 Obsidian 時）。
   - 現行腳本已改用 `cp -f` + 5 次重試規避；舊的 `shutil`/`rsync` 版會 `sync 失敗`。
   - 若日後改寫同步邏輯，避免在 launchd context 用 Python/Node 直接寫 `~/Documents`。

5. **`📊 今日市場報告.md` 自 2026-08-18 起沒再產出過 ⚠️ 未修**
   - `data/summaries/` 原始輸出與 Obsidian 兩邊都只剩 `📊 Portfolio.md` + `📋 個股與產業.md`。
   - `orchestrator.py:251` 的 `if market_report:` 沒過 → 檔案沒寫。`generate_market_report`
     外面沒有 try/except，所以是它回了空字串；它唯一的空返回是 `summarizer.py:432` 的
     `if not items and not category_reports`。要查的是 `save_category_folder` 的回傳值
     （檔案有寫出來，不代表 dict 有回內容）。
   - 連帶影響：Telegram 推播的「今日一句話 / Macro / 財報摘要 / 行動清單」全是從這份報告
     萃取的，等於已經空了兩週。

6. **Obsidian 目的地已遷移**
   - 新：`~/Documents/arthurwang_DB/Digest/stock/<日期>/`（最新持續更新）
   - 舊：`~/Documents/arthurwang_DB/投資/Stock Digest/<日期>/`（停在 2026-06-10，過時腳本殘留）

---

## 9. 關鍵檔案速查

| 角色 | 檔案 |
|------|------|
| **運行腳本（版控）** | **`digest/stock/scripts/stock-digest.sh`** = 部署到 `~/Library/Scripts/stock-digest.sh`（含 Telegram + cp 同步） |
| LaunchAgent | `~/Library/LaunchAgents/com.arthurwang.stock-digest.plist` |
| CLI 入口 | `horizon/src/main.py` |
| **核心管線** | `horizon/src/orchestrator.py`（`HorizonOrchestrator.run`） |
| 報告生成 | `horizon/src/ai/summarizer.py`（market/portfolio/category + Finnhub） |
| 評分 | `horizon/src/ai/analyzer.py` |
| Enrich | `horizon/src/ai/enricher.py` |
| 來源抓取 | `horizon/src/scrapers/{rss,reddit}.py` |
| 通知 | `horizon/src/services/webhook.py`（Telegram/Feishu/Slack 等） |
| 來源/模型設定 | `horizon/data/config.json` |
| 持倉資料 | `stock-radar/backend/stock_valuation.db`（`holding_snapshots` / `mimi_watchlist`） |
