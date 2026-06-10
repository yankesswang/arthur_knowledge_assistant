#!/usr/bin/env python3
"""
AI 爬蟲工作流
從 Twitter / 知乎抓取 AI/LLM/Agent 相關內容，用 Gemini 篩選並分類，存入 Obsidian。

資料流：
  Twitter  → search → 完整推文 YAML → Gemini 篩選 + 摘要 → 存入 Obsidian
  知乎     → hot / search → 標題+URL → Gemini 選題 → download 全文 → Gemini 摘要 → 存入 Obsidian
"""

import subprocess
import json
import re
import sys
import logging
import tempfile
import time
from datetime import datetime
from pathlib import Path

import yaml  # pip install pyyaml

# ── 設定 ─────────────────────────────────────────────────────────────────────

VAULT_BASE = Path("/Users/yankesswang/Documents/arthurwang_DB/AI 爬蟲")
SCRIPT_DIR = Path(__file__).parent
LOG_FILE   = SCRIPT_DIR / "crawler.log"
TODAY      = datetime.now().strftime("%Y-%m-%d")

TWITTER_KEYWORDS = ["AI agent", "LLM", "大語言模型"]
ZHIHU_KEYWORDS   = ["AI Agent", "LLM 大模型"]
FETCH_LIMIT      = "15"
GEMINI_TIMEOUT   = "120"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ── 工具函式 ─────────────────────────────────────────────────────────────────

def run(args: list[str], timeout: int = 120, cwd: str | None = None) -> str:
    try:
        r = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, cwd=cwd
        )
        return _strip_update_notice(r.stdout)
    except subprocess.TimeoutExpired:
        log.warning(f"逾時：{' '.join(args[:3])}")
        return ""
    except Exception as e:
        log.warning(f"執行失敗：{e}")
        return ""


def _strip_update_notice(text: str) -> str:
    """移除 opencli 的 'Update available' 噪音。"""
    lines = text.splitlines()
    cleaned = [l for l in lines
               if "Update available" not in l and "npm install" not in l]
    return "\n".join(cleaned).strip()


def parse_yaml_list(text: str) -> list[dict]:
    """解析 opencli 輸出的 YAML list，容錯處理。"""
    try:
        result = yaml.safe_load(text)
        if isinstance(result, list):
            return result
    except yaml.YAMLError:
        pass
    return []


def gemini_ask(prompt: str) -> str:
    time.sleep(2)  # 避免連續呼叫搶 browser session
    return run(["opencli", "gemini", "ask", prompt, "--timeout", GEMINI_TIMEOUT, "--new"],
               timeout=150)


def extract_json(text: str):
    """從 Gemini 回覆中提取 JSON array 或 object，容忍前後綴噪音。"""
    # 找第一個 [ 或 { 作為 JSON 起點
    start = next((i for i, c in enumerate(text) if c in "[{"), None)
    if start is None:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text, start)
        return obj
    except json.JSONDecodeError:
        return None


def safe_filename(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*\n\r]', '', s).strip()[:60]


# ── Twitter ───────────────────────────────────────────────────────────────────

def fetch_twitter() -> list[dict]:
    """搜尋 Twitter，回傳每則推文 dict（含 author, text, url）。"""
    tweets = []
    for kw in TWITTER_KEYWORDS:
        log.info(f"  Twitter 搜尋：{kw}")
        raw = run(["opencli", "twitter", "search", kw, "--limit", FETCH_LIMIT])
        items = parse_yaml_list(raw)
        for item in items:
            item["_keyword"] = kw
            tweets.append(item)
    log.info(f"  Twitter 共抓到 {len(tweets)} 則推文")
    return tweets


def evaluate_and_summarize_tweets(tweets: list[dict]) -> list[dict]:
    """
    一次性送 Gemini 篩選 + 摘要所有推文。
    回傳有價值的筆記 list。
    """
    if not tweets:
        return []

    batch_text = "\n\n".join(
        f"[{i+1}] @{t.get('author','')} | {t.get('url','')}\n{t.get('text','')}"
        for i, t in enumerate(tweets)
    )

    prompt = f"""你是 Arthur 的 AI 知識篩選助理。以下是從 Twitter 搜尋到的 {len(tweets)} 則推文：

---
{batch_text[:5000]}
---

請篩選出有學習或研究價值的推文（AI 技術、LLM、Agent、或明確投資觀點）。
對每則有價值的推文輸出 JSON array，每個元素包含：

- title: 精簡繁體中文標題（15字以內）
- category: 只能是 "AI" 或 "投資" 或 "其他"
- summary: 3-5 條重點（繁體中文，每條以 "- " 開頭）
- key_insight: 最值得記錄的一個洞見（1句繁體中文）
- tags: 3-5 個標籤（繁體中文陣列）
- url: 原文連結（從上方複製）

規則：純轉發、廣告、沒有實質內容的推文直接跳過。
如果都沒有值得記錄的，回傳空陣列 []。
只輸出 JSON array，不要任何其他說明文字。"""

    log.info("    Gemini 篩選 Twitter 推文…")
    response = gemini_ask(prompt)
    items = extract_json(response)
    if not isinstance(items, list):
        log.warning(f"    JSON 解析失敗：{response[:150]}")
        return []

    log.info(f"    Twitter 篩選結果：{len(items)} 筆有價值")
    return items


