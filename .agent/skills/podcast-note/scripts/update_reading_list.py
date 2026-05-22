#!/usr/bin/env python3
"""
update_reading_list.py — 將 Podcast 筆記加入待閱讀清單
用法：python3 update_reading_list.py <work_dir>
"""

import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

READING_LIST = Path("/home/trx50/Documents/arthurwang_DB/待閱讀清單.md")
SKILL_DIR    = Path(__file__).parent.parent
CONFIG_PATH  = SKILL_DIR / "config" / "podcasts.json"


def load_config(podcast_id: str) -> dict:
    cfg = json.loads(CONFIG_PATH.read_text())
    return next(p for p in cfg["podcasts"] if p["id"] == podcast_id)


def main():
    if len(sys.argv) < 2:
        print("用法：update_reading_list.py <work_dir>", file=sys.stderr)
        sys.exit(1)

    work_dir = Path(sys.argv[1])
    note_path_file = work_dir / "note_path.txt"
    analysis_file  = work_dir / "analysis.json"

    if not note_path_file.exists():
        print("ERROR: 找不到 note_path.txt", file=sys.stderr)
        sys.exit(1)

    note_path = Path(note_path_file.read_text().strip())
    note_title = note_path.stem

    podcast_id = os.environ.get("PODCAST_ID", "gooaye")
    pod_cfg    = load_config(podcast_id)
    category   = pod_cfg.get("reading_list_category", "投資")

    # 計算本週區間
    today  = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    this_week_header = (
        f"## 🆕 本週新增（{monday.year}/{monday.month:02d}/{monday.day:02d}"
        f" – {sunday.month:02d}/{sunday.day:02d}）"
    )

    content = READING_LIST.read_text(encoding="utf-8")

    # 判斷是否需要輪替週別
    current_match = re.search(r'## 🆕 本週新增（[^）]+）', content)
    need_new_week = True
    if current_match:
        m = re.search(r'(\d{4})/(\d{2})/(\d{2})', current_match.group(0))
        if m:
            existing_monday = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if existing_monday == monday:
                need_new_week = False

    if need_new_week and current_match:
        existing_header = current_match.group(0)
        m2 = re.search(r'（(\d{4}/\d{2}/\d{2} – \d{2}/\d{2})）', existing_header)
        last_week_range = m2.group(1) if m2 else ""
        last_week_label = f"## 📅 上週（{last_week_range}）"
        content = content.replace(existing_header, last_week_label, 1)
        content = content.replace(last_week_label, f"{this_week_header}\n\n" + last_week_label, 1)
    elif need_new_week:
        insert_after = re.search(r'^# 待閱讀清單\n', content, re.MULTILINE)
        pos = insert_after.end() if insert_after else 0
        content = content[:pos] + f"\n{this_week_header}\n\n---\n\n" + content[pos:]

    # 插入條目
    new_entry = f"- [ ] [[{note_title}]]"
    if new_entry in content:
        print(f"已存在，跳過：{note_title}")
        return

    category_header = f"### {category}"
    week_block = re.search(r'(## 🆕 本週新增[^\n]*\n)(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if week_block:
        week_body = week_block.group(2)
        if category_header in week_body:
            content = content.replace(category_header + "\n", category_header + "\n" + new_entry + "\n", 1)
        else:
            insert_pos = week_block.end()
            content = content[:insert_pos] + f"\n{category_header}\n{new_entry}\n" + content[insert_pos:]

    READING_LIST.write_text(content, encoding="utf-8")
    print(f"已加入 待閱讀清單 [{category}]：{note_title}")


if __name__ == "__main__":
    main()
