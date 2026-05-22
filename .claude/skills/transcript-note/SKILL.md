---
name: transcript-note
description: YouTube CC subtitle URL → yt-dlp transcript → Claude analysis → deep Obsidian note (AI lecture format)
---

# /transcript-note

Given a YouTube URL with CC subtitles (auto-generated or manual), automatically:
1. Download transcript via yt-dlp (CC subs + metadata + chapters)
2. Parse + condense VTT into clean timestamped text
3. Analyze with Claude (chunked for long videos) using `note-ai-lecture.md` format
4. Generate Obsidian note: TL;DR + 章節筆記 + 關鍵洞見 + 數據速查表
5. Add entry to 待看影片與Podcast清單

No video download, no screenshots. Pure transcript → structured knowledge note.

## Usage

```
/transcript-note https://youtu.be/VIDEO_ID
/transcript-note https://www.youtube.com/watch?v=VIDEO_ID
/transcript-note https://www.youtube.com/shorts/VIDEO_ID
/transcript-note https://www.youtube.com/live/VIDEO_ID
```

## Vault Paths

- **Notes**: `/home/trx50/Documents/arthurwang_DB/AI Knowledge/影片筆記/`
- **Temp work**: `/tmp/transcript_note/<VIDEO_ID>/`
- **Reading list**: `/home/trx50/Documents/arthurwang_DB/待看影片與Podcast清單.md`

---

## What You Must Do When Invoked

Follow these steps in order. Do not skip or reorder.

---

### Step 1 — Parse URL, setup, dependency check

```bash
export YT_URL="<user-provided URL>"

export VIDEO_ID=$(python3 - "$YT_URL" << 'PYEOF'
import re, sys
url = sys.argv[1]
for p in [
    r'(?:v=)([A-Za-z0-9_-]{11})',
    r'youtu\.be/([A-Za-z0-9_-]{11})',
    r'youtube\.com/(?:shorts|embed|live)/([A-Za-z0-9_-]{11})',
]:
    m = re.search(p, url)
    if m: print(m.group(1)); import sys; sys.exit(0)
print("")
PYEOF
)
if [ -z "$VIDEO_ID" ]; then echo "ERROR: Cannot extract video ID from URL"; exit 1; fi

export WORK_DIR="/tmp/transcript_note/$VIDEO_ID"
export NOTE_DIR="/home/trx50/Documents/arthurwang_DB/AI Knowledge/影片筆記"
mkdir -p "$WORK_DIR" "$NOTE_DIR"
echo "Video ID: $VIDEO_ID  |  Work dir: $WORK_DIR"

command -v yt-dlp >/dev/null || { echo "ERROR: yt-dlp not found. Run: pip install yt-dlp"; exit 1; }
echo "Dependencies OK"
```

---

### Step 2 — Download metadata and CC transcript

Priority order: manual CC (zh-TW → zh-Hant → zh) → auto-generated CC (en → zh-TW → zh).
We never download the video.

```bash
# Metadata
yt-dlp --dump-json --no-playlist "$YT_URL" 2>/dev/null > "$WORK_DIR/meta.json"
if [ ! -s "$WORK_DIR/meta.json" ]; then
  echo '{"title":"Unknown","channel":"Unknown","duration":0,"description":"","chapters":[]}' > "$WORK_DIR/meta.json"
fi

# Manual subs first (highest quality), then auto-generated
yt-dlp --skip-download \
  --write-subs \
  --sub-lang "zh-TW,zh-Hant,zh,en" \
  --sub-format "vtt" \
  -o "$WORK_DIR/transcript_manual.%(ext)s" \
  "$YT_URL" 2>/dev/null

export VTT_FILE=$(ls "$WORK_DIR"/transcript_manual.*.vtt 2>/dev/null | head -1)

if [ -z "$VTT_FILE" ]; then
  yt-dlp --skip-download \
    --write-auto-subs \
    --sub-lang "zh-TW,zh-Hant,zh,en" \
    --sub-format "vtt" \
    -o "$WORK_DIR/transcript_auto.%(ext)s" \
    "$YT_URL" 2>/dev/null
  export VTT_FILE=$(ls "$WORK_DIR"/transcript_auto.*.vtt 2>/dev/null | head -1)
fi

echo "Meta: $(python3 -c "import json; d=json.load(open('$WORK_DIR/meta.json')); ch=d.get('chapters') or []; print(d.get('title','?')[:60], '| dur:', d.get('duration',0),'s | chapters:', len(ch))" 2>/dev/null)"
echo "VTT:  ${VTT_FILE:-NONE (will use description)}"
```