# ── 知乎 ──────────────────────────────────────────────────────────────────────

def fetch_zhihu_titles() -> list[dict]:
    """抓取知乎熱榜 + 搜尋結果，回傳 {title, url} list。"""
    items = []

    log.info("  知乎 熱榜")
    raw = run(["opencli", "zhihu", "hot", "--limit", FETCH_LIMIT])
    items += parse_yaml_list(raw)

    for kw in ZHIHU_KEYWORDS:
        log.info(f"  知乎 搜尋：{kw}")
        raw = run(["opencli", "zhihu", "search", kw, "--limit", FETCH_LIMIT])
        results = parse_yaml_list(raw)
        for r in results:
            r["_keyword"] = kw
        items += results

    log.info(f"  知乎 共 {len(items)} 個條目（含標題）")
    return items


def filter_zhihu_titles(items: list[dict]) -> list[dict]:
    """
    用 Gemini 從標題清單中選出值得下載的 AI / 投資相關條目。
    每批最多 15 筆，避免 Gemini timeout。
    回傳 [{title, url, category}] 。
    """
    if not items:
        return []

    BATCH = 15
    selected: list[dict] = []

    for batch_start in range(0, len(items), BATCH):
        batch = items[batch_start: batch_start + BATCH]
        title_list = "\n".join(
            f"[{i+1}] {it.get('title','')} | {it.get('url','')}"
            for i, it in enumerate(batch)
        )

        prompt = f"""以下是知乎的標題清單（{len(batch)} 個）：

{title_list}

請從中選出與 AI、LLM、Agent、量化投資、科技產業 相關、且有實質學習價值的條目。
輸出 JSON array，每個元素包含：

- title: 原文標題（直接複製）
- url: 原文連結（直接複製）
- category: 只能是 "AI" 或 "投資" 或 "其他"

規則：生活娛樂、社會新聞等與主題無關的直接跳過。
如果都沒有，回傳空陣列 []。
只輸出 JSON array，不要任何其他說明。"""

        log.info(f"    Gemini 篩選知乎標題（第 {batch_start//BATCH+1} 批，{len(batch)} 筆）…")
        response = gemini_ask(prompt)

        if not response or "NO RESPONSE" in response:
            log.warning("    Gemini 無回應，跳過此批")
            continue

        result = extract_json(response)
        if not isinstance(result, list):
            log.warning(f"    JSON 解析失敗：{response[:150]}")
            continue

        selected.extend(result)

    log.info(f"    知乎共選中 {len(selected)} 篇值得下載")
    return selected


def download_zhihu_article(url: str) -> str:
    """下載知乎文章全文，回傳 Markdown 字串。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        run(["opencli", "zhihu", "download", "--url", url], cwd=tmpdir)
        # 找 tmp dir 內所有 .md 檔
        md_files = list(Path(tmpdir).rglob("*.md"))
        if md_files:
            return md_files[0].read_text(encoding="utf-8", errors="replace")
        log.warning(f"    找不到下載的 md 檔：{url}")
        return ""


def summarize_zhihu_batch(articles: list[dict]) -> list[dict]:
    """
    批次摘要多篇知乎文章（每批 3 篇），減少 Gemini session 呼叫次數。
    articles: [{title, url, content}]
    回傳: [{title, url, category, summary, key_insight, tags}]
    """
    BATCH_SIZE = 3
    results: list[dict] = []

    for batch_start in range(0, len(articles), BATCH_SIZE):
        batch = articles[batch_start: batch_start + BATCH_SIZE]
        articles_text = "\n\n---\n\n".join(
            f"【文章{j+1}】\n標題：{a['title']}\n\n{a['content'][:1500]}"
            for j, a in enumerate(batch)
        )

        prompt = f"""你是 Arthur 的知識助理。請為以下 {len(batch)} 篇文章各自產生摘要，輸出 JSON array。

