#!/usr/bin/env python3
"""Step 5: 合成 supercut — zoom punch-in + 置中黃色大字卡 + 色彩增強"""
import json, os, subprocess, sys

work_dir    = sys.argv[1]
face_dir    = f"{work_dir}/face"
supercut_dir = f"{work_dir}/supercut"
seg_dir     = f"{work_dir}/supercut/segs"
os.makedirs(seg_dir, exist_ok=True)

OUT_W, OUT_H = 1080, 1920
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"

moments = json.load(open(f"{work_dir}/moments.json"))

def esc(t):
    return t.replace("'", "\\'").replace(":", "\\:").replace("\\", "")

def txt_filter(text, y, dur):
    enable = f"between(t\\,0\\,{dur:.2f})"
    return (
        f"drawtext=fontfile={FONT}:"
        f"text='{esc(text)}':"
        f"fontsize=76:fontcolor=#FFE033:"
        f"borderw=5:bordercolor=black:"
        f"shadowx=3:shadowy=3:shadowcolor=black@0.9:"
        f"x=(w-text_w)/2:y={y}:"
        f"enable='{enable}'"
    )

def make_seg(idx, m):
    face_clip = f"{face_dir}/{m['slug']}.mp4"
    out       = f"{seg_dir}/seg_{idx:02d}.mp4"
    if os.path.exists(out) and os.path.getsize(out) > 50_000:
        return out

    l1  = m.get("label_line1", "")
    l2  = m.get("label_line2", "")
    dur = m["moment_dur"]

    y1  = "(h/2)-85" if l2 else "(h-text_h)/2"
    y2  = "(h/2)+15"

    sub = txt_filter(l1, y1, dur)
    if l2: sub += "," + txt_filter(l2, y2, dur)

    vf = (
        f"zoompan=z='if(lt(on\\,9)\\,1.05\\,1.0)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d=1:s={OUT_W}x{OUT_H}:fps=30,"
        f"eq=saturation=1.3:contrast=1.06,"
        f"{sub}"
    )
    r = subprocess.run([
        "ffmpeg", "-y",
        "-ss", str(m["moment_start"]), "-i", face_clip,
        "-t", str(dur),
        "-vf", vf,
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k", "-r", "30",
        out, "-loglevel", "error"
    ], capture_output=True, text=True, timeout=120)

    if r.returncode != 0:
        # fallback：移除 zoompan
        vf_simple = f"eq=saturation=1.3:contrast=1.06,{sub}"
        r2 = subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(m["moment_start"]), "-i", face_clip,
            "-t", str(dur), "-vf", vf_simple,
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k",
            out, "-loglevel", "error"
        ], capture_output=True, text=True, timeout=120)
        if r2.returncode != 0:
            print(f"  ERROR seg{idx}: {r2.stderr[-150:]}")
            return None
    return out

segs = []
total_dur = 0
for i, m in enumerate(moments):
    print(f"  [{i+1:02d}] {m.get('label_line1','')}", flush=True)
    seg = make_seg(i, m)
    if seg:
        segs.append(seg)
        total_dur += m["moment_dur"]

concat_list = f"{seg_dir}/concat.txt"
with open(concat_list, "w") as f:
    for s in segs: f.write(f"file '{os.path.abspath(s)}'\n")

final = f"{supercut_dir}/supercut.mp4"
r = subprocess.run([
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0", "-i", concat_list,
    "-c:v", "libx264", "-crf", "18", "-preset", "fast",
    "-c:a", "aac", "-b:a", "128k",
    "-movflags", "+faststart",
    final, "-loglevel", "warning"
], capture_output=True, text=True, timeout=300)

if r.returncode != 0:
    print(f"ERROR: {r.stderr[-300:]}")
    sys.exit(1)

size = os.path.getsize(final)/1024/1024
print(f"\n✓ {final}")
print(f"  {size:.1f} MB | {total_dur:.0f}s | {OUT_W}×{OUT_H}")
