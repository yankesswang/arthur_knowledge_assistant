#!/usr/bin/env python3
"""Parse a scraped Booking.com hotel detail page into JSON.

Usage: parse_booking_hotel.py DIR   (a scrape.py output dir with page.html)
Emits: name, address, rating (ld+json), image URLs (deduped, max500),
review quotes (「…」 from rendered text).
"""
import json
import re
import sys
from pathlib import Path


def main():
    d = Path(sys.argv[1])
    html = (d / "page.html").read_text(encoding="utf-8", errors="replace")
    out = {}

    for block in re.findall(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            ld = json.loads(block)
        except json.JSONDecodeError:
            continue
        if ld.get("@type") == "Hotel":
            out["name"] = ld.get("name")
            out["address"] = (ld.get("address") or {}).get("streetAddress")
            agg = ld.get("aggregateRating") or {}
            out["score"] = agg.get("ratingValue")
            out["review_count"] = agg.get("reviewCount")
            out["description"] = ld.get("description")

    # gallery images: rebuild every photo id at max500, dedupe, keep order
    seen, images = set(), []
    for m in re.finditer(
            r'https://cf\.bstatic\.com/xdata/images/hotel/([a-z0-9x]+)/(\d+)\.(?:jpe?g|webp)\?k=([0-9a-f]+)', html):
        pid, k = m.group(2), m.group(3)
        if pid not in seen:
            seen.add(pid)
            images.append(f"https://cf.bstatic.com/xdata/images/hotel/max500/{pid}.jpg?k={k}&o=")
    out["images"] = images[:12]

    # review quotes from rendered text (zh pages wrap featured reviews in 「」)
    text = re.sub(r"<[^>]+>", " ", html)
    quotes = []
    for q in re.findall(r"「([^」]{10,160})」", text):
        q = re.sub(r"\s+", " ", q).strip()
        if q not in quotes:
            quotes.append(q)
    out["reviews"] = quotes[:8]

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
