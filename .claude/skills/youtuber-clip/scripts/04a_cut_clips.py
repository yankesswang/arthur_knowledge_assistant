#!/usr/bin/env python3
"""Step 4a: 從 moments.json 裁出橫版原始片段（無字幕）"""
import json, os, subprocess, sys

work_dir = sys.argv[1]
video    = f"{work_dir}/video.mp4"
moments  = json.load(open(f"{work_dir}/moments.json"))
out_dir  = f"{work_dir}/clips"
os.makedirs(out_dir, exist_ok=True)

for m in moments:
    slug = m["slug"]
    out  = f"{out_dir}/{slug}.mp4"
    if os.path.exists(out) and os.path.getsize(out) > 500_000:
        print(f"[SKIP] {slug}")
        continue
    dur = m["abs_end"] - m["abs_start"]
    r = subprocess.run([
        "ffmpeg", "-y",
        "-ss", str(m["abs_start"]), "-i", video, "-t", str(dur),
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        out, "-loglevel", "error"
    ], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        print(f"ERROR {slug}: {r.stderr[-150:]}")
    else:
        print(f"✓ {slug}")
