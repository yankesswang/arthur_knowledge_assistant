"""YouTube API routes."""

import json
import os
import re
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from reading_routes import _load_inbox, _save_inbox
from settings import (
    YT_AUTO_TRANSCRIPT,
    YT_AUTO_TRANSCRIPT_INTERVAL_SECONDS,
    YT_AUTO_TRANSCRIPT_LIMIT_PER_CHANNEL,
    YT_AUTO_TRANSCRIPT_START_DELAY_SECONDS,
    YT_CHANNEL_CFG,
    YT_DATA_DIR,
    YT_QUEUE_FILE,
    YT_SKILL_DIR,
)
from state import (
    _jobs,
    _remote_cache_lock,
    _remote_yt_cache,
    _remote_yt_details_ready,
    _remote_yt_loading,
)
from youtube_services import (
    YT_FLAT_VIDEO_PRINT,
    _backfill_avatars,
    _extract_video_id,
    _yt_fetch_channel_avatar,
    _yt_fetch_channel_id,
    _yt_fetch_rss_dates,
    _yt_is_placeholder_avatar,
    _yt_load_channels,
    _yt_load_processed,
    _yt_load_queue,
    _yt_fetch_video_details,
    _yt_parse_flat_video_line,
    _load_remote_yt_cache_from_db,
    _fetch_remote_yt_videos,
    _yt_parse_condensed,
    _yt_parse_note,
    _yt_scan_videos,
)

router = APIRouter()

_yt_worker_lock = threading.Lock()
_yt_auto_worker_started = False
_yt_active_ids: set[str] = set()
_yt_auto_failed_ids: set[str] = set()


def _yt_transcript_source(video_id: str) -> str:
    vid_dir = YT_DATA_DIR / video_id
    condensed_path = vid_dir / "condensed.txt"
    src_path = vid_dir / "transcript_source.txt"

    if src_path.exists():
        source = src_path.read_text(encoding="utf-8", errors="ignore").strip() or "unknown"
    else:
        source = "cc" if condensed_path.exists() else "unknown"

    if condensed_path.exists() and source in ("none", "unknown"):
        first = condensed_path.read_text(encoding="utf-8", errors="ignore")[:80]
        if first.startswith("[Description"):
            return "description"
        if source == "unknown":
            return "cc"

    return source


def _has_usable_yt_transcript(video_id: str) -> bool:
    condensed_path = YT_DATA_DIR / video_id / "condensed.txt"
    return (
        condensed_path.exists()
        and condensed_path.stat().st_size > 0
        and _yt_transcript_source(video_id) in ("cc", "whisper")
    )


def _run_yt_setup(job: dict, url: str, video_id: str) -> None:
    """Run transcript-note setup.sh, which uses yt-dlp to fetch transcript first."""
    setup_script = YT_SKILL_DIR / "scripts" / "setup.sh"
    if not setup_script.exists():
        raise RuntimeError(f"找不到 setup.sh：{setup_script}")

    job["phase"] = "抓取逐字稿"
    job["progress"] = max(job.get("progress", 0), 5)

    def log(line: str):
        job["log"].append(line)

    proc = subprocess.Popen(
        ["bash", str(setup_script), url],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=os.environ.copy(),
        cwd=str(YT_SKILL_DIR),
    )
    for line in proc.stdout:
        line = line.rstrip()
        if not line:
            continue
        log(line)
        if "VTT:" in line:
            job["progress"] = max(job.get("progress", 0), 35)
        elif "Setup complete" in line:
            job["progress"] = max(job.get("progress", 0), 50)
    proc.wait()

    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp 逐字稿抓取失敗（exit {proc.returncode}）")

    vid_dir = YT_DATA_DIR / video_id
    condensed_path = vid_dir / "condensed.txt"
    src_path = vid_dir / "transcript_source.txt"
    transcript_source = src_path.read_text(encoding="utf-8", errors="ignore").strip() if src_path.exists() else "unknown"
    if not condensed_path.exists():
        raise RuntimeError("yt-dlp setup 完成但沒有產生 condensed.txt")
    if transcript_source == "none":
        job["log"].append("yt-dlp 沒抓到 CC 字幕，準備改用 Whisper 轉錄")

    job["phase"] = "yt-dlp 完成"
    job["progress"] = max(job.get("progress", 0), 50)


