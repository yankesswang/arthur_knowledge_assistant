#!/usr/bin/env python3
"""Step 4b: insightface 人臉追蹤 → 9:16 動態裁切"""
import cv2, numpy as np, json, os, subprocess, sys

work_dir  = sys.argv[1]
clips_dir = f"{work_dir}/clips"
face_dir  = f"{work_dir}/face"
os.makedirs(face_dir, exist_ok=True)

SRC_W, SRC_H = 1920, 1080
OUT_W, OUT_H = 1080, 1920
CROP_W = int(SRC_H * 9 / 16)   # 607
CROP_H = SRC_H
ALPHA  = 0.08
EVERY  = 15

from insightface.app import FaceAnalysis
app = FaceAnalysis(name='buffalo_sc', providers=['CPUExecutionProvider'])
app.prepare(ctx_id=0, det_size=(640, 640))

def process(clip_path, out_path, cmd_path):
    cap   = cv2.VideoCapture(clip_path)
    fps   = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # 偵測
    cx_map, fi = {}, 0
    while True:
        ret, frame = cap.read()
        if not ret: break
        if fi % EVERY == 0:
            faces = app.get(frame)
            if faces:
                b = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1])).bbox.astype(int)
                cx_map[fi] = (b[0]+b[2])//2
        fi += 1
    cap.release()

    if not cx_map: cx_map = {0: SRC_W // 2}

    # 插值
    det = sorted(cx_map)
    cx_all = dict(cx_map)
    for i, f0 in enumerate(det[:-1]):
        f1 = det[i+1]
        for f in range(f0+1, f1):
            t = (f-f0)/(f1-f0)
            cx_all[f] = int(cx_map[f0]*(1-t)+cx_map[f1]*t)
    for f in range(0, det[0]):          cx_all[f] = cx_map[det[0]]
    for f in range(det[-1]+1, total):   cx_all[f] = cx_map[det[-1]]

    # EMA 平滑
    smooth, prev = {}, cx_all.get(0, SRC_W//2)
    for f in range(total):
        s = ALPHA*cx_all.get(f, prev) + (1-ALPHA)*prev
        smooth[f] = s; prev = s

    # sendcmd
    half   = CROP_W // 2
    crop_x = {f: int(max(0, min(SRC_W-CROP_W, smooth[f]-half))) for f in range(total)}
    lines, prev_x = [], None
    for f in range(total):
        x = crop_x[f]
        if prev_x is None or abs(x-prev_x) >= 2:
            lines.append(f"{f/fps:.4f} crop x {x};")
            prev_x = x
    with open(cmd_path, "w") as fp: fp.write("\n".join(lines))

    init_x  = crop_x.get(0, SRC_W//2-half)
    cmd_esc = cmd_path.replace(":", "\\:")
    vf = f"sendcmd=f={cmd_esc},crop={CROP_W}:{CROP_H}:{init_x}:0,scale={OUT_W}:{OUT_H}"
    r = subprocess.run([
        "ffmpeg", "-y", "-i", clip_path,
        "-vf", vf,
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        out_path, "-loglevel", "error"
    ], capture_output=True, text=True, timeout=300)
    return r.returncode == 0

moments = json.load(open(f"{work_dir}/moments.json"))
for m in moments:
    slug     = m["slug"]
    clip     = f"{clips_dir}/{slug}.mp4"
    out      = f"{face_dir}/{slug}.mp4"
    cmd_path = f"{face_dir}/{slug}_crop.txt"

    if not os.path.exists(clip):
        print(f"[SKIP] {slug} — clip 不存在"); continue
    if os.path.exists(out) and os.path.getsize(out) > 500_000:
        print(f"[SKIP] {slug}"); continue

    print(f"[追蹤] {slug}", flush=True)
    ok = process(clip, out, cmd_path)
    if ok:
        print(f"  ✓ {os.path.getsize(out)/1024/1024:.1f} MB")
    else:
        print(f"  ERROR")