---

### Step 3 — Parse VTT + extract metadata

```bash
python3 << 'PYEOF'
import re, json, os, sys

work_dir = os.environ["WORK_DIR"]
vtt_file = os.environ.get("VTT_FILE", "")

with open(f"{work_dir}/meta.json") as f:
    meta = json.load(f)

title        = meta.get("title", "Unknown")
channel      = meta.get("channel", "Unknown")
duration_sec = int(meta.get("duration", 0))
duration_fmt = f"{duration_sec//3600:02d}:{(duration_sec%3600)//60:02d}:{duration_sec%60:02d}"
chapters_raw = meta.get("chapters") or []
upload_date  = meta.get("upload_date", "")  # YYYYMMDD
if upload_date and len(upload_date) == 8:
    upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"

chapters = [
    {"title": ch.get("title",""), "start_sec": int(ch.get("start_time",0)), "end_sec": int(ch.get("end_time", duration_sec))}
    for ch in chapters_raw
]

info = {
    "title": title, "channel": channel,
    "duration": duration_fmt, "duration_sec": duration_sec,
    "upload_date": upload_date,
    "has_chapters": len(chapters) > 0, "chapters": chapters
}
with open(f"{work_dir}/info.json", "w") as f:
    json.dump(info, f, ensure_ascii=False)

if chapters:
    print(f"YouTube chapters: {len(chapters)}")
    for ch in chapters[:6]:
        m, s = divmod(ch["start_sec"], 60)
        print(f"  [{m:02d}:{s:02d}] {ch['title']}")

if not vtt_file or not os.path.exists(vtt_file):
    desc = meta.get("description", "")[:4000]
    with open(f"{work_dir}/condensed.txt", "w") as f:
        f.write(f"[Description only — no CC subtitles found]\n{desc}")
    print(f"No VTT — using description ({len(desc)} chars)")
    sys.exit(0)

with open(vtt_file, encoding="utf-8", errors="ignore") as f:
    content = f.read()

# Clean VTT markup
content = re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', content)
content = re.sub(r'</?c>', '', content)
content = re.sub(r'<[^>]+>', '', content)
for ent, val in [('&gt;','>'),('&lt;','<'),('&amp;','&'),('&nbsp;',' ')]:
    content = content.replace(ent, val)

blocks = re.split(r'\n{2,}', content)
timeline, prev_text = [], ''
for block in blocks:
    lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
    ts_line = next((l for l in lines if '-->' in l), None)
    if not ts_line: continue
    parts = ts_line.split('-->')[0].strip().replace(',','.').split(':')
    try:
        secs = int(parts[0])*3600+int(parts[1])*60+float(parts[2]) if len(parts)==3 \
               else int(parts[0])*60+float(parts[1])
    except: continue
    text = ' '.join(l for l in lines if '-->' not in l).strip()
    if text and text != prev_text and not text.startswith('['):
        timeline.append((secs, text)); prev_text = text

# 60-second buckets (wider than youtube-note's 30s — captures fuller sentences for analysis)
interval = 60
buckets = {}
for secs, text in timeline:
    buckets.setdefault(int(secs) // interval, []).append(text)

def dedupe_keep_order(items):
    seen, out = set(), []
    for x in items:
        x = re.sub(r'\s+', ' ', x).strip()
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out

condensed_lines = []
for b in sorted(buckets):
    texts  = dedupe_keep_order(buckets[b])
    merged = " ".join(texts)
    m2, s2 = divmod(b * interval, 60)
    h2, m2 = divmod(m2, 60)
    ts = f"{h2:02d}:{m2:02d}:{s2:02d}" if h2 else f"{m2:02d}:{s2:02d}"
    condensed_lines.append(f"[{ts}] {merged}")

condensed = '\n'.join(condensed_lines)
with open(f"{work_dir}/condensed.txt", "w") as f:
    f.write(condensed)
print(f"Transcript: {len(timeline)} entries → {len(condensed_lines)} lines ({len(condensed)} chars)")
PYEOF
```

