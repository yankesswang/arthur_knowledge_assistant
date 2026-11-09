#!/usr/bin/env python3
"""Playwright web scraper — renders JS-heavy / anti-bot pages and saves the full HTML.

Output files in --out dir:
  page.html       rendered DOM (after JS)
  meta.json       title / final URL / status / og metadata
  screenshot.png  full-page screenshot (only with --screenshot)

Typical pipeline (done by the skill, not this script):
  scrape.py URL --out DIR  &&  defuddle parse DIR/page.html --md
"""
import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = window.chrome || { runtime: {} };
Object.defineProperty(navigator, 'languages', {get: () => ['zh-TW', 'zh', 'en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
"""


def autoscroll(page, rounds: int, pause_ms: int = 600):
    """Scroll to bottom in steps to trigger lazy-loaded content."""
    for _ in range(rounds):
        page.evaluate("window.scrollBy(0, window.innerHeight * 0.9)")
        page.wait_for_timeout(pause_ms)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(300)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("url")
    ap.add_argument("--out", default=".", help="output directory (default: cwd)")
    ap.add_argument("--timeout", type=int, default=45000, help="nav timeout ms")
    ap.add_argument("--selector", help="CSS selector to wait for before capture")
    ap.add_argument("--scroll", type=int, default=3,
                    help="autoscroll rounds for lazy content (0 = off, default 3)")
    ap.add_argument("--screenshot", action="store_true", help="save full-page screenshot")
    ap.add_argument("--headed", action="store_true",
                    help="visible browser window (last resort for hard bot walls)")
    ap.add_argument("--no-chrome-channel", action="store_true",
                    help="use bundled Chromium instead of installed Google Chrome")
    ap.add_argument("--locale", default="zh-TW")
    ap.add_argument("--timezone", default="Asia/Taipei")
    ap.add_argument("--extra-wait", type=int, default=1500,
                    help="extra settle ms after load (default 1500)")
    ap.add_argument("--profile",
                    help="persistent browser profile dir — keeps cookies "
                         "across runs so an anti-bot challenge passed once "
                         "is reused (recommended for booking/agoda etc.)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        headless = not args.headed
        browser = None
        ctx = None
        channels = [None] if args.no_chrome_channel else ["chrome", None]

        if args.profile:
            for ch in channels:
                try:
                    ctx = p.chromium.launch_persistent_context(
                        args.profile,
                        headless=headless,
                        channel=ch,
                        user_agent=UA,
                        locale=args.locale,
                        timezone_id=args.timezone,
                        viewport={"width": 1440, "height": 900},
                        device_scale_factor=2,
                    )
                    break
                except Exception as e:
                    if ch is None:
                        raise
                    print(f"WARN: chrome channel unavailable ({e}), "
                          "falling back to bundled Chromium", file=sys.stderr)
        else:
            for ch in channels:
                try:
                    browser = p.chromium.launch(headless=headless, channel=ch)
                    break
                except Exception as e:
                    if ch is None:
                        raise
                    print(f"WARN: chrome channel unavailable ({e}), "
                          "falling back to bundled Chromium", file=sys.stderr)
            assert browser is not None
            ctx = browser.new_context(
                user_agent=UA,
                locale=args.locale,
                timezone_id=args.timezone,
                viewport={"width": 1440, "height": 900},
                device_scale_factor=2,
            )

        assert ctx is not None
        ctx.add_init_script(STEALTH_JS)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        status = None
        try:
            resp = page.goto(args.url, wait_until="domcontentloaded",
                             timeout=args.timeout)
            status = resp.status if resp else None
        except PWTimeout:
            print("WARN: navigation timeout, capturing whatever loaded",
                  file=sys.stderr)

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PWTimeout:
            pass

        if args.selector:
            try:
                page.wait_for_selector(args.selector, timeout=args.timeout)
            except PWTimeout:
                print(f"WARN: selector never appeared: {args.selector}",
                      file=sys.stderr)

        if args.scroll:
            autoscroll(page, args.scroll)

        if args.extra_wait:
            page.wait_for_timeout(args.extra_wait)

        html = page.content()
        (out / "page.html").write_text(html, encoding="utf-8")

        meta = {
            "url": args.url,
            "final_url": page.url,
            "title": page.title(),
            "status": status,
            "html_bytes": len(html.encode("utf-8")),
            "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        for prop in ("og:title", "og:description", "og:image"):
            try:
                el = page.query_selector(f'meta[property="{prop}"]')
                if el:
                    meta[prop] = el.get_attribute("content")
            except Exception:
                pass
        (out / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        if args.screenshot:
            try:
                page.screenshot(path=str(out / "screenshot.png"), full_page=True)
            except Exception as e:
                print(f"WARN: screenshot failed: {e}", file=sys.stderr)
                page.screenshot(path=str(out / "screenshot.png"))

        ctx.close()
        if browser is not None:
            browser.close()

    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
