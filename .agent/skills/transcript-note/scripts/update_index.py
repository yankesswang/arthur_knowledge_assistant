#!/usr/bin/env python3
"""Step 6b: Append new entry to _INDEX.md master table"""
import json, os, re
from datetime import date

work_dir  = os.environ["WORK_DIR"]
video_id  = os.environ["VIDEO_ID"]
_vault = os.environ.get("VAULT_ROOT", os.path.join(os.path.expanduser("~"), "Documents", "arthurwang_DB"))
index_path = os.environ.get("YT_INDEX_PATH", os.path.join(_vault, "影片筆記", "_INDEX.md"))

with open(f"{work_dir}/note_path.txt") as f: note_path = f.read().strip()
with open(f"{work_dir}/analysis.json") as f: data      = json.load(f)
with open(f"{work_dir}/info.json")     as f: info      = json.load(f)

title    = data.get("title_zh", info["title"])
channel  = info.get("channel", "")
category = data.get("reading_list_category", "").split("|")[0].strip()
today    = date.today().isoformat()
note_title = os.path.splitext(os.path.basename(note_path))[0]
url      = f"https://www.youtube.com/watch?v={video_id}"

new_row  = f"| {today} | [[{note_title}]] | {channel} | {category} | [{video_id}]({url}) |"

with open(index_path, encoding="utf-8") as f:
    content = f.read()

# Skip if already in index
if video_id in content:
    print(f"Already in _INDEX.md: {video_id}")
else:
    # Insert after the header row of the main table
    insert_marker = "| -------- | ---- | ---- | ---- | -------- |"
    if insert_marker in content:
        content = content.replace(
            insert_marker + "\n",
            insert_marker + "\n" + new_row + "\n",
            1
        )
        # Update count
        current_count = len(re.findall(r'^\| 2\d{3}-\d{2}-\d{2} \|', content, re.MULTILINE))
        content = re.sub(
            r'(\| 已整理影片 \| )\d+',
            f'\\g<1>{current_count}',
            content
        )
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Added to _INDEX.md: {note_title}")
    else:
        print("WARNING: Could not find table header in _INDEX.md")
