#!/usr/bin/env python3
"""Step 5: Generate Obsidian note from analysis.json + info.json"""
import json, os, re
from datetime import date

work_dir      = os.environ["WORK_DIR"]
yt_url        = os.environ["YT_URL"]
video_id      = os.environ["VIDEO_ID"]
NOTE_ROOT     = "/home/trx50/Documents/arthurwang_DB/影片筆記"

with open(f"{work_dir}/analysis.json") as f: data = json.load(f)
with open(f"{work_dir}/info.json")     as f: info = json.load(f)

# 頻道子資料夾
channel_raw  = info.get("channel", "").strip()
safe_channel = re.sub(r'[/\\:*?"<>|]', ' ', channel_raw).strip() if channel_raw else "未分類"
safe_channel = re.sub(r'\s+', ' ', safe_channel)
note_dir     = os.path.join(NOTE_ROOT, safe_channel)
os.makedirs(note_dir, exist_ok=True)

title_zh      = data.get("title_zh", info["title"])
note_type     = data.get("note_type", "A")
topic         = data.get("topic", "")
tags          = data.get("tags", [])
tldr          = data.get("tldr", {})
sections      = data.get("sections", [])
key_insights  = data.get("key_insights", [])
data_table    = data.get("data_table", [])
today         = date.today().isoformat()
source_date   = info.get("upload_date", today)

def ts_to_seconds(ts):
    parts = ts.strip().split(":")
    try:
        if len(parts) == 3: return int(parts[0])*3600+int(parts[1])*60+int(float(parts[2]))
        elif len(parts) == 2: return int(parts[0])*60+int(float(parts[1]))
    except: pass
    return 0

def yt_link(ts):
    return f"https://www.youtube.com/watch?v={video_id}&t={ts_to_seconds(ts)}s"

def yq(x):
    return json.dumps(str(x), ensure_ascii=False)

# --- Frontmatter ---
tag_lines = ["  - 影片筆記", "  - YouTube", "  - 逐字稿筆記"]
for t in tags:
    tag_lines.append(f"  - {t}")

lines = [
    "---",
    f"title: {yq(title_zh)}",
    f"date: {yq(today)}",
    f"source: {yq(info['channel'])}",
    f"topic: {yq(topic)}",
    "tags:",
] + tag_lines + [
    f"url: {yq(yt_url)}",
    "---",
    "",
]

# --- Thumbnail ---
lines += [f"![thumbnail](https://img.youtube.com/vi/{video_id}/maxresdefault.jpg)", ""]

# --- TL;DR ---
lines += ["## TL;DR", ""]
tldr_map = [
    ("核心主張",       tldr.get("核心主張", "")),
    ("關鍵機制 / 問題", tldr.get("關鍵機制_問題", "")),
    ("重要結論",       tldr.get("重要結論", "")),
    ("適用條件 / 限制", tldr.get("適用條件_限制", "")),
]
for label, val in tldr_map:
    if val:
        lines.append(f"- **{label}**：{val}")
lines.append("")

# --- 影片資訊 ---
lines += [
    "## 影片資訊", "",
    "| 欄位 | 內容 |", "| ---- | ---- |",
    f"| 頻道 | {info['channel']} |",
    f"| 時長 | {info['duration']} |",
    f"| 發布 | {source_date} |",
    f"| 來源 | [{info['title']}]({yt_url}) |",
    "",
]

# --- 章節筆記 ---
lines += ["## 章節筆記", ""]
for i, sec in enumerate(sections):
    start   = sec.get("start_time", "00:00")
    title_s = sec.get("title", f"章節 {i+1}")
    points  = sec.get("content_points", [])
    lines.append(f"### {i+1}. [{start}]({yt_link(start)}) {title_s}")
    lines.append("")
    for pt in points:
        lines.append(pt)
    lines.append("")

# --- 關鍵洞見 ---
if key_insights:
    lines += ["## 關鍵洞見", ""]
    for ins in key_insights:
        lines.append(f"- {ins}")
    lines.append("")

# --- 關鍵數據速查 ---
lines += ["## 附：關鍵數據速查", ""]
if data_table:
    lines += ["| 指標 | 數值 | 備註 |", "| ---- | ---- | ---- |"]
    for row in data_table:
        lines.append(f"| {row.get('指標','')} | {row.get('數值','')} | {row.get('備註','')} |")
else:
    lines += ["| 指標 | 數值 | 備註 |", "| ---- | ---- | ---- |",
              "| （影片無具體數字） | — | — |"]
lines.append("")

# --- 同頻道影片 ---
import glob
# 同頻道影片：直接列同一資料夾下的其他 .md
related = []
for md_path in glob.glob(os.path.join(note_dir, "*.md")):
    if os.path.basename(md_path) == "_INDEX.md":
        continue
    stem = os.path.splitext(os.path.basename(md_path))[0]
    if stem != re.sub(r'[/\\:*?"<>|]', ' ', data.get("title_zh", "")).strip():
        related.append(stem)

if related:
    lines += ["## 同頻道影片", ""]
    for r in sorted(related):
        lines.append(f"- [[{r}]]")
    lines.append("")

note_content = "\n".join(lines)

safe_title = re.sub(r'[/\\:*?"<>|]', ' ', title_zh).strip()
safe_title = re.sub(r'\s+', ' ', safe_title)[:70]
note_path  = os.path.join(note_dir, f"{safe_title}.md")
if os.path.exists(note_path):
    note_path = os.path.join(note_dir, f"{safe_title} - {video_id}.md")

with open(note_path, "w", encoding="utf-8") as f:
    f.write(note_content)
with open(f"{work_dir}/note_path.txt", "w") as f:
    f.write(note_path)
print(f"Note written: {note_path}")
