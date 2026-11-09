#!/usr/bin/env python3
"""Parse a scraped Booking.com search-results page.html into structured JSON.

Usage: parse_booking_search.py DIR/page.html [-o out.json]
Extracts per property card: name, url, review score/label/count, location,
distance, stars, room type, bed info, nights/guests, price, taxes note.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def txt(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else None


def parse_card(card):
    d = {}
    d["name"] = txt(card.select_one('[data-testid="title"]'))
    link = card.select_one('a[data-testid="title-link"], a[data-testid="property-card-desktop-single-image"]')
    if link and link.get("href"):
        d["url"] = link["href"].split("?")[0]

    score_el = card.select_one('[data-testid="review-score"]')
    if score_el:
        t = txt(score_el) or ""
        m = re.search(r"(\d\.\d)", t)
        d["score"] = float(m.group(1)) if m else None
        m = re.search(r"([\d,]+)\s*則評語", t)
        d["review_count"] = int(m.group(1).replace(",", "")) if m else None
        m = re.search(r"(好極了|極好|很好|好|傑出|尚可)", t)
        d["score_label"] = m.group(1) if m else None

    img = card.select_one('img[data-testid="image"]') or card.select_one("img")
    if img and img.get("src", "").startswith("http"):
        d["image"] = img["src"]

    d["location"] = txt(card.select_one('[data-testid="address"]'))
    d["distance"] = txt(card.select_one('[data-testid="distance"]'))

    stars = card.select_one('[data-testid="rating-stars"], [data-testid="rating-squares"]')
    if stars:
        # each star is one direct child div (containing layered svgs)
        d["stars"] = len(stars.find_all("div", recursive=False)) or None

    d["room_type"] = txt(card.select_one('[data-testid="recommended-units"] h4'))
    price = txt(card.select_one('[data-testid="price-and-discounted-price"]'))
    if price:
        d["price"] = price.replace("\xa0", " ")
        m = re.search(r"([A-Z]{3})\s*([\d,]+)", d["price"])
        if m:
            d["currency"] = m.group(1)
            d["price_value"] = int(m.group(2).replace(",", ""))
    d["price_for"] = txt(card.select_one('[data-testid="price-for-x-nights"]'))
    d["taxes_note"] = txt(card.select_one('[data-testid="taxes-and-charges"]'))

    units = card.select_one('[data-testid="recommended-units"]')
    if units:
        beds = txt(units)
        m = re.search(r"(\d+\s*張[^ ]{1,12}床)", beds or "")
        if m:
            d["beds"] = m.group(1)
    return {k: v for k, v in d.items() if v is not None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    soup = BeautifulSoup(Path(args.html).read_text(encoding="utf-8"), "lxml")
    cards = soup.select('[data-testid="property-card"]')
    results = [parse_card(c) for c in cards]

    heading = soup.select_one("h1")
    out = {
        "heading": txt(heading),
        "property_count": len(results),
        "properties": results,
    }
    payload = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"{len(results)} properties → {args.out}", file=sys.stderr)
    else:
        print(payload)


if __name__ == "__main__":
    main()
