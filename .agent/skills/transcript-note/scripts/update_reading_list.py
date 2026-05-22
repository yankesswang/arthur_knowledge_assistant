#!/usr/bin/env python3
"""Step 6: Update 待看影片與Podcast清單.md with new note entry"""
import json, os, re
from datetime import date, timedelta

work_dir = os.environ["WORK_DIR"]

with open(f"{work_dir}/note_path.txt") as f:
    note_path = f.read().strip()
with open(f"{work_dir}/analysis.json") as f:
    data = json.load(f)

note_title    = os.path.splitext(os.path.basename(note_path))[0]
category      = data.get("reading_list_category", "").split("|")[0].strip()
_vault = os.environ.get("VAULT_ROOT", os.path.join(os.path.expanduser("~"), "Documents", "arthurwang_DB"))
reading_list  = os.environ.get("READING_LIST_PATH", os.path.join(_vault, "待看影片與Podcast清單.md"))

# ── Compute this week's Monday–Sunday (week starts Monday) ──────────────────
today   = date.today()
monday  = today - timedelta(days=today.weekday())
sunday  = monday + timedelta(days=6)
this_week_header = (
    f"## 🆕 本週新增（{monday.year}/{monday.month:02d}/{monday.day:02d}"
    f" – {sunday.month:02d}/{sunday.day:02d}）"
)

with open(reading_list, encoding="utf-8") as f:
    content = f.read()

# ── Check whether the existing 🆕 header matches this week ─────────────────
current_header_match = re.search(r'## 🆕 本週新增（[^）]+）', content)
need_new_week = True
if current_header_match:
    existing = current_header_match.group(0)
    m = re.search(r'(\d{4})/(\d{2})/(\d{2})', existing)
    if m:
        existing_monday = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if existing_monday == monday:
            need_new_week = False

# ── Rotate week if needed ───────────────────────────────────────────────────
if need_new_week and current_header_match:
    existing_header = current_header_match.group(0)
    m2 = re.search(r'（(\d{4}/\d{2}/\d{2} – \d{2}/\d{2})）', existing_header)
    last_week_range = m2.group(1) if m2 else ""
    last_week_label = f"## 📅 上週（{last_week_range}）"
    content = content.replace(existing_header, last_week_label, 1)
    new_block = f"{this_week_header}\n\n"
    content = content.replace(last_week_label, new_block + last_week_label, 1)
elif need_new_week:
    insert_after = re.search(r'^# 待看影片與 Podcast 清單\n', content, re.MULTILINE)
    pos = insert_after.end() if insert_after else 0
    content = content[:pos] + f"\n{this_week_header}\n\n---\n\n" + content[pos:]

# ── Find the target 🆕 section and insert entry ─────────────────────────────
new_entry = f"- [ ] [[{note_title}]]"
if new_entry in content:
    print(f"Already in list: {note_title}")
else:
    category_header = f"### {category}"
    week_block_match = re.search(
        r'(## 🆕 本週新增[^\n]*\n)(.*?)(?=\n## |\Z)',
        content, re.DOTALL
    )
    if week_block_match:
        week_body = week_block_match.group(2)
        if category_header in week_body:
            content = content.replace(
                category_header + "\n",
                category_header + "\n" + new_entry + "\n",
                1
            )
        else:
            insert_pos = week_block_match.end()
            new_section = f"\n{category_header}\n{new_entry}\n"
            content = content[:insert_pos] + new_section + content[insert_pos:]
    with open(reading_list, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Added to 待看影片與Podcast清單 [{category}]: {note_title}")