---

### Step 4 — LLM analysis (Claude, via Read tool on condensed.txt)

**DO NOT use `opencli` or external LLM tools. Use your own analysis capability.**

Read `$WORK_DIR/condensed.txt` and `$WORK_DIR/info.json`, then analyze the content directly as Claude.

The analysis must follow the `note-ai-lecture.md` format (Type A: 課程/講座 structure).

Produce a JSON object and write it to `$WORK_DIR/analysis.json`:

```json
{
  "title_zh": "影片中文標題（保留英文專有名詞）",
  "note_type": "A",
  "topic": "技術主題（如 LLM 評估 / Agentic Framework / KV Cache 壓縮）",
  "tags": ["核心技術1", "核心技術2"],
  "tldr": {
    "核心主張": "這份筆記在講什麼（一句話）",
    "關鍵機制_問題": "核心問題是什麼，為什麼重要",
    "重要結論": "最重要的洞見或結論（帶具體數字）",
    "適用條件_限制": "什麼情況下這些結論成立"
  },
  "sections": [
    {
      "title": "章節標題（繁體中文，5-20字）",
      "start_time": "MM:SS",
      "content_points": [
        "- **概念名稱**：一句話定義",
        "    - **子觀點**：說明內容（保留推理過程）",
        "    - **問題/限制**：...",
        "    - **解決方案**：..."
      ]
    }
  ],
  "key_insights": [
    "洞見1（不超過40字）",
    "洞見2",
    "洞見3"
  ],
  "data_table": [
    {"指標": "...", "數值": "...", "備註": "..."}
  ],
  "reading_list_category": "AI Agent 工程 | LLM 技術 / 論文 | Claude Code / 開發工具 | 產業與策略 | 創業 | 投資 | 量化交易 | 知識創作"
}
```

**Analysis quality requirements** (from `note-ai-lecture.md`):
- `sections` should follow YouTube chapters if available; otherwise infer 5-8 logical sections
- `content_points` per section: 5-12 bullet points using nested structure `- **概念**: ...` → `    - **子觀點**: ...`
- Preserve reasoning chains: write WHY A leads to B, not just "A leads to B"
- Keep all specific numbers, benchmarks, percentages
- Preserve comparisons fully (old method vs. new method — do NOT compress to one line)
- If transcript is long (>15K chars), chunk into sections by timestamp, analyze each, then merge

**For long transcripts (>15K chars)**: Split condensed.txt by natural breaks (timestamp intervals), analyze each chunk's key points, then synthesize into the final JSON.

Write the result JSON to `$WORK_DIR/analysis.json`.

---

### Step 5 — Generate Obsidian note

```bash
python3 << 'PYEOF'
import json, os, re
from datetime import date

work_dir = os.environ["WORK_DIR"]
yt_url   = os.environ["YT_URL"]
video_id = os.environ["VIDEO_ID"]
note_dir = "/home/trx50/Documents/arthurwang_DB/AI Knowledge/影片筆記"

with open(f"{work_dir}/analysis.json") as f: data = json.load(f)
with open(f"{work_dir}/info.json")     as f: info = json.load(f)

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
    start  = sec.get("start_time", "00:00")
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

note_content = "\n".join(lines)

safe_title = re.sub(r'[/\\:*?"<>|]', ' ', title_zh).strip()
safe_title = re.sub(r'\s+', ' ', safe_title)[:70]
note_path  = os.path.join(note_dir, f"{safe_title}.md")
# If a file with that name already exists, append video_id to avoid overwrite
if os.path.exists(note_path):
    note_path = os.path.join(note_dir, f"{safe_title} - {video_id}.md")

with open(note_path, "w", encoding="utf-8") as f:
    f.write(note_content)
with open(f"{work_dir}/note_path.txt", "w") as f:
    f.write(note_path)
print(f"Note written: {note_path}")
PYEOF
```

