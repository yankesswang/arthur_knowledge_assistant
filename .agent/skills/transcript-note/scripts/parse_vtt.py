#!/usr/bin/env python3
"""Step 3: Parse VTT subtitle file + extract metadata → condensed.txt + info.json"""
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

def dedup_rolling(texts):
    """YouTube auto-captions use a rolling window — each sentence appears 2-3x.
    Merge by finding the longest suffix-prefix overlap between consecutive blocks."""
    result_words = []
    for text in texts:
        text = re.sub(r'\s+', ' ', text).strip()
        if not text:
            continue
        words = text.split()
        if not result_words:
            result_words.extend(words)
            continue
        # Find longest overlap: suffix of result_words == prefix of words
        overlap = 0
        for n in range(min(len(words), min(len(result_words), 25)), 0, -1):
            if result_words[-n:] == words[:n]:
                overlap = n
                break
        result_words.extend(words[overlap:])
    return " ".join(result_words)

condensed_lines = []
for b in sorted(buckets):
    merged = dedup_rolling(buckets[b])
    m2, s2 = divmod(b * interval, 60)
    h2, m2 = divmod(m2, 60)
    ts = f"{h2:02d}:{m2:02d}:{s2:02d}" if h2 else f"{m2:02d}:{s2:02d}"
    condensed_lines.append(f"[{ts}] {merged}")

condensed = '\n'.join(condensed_lines)
with open(f"{work_dir}/condensed.txt", "w") as f:
    f.write(condensed)
print(f"Transcript: {len(timeline)} entries → {len(condensed_lines)} lines ({len(condensed)} chars)")
