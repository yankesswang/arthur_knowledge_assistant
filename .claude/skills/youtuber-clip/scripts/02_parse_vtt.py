#!/usr/bin/env python3
"""Step 2: VTT → srt_entries.json（6 秒合併，保留實際說話時間）"""
import re, json, sys, os

work_dir = sys.argv[1]
vtt_path = f"{work_dir}/subs.en.vtt"

if not os.path.exists(vtt_path):
    print("WARNING: 無字幕檔，產生空 srt_entries.json")
    json.dump([], open(f"{work_dir}/srt_entries.json", "w"))
    sys.exit(0)

with open(vtt_path, encoding="utf-8", errors="ignore") as f:
    content = f.read()

content = re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', content)
content = re.sub(r'</?[a-zA-Z][\w.]*>', '', content)
for ent, val in [('&gt;','>'),('&lt;','<'),('&amp;','&'),('&nbsp;',' '),('&#39;',"'")]:
    content = content.replace(ent, val)

def parse_ts(s):
    s = s.strip().split()[0].replace(',', '.')
    parts = s.split(':')
    try:
        if len(parts) == 3: return float(parts[0])*3600+float(parts[1])*60+float(parts[2])
        if len(parts) == 2: return float(parts[0])*60+float(parts[1])
    except: pass
    return 0.0

entries = []
for block in re.split(r'\n{2,}', content.strip()):
    lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
    ts_line = next((l for l in lines if '-->' in l), None)
    if not ts_line: continue
    parts = ts_line.split('-->')
    start = parse_ts(parts[0])
    end   = parse_ts(parts[1]) if len(parts) > 1 else start + 3.0
    text  = ' '.join(l for l in lines if '-->' not in l and not l.isdigit()).strip()
    text  = re.sub(r'\s+', ' ', text)
    if text and not text.startswith('[') and len(text) > 1:
        entries.append({"start": start, "end": end, "original": text})

clean = [e for e in entries if (e["end"] - e["start"]) >= 0.1]
real  = clean[1::2]
if len(clean) % 2 == 1: real.append(clean[-1])

CHUNK = 6.0
chunks, buf_texts, buf_start, buf_end = [], [], None, None
for e in real:
    if buf_start is None: buf_start = e["start"]
    buf_texts.append(e["original"])
    buf_end = e["end"]
    if (buf_end - buf_start) >= CHUNK:
        chunks.append({"start": buf_start, "end": buf_end, "original": " ".join(buf_texts)})
        buf_texts, buf_start, buf_end = [], None, None
if buf_texts:
    chunks.append({"start": buf_start, "end": buf_end, "original": " ".join(buf_texts)})

json.dump(chunks, open(f"{work_dir}/srt_entries.json", "w"), ensure_ascii=False, indent=2)
print(f"解析完成：{len(chunks)} 段 | 第一段 [{chunks[0]['start']:.1f}s]: {chunks[0]['original'][:60]}")