---

### Step 6 — Update 待看影片與Podcast清單

Read `$WORK_DIR/note_path.txt` to get the note filename (without path and `.md`).
Read `$WORK_DIR/analysis.json` to get `reading_list_category`.

Then run the following Python script to update `/home/trx50/Documents/arthurwang_DB/待看影片與Podcast清單.md`:

```python
import json, os, re
from datetime import date, timedelta

work_dir = os.environ["WORK_DIR"]

with open(f"{work_dir}/note_path.txt") as f:
    note_path = f.read().strip()
with open(f"{work_dir}/analysis.json") as f:
    data = json.load(f)

note_title    = os.path.splitext(os.path.basename(note_path))[0]
category      = data.get("reading_list_category", "").split("|")[0].strip()
reading_list  = "/home/trx50/Documents/arthurwang_DB/待看影片與Podcast清單.md"

# ── Compute this week's Monday–Sunday (week starts Monday) ──────────────────
today   = date.today()
monday  = today - timedelta(days=today.weekday())          # Monday of this week
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
    # Extract start date from existing header e.g. 2026/05/11 – 05/17
    m = re.search(r'(\d{4})/(\d{2})/(\d{2})', existing)
    if m:
        existing_monday = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if existing_monday == monday:
            need_new_week = False  # same week, no rotation needed

# ── Rotate week if needed ───────────────────────────────────────────────────
if need_new_week and current_header_match:
    existing_header = current_header_match.group(0)
    # Derive last week's label from the existing header's date range
    m2 = re.search(r'（(\d{4}/\d{2}/\d{2} – \d{2}/\d{2})）', existing_header)
    last_week_range = m2.group(1) if m2 else ""
    last_week_label = f"## 📅 上週（{last_week_range}）"
    # Replace 🆕 header → 上週 header, then prepend new 🆕 block
    content = content.replace(existing_header, last_week_label, 1)
    new_block = f"{this_week_header}\n\n"
    # Insert new block just before the now-demoted 上週 block
    content = content.replace(last_week_label, new_block + last_week_label, 1)
elif need_new_week:
    # No existing 🆕 block at all — prepend after frontmatter / H1
    insert_after = re.search(r'^# 待看影片與 Podcast 清單\n', content, re.MULTILINE)
    pos = insert_after.end() if insert_after else 0
    content = content[:pos] + f"\n{this_week_header}\n\n---\n\n" + content[pos:]

# ── Find the target 🆕 section and insert entry ─────────────────────────────
new_entry = f"- [ ] [[{note_title}]]"
if new_entry in content:
    print(f"Already in list: {note_title}")
else:
    category_header = f"### {category}"
    # Find the 🆕 block boundary (ends at the next ## block)
    week_block_match = re.search(
        r'(## 🆕 本週新增[^\n]*\n)(.*?)(?=\n## |\Z)',
        content, re.DOTALL
    )
    if week_block_match:
        week_body = week_block_match.group(2)
        if category_header in week_body:
            # Insert after the category header line
            content = content.replace(
                category_header + "\n",
                category_header + "\n" + new_entry + "\n",
                1
            )
        else:
            # Create the subsection inside the 🆕 block, before next ##
            insert_pos = week_block_match.end()
            new_section = f"\n{category_header}\n{new_entry}\n"
            content = content[:insert_pos] + new_section + content[insert_pos:]
    with open(reading_list, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Added to 待看影片與Podcast清單 [{category}]: {note_title}")
```

