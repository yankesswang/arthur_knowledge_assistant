---
name: web-scrape
description: URL → Playwright 真 Chrome 渲染（過 JS/反爬）→ 存 HTML/截圖 → defuddle 轉乾淨 markdown。適用 Booking.com、動態 SPA、WebFetch/defuddle 直接抓會失敗的網站。Trigger: /web-scrape <URL>
---

# /web-scrape

用 Playwright（優先走本機 Google Chrome channel，真瀏覽器指紋）渲染網頁，
存下完整 DOM HTML + metadata + 截圖，再用 defuddle 轉成乾淨 markdown。

**什麼時候用這個而不是 defuddle/WebFetch 直接抓：**
- JS 渲染的 SPA（內容不在原始 HTML 裡）
- 有反爬蟲的網站（Booking.com、Agoda、航空公司、電商）
- 需要等待、捲動、懶載入才出現的內容
- 需要頁面截圖

一般靜態文章頁 → 直接用 `defuddle parse <url> --md` 就好，不要動 Playwright。

## Usage

```
/web-scrape https://www.booking.com/hotel/...
/web-scrape <URL> 存到 xxx.md          # 指定輸出
/web-scrape <URL> 要截圖
```

## 工具位置

- 主腳本：`~/.claude/skills/web-scrape/scripts/scrape.py`
- 依賴：python3 + playwright（已裝）、Google Chrome（有裝就自動用）、defuddle CLI（/opt/homebrew/bin/defuddle）
- Temp work：`/tmp/web_scrape/<slug>/`

---

## What You Must Do When Invoked

### Step 1 — 準備

從使用者輸入取出 URL（可多個，逐一處理）。為每個 URL 建工作目錄：

```bash
export URL="<user URL>"
# slug 取 domain + path 前段，避免特殊字元
export WORK_DIR="/tmp/web_scrape/$(python3 -c "
from urllib.parse import urlparse; import re, sys
u = urlparse('$URL')
print(re.sub(r'[^A-Za-z0-9._-]', '_', (u.netloc + '_' + u.path.strip('/').replace('/', '_'))[:80]))
")"
mkdir -p "$WORK_DIR"
```

### Step 2 — Playwright 渲染

```bash
python3 ~/.claude/skills/web-scrape/scripts/scrape.py "$URL" --out "$WORK_DIR" --screenshot
```

腳本會輸出 meta JSON（title / final_url / status / og:*）。產物：
- `$WORK_DIR/page.html` — 渲染後完整 DOM
- `$WORK_DIR/meta.json`
- `$WORK_DIR/screenshot.png`（有 `--screenshot` 才有）

常用旗標（視情況加）：
| 情況 | 旗標 |
|---|---|
| 關鍵內容要等某元素出現（如價格表） | `--selector "CSS選擇器"` |
| 懶載入很多（長頁、圖片牆） | `--scroll 8`（預設 3，0 關閉） |
| 網站很慢 | `--timeout 90000` |
| headless 被擋（頁面只剩驗證牆） | `--headed`（會開視窗，最後手段） |
| 反爬站要連抓多頁/重試 | `--profile /tmp/web_scrape/.chrome_profile`（持久 cookie，challenge 過一次就重用；連續抓同站一律加） |
| 不想用本機 Chrome | `--no-chrome-channel` |

### Step 3 — 轉 markdown

```bash
defuddle parse "$WORK_DIR/page.html" --md -o "$WORK_DIR/content.md"
```

### Step 4 — 品質檢查與 fallback

1. 看 `content.md` 行數/內容。若太薄（< 20 行）或明顯漏掉主內容：
   - 先回 Step 2 加 `--selector` / `--scroll` 重抓；
   - defuddle 還是抽不好 → fallback：`python3 -c "import html2text,sys,pathlib; h=html2text.HTML2Text(); h.ignore_images=True; h.body_width=0; print(h.handle(pathlib.Path(sys.argv[1]).read_text()))" "$WORK_DIR/page.html" > "$WORK_DIR/content.md"`
   - 都不行 → 直接 grep/讀 `page.html` 找目標區塊。
2. `meta.json` 的 title 若是 "Just a moment"、"Access Denied"、驗證碼字樣 → 被擋了，改用 `--headed` 重跑一次，仍失敗就誠實告訴使用者這站擋 headless 抓取。

### Step 5 —（需要時）結構化輸出

使用者要「結構化結果 / JSON / 表格資料」時：

1. 先抽機器可讀的種子資料（schema.org ld+json + og meta + title）：
   ```bash
   python3 ~/.claude/skills/web-scrape/scripts/extract_structured.py "$WORK_DIR/page.html" > "$WORK_DIR/seed.json"
   ```
   很多網站（Booking、電商、新聞、食譜）都埋了 ld+json，欄位比正文可靠（評分、地址、價格區間、reviewCount）。
2. 讀 `seed.json` + `content.md`，由你（LLM）合併整理成 `$WORK_DIR/structured.json`：
   - 依內容型態設計 schema（飯店→ hotel/ratings/rooms/facilities/policies/location；商品→ product/price/specs/reviews；文章→ title/author/date/sections）。
   - 頂層固定帶 `source`（url、scraped_at、查詢參數）。
   - **抓不到的欄位填 `null` 並加 note 說明原因**（如價格被反爬擋掉），絕不編造數字。
3. 把 `structured.json` 路徑與重點摘要回覆給使用者；使用者指定存檔位置就複製過去。

### Step 6 — 交付

- 使用者只是要「看內容/摘要」→ 讀 `content.md`，整理重點回覆（保留價格、日期、數字等關鍵事實）。
- 使用者要存檔 → 把 `content.md` 複製/整理到指定路徑；沒指定路徑但明說要存 → 問清楚或存到目前專案下。
- 有截圖需求 → 告知 `screenshot.png` 路徑，必要時用 Read 打開確認內容。
- 回覆最後附上工作目錄路徑，方便使用者自己翻原始 HTML。

## Booking.com 專用筆記

- **搜尋結果頁**（searchresults.*.html）可完整抓到含價格的飯店清單，條件：
  1. URL 一定要帶 **未來的** `checkin`/`checkout` — 過期日期會被踢回首頁（`errorc_searchstring_not_found`），使用者貼的舊連結日期常已過期，先檢查並換成未來日期。
  2. 沒帶日期也能抓到飯店清單（名稱/評分/連結），但不會有價格。
  3. 用 `--selector '[data-testid="property-card"]' --scroll 10 --profile /tmp/web_scrape/.chrome_profile`。
- 搜尋結果頁的結構化解析用現成腳本（每卡片：名稱/連結/評分/評語數/星等/距離/房型/床型/價格/稅註）：
  ```bash
  python3 ~/.claude/skills/web-scrape/scripts/parse_booking_search.py "$WORK_DIR/page.html" -o "$WORK_DIR/search_results.json"
  ```
  一頁約 50 家（該市總數在 JSON `heading` 裡）。要更多頁加 `&offset=25/50/75...` 逐頁抓。
- **單一飯店頁**的房價由另外的 XHR 載入，headless 下常被擋（顯示「發生錯誤」）→ 房價改從搜尋結果頁拿，或誠實告知抓不到。
- 連續抓 Booking 若突然變空殼頁（title 變「官方網站」、搜尋框空白）= 被 challenge 洗掉參數，加 `--profile` 重試。

## 注意

- 只抓使用者明確給的 URL，不要自行大量爬站（單次多 URL 逐一處理即可）。
- 反爬站抓不到的欄位（價格等）明講即可，不要瞎猜數字。
