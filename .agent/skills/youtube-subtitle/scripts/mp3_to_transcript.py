#!/usr/bin/env python3
"""
mp3_to_transcript.py — MP3/音訊 → 逐字稿

使用 faster-whisper 轉錄，輸出純文字逐字稿（.txt）和帶時間戳 JSON（.json）。

用法：
  python3 mp3_to_transcript.py <audio_file> [選項]

選項：
  --model       Whisper 模型大小：tiny/base/small/medium/large-v3（預設 large-v3）
  --lang        音訊語言（ISO 639-1，如 en/zh/ja）；不指定則自動偵測
  --output-dir  輸出目錄（預設：與音訊同目錄）
  --format      輸出格式：txt / json / both（預設 both）
  --device      cpu / cuda（預設 auto 偵測）

範例：
  python3 mp3_to_transcript.py podcast.mp3
  python3 mp3_to_transcript.py lecture.mp3 --lang en --model medium
  python3 mp3_to_transcript.py interview.mp3 --output-dir /tmp/transcripts
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path


def detect_device():
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def transcribe(audio_path: str, model_size: str, language: str | None, device: str):
    from faster_whisper import WhisperModel

    print(f"載入模型 {model_size}（{device}）...", flush=True)
    t0 = time.time()

    compute_type = "float16" if device == "cuda" else "int8"
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    print(f"模型載入完成（{time.time()-t0:.1f}s），開始轉錄...", flush=True)
    t1 = time.time()

    kwargs = {"beam_size": 5, "vad_filter": True, "vad_parameters": {"min_silence_duration_ms": 500}}
    if language:
        kwargs["language"] = language

    segments, info = model.transcribe(audio_path, **kwargs)

    entries = []
    for seg in segments:
        entries.append({
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
        })
        # 即時顯示進度
        print(f"  [{seg.start:7.1f}s] {seg.text.strip()[:70]}", flush=True)

    elapsed = time.time() - t1
    audio_dur = info.duration
    speed = audio_dur / elapsed if elapsed > 0 else 0

    print(f"\n轉錄完成：{len(entries)} 段 | 音訊 {audio_dur/60:.1f} 分 | "
          f"耗時 {elapsed:.1f}s（{speed:.1f}x 速）", flush=True)

    if not language:
        print(f"偵測語言：{info.language}（信心 {info.language_probability:.2%}）")

    return entries, info


def write_txt(entries: list, out_path: str):
    lines = []
    for e in entries:
        m = int(e["start"]) // 60
        s = e["start"] % 60
        lines.append(f"[{m:02d}:{s:05.2f}] {e['text']}")
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"逐字稿（TXT）：{out_path}")


def write_json(entries: list, info, out_path: str):
    data = {
        "language": getattr(info, "language", "unknown"),
        "language_probability": round(getattr(info, "language_probability", 0), 4),
        "duration": round(getattr(info, "duration", 0), 3),
        "segments": entries,
    }
    Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"逐字稿（JSON）：{out_path}")


def main():
    parser = argparse.ArgumentParser(description="MP3/音訊 → 逐字稿（faster-whisper）")
    parser.add_argument("audio", help="輸入音訊檔案（mp3/m4a/wav/flac 等）")
    parser.add_argument("--model", default="large-v3",
                        choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
                        help="Whisper 模型（預設 large-v3）")
    parser.add_argument("--lang", default=None, help="音訊語言（如 en/zh），不指定則自動偵測")
    parser.add_argument("--output-dir", default=None, help="輸出目錄（預設同音訊目錄）")
    parser.add_argument("--format", default="both", choices=["txt", "json", "both"],
                        help="輸出格式（預設 both）")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"],
                        help="運算裝置（預設 auto）")
    args = parser.parse_args()

    audio_path = Path(args.audio).resolve()
    if not audio_path.exists():
        print(f"ERROR: 找不到音訊檔案：{audio_path}", file=sys.stderr)
        sys.exit(1)

    device = detect_device() if args.device == "auto" else args.device

    out_dir = Path(args.output_dir) if args.output_dir else audio_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = audio_path.stem
    txt_path  = out_dir / f"{stem}_transcript.txt"
    json_path = out_dir / f"{stem}_transcript.json"

    print(f"輸入：{audio_path}")
    print(f"輸出：{out_dir}")
    print("-" * 50)

    entries, info = transcribe(str(audio_path), args.model, args.lang, device)

    print("-" * 50)
    if args.format in ("txt", "both"):
        write_txt(entries, str(txt_path))
    if args.format in ("json", "both"):
        write_json(entries, info, str(json_path))

    print("\n完成。")


if __name__ == "__main__":
    main()