Category mapping (from `reading_list_category` field in analysis.json):
- `AI Agent 工程` → `### AI Agent 工程`
- `LLM 技術 / 論文` → `### LLM 技術 / 論文`
- `Claude Code / 開發工具` → `### Claude Code / 開發工具`
- `產業與策略` → `### 產業與策略`
- `創業` → `### 創業`
- `投資` → `### 投資`
- `量化交易` → `### 量化交易`
- `知識創作` → `### 知識創作`

---

### Step 7 — Report

```bash
python3 << 'PYEOF'
import json, os

work_dir = os.environ["WORK_DIR"]
video_id = os.environ["VIDEO_ID"]

with open(f"{work_dir}/info.json")     as f: info      = json.load(f)
with open(f"{work_dir}/analysis.json") as f: data      = json.load(f)
with open(f"{work_dir}/note_path.txt") as f: note_path = f.read().strip()

sections = data.get("sections", [])
insights = data.get("key_insights", [])
has_vtt  = os.path.exists(f"{work_dir}/condensed.txt") and \
    not open(f"{work_dir}/condensed.txt").read().startswith("[Description")

short = note_path.replace("/home/trx50/Documents/arthurwang_DB/", "")
print(f"\n✓ Note:      {short}")
print(f"✓ Sections:  {len(sections)}")
print(f"✓ Insights:  {len(insights)}")
print(f"✓ Chapters:  {'yes (' + str(len(info.get('chapters',[]))) + ')' if info['has_chapters'] else 'no (LLM inferred)'}")
print(f"✓ Transcript: {'CC subtitles' if has_vtt else 'description only'}")
print(f"\nWork dir: {work_dir}")
PYEOF
```

---

## Key Differences from /youtube-note

| Aspect | /youtube-note | /transcript-note |
| --- | --- | --- |
| Purpose | 影片摘要筆記（截圖＋重點） | 深度知識筆記（逐字稿→結構化分析） |
| Video download | Yes (480p for screenshots) | No |
| Screenshots | Yes (3 candidates per section) | No |
| LLM provider | opencli gemini / chatgpt-app | Claude (self, no external CLI) |
| Note format | 影片資訊 + 章節摘要 + 截圖 | AI lecture format (TL;DR + 推理鏈 + 洞見) |
| Output depth | 每章節 3 bullet points | 每章節 5-12 nested bullet points |
| Reading list | No | Yes (自動更新待看影片與Podcast清單) |

## Edge Cases

| Situation | Action |
| --- | --- |
| No CC subtitles | Use video description (up to 4000 chars); note in frontmatter |
| Manual CC available | Prefer over auto-generated |
| YouTube chapters available | Use as section boundaries in analysis |
| Long transcript (>15K chars) | Chunk by timestamps → analyze → merge |
| VTT has garbled encoding | `errors="ignore"` in open(); strip HTML tags |
| LLM response has extra text | Write JSON manually after analysis; validate required keys |
| Note file already exists | Append ` - {video_id}` suffix to prevent overwrite |
| Reading list subsection missing | Create `### 子分區` under `🆕 本週新增` |

## Architecture

```
URL (v=, youtu.be, shorts, live)
 │
 ├─ Step 1: parse + dep check (yt-dlp only)
 ├─ Step 2: yt-dlp → meta.json (chapters + upload_date)
 │           manual CC → auto CC → description fallback
 ├─ Step 3: VTT parse → 60s bucket merge + dedupe → condensed.txt
 ├─ Step 4: Claude self-analysis (Read condensed.txt → analysis.json)
 │           chapters-aware · chunked for long transcripts
 │           note-ai-lecture.md format: TL;DR + nested bullet points
 ├─ Step 5: Obsidian note (frontmatter + TL;DR + 章節筆記 + 洞見 + 速查表)
 │           timestamp links: [MM:SS](youtube.com/watch?v=...&t=Xs)
 ├─ Step 6: 待看影片與Podcast清單 update ([ ] entry, correct subsection)
 └─ Step 7: report
```
