#!/usr/bin/env python3
"""Extract machine-readable seed data from a scraped page.html.

Pulls schema.org <script type="application/ld+json"> blocks, og:/twitter: meta
tags, and <title>. Output is the STARTING POINT for structured parsing —
the LLM merges it with content.md into the final structured.json.

Usage: extract_structured.py DIR/page.html  (prints JSON to stdout)
"""
import json
import re
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    html = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")

    out = {"ld_json": [], "meta": {}, "title": None}

    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
    if m:
        out["title"] = m.group(1).strip()

    for block in re.findall(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html, re.S):
        try:
            out["ld_json"].append(json.loads(block))
        except json.JSONDecodeError:
            pass

    for prop, content in re.findall(
            r'<meta[^>]+(?:property|name)="((?:og|twitter|article):[^"]+)"[^>]+content="([^"]*)"',
            html):
        out["meta"].setdefault(prop, content)

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