{articles_text}

每篇輸出一個 JSON 物件，整體為 JSON array，欄位如下：
- article_index: 文章編號（1, 2, 3...）
- title: 精簡繁體中文標題（20字以內）
- category: 只能是 "AI" 或 "投資" 或 "其他"
- summary: 3-5 條重點（繁體中文，每條以 "- " 開頭，用 \\n 分隔）
- key_insight: 最值得記錄的一個洞見（1句）
- tags: 3-5 個標籤（繁體中文陣列）

只輸出 JSON array，不要其他說明文字。"""

        log.info(f"    Gemini 批次摘要（第 {batch_start//BATCH_SIZE+1} 批，{len(batch)} 篇）…")
        response = gemini_ask(prompt)

        if not response or "NO RESPONSE" in response:
            log.warning("    Gemini 無回應，跳過此批")
            continue

        batch_results = extract_json(response)
        if not isinstance(batch_results, list):
            log.warning(f"    JSON 解析失敗：{response[:150]}")
            continue

        for r in batch_results:
            idx = r.get("article_index", 1) - 1
            if 0 <= idx < len(batch):
                r["url"] = batch[idx]["url"]
            results.append(r)

    return results


# ── 存檔 ─────────────────────────────────────────────────────────────────────

def save_note(metadata: dict, source: str, url: str = "") -> Path:
    category = metadata.get("category", "其他")
    if category not in ("AI", "投資", "其他"):
        category = "其他"

    title   = metadata.get("title", "未命名")
    raw_sum = metadata.get("summary", "")
    summary = "\n".join(raw_sum) if isinstance(raw_sum, list) else raw_sum
    insight = metadata.get("key_insight", "")
    tags    = metadata.get("tags", [])

    folder = VAULT_BASE / source / category
    folder.mkdir(parents=True, exist_ok=True)

    filename = f"{TODAY} [{source}] {safe_filename(title)}.md"
    filepath = folder / filename

    tag_yaml = "\n".join(f"  - {t}" for t in tags)
    note = f"""---
date: {TODAY}
source: {source}
category: {category}
url: "{url}"
tags:
{tag_yaml}
---

# {title}

## 重點摘要

{summary}

## 關鍵洞見

> {insight}
"""
    filepath.write_text(note, encoding="utf-8")
    return filepath


# ── 主程式 ────────────────────────────────────────────────────────────────────

def main():
    log.info(f"{'='*55}")
    log.info(f"AI 爬蟲工作流  {TODAY}")
    log.info(f"{'='*55}")

    total_saved = 0

    # ── Twitter ──────────────────────────────────────────
    log.info("\n▶ Twitter")
    tweets = fetch_twitter()
    twitter_notes = evaluate_and_summarize_tweets(tweets)
    for note in twitter_notes:
        try:
            fp = save_note(note, "Twitter", note.get("url", ""))
            log.info(f"  ✅  {fp.relative_to(VAULT_BASE)}")
            total_saved += 1
        except Exception as e:
            log.error(f"  儲存失敗：{e}")

    # ── 知乎 ──────────────────────────────────────────────
    log.info("\n▶ 知乎")
    zhihu_items = fetch_zhihu_titles()
    selected    = filter_zhihu_titles(zhihu_items)

    # 先下載全部文章，再批次送 Gemini（減少 session 呼叫次數）
    articles: list[dict] = []
    for item in selected:
        url   = item.get("url", "")
        title = item.get("title", "")
        log.info(f"  下載：{title[:35]}…")
        content = download_zhihu_article(url)
        if content:
            articles.append({
                "title":    title,
                "url":      url,
                "content":  content,
                "category": item.get("category", "其他"),
            })

    log.info(f"  共下載 {len(articles)} 篇，送 Gemini 批次摘要…")
    summaries = summarize_zhihu_batch(articles)

    for meta in summaries:
        if not meta.get("category"):
            meta["category"] = "其他"
        try:
            fp = save_note(meta, "知乎", meta.get("url", ""))
            log.info(f"  ✅  {fp.relative_to(VAULT_BASE)}")
            total_saved += 1
        except Exception as e:
            log.error(f"  儲存失敗：{e}")

    log.info(f"\n{'='*55}")
    log.info(f"完成！共儲存 {total_saved} 篇筆記 → {VAULT_BASE}")
    log.info(f"{'='*55}\n")


if __name__ == "__main__":
    main()