def _run_yt_whisper(job: dict, url: str, video_id: str) -> None:
    transcribe_script = YT_SKILL_DIR / "scripts" / "transcribe_yt.py"
    if not transcribe_script.exists():
        raise RuntimeError(f"找不到 transcribe_yt.py：{transcribe_script}")

    work_dir = YT_DATA_DIR / video_id
    work_dir.mkdir(parents=True, exist_ok=True)

    job["phase"] = "Whisper 轉錄中"
    job["progress"] = max(job.get("progress", 0), 55)

    env = os.environ.copy()
    env["YT_URL"] = url

    def run_attempt(model: str, device: str) -> int:
        job["log"].append(f"Whisper attempt: model={model}, device={device}")
        proc = subprocess.Popen(
            [
                "python3.10",
                str(transcribe_script),
                str(work_dir),
                "--lang",
                "auto",
                "--model",
                model,
                "--device",
                device,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            cwd=str(YT_SKILL_DIR),
        )

        segment_count = 0
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            if line.startswith("  ["):
                segment_count += 1
                if segment_count % 25 == 0:
                    job["log"].append(f"Whisper 已轉錄 {segment_count} 段...")
                continue
            job["log"].append(line)
            if "下載音頻" in line:
                job["progress"] = max(job.get("progress", 0), 62)
            elif "載入 Whisper" in line:
                job["progress"] = max(job.get("progress", 0), 70)
            elif "模型就緒" in line:
                job["progress"] = max(job.get("progress", 0), 75)
            elif "轉錄完成" in line:
                job["progress"] = max(job.get("progress", 0), 90)
        proc.wait()
        return proc.returncode

    returncode = run_attempt("medium", "auto")
    if returncode != 0:
        job["log"].append(f"Whisper GPU/auto 失敗（exit {returncode}），改用 CPU small 重試")
        job["progress"] = max(job.get("progress", 0), 56)
        returncode = run_attempt("small", "cpu")

    if returncode != 0:
        raise RuntimeError(f"Whisper 轉錄失敗（exit {returncode}）")
    if not _has_usable_yt_transcript(video_id):
        raise RuntimeError("Whisper 完成但沒有產生可用逐字稿")

    job["phase"] = "Whisper 逐字稿完成"
    job["progress"] = max(job.get("progress", 0), 95)


def _ensure_yt_transcript(job: dict, url: str, video_id: str) -> None:
    if _has_usable_yt_transcript(video_id):
        job["log"].append("已有可用逐字稿，跳過抓取")
        job["phase"] = "逐字稿完成"
        job["progress"] = max(job.get("progress", 0), 60)
        return

    _run_yt_setup(job, url, video_id)
    if _has_usable_yt_transcript(video_id):
        job["phase"] = "逐字稿完成"
        job["progress"] = max(job.get("progress", 0), 60)
        return

    source = _yt_transcript_source(video_id)
    job["log"].append(f"目前逐字稿來源為 {source}，啟動 Whisper fallback")
    _run_yt_whisper(job, url, video_id)
    job["phase"] = "逐字稿完成"
    job["progress"] = max(job.get("progress", 0), 95)


def _canonical_yt_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _yt_remove_from_queue(video_id: str) -> None:
    queue = _yt_load_queue()
    new_queue = [url for url in queue if _extract_video_id(url) != video_id]
    if new_queue == queue:
        return
    YT_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    YT_QUEUE_FILE.write_text(
        "\n".join(new_queue) + ("\n" if new_queue else ""),
        encoding="utf-8",
    )


def _yt_append_queue_urls(urls: list[str]) -> int:
    if not urls:
        return 0

    queue = _yt_load_queue()
    known_ids = {_extract_video_id(url) for url in queue}
    added: list[str] = []

    with _yt_worker_lock:
        active_ids = set(_yt_active_ids)
        failed_ids = set(_yt_auto_failed_ids)

    for url in urls:
        video_id = _extract_video_id(url)
        if (
            not video_id
            or video_id in known_ids
            or video_id in active_ids
            or video_id in failed_ids
            or _has_usable_yt_transcript(video_id)
        ):
            continue
        added.append(_canonical_yt_url(video_id))
        known_ids.add(video_id)

    if not added:
        return 0

    YT_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with YT_QUEUE_FILE.open("a", encoding="utf-8") as f:
        for url in added:
            f.write(url + "\n")
    return len(added)


def _parse_auto_limit(channel_limit) -> int | None:
    raw = str(YT_AUTO_TRANSCRIPT_LIMIT_PER_CHANNEL).strip().lower()
    if raw == "channel":
        raw = str(channel_limit or "5").strip().lower()
    if raw in ("", "none", "all", "0", "-1"):
        return None
    try:
        limit = int(raw)
    except ValueError:
        return 5
    return None if limit <= 0 else limit


def _yt_auto_enqueue_channel_candidates() -> int:
    urls: list[str] = []
    for ch in _yt_load_channels():
        if not ch.get("enabled", True):
            continue
        handle = ch.get("handle", "")
        if not handle:
            continue

        with _remote_cache_lock:
            remote = list(_remote_yt_cache.get(handle, []))
        if not remote:
            remote, _ = _load_remote_yt_cache_from_db(handle)
        if not remote:
            continue

        limit = _parse_auto_limit(ch.get("limit", 5))
        videos = remote if limit is None else remote[:limit]
        for video in videos:
            video_id = video.get("id", "")
            if video_id:
                urls.append(_canonical_yt_url(video_id))

    return _yt_append_queue_urls(urls)


def _run_yt_transcript_job(job: dict, url: str, video_id: str) -> None:
    with _yt_worker_lock:
        if video_id in _yt_active_ids:
            job["status"] = "error"
            job["phase"] = "已有相同影片在處理"
            job["finished_at"] = time.time()
            return
        _yt_active_ids.add(video_id)

    try:
        job["status"] = "running"
        _ensure_yt_transcript(job, url, video_id)
        job["status"] = "done"
        job["phase"] = "逐字稿完成"
        job["progress"] = 100
        _yt_remove_from_queue(video_id)
    except Exception as e:
        job["status"] = "error"
        job["phase"] = "逐字稿失敗"
        job["log"].append(f"✗ 例外：{e}")
        if job.get("type") == "yt_auto_transcript":
            with _yt_worker_lock:
                _yt_auto_failed_ids.add(video_id)
    finally:
        with _yt_worker_lock:
            _yt_active_ids.discard(video_id)
        job["finished_at"] = time.time()


def _yt_active_job_id(video_id: str) -> str:
    matches = [
        job for job in _jobs.values()
        if job.get("video_id") == video_id and job.get("status") in ("pending", "running")
    ]
    if not matches:
        return ""
    matches.sort(key=lambda job: job.get("started_at", 0), reverse=True)
    return matches[0].get("job_id", "")


def _yt_auto_process_once() -> int:
    _yt_auto_enqueue_channel_candidates()

    processed_count = 0
    for url in list(_yt_load_queue()):
        video_id = _extract_video_id(url)
        if not video_id:
            continue

        with _yt_worker_lock:
            should_skip = video_id in _yt_active_ids or video_id in _yt_auto_failed_ids
        if should_skip:
            continue

        if _has_usable_yt_transcript(video_id):
            _yt_remove_from_queue(video_id)
            continue

        # try to find title from remote cache
        video_title = ""
        with _remote_cache_lock:
            for cached in _remote_yt_cache.values():
                match = next((v for v in cached if v.get("id") == video_id), None)
                if match:
                    video_title = match.get("title_zh") or match.get("title", "")
                    break

        job_id = f"yt-auto-{video_id[:8]}-{str(uuid.uuid4())[:4]}"
        _jobs[job_id] = {
            "job_id": job_id,
            "type": "yt_auto_transcript",
            "video_id": video_id,
            "url": url,
            "title": video_title,
            "status": "pending",
            "phase": "自動排隊中",
            "progress": 0,
            "log": [],
            "started_at": time.time(),
        }
        _run_yt_transcript_job(_jobs[job_id], url, video_id)
        processed_count += 1

    return processed_count


def start_youtube_auto_transcript_worker() -> None:
    global _yt_auto_worker_started
    if not YT_AUTO_TRANSCRIPT:
        print("[yt-auto] disabled")
        return

    with _yt_worker_lock:
        if _yt_auto_worker_started:
            return
        _yt_auto_worker_started = True

    def _loop():
        if YT_AUTO_TRANSCRIPT_START_DELAY_SECONDS > 0:
            time.sleep(YT_AUTO_TRANSCRIPT_START_DELAY_SECONDS)
        while True:
            try:
                count = _yt_auto_process_once()
                if count:
                    print(f"[yt-auto] processed {count} transcript job(s)")
            except Exception as e:
                print(f"[yt-auto] error: {e}")
            time.sleep(max(60, YT_AUTO_TRANSCRIPT_INTERVAL_SECONDS))

    threading.Thread(target=_loop, daemon=True).start()


# ── YouTube API routes ───────────────────────────────────────────────────────

@router.get("/api/youtube/channels/{handle}/remote-videos")
def yt_remote_videos(handle: str, limit: int = 0):
    """用 yt-dlp 抓頻道影片列表，比對本地已處理狀態"""
    handle = urllib.parse.unquote(handle)
    if not handle.startswith("@"):
        handle = "@" + handle

    channel_url = f"https://www.youtube.com/{handle}/videos"
    playlist_args = ["--playlist-items", f"1-{limit}"] if limit > 0 else []
    try:
        r = subprocess.run(
            ["yt-dlp", "--flat-playlist", *playlist_args,
             "--print", YT_FLAT_VIDEO_PRINT,
             channel_url],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0 and not r.stdout.strip():
            raise HTTPException(502, f"yt-dlp 失敗：{r.stderr[:200]}")
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "yt-dlp 超時，請稍後再試")

    processed  = _yt_load_processed()
    local_ids  = {d.name for d in YT_DATA_DIR.iterdir() if d.is_dir()} if YT_DATA_DIR.exists() else set()
    queued_ids = {_extract_video_id(u) for u in _yt_load_queue()} - {""}

    channel_id = _yt_fetch_channel_id(handle)
    rss_dates: dict[str, str] = {}
    if channel_id:
        rss_dates = _yt_fetch_rss_dates(channel_id)

    videos = []
    for line in r.stdout.strip().splitlines():
        video = _yt_parse_flat_video_line(line, rss_dates)
        if not video:
            continue

        video_id      = video["id"]
        has_local     = video_id in local_ids
        analysis_path = YT_DATA_DIR / video_id / "analysis.json"
        title_zh      = video["title"]
        if has_local and analysis_path.exists():
            try:
                title_zh = json.loads(analysis_path.read_text()).get("title_zh") or video["title"]
            except Exception:
                pass

        videos.append({
            **video,
            "title_zh":     title_zh,
            "has_local":    has_local,
            "has_analysis": has_local and analysis_path.exists(),
            "is_processed": video_id in processed,
            "is_queued":    video_id in queued_ids,
        })

    missing_detail_ids = [
        v["id"] for v in videos
        if not v.get("upload_date") or not v.get("duration")
    ]
    details = _yt_fetch_video_details(missing_detail_ids)
    for video in videos:
        detail = details.get(video["id"], {})
        if not video.get("upload_date"):
            video["upload_date"] = detail.get("upload_date", "")
        if not video.get("duration"):
            video["duration"] = detail.get("duration", "")

    # 取頻道頭像（優先從 cache，cache miss 則同步抓一次）
    avatar = _yt_fetch_channel_avatar(handle)

    return {"handle": handle, "videos": videos, "avatar": avatar, "channel_id": channel_id}


@router.get("/api/youtube/channels")
def yt_list_channels():
    channels    = _yt_load_channels()
    local_vids  = _yt_scan_videos()
    local_by_id = {v["id"]: v for v in local_vids}

    result = []
    for ch in channels:
        handle = ch.get("handle", "")
        name   = ch.get("name", handle)

        # 遠端快取
        with _remote_cache_lock:
            remote = list(_remote_yt_cache.get(handle, []))
            remote_loading = handle in _remote_yt_loading
            details_ready = handle in _remote_yt_details_ready

        needs_db_backfill = (
            not remote
            or not details_ready
            or any(not v.get("upload_date") or not v.get("duration") for v in remote)
        )
        if needs_db_backfill:
            cached_remote, meta = _load_remote_yt_cache_from_db(handle)
            cached_by_id = {v["id"]: v for v in cached_remote}
            if not remote:
                remote = cached_remote
                remote_loading = False
            elif cached_remote:
                merged_remote = []
                seen_remote_ids = set()
                for r in remote:
                    cached = cached_by_id.get(r.get("id", ""))
                    if cached:
                        r = {
                            **r,
                            "upload_date": r.get("upload_date") or cached.get("upload_date", ""),
                            "duration": r.get("duration") or cached.get("duration", ""),
                            "title_zh": r.get("title_zh") or cached.get("title_zh") or cached.get("title", ""),
                        }
                    merged_remote.append(r)
                    if r.get("id"):
                        seen_remote_ids.add(r["id"])
                for cached in cached_remote:
                    if cached.get("id") not in seen_remote_ids:
                        merged_remote.append(cached)
                remote = merged_remote
            details_ready = details_ready or bool(meta.get("details_ready"))

        # 本地歸屬此頻道的影片
        ch_local = [v for v in local_vids
                    if v["channel"].lower() == name.lower()
                    or v["channel"].replace(" ", "").lower() == name.replace(" ", "").lower()]

        # 合併
        merged: list[dict] = []
        seen_ids: set[str] = set()

        for r in remote:
            vid_id   = r["id"]
            local_v  = local_by_id.get(vid_id)
            merged.append({
                "id":           vid_id,
                "title":        r["title"],
                "title_zh":     local_v["title_zh"] if local_v and local_v.get("title_zh") else r["title_zh"],
                "channel":      name,
                "upload_date":  local_v["upload_date"] if local_v and local_v.get("upload_date") else r["upload_date"],
                "duration":     r["duration"],
                "url":          r["url"],
                "thumbnail":    r["thumbnail"],
                "has_note":     bool(local_v and local_v.get("has_note")),
                "has_analysis": bool(local_v and local_v.get("has_analysis")),
                "has_transcript": bool(local_v and local_v.get("has_transcript")),
                "is_local":     local_v is not None,
                "is_processed": bool(local_v and local_v.get("is_processed")),
            })
            seen_ids.add(vid_id)

        # 補上本地有但遠端沒覆蓋到的
        for lv in ch_local:
            if lv["id"] not in seen_ids:
                merged.append({**lv, "is_local": True})

        # 按日期降序
        merged.sort(key=lambda v: v.get("upload_date", ""), reverse=True)

        result.append({
            "handle":       handle,
            "name":         name,
            "enabled":      ch.get("enabled", True),
            "avatar":       ch.get("avatar", ""),
            "video_count":  len(merged),
            "note_count":   sum(1 for v in merged if v["has_note"]),
            "remote_ready": bool(remote),
            "remote_loading": remote_loading,
            "dates_ready":   bool(remote) and details_ready,
            "videos":       merged,
        })

    return result


@router.get("/api/youtube/videos")
def yt_list_videos():
    return _yt_scan_videos()


@router.get("/api/youtube/videos/{video_id}/note")
def yt_get_note(video_id: str):
    vid_dir = YT_DATA_DIR / video_id
    has_analysis  = (vid_dir / "analysis.json").exists()
    has_note_ptr  = (vid_dir / "note_path.txt").exists() and Path(
        (vid_dir / "note_path.txt").read_text().strip()
    ).exists()
    if not has_analysis and not has_note_ptr:
        raise HTTPException(404, "此影片尚無分析結果")
    return _yt_parse_note(video_id)


@router.get("/api/youtube/videos/{video_id}/note-raw")
def yt_get_note_raw(video_id: str):
    """回傳 Obsidian .md 筆記的原始文字（供複製用）"""
    vid_dir = YT_DATA_DIR / video_id
    note_ptr = vid_dir / "note_path.txt"
    if note_ptr.exists():
        md_path = Path(note_ptr.read_text().strip())
        if md_path.exists():
            return {"markdown": md_path.read_text(encoding="utf-8"), "path": str(md_path)}
    raise HTTPException(404, "此影片尚無 Obsidian 筆記檔案")


@router.patch("/api/youtube/videos/{video_id}/highlight")
def yt_highlight(video_id: str, body: dict):
    """在 .md 裡把選取的文字包上或移除 ==...==（Obsidian 螢光筆語法）"""
    from podcast_routes import _apply_highlight
    text   = (body.get("text") or "").strip()
    remove = body.get("remove", False)
    if not text:
        raise HTTPException(400, "缺少 text")
    vid_dir = YT_DATA_DIR / video_id
    note_ptr = vid_dir / "note_path.txt"
    if not note_ptr.exists():
        raise HTTPException(404, "此影片尚無筆記")
    md_path = Path(note_ptr.read_text().strip())
    if not md_path.exists():
        raise HTTPException(404, "筆記檔案不存在")
    content = md_path.read_text(encoding="utf-8")
    if remove:
        if f"=={text}==" not in content:
            return {"status": "not_found"}
        md_path.write_text(content.replace(f"=={text}==", text, 1), encoding="utf-8")
        return {"status": "removed"}
    new_content = _apply_highlight(content, text)
    if new_content is None:
        raise HTTPException(422, "在筆記中找不到此文字")
    if new_content == content:
        return {"status": "already_highlighted"}
    md_path.write_text(new_content, encoding="utf-8")
    return {"status": "ok"}


@router.delete("/api/youtube/videos/{video_id}/note")
def yt_delete_note(video_id: str):
    """刪除 Obsidian 筆記檔案"""
    vid_dir = YT_DATA_DIR / video_id
    note_ptr = vid_dir / "note_path.txt"
    if not note_ptr.exists():
        raise HTTPException(404, "此影片尚無筆記")
    md_path = Path(note_ptr.read_text().strip())
    if not md_path.exists():
        raise HTTPException(404, "筆記檔案不存在")
    md_path.unlink()
    note_ptr.unlink()
    # also remove analysis.json so it can be regenerated
    analysis_path = vid_dir / "analysis.json"
    if analysis_path.exists():
        analysis_path.unlink()
    return {"deleted": str(md_path)}


@router.post("/api/youtube/videos/{video_id}/analyze")
def yt_start_analyze(video_id: str):
    """觸發 claude -p 自動分析逐字稿 → 產生 analysis.json + Obsidian 筆記"""
    vid_dir = YT_DATA_DIR / video_id

    analyze_script = YT_SKILL_DIR / "scripts" / "analyze.py"
    if not analyze_script.exists():
        raise HTTPException(500, f"找不到 analyze.py：{analyze_script}")

    job_id = f"yt-{video_id[:8]}-{str(uuid.uuid4())[:4]}"
    _jobs[job_id] = {
        "job_id":     job_id,
        "type":       "yt_analyze",
        "video_id":   video_id,
        "status":     "pending",
        "phase":      "排隊中",
        "progress":   0,
        "log":        [],
        "started_at": time.time(),
    }

    def _run():
        job = _jobs[job_id]
        job["status"] = "running"
        job["phase"]  = "準備逐字稿"

        def log(line):
            job["log"].append(line)

        try:
            _ensure_yt_transcript(job, f"https://www.youtube.com/watch?v={video_id}", video_id)

            job["phase"]    = "分析中"
            job["progress"] = max(job.get("progress", 0), 65)
            proc = subprocess.Popen(
                ["python3.10", str(analyze_script), video_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=os.environ.copy(),
                cwd=str(YT_SKILL_DIR),
            )
            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                if line.startswith("PROGRESS:"):
                    parts = line.split(":", 2)
                    if len(parts) >= 2:
                        try:
                            # YT analyze runs after transcript (which ends at ~65%), so remap 5-95 → 65-98
                            raw = int(parts[1])
                            job["progress"] = max(job.get("progress", 0), 65 + int(raw * 0.33))
                        except ValueError:
                            pass
                        if len(parts) >= 3:
                            job["phase"] = parts[2]
                else:
                    log(line)
            proc.wait()

            if proc.returncode == 0:
                job["status"]   = "done"
                job["phase"]    = "完成"
                job["progress"] = 100
                note_ptr = vid_dir / "note_path.txt"
                note_path = ""
                if note_ptr.exists():
                    note_path = note_ptr.read_text().strip()
                    log(f"筆記：{note_path}")
                # 取標題
                title_zh = video_id
                analysis_path = vid_dir / "analysis.json"
                if analysis_path.exists():
                    try:
                        title_zh = json.loads(analysis_path.read_text()).get("title_zh") or video_id
                    except Exception:
                        pass
                info_path = vid_dir / "info.json"
                channel = ""
                pub_date = ""
                thumbnail = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
                if info_path.exists():
                    try:
                        info = json.loads(info_path.read_text())
                        channel = info.get("channel", "")
                        pub_date = info.get("upload_date", "")
                    except Exception:
                        pass
                inbox_item = {
                    "id":        f"yt:{video_id}",
                    "type":      "yt",
                    "video_id":  video_id,
                    "title":     title_zh,
                    "channel":   channel,
                    "pub_date":     pub_date,
                    "thumbnail":    thumbnail,
                    "note_path":    note_path,
                    "note_created": int(Path(note_path).stat().st_ctime) if note_path and Path(note_path).exists() else 0,
                    "url":          f"https://www.youtube.com/watch?v={video_id}",
                }
                items = _load_inbox()
                if not any(i.get("id") == inbox_item["id"] for i in items):
                    inbox_item["ts"] = time.time()
                    items.insert(0, inbox_item)
                    _save_inbox(items)
            else:
                job["status"] = "error"
                job["phase"]  = "分析失敗"
        except Exception as e:
            job["status"] = "error"
            job["phase"]  = "失敗"
            log(f"✗ 例外：{e}")

        job["finished_at"] = time.time()

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return {"job_id": job_id, "video_id": video_id}


@router.get("/api/youtube/videos/{video_id}/transcript")
def yt_get_transcript(video_id: str):
    segments = _yt_parse_condensed(video_id)
    if not segments:
        raise HTTPException(404, "此影片無壓縮逐字稿")
    info_path = YT_DATA_DIR / video_id / "info.json"
    duration  = json.loads(info_path.read_text()).get("duration") if info_path.exists() else None
    return {"segments": segments, "duration": duration, "video_id": video_id}


@router.get("/api/youtube/queue")
def yt_get_queue():
    return {"queue": _yt_load_queue(), "processed_count": len(_yt_load_processed())}


@router.post("/api/youtube/queue")
def yt_add_to_queue(body: dict):
    url = (body.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "缺少 url")
    video_id = _extract_video_id(url)
    if not video_id:
        raise HTTPException(422, "無法解析 YouTube video ID，請確認網址格式")

    processed = _yt_load_processed()
    if video_id in processed and _has_usable_yt_transcript(video_id):
        raise HTTPException(409, f"此影片已處理過（{video_id}）")

    with _yt_worker_lock:
        is_active = video_id in _yt_active_ids
        _yt_auto_failed_ids.discard(video_id)
    active_job_id = _yt_active_job_id(video_id) if is_active else ""
    if active_job_id:
        return {
            "video_id": video_id,
            "url": url,
            "queue_size": len(_yt_load_queue()),
            "already_queued": True,
            "job_id": active_job_id,
        }

    queue = _yt_load_queue()
    already_queued = url in queue or any(video_id in q for q in queue)

    if not already_queued:
        YT_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with YT_QUEUE_FILE.open("a", encoding="utf-8") as f:
            f.write(url + "\n")

    # try to find title from remote cache
    setup_title = ""
    with _remote_cache_lock:
        for cached in _remote_yt_cache.values():
            match = next((v for v in cached if v.get("id") == video_id), None)
            if match:
                setup_title = match.get("title_zh") or match.get("title", "")
                break

    job_id = f"yt-setup-{video_id[:8]}-{str(uuid.uuid4())[:4]}"
    _jobs[job_id] = {
        "job_id":     job_id,
        "type":       "yt_setup",
        "video_id":   video_id,
        "url":        url,
        "title":      setup_title,
        "status":     "pending",
        "phase":      "排隊中",
        "progress":   0,
        "log":        [],
        "started_at": time.time(),
    }

    def _run():
        job = _jobs[job_id]
        _run_yt_transcript_job(job, url, video_id)

    threading.Thread(target=_run, daemon=True).start()

    return {
        "video_id": video_id,
        "url": url,
        "queue_size": len(queue) + (0 if already_queued else 1),
        "already_queued": already_queued,
        "job_id": job_id,
    }


@router.delete("/api/youtube/queue")
def yt_clear_queue_item(body: dict):
    url = (body.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "缺少 url")
    queue = _yt_load_queue()
    new_q = [q for q in queue if q != url]
    YT_QUEUE_FILE.write_text("\n".join(new_q) + ("\n" if new_q else ""), encoding="utf-8")
    return {"removed": url, "queue_size": len(new_q)}


@router.get("/api/youtube/search-channels")
def yt_search_channels(q: str, limit: int = 8):
    """用 yt-dlp 搜尋 YouTube 頻道，回傳去重的頻道清單（含頭像、handle）"""
    if not q or len(q.strip()) < 2:
        raise HTTPException(400, "搜尋關鍵字太短")
    try:
        r = subprocess.run(
            ["yt-dlp", f"ytsearch{limit * 3}:{q.strip()}",
             "--flat-playlist",
             "--print", "%(channel)s|%(channel_id)s|%(uploader_id)s"],
            capture_output=True, text=True, timeout=20,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "搜尋超時")

    seen_ids: set[str] = set()
    results  = []
    for line in r.stdout.strip().splitlines():
        parts = line.split("|")
        if len(parts) < 3:
            continue
        name       = parts[0].strip()
        channel_id = parts[1].strip()
        uploader   = parts[2].strip()  # @Handle

        if not channel_id or channel_id == "NA" or channel_id in seen_ids:
            continue
        seen_ids.add(channel_id)

        handle = uploader if uploader.startswith("@") else f"@{uploader}"
        if handle == "@NA":
            continue
        avatar = _yt_fetch_channel_avatar(handle)
        results.append({
            "name":       name,
            "handle":     handle,
            "channel_id": channel_id,
            "thumbnail":  avatar,
            "avatar":     avatar,
        })
        if len(results) >= limit:
            break

    return results


@router.post("/api/youtube/channels")
def yt_add_channel(body: dict):
    raw    = (body.get("handle") or "").strip()
    name   = (body.get("name") or "").strip()
    if not raw:
        raise HTTPException(400, "缺少 handle（如 @ChannelName）")

    # 若使用者貼了完整 URL，自動抽出 @handle 部分
    url_match = re.search(r'youtube\.com/(@[A-Za-z0-9_\-\.]+)', raw)
    if url_match:
        handle = url_match.group(1)
    else:
        handle = raw if raw.startswith("@") else "@" + raw

    # handle 只允許 @英數字底線連字號，拒絕含 URL 或空格的值
    if not re.match(r'^@[A-Za-z0-9_\-\.]{2,50}$', handle):
        raise HTTPException(422, f"無效的 handle 格式：{handle}（應為 @ChannelName）")

    YT_CHANNEL_CFG.parent.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(YT_CHANNEL_CFG.read_text()) if YT_CHANNEL_CFG.exists() else {"channels": []}
    channels = cfg.get("channels", [])

    if any(c["handle"] == handle for c in channels):
        raise HTTPException(409, f"頻道 {handle} 已存在")

    channel_id = (body.get("channel_id") or "").strip()
    avatar     = (body.get("avatar") or "").strip()
    if _yt_is_placeholder_avatar(avatar):
        avatar = _yt_fetch_channel_avatar(handle, force=True)
    new_ch = {
        "handle":     handle,
        "name":       name or handle.lstrip("@"),
        "limit":      5,
        "enabled":    True,
        **({"channel_id": channel_id} if channel_id else {}),
        **({"avatar":     avatar}     if avatar     else {}),
    }
    channels.append(new_ch)
    cfg["channels"] = channels
    YT_CHANNEL_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    def _prime_new_channel():
        try:
            limit = _parse_auto_limit(new_ch.get("limit", 5))
            videos = _fetch_remote_yt_videos(handle, limit)
            _yt_append_queue_urls([v["url"] for v in videos if v.get("url")])
            _yt_auto_process_once()
        except Exception as e:
            print(f"[yt-auto] new channel {handle} error: {e}")

    threading.Thread(target=_prime_new_channel, daemon=True).start()
    return new_ch


@router.delete("/api/youtube/channels/{handle}")
def yt_remove_channel(handle: str):
    handle = urllib.parse.unquote(handle)
    if not YT_CHANNEL_CFG.exists():
        raise HTTPException(404, "頻道設定不存在")
    cfg      = json.loads(YT_CHANNEL_CFG.read_text())
    channels = cfg.get("channels", [])
    new_list = [c for c in channels if c["handle"] != handle]
    if len(new_list) == len(channels):
        raise HTTPException(404, f"找不到頻道 {handle}")
    cfg["channels"] = new_list
    YT_CHANNEL_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"deleted": handle}


@router.get("/api/proxy-image")
def proxy_image(url: str):
    """Proxy external images (e.g. yt3.googleusercontent.com) to avoid browser referrer blocks."""
    allowed_prefixes = (
        "https://yt3.googleusercontent.com/",
        "https://yt3.ggpht.com/",
        "https://img.youtube.com/",
        "https://i.ytimg.com/",
    )
    if not any(url.startswith(p) for p in allowed_prefixes):
        raise HTTPException(400, "不允許的圖片來源")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.youtube.com/"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
            content_type = r.headers.get("Content-Type", "image/jpeg")
    except Exception as e:
        raise HTTPException(502, f"無法取得圖片：{e}")
    return Response(content=data, media_type=content_type, headers={"Cache-Control": "public, max-age=86400"})


@router.post("/api/youtube/channels/refresh-avatars")
def yt_refresh_avatars():
    """手動觸發補抓所有缺 avatar 的頻道（背景執行）。"""
    _backfill_avatars()
    return {"status": "started"}
