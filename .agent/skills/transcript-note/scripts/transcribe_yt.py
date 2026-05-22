#!/usr/bin/env python3
"""
transcribe_yt.py — YouTube 影片 → faster-whisper 轉錄 → condensed.txt
用於 CC 字幕不可用時的 fallback。

用法：python3.10 transcribe_yt.py <work_dir> [--lang auto] [--model medium]
環境變數：YT_URL（YouTube URL，用於下載音頻）

輸出：
  <work_dir>/condensed.txt     — 60 秒 bucket 格式（與 parse_vtt.py 一致）
  <work_dir>/audio.m4a         — 下載的音頻（可清除）
  <work_dir>/transcript_source.txt — 更新為 "whisper"
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

CUDNN_LIB = Path.home() / ".local/lib/python3.10/site-packages/nvidia/cudnn/lib"


def setup_cudnn():
    if not CUDNN_LIB.exists():
        return
    mappings = {
        "libcudnn_ops_infer.so.8": "libcudnn_ops.so.9",
        "libcudnn_cnn_infer.so.8": "libcudnn_cnn.so.9",
        "libcudnn_adv_infer.so.8": "libcudnn_adv.so.9",
        "libcudnn.so.8":           "libcudnn.so.9",
    }
    for link_name, target in mappings.items():
        link = CUDNN_LIB / link_name
        t    = CUDNN_LIB / target
        if t.exists() and not link.exists():
            link.symlink_to(t)
    lib_str = str(CUDNN_LIB)
    ld = os.environ.get("LD_LIBRARY_PATH", "")
    if lib_str not in ld:
        os.environ["LD_LIBRARY_PATH"] = f"{lib_str}:{ld}"


def detect_device():
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def check_gpu_memory_gb() -> float:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        val = r.stdout.strip().splitlines()[0].strip()
        return float(val) / 1024
    except Exception:
        return 0.0


def choose_model(requested: str, device: str) -> str:
    if device != "cuda":
        return "small"
    free_gb = check_gpu_memory_gb()
    order = ["large-v3", "medium", "small", "base", "tiny"]
    min_gb = {"large-v3": 6, "medium": 3, "small": 1.5, "base": 1, "tiny": 0.5}
    if requested in order and free_gb >= min_gb.get(requested, 99):
        return requested
    for m in order:
        if free_gb >= min_gb[m]:
            print(f"GPU 記憶體 {free_gb:.1f} GB，降級至 {m}", flush=True)
            return m
    return "tiny"


def download_audio(yt_url: str, work_dir: Path) -> Path:
    audio_path = work_dir / "audio.m4a"
    if audio_path.exists():
        print(f"音頻已存在：{audio_path}", flush=True)
        return audio_path

    print("下載音頻（最佳音質，無影像）...", flush=True)
    r = subprocess.run(
        ["yt-dlp", "-f", "bestaudio[ext=m4a]/bestaudio/best",
         "--no-playlist", "-o", str(audio_path), yt_url],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or not audio_path.exists():
        # fallback：嘗試 mp3
        audio_path = work_dir / "audio.mp3"
        subprocess.run(
            ["yt-dlp", "-f", "bestaudio", "--extract-audio", "--audio-format", "mp3",
             "--no-playlist", "-o", str(audio_path), yt_url],
            check=True,
        )
    print(f"✓ 音頻：{audio_path} ({audio_path.stat().st_size // 1024} KB)", flush=True)
    return audio_path


def transcribe(audio_path: Path, model_size: str, language: str | None, device: str):
    from faster_whisper import WhisperModel
    compute_type = "float16" if device == "cuda" else "int8"
    print(f"載入 Whisper {model_size}（{device}/{compute_type}）...", flush=True)
    t0    = time.time()
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    print(f"模型就緒（{time.time()-t0:.1f}s），開始轉錄...", flush=True)

    kwargs = {"beam_size": 5, "vad_filter": True,
              "vad_parameters": {"min_silence_duration_ms": 500}}
    if language and language != "auto":
        kwargs["language"] = language

    segments, info = model.transcribe(str(audio_path), **kwargs)
    entries = []
    for seg in segments:
        entries.append({"start": round(seg.start, 3), "end": round(seg.end, 3), "text": seg.text.strip()})
        print(f"  [{seg.start:7.1f}s] {seg.text.strip()[:80]}", flush=True)

    elapsed = time.time() - t0
    speed   = info.duration / elapsed if elapsed > 0 else 0
    print(f"\n轉錄完成：{len(entries)} 段 | {info.duration/60:.1f} 分 | {elapsed:.1f}s（{speed:.1f}x）", flush=True)
    if not language or language == "auto":
        print(f"偵測語言：{info.language}（{info.language_probability:.1%}）")
    return entries, info


def entries_to_condensed(entries: list[dict], interval: int = 60) -> list[str]:
    """與 parse_vtt.py 相同的 60 秒 bucket 格式。"""
    buckets: dict[int, list[str]] = {}
    for e in entries:
        key = int(e["start"]) // interval
        buckets.setdefault(key, []).append(e["text"])

    def dedupe(items):
        seen, out = set(), []
        for x in items:
            x = re.sub(r'\s+', ' ', x).strip()
            if x and x not in seen:
                seen.add(x); out.append(x)
        return out

    lines = []
    for b in sorted(buckets):
        texts  = dedupe(buckets[b])
        merged = " ".join(texts)
        total  = b * interval
        h, rem = divmod(total, 3600)
        m, s   = divmod(rem, 60)
        ts = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
        lines.append(f"[{ts}] {merged}")
    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir")
    parser.add_argument("--lang",  default="auto",
                        help="語言代碼（auto / zh / en / ja...）")
    parser.add_argument("--model", default="medium",
                        choices=["tiny","base","small","medium","large-v2","large-v3"])
    parser.add_argument("--device", default="auto", choices=["auto","cpu","cuda"])
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    yt_url   = os.environ.get("YT_URL", "")
    if not yt_url:
        # 從 meta.json 取 webpage_url
        meta_path = work_dir / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            yt_url = meta.get("webpage_url") or meta.get("original_url", "")
    if not yt_url:
        print("ERROR: 缺少 YT_URL 環境變數，且 meta.json 中無 webpage_url", file=sys.stderr)
        sys.exit(1)

    setup_cudnn()
    device = detect_device() if args.device == "auto" else args.device
    model  = choose_model(args.model, device)
    print(f"裝置：{device} | 模型：{model}", flush=True)

    # 1. 下載音頻
    audio_path = download_audio(yt_url, work_dir)

    # 2. Whisper 轉錄
    lang = None if args.lang == "auto" else args.lang
    entries, info = transcribe(audio_path, model, lang, device)

    # 3. 寫 condensed.txt（60 秒 bucket，與 CC 路徑格式一致）
    lines = entries_to_condensed(entries, interval=60)
    condensed_path = work_dir / "condensed.txt"
    condensed_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"condensed.txt：{len(lines)} 行（{condensed_path.stat().st_size} bytes）")

    # 4. 更新 transcript_source
    (work_dir / "transcript_source.txt").write_text("whisper")
    print("transcript_source → whisper")


if __name__ == "__main__":
    main()
