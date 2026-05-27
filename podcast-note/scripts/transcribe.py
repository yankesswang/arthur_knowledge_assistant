#!/usr/bin/env python3
"""
transcribe.py — MP3 → 逐字稿（faster-whisper，GPU 優先）
用法：python3.10 transcribe.py <work_dir> [--lang zh] [--model medium]
輸出：<work_dir>/transcript.txt（帶時間戳）和 <work_dir>/transcript.json
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

PODCAST_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = PODCAST_ROOT.parent
TRANSCRIPTION_SETTINGS_PATH = PROJECT_ROOT / "server" / "data" / "transcription_settings.json"

CUDNN_LIB = Path.home() / ".local/lib/python3.10/site-packages/nvidia/cudnn/lib"


def setup_cudnn():
    """讓 ctranslate2 找到 cuDNN 9（symlink to .so.8 名稱）。"""
    if not CUDNN_LIB.exists():
        return
    mappings = {
        "libcudnn_ops_infer.so.8": "libcudnn_ops.so.9",
        "libcudnn_cnn_infer.so.8": "libcudnn_cnn.so.9",
        "libcudnn_adv_infer.so.8": "libcudnn_adv.so.9",
        "libcudnn.so.8": "libcudnn.so.9",
    }
    for link_name, target_name in mappings.items():
        link = CUDNN_LIB / link_name
        target = CUDNN_LIB / target_name
        if target.exists() and not link.exists():
            link.symlink_to(target)
    lib_str = str(CUDNN_LIB)
    ld_path = os.environ.get("LD_LIBRARY_PATH", "")
    if lib_str not in ld_path:
        os.environ["LD_LIBRARY_PATH"] = f"{lib_str}:{ld_path}"


def detect_device():
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def transcribe(audio_path: str, model_size: str, language: str | None, device: str):
    from faster_whisper import WhisperModel

    compute_type = "float16" if device == "cuda" else "int8"
    print(f"載入模型 {model_size}（{device}/{compute_type}）...", flush=True)
    t0 = time.time()
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    print(f"模型載入完成（{time.time()-t0:.1f}s），開始轉錄...", flush=True)

    kwargs = {
        "beam_size": 5,
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 500},
    }
    if language:
        kwargs["language"] = language

    segments, info = model.transcribe(audio_path, **kwargs)

    entries = []
    for seg in segments:
        entries.append({"start": round(seg.start, 3), "end": round(seg.end, 3), "text": seg.text.strip()})
        print(f"  [{seg.start:7.1f}s] {seg.text.strip()[:80]}", flush=True)

    elapsed = time.time() - t0
    speed = info.duration / elapsed if elapsed > 0 else 0
    print(f"\n轉錄完成：{len(entries)} 段 | 音頻 {info.duration/60:.1f} 分 | 耗時 {elapsed:.1f}s（{speed:.1f}x）", flush=True)
    if not language:
        print(f"偵測語言：{info.language}（信心 {info.language_probability:.2%}）")
    return entries, info


def get_transcription_settings() -> dict:
    if TRANSCRIPTION_SETTINGS_PATH.exists():
        try:
            return json.loads(TRANSCRIPTION_SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"mode": "local", "openai_api_key": "", "whisper_model": "medium"}


_WHISPER_API_MAX_BYTES = 24 * 1024 * 1024  # 24 MB，留 1 MB 餘裕


def _split_audio(audio_path: str, chunk_dir: Path, chunk_secs: int = 3000) -> list[Path]:
    """用 ffmpeg 把音頻切成 chunk_secs 秒一段，回傳各段路徑。"""
    import subprocess as _sp
    chunk_dir.mkdir(parents=True, exist_ok=True)
    pattern = chunk_dir / "chunk_%03d.mp3"
    _sp.run(
        ["ffmpeg", "-y", "-i", audio_path,
         "-f", "segment", "-segment_time", str(chunk_secs),
         "-ar", "16000", "-ac", "1", "-q:a", "5",
         str(pattern)],
        check=True, capture_output=True,
    )
    return sorted(chunk_dir.glob("chunk_*.mp3"))


def _transcribe_api_file(client, audio_path: str, language: str | None, offset: float) -> list[dict]:
    """單一檔案送 Whisper API，回傳帶 offset 修正的 entries。"""
    with open(audio_path, "rb") as f:
        kwargs = {
            "model": "whisper-1",
            "response_format": "verbose_json",
            "timestamp_granularities": ["segment"],
        }
        if language and language != "auto":
            kwargs["language"] = language
        result = client.audio.transcriptions.create(file=f, **kwargs)
    entries = []
    for seg in result.segments:
        entries.append({
            "start": round(seg.start + offset, 3),
            "end":   round(seg.end   + offset, 3),
            "text":  seg.text.strip(),
        })
        print(f"  [{seg.start + offset:7.1f}s] {seg.text.strip()[:80]}", flush=True)
    return entries


def _chunk_duration(chunk_path: Path) -> float:
    """用 ffprobe 取切片時長（秒）。"""
    import subprocess as _sp
    r = _sp.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(chunk_path)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 1200.0


def transcribe_api(audio_path: str, language: str | None) -> list[dict]:
    """Whisper API（OpenAI）轉錄，超過 24 MB 自動切片並行送出。"""
    cfg = get_transcription_settings()
    api_key = cfg.get("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("Whisper API 模式需要 OpenAI API key，請到設定頁填入。")

    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("請先安裝 openai：pip install openai")

    client = OpenAI(api_key=api_key)
    file_size = Path(audio_path).stat().st_size
    t0 = time.time()

    if file_size <= _WHISPER_API_MAX_BYTES:
        print(f"送出 Whisper API 請求：{audio_path}（{file_size//1024//1024} MB）", flush=True)
        entries = _transcribe_api_file(client, audio_path, language, offset=0.0)
    else:
        print(f"檔案 {file_size//1024//1024} MB > 24 MB，切片並行送 API...", flush=True)
        chunk_dir = Path(audio_path).parent / "_chunks"
        try:
            chunks = _split_audio(audio_path, chunk_dir)
            n = len(chunks)
            print(f"切成 {n} 段，計算各段 offset...", flush=True)

            # 先用 ffprobe 算出每段的起始 offset（可並行，但很快，sequential 即可）
            durations = [_chunk_duration(c) for c in chunks]
            offsets = [sum(durations[:i]) for i in range(n)]

            print(f"並行送出 {n} 個 API 請求...", flush=True)
            from concurrent.futures import ThreadPoolExecutor, as_completed

            results: dict[int, list[dict]] = {}
            futures = {}
            with ThreadPoolExecutor(max_workers=n) as pool:
                for i, (chunk, offset) in enumerate(zip(chunks, offsets)):
                    fut = pool.submit(_transcribe_api_file, client, str(chunk), language, offset)
                    futures[fut] = i

                for fut in as_completed(futures):
                    i = futures[fut]
                    results[i] = fut.result()
                    print(f"  ✓ 第 {i+1}/{n} 段完成", flush=True)

            entries = []
            for i in range(n):
                entries.extend(results[i])

        finally:
            import shutil
            if chunk_dir.exists():
                shutil.rmtree(chunk_dir)

    elapsed = time.time() - t0
    print(f"Whisper API 完成（{elapsed:.1f}s，{len(entries)} 段）", flush=True)

    duration_min = (entries[-1]["end"] / 60) if entries else 0
    cost_usd = round(duration_min * 0.006, 4)
    print(f"TRANSCRIPT_COST:{duration_min:.2f}:{cost_usd:.4f}", flush=True)

    return entries


def write_txt(entries, out_path):
    lines = []
    for e in entries:
        m = int(e["start"]) // 60
        s = e["start"] % 60
        lines.append(f"[{m:02d}:{s:05.2f}] {e['text']}")
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"逐字稿 TXT：{out_path}")


def write_json(entries, info, out_path):
    data = {
        "language": getattr(info, "language", "unknown"),
        "language_probability": round(getattr(info, "language_probability", 0), 4),
        "duration": round(getattr(info, "duration", 0), 3),
        "segments": entries,
    }
    Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"逐字稿 JSON：{out_path}")


CONFIG_PATH = PODCAST_ROOT / "config" / "podcasts.json"


def get_transcript_dir(podcast_id: str) -> Path | None:
    """從 config 取得 Obsidian transcript 存放路徑。"""
    try:
        cfg = json.loads(CONFIG_PATH.read_text())
        pod = next((p for p in cfg["podcasts"] if p["id"] == podcast_id), None)
        if pod and pod.get("transcript_dir"):
            return Path(pod["transcript_dir"])
    except Exception:
        pass
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir", help="工作目錄（含 audio.mp3）")
    parser.add_argument("--lang", default="zh", help="語言（預設 zh）")
    parser.add_argument("--model", default="", choices=["", "tiny", "base", "small", "medium", "large-v2", "large-v3"])
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--episode", default="", help="集數標籤（如 EP663），用於逐字稿檔名")
    parser.add_argument("--mode", default="", choices=["", "local", "api"], help="轉錄模式（覆蓋設定檔）")
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    audio_file = next(work_dir.glob("audio.*"), None)
    if not audio_file:
        print(f"ERROR: 找不到 audio.* 在 {work_dir}", file=sys.stderr)
        sys.exit(1)

    cfg = get_transcription_settings()
    mode = args.mode or cfg.get("mode", "local")
    print(f"轉錄模式：{mode}", flush=True)

    if mode == "api":
        entries = transcribe_api(str(audio_file), args.lang if args.lang != "zh" else None)
        # build minimal info-like object for write_json
        class _Info:
            language = "unknown"
            language_probability = 0.0
            duration = 0.0
        info = _Info()
    else:
        setup_cudnn()
        device = detect_device() if args.device == "auto" else args.device
        model = args.model or cfg.get("whisper_model", "medium")
        print(f"使用裝置：{device}", flush=True)
        entries, info = transcribe(str(audio_file), model, args.lang, device)

    # work_dir 內的 transcript（供後續分析用）
    write_txt(entries, work_dir / "transcript.txt")
    write_json(entries, info, work_dir / "transcript.json")

    # Obsidian 永久存放
    podcast_id = os.environ.get("PODCAST_ID", "")
    transcript_dir = get_transcript_dir(podcast_id) if podcast_id else None
    if transcript_dir:
        transcript_dir.mkdir(parents=True, exist_ok=True)
        # 檔名：EP663.txt 或 fallback 到時間戳
        episode_label = args.episode or os.environ.get("EPISODE_LABEL", "")
        if not episode_label:
            from datetime import date
            episode_label = date.today().isoformat()
        safe_label = re.sub(r'[/\\:*?"<>|]', '_', episode_label)
        obsidian_txt = transcript_dir / f"{safe_label}.txt"
        write_txt(entries, obsidian_txt)
        print(f"Obsidian 逐字稿：{obsidian_txt}")

    print("\n轉錄完成。")


if __name__ == "__main__":
    main()
