"""YouTube transcript-note data access helpers."""

import json
import re
import subprocess
import threading
import time
import urllib.request
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from cache_store import add_youtube_queue_url, load_cached_youtube_videos, load_youtube_queue, save_cached_youtube_videos
from settings import (
    YT_CHANNEL_CFG,
    YT_DATA_DIR,
    YT_DETAIL_BATCH_SIZE,
    YT_DETAIL_LIMIT,
    YT_DETAIL_WORKERS,
    YT_NOTE_DIR,
    YT_PROC_FILE,
    YT_QUEUE_FILE,
)
from state import _remote_cache_lock, _remote_yt_cache, _remote_yt_details_ready, _remote_yt_loading

YT_FLAT_VIDEO_PRINT = "%(id)s\t%(title)s\t%(upload_date)s\t%(duration)s\t%(duration_string)s"
YT_VIDEO_DETAIL_PRINT = "%(id)s\t%(upload_date)s\t%(duration)s\t%(duration_string)s\t%(timestamp)s\t%(release_timestamp)s"
YT_PLACEHOLDER_AVATAR = "https://img.youtube.com/vi/_placeholder/default.jpg"

# ── YouTube helpers ─────────────────────────────────────────────────────────

def _yt_load_channels() -> list[dict]:
    if not YT_CHANNEL_CFG.exists():
        return []
    return json.loads(YT_CHANNEL_CFG.read_text()).get("channels", [])

def _yt_load_queue() -> list[str]:
    queue = load_youtube_queue()
    if YT_QUEUE_FILE.exists():
        for url in [l.strip() for l in YT_QUEUE_FILE.read_text().splitlines() if l.strip()]:
            video_id = _extract_video_id(url)
            if video_id:
                add_youtube_queue_url(video_id, url)
        queue = load_youtube_queue()
    return queue

def _yt_load_processed() -> set[str]:
    if not YT_PROC_FILE.exists():
        return set()
    return {l.strip() for l in YT_PROC_FILE.read_text().splitlines() if l.strip()}

def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from any URL format."""
    patterns = [
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"youtube\.com/watch\?.*v=([A-Za-z0-9_-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
        r"youtube\.com/live/([A-Za-z0-9_-]{11})",
        r"youtube\.com/embed/([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return ""

def _yt_read_obsidian_note(md_path: str) -> dict:
    """從 Obsidian .md 取 title、channel、upload_date、topic、tags。"""
    try:
        text = Path(md_path).read_text(encoding="utf-8", errors="ignore")
        fm   = {}
        m    = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
        if m:
            for line in m.group(1).splitlines():
                kv = re.match(r'^(\w+):\s*"?(.+?)"?\s*$', line)
                if kv:
                    fm[kv.group(1)] = kv.group(2)
        tags = re.findall(r'  - (.+)', m.group(1) if m else "")
        tags = [t for t in tags if t not in ("影片筆記", "YouTube", "逐字稿筆記")]
        source = fm.get("source", "")
        if _extract_video_id(source):
            source = ""  # source 是 URL 而非頻道名
        return {
            "title":      fm.get("title", ""),
            "channel":    source or fm.get("channel", ""),
            "date":       fm.get("date", "") or fm.get("created", ""),
            "topic":      fm.get("topic", ""),
            "tags":       tags,
        }
    except Exception:
        return {}


def _yt_extract_id_from_note(path: Path) -> str:
    """從 Obsidian .md 的 frontmatter url:/source: 或 body 取 YouTube video ID。"""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    fm_m = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
    if fm_m:
        for field in ("url", "source"):
            m = re.search(rf'^{field}:\s*"?([^"\n]+)"?\s*$', fm_m.group(1), re.MULTILINE)
            if m:
                vid = _extract_video_id(m.group(1).strip())
                if vid:
                    return vid
    m = re.search(r'(?:youtube\.com/watch\?.*?v=|youtu\.be/)([A-Za-z0-9_-]{11})', text)
    return m.group(1) if m else ""


def _yt_entry_from_obsidian_note(path: Path, video_id: str, processed: set) -> dict:
    """從 Obsidian .md 建構與 _yt_scan_videos() 相容的 video entry dict。"""
    meta = _yt_read_obsidian_note(str(path))
    title = meta.get("title", "") or path.stem
    channel = meta.get("channel", "")
    if not channel and path.parent.name not in ("影片筆記", "未分類"):
        channel = path.parent.name
    upload_date = _yt_format_upload_date(meta.get("date", "").replace("-", "") or "")
    return {
        "id":                video_id,
        "title_zh":          title,
        "channel":           channel,
        "upload_date":       upload_date,
        "has_analysis":      False,
        "has_transcript":    False,
        "transcript_source": "none",
        "has_note":          True,
        "note_path":         str(path),
        "url":               f"https://www.youtube.com/watch?v={video_id}",
        "thumbnail":         f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
        "topic":             meta.get("topic", ""),
        "tags":              meta.get("tags", []),
        "reading_list_category": "",
        "is_processed":      video_id in processed,
    }


def _yt_find_obsidian_note(video_id: str) -> Path | None:
    """在 YT_NOTE_DIR 中找含有指定 video ID 的 .md 檔。"""
    if not YT_NOTE_DIR.exists():
        return None
    for md_path in YT_NOTE_DIR.glob("**/*.md"):
        if _yt_extract_id_from_note(md_path) == video_id:
            return md_path
    return None


_obsidian_index_cache: dict[str, Path] = {}
_obsidian_index_ts: float = 0.0
_OBSIDIAN_INDEX_TTL = 120.0  # seconds


def _yt_build_obsidian_index() -> dict[str, Path]:
    """掃描 YT_NOTE_DIR，建立 video_id → Path 索引，TTL 120s 快取避免每次 poll 都重掃。"""
    global _obsidian_index_cache, _obsidian_index_ts
    now = time.monotonic()
    if _obsidian_index_cache and now - _obsidian_index_ts < _OBSIDIAN_INDEX_TTL:
        return _obsidian_index_cache
    index: dict[str, Path] = {}
    if YT_NOTE_DIR.exists():
        for md_path in YT_NOTE_DIR.glob("**/*.md"):
            vid = _yt_extract_id_from_note(md_path)
            if vid:
                index[vid] = md_path
    _obsidian_index_cache = index
    _obsidian_index_ts = now
    return index


def _yt_scan_videos() -> list[dict]:
    """掃描 data/transcripts/ 以及 Obsidian 影片筆記資料夾，合併成完整影片列表。"""
    videos: list[dict] = []
    seen_ids: set[str] = set()
    processed = _yt_load_processed()

    # 預先建立 Obsidian 索引，避免在 loop 內重複掃檔
    obsidian_index = _yt_build_obsidian_index()

    # 1. 掃本地 transcript data 目錄
    if YT_DATA_DIR.exists():
        for vid_dir in sorted(YT_DATA_DIR.iterdir(), reverse=True):
            if not vid_dir.is_dir():
                continue
            video_id = vid_dir.name

            info_path      = vid_dir / "info.json"
            analysis_path  = vid_dir / "analysis.json"
            condensed_path = vid_dir / "condensed.txt"
            note_ptr_path  = vid_dir / "note_path.txt"

            info     = json.loads(info_path.read_text())     if info_path.exists()     else {}
            analysis = json.loads(analysis_path.read_text()) if analysis_path.exists() else {}

            # 優先讀 note_path.txt，其次查 Obsidian 索引
            note_path = None
            note_meta = {}
            if note_ptr_path.exists():
                candidate = note_ptr_path.read_text().strip()
                if Path(candidate).exists():
                    note_path = candidate
                    note_meta = _yt_read_obsidian_note(candidate)

            if note_path is None and video_id in obsidian_index:
                note_path = str(obsidian_index[video_id])
                note_meta = _yt_read_obsidian_note(note_path)

            # transcript source
            src_path = vid_dir / "transcript_source.txt"
            transcript_source = src_path.read_text().strip() if src_path.exists() else (
                "cc" if condensed_path.exists() else "none"
            )
            if condensed_path.exists() and transcript_source == "none":
                first = condensed_path.read_text(encoding="utf-8", errors="ignore")[:30]
                transcript_source = "description" if "[Description" in first else "cc"

            seen_ids.add(video_id)
            videos.append({
                "id":                video_id,
                "title_zh":          (analysis.get("title_zh") or note_meta.get("title") or info.get("title", video_id)),
                "channel":           info.get("channel") or note_meta.get("channel", ""),
                "upload_date":       info.get("upload_date") or note_meta.get("date", ""),
                "has_analysis":      analysis_path.exists(),
                "has_transcript":    condensed_path.exists() and transcript_source in ("cc", "whisper"),
                "transcript_source": transcript_source,
                "has_note":          note_path is not None,
                "note_path":         note_path,
                "url":               f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail":         f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                "topic":             analysis.get("topic") or note_meta.get("topic", ""),
                "tags":              analysis.get("tags") or note_meta.get("tags", []),
                "reading_list_category": analysis.get("reading_list_category", ""),
                "is_processed":      video_id in processed,
            })

    # 2. 補上只有 Obsidian 筆記、沒有本地 data 目錄的影片
    for video_id, md_path in sorted(obsidian_index.items(),
                                    key=lambda kv: kv[1].stat().st_mtime, reverse=True):
        if video_id in seen_ids:
            continue
        entry = _yt_entry_from_obsidian_note(md_path, video_id, processed)
        if entry:
            seen_ids.add(video_id)
            videos.append(entry)

    return videos

def _yt_parse_note(video_id: str) -> dict:
    """Parse analysis.json（or Obsidian .md）+ info.json into frontend-ready dict."""
    vid_dir       = YT_DATA_DIR / video_id
    analysis_path = vid_dir / "analysis.json"
    info_path     = vid_dir / "info.json"
    note_ptr_path = vid_dir / "note_path.txt"

    analysis = json.loads(analysis_path.read_text()) if analysis_path.exists() else {}
    info     = json.loads(info_path.read_text())     if info_path.exists()     else {}

    # 優先讀 note_path.txt 指向的 .md
    if not analysis and note_ptr_path.exists():
        md_path = note_ptr_path.read_text().strip()
        if Path(md_path).exists():
            analysis = _yt_build_analysis_from_md(md_path, video_id)

    # fallback：掃 Obsidian vault
    if not analysis:
        obsidian_note = _yt_find_obsidian_note(video_id)
        if obsidian_note:
            analysis = _yt_build_analysis_from_md(str(obsidian_note), video_id)
            if not info:
                meta = _yt_read_obsidian_note(str(obsidian_note))
                info = {
                    "channel":     meta.get("channel", ""),
                    "duration":    "",
                    "upload_date": _yt_format_upload_date(meta.get("date", "").replace("-", "") or ""),
                    "title":       meta.get("title", video_id),
                }

    return {
        "title_zh":     analysis.get("title_zh") or info.get("title", video_id),
        "topic":        analysis.get("topic", ""),
        "tags":         analysis.get("tags", []),
        "tldr":         analysis.get("tldr", {}),
        "sections":     analysis.get("sections", []),
        "key_insights": analysis.get("key_insights", []),
        "data_table":   analysis.get("data_table", []),
        "_meta": {
            "channel":    info.get("channel", ""),
            "duration":   info.get("duration", ""),
            "upload_date": info.get("upload_date", ""),
            "video_id":   video_id,
            "url":        f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail":  f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
        },
    }


def _yt_build_analysis_from_md(md_path: str, video_id: str) -> dict:
    """從 Obsidian .md 建構 analysis-like dict（供 detail view 使用）。"""
    try:
        text = Path(md_path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}

    # frontmatter
    fm, body = {}, text
    fm_m = re.match(r'^---\n(.*?)\n---\n?', text, re.DOTALL)
    if fm_m:
        body = text[fm_m.end():]
        for line in fm_m.group(1).splitlines():
            kv = re.match(r'^(\w+):\s*"?(.+?)"?\s*$', line)
            if kv:
                fm[kv.group(1)] = kv.group(2)
        tags = [t for t in re.findall(r'  - (.+)', fm_m.group(1))
                if t not in ("影片筆記", "YouTube", "逐字稿筆記")]
    else:
        tags = []

    # TL;DR block
    tldr = {}
    tldr_block = re.search(r'## TL;DR\n(.*?)(?=\n## |\Z)', body, re.DOTALL)
    if tldr_block:
        key_map = {
            "核心主張": "核心主張", "關鍵機制": "關鍵機制_問題",
            "重要結論": "重要數字", "重要數字": "重要數字",
            "適用條件": "風險_限制", "操作建議": "操作建議",
        }
        for line in tldr_block.group(1).splitlines():
            m2 = re.match(r'- \*\*(.+?)\*\*[：:]\s*(.+)', line)
            if m2:
                raw_key = m2.group(1).split("/")[0].strip()
                for k, v in key_map.items():
                    if k in raw_key:
                        tldr[v] = m2.group(2).strip()
                        break

    # sections（### N. ...）
    sections = []
    for sec in re.finditer(
        r'### (\d+)\.\s*(?:\[(\d+:\d+)\]\s*)?(.*?)\n(.*?)(?=\n### \d+\.|\n## |\Z)',
        body, re.DOTALL
    ):
        points = [l.rstrip() for l in sec.group(4).strip().splitlines() if l.strip()]
        sections.append({"title": sec.group(3).strip(), "start_time": sec.group(2) or "", "content_points": points})

    # key insights
    insights = []
    ins_m = re.search(r'## 關鍵洞見\n(.*?)(?=\n## |\Z)', body, re.DOTALL)
    if ins_m:
        for line in ins_m.group(1).splitlines():
            m3 = re.match(r'- (.+)', line.strip())
            if m3:
                insights.append(m3.group(1))

    # data table
    data_table = []
    tbl_m = re.search(r'## 附[：:]關鍵數據速查\n(.*?)(?=\n## |\Z)', body, re.DOTALL)
    if tbl_m:
        for row in re.finditer(r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|', tbl_m.group(1)):
            vals = [row.group(i).strip() for i in (1, 2, 3)]
            if vals[0] and vals[0] not in ("指標", "----", "——"):
                data_table.append({"指標": vals[0], "數值": vals[1], "備註": vals[2]})

    return {
        "title_zh":     fm.get("title", ""),
        "topic":        fm.get("topic", ""),
        "tags":         tags,
        "tldr":         tldr,
        "sections":     sections,
        "key_insights": insights,
        "data_table":   data_table,
    }

def _yt_parse_condensed(video_id: str) -> list[dict]:
    """Parse condensed.txt into segments list."""
    path = YT_DATA_DIR / video_id / "condensed.txt"
    if not path.exists():
        return []
    segments = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*)", line)
        if m:
            ts = m.group(1)
            parts = ts.split(":")
            if len(parts) == 3:
                seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else:
                seconds = int(parts[0]) * 60 + int(parts[1])
            segments.append({
                "time":    ts,
                "seconds": seconds,
                "text":    m.group(2).strip(),
            })
    return segments


def _yt_fetch_rss_dates(channel_id: str) -> dict[str, str]:
    """從 YouTube RSS feed 取最新 15 支影片的發布日期（video_id → YYYY-MM-DD）。"""
    try:
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            xml = r.read().decode("utf-8", errors="ignore")
        dates = {}
        for entry in re.findall(r'<entry>(.*?)</entry>', xml, re.DOTALL):
            vid = re.search(r'<yt:videoId>(.*?)</yt:videoId>', entry)
            pub = re.search(r'<published>(.*?)</published>', entry)
            if vid and pub:
                dates[vid.group(1).strip()] = pub.group(1).strip()[:10]
        return dates
    except Exception:
        return {}


def _yt_get_cached_channel_id(handle: str) -> str:
    if not YT_CHANNEL_CFG.exists():
        return ""
    try:
        cfg = json.loads(YT_CHANNEL_CFG.read_text())
    except Exception:
        return ""
    for ch in cfg.get("channels", []):
        if ch.get("handle") == handle and ch.get("channel_id"):
            return ch["channel_id"]
    return ""


def _yt_cache_channel_id(handle: str, channel_id: str) -> None:
    if not channel_id or not YT_CHANNEL_CFG.exists():
        return
    try:
        cfg = json.loads(YT_CHANNEL_CFG.read_text())
    except Exception:
        return
    for ch in cfg.get("channels", []):
        if ch.get("handle") == handle:
            ch["channel_id"] = channel_id
            YT_CHANNEL_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
            break


def _yt_fetch_channel_id(handle: str) -> str:
    """Resolve a YouTube channel_id from config first, then yt-dlp."""
    if not handle.startswith("@"):
        handle = "@" + handle

    cached = _yt_get_cached_channel_id(handle)
    if cached:
        return cached

    try:
        r = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--playlist-items", "1",
             "--print", "%(playlist_channel_id)s",
             f"https://www.youtube.com/{handle}/videos"],
            capture_output=True, text=True, timeout=15,
        )
        channel_id = r.stdout.strip().splitlines()[0].strip() if r.stdout.strip() else ""
    except Exception:
        return ""

    if channel_id and channel_id != "NA":
        _yt_cache_channel_id(handle, channel_id)
        return channel_id
    return ""


def _yt_format_upload_date(raw: str) -> str:
    raw = (raw or "").strip()
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return raw
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return ""


def _yt_format_timestamp_date(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw or raw == "NA":
        return ""
    try:
        return datetime.utcfromtimestamp(int(float(raw))).strftime("%Y-%m-%d")
    except (ValueError, OSError, OverflowError):
        return ""


def _yt_format_duration(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw or raw == "NA":
        return ""
    if ":" in raw:
        return raw
    try:
        dur_s = int(float(raw))
    except ValueError:
        return ""
    return f"{dur_s // 60}:{dur_s % 60:02d}" if dur_s else ""


def _yt_parse_flat_video_line(line: str, rss_dates: dict[str, str] | None = None) -> dict | None:
    parts = line.split("\t")
    if len(parts) < 2:
        return None

    video_id = parts[0].strip()
    title = parts[1].strip()
    if not video_id or video_id == "NA":
        return None

    raw_date = parts[2].strip() if len(parts) > 2 else ""
    raw_duration = parts[3].strip() if len(parts) > 3 else ""
    raw_duration_string = parts[4].strip() if len(parts) > 4 else ""

    rss_dates = rss_dates or {}
    return {
        "id": video_id,
        "title": title,
        "title_zh": title,
        "upload_date": rss_dates.get(video_id) or _yt_format_upload_date(raw_date),
        "duration": _yt_format_duration(raw_duration_string) or _yt_format_duration(raw_duration),
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
    }


def _yt_fetch_video_details_batch(video_ids: list[str]) -> dict[str, dict]:
    """Fetch one batch of per-video metadata for dates/durations that flat playlist omits."""
    ids = [vid for vid in video_ids if vid]
    if not ids:
        return {}

    urls = [f"https://www.youtube.com/watch?v={vid}" for vid in ids]
    try:
        r = subprocess.run(
            ["yt-dlp", "--ignore-errors", "--skip-download",
             "--print", YT_VIDEO_DETAIL_PRINT, *urls],
            capture_output=True,
            text=True,
            timeout=max(60, len(ids) * 10),
        )
    except Exception:
        return {}

    details: dict[str, dict] = {}
    for line in r.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        video_id = parts[0].strip()
        if not video_id or video_id == "NA":
            continue
        raw_date = parts[1].strip() if len(parts) > 1 else ""
        raw_duration = parts[2].strip() if len(parts) > 2 else ""
        raw_duration_string = parts[3].strip() if len(parts) > 3 else ""
        raw_timestamp = parts[4].strip() if len(parts) > 4 else ""
        raw_release_timestamp = parts[5].strip() if len(parts) > 5 else ""
        details[video_id] = {
            "upload_date": (
                _yt_format_upload_date(raw_date)
                or _yt_format_timestamp_date(raw_timestamp)
                or _yt_format_timestamp_date(raw_release_timestamp)
            ),
            "duration": _yt_format_duration(raw_duration_string) or _yt_format_duration(raw_duration),
        }
    return details


def _yt_fetch_video_details(video_ids: list[str]) -> dict[str, dict]:
    """Fetch per-video metadata in parallel batches."""
    ids = [vid for vid in video_ids if vid]
    if not ids:
        return {}

    batch_size = max(1, YT_DETAIL_BATCH_SIZE)
    workers = max(1, YT_DETAIL_WORKERS)
    batches = [ids[i:i + batch_size] for i in range(0, len(ids), batch_size)]
    results: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_yt_fetch_video_details_batch, batch) for batch in batches]
        for fut in as_completed(futures):
            try:
                results.update(fut.result() or {})
            except Exception:
                continue

    return results


def _yt_parse_detail_limit(total: int) -> int:
    raw = str(YT_DETAIL_LIMIT).strip().lower()
    if raw in ("", "none", "all", "0", "-1"):
        return total
    try:
        limit = int(raw)
    except ValueError:
        return total
    return total if limit <= 0 else min(total, limit)


def _load_remote_yt_cache_from_db(handle: str) -> tuple[list[dict], dict]:
    if not handle.startswith("@"):
        handle = "@" + handle
    videos, meta = load_cached_youtube_videos(handle)
    if videos:
        with _remote_cache_lock:
            _remote_yt_cache[handle] = videos
            if meta.get("details_ready"):
                _remote_yt_details_ready.add(handle)
            else:
                _remote_yt_details_ready.discard(handle)
    return videos, meta


def _yt_is_placeholder_avatar(url: str) -> bool:
    return not url or "_placeholder" in url or url.endswith("/_placeholder/default.jpg")


def _yt_clean_avatar_url(url: str) -> str:
    return (url or "").replace("\\u0026", "&").replace("\\/", "/")


def _yt_pick_channel_avatar(thumbnails: list[dict]) -> str:
    best_url = ""
    best_score = -1_000_000
    for idx, thumb in enumerate(thumbnails or []):
        url = _yt_clean_avatar_url(str(thumb.get("url", "")))
        if not url.startswith("https://yt3."):
            continue

        width = int(thumb.get("width") or 0)
        height = int(thumb.get("height") or 0)
        thumb_id = str(thumb.get("id", "")).lower()

        # Prefer square channel avatars over wide banners.
        score = 0
        if "avatar" in thumb_id:
            score += 5000
        if width and height:
            aspect_penalty = abs(width - height)
            score += max(0, 4000 - aspect_penalty)
            score += min(width, height)
            if width > height * 2:
                score -= 5000
        if "s900-c" in url or "s800-c" in url or "s240-c" in url:
            score += 1000
        score -= idx

        if score > best_score:
            best_score = score
            best_url = url
    return best_url


def _yt_fetch_channel_avatar_from_ytdlp(handle: str) -> str:
    try:
        r = subprocess.run(
            [
                "yt-dlp",
                "--flat-playlist",
                "--playlist-items",
                "1",
                "--dump-single-json",
                f"https://www.youtube.com/{handle}/videos",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return ""
        data = json.loads(r.stdout)
        return _yt_pick_channel_avatar(data.get("thumbnails") or [])
    except Exception:
        return ""


def _yt_fetch_channel_avatar(handle: str, force: bool = False) -> str:
    """從頻道頁面 HTML 擷取頻道頭像 URL，並快取到 channels.json。"""
    if not handle.startswith("@"):
        handle = "@" + handle

    # 先從 config 讀快取
    if YT_CHANNEL_CFG.exists():
        cfg = json.loads(YT_CHANNEL_CFG.read_text())
        for ch in cfg.get("channels", []):
            cached = ch.get("avatar", "")
            if ch.get("handle") == handle and cached and not force and not _yt_is_placeholder_avatar(cached):
                return ch["avatar"]

    avatar = _yt_fetch_channel_avatar_from_ytdlp(handle)
    if not avatar:
        avatar = _yt_fetch_channel_avatar_from_html(handle)

    # 寫回快取
    if avatar and YT_CHANNEL_CFG.exists():
        cfg = json.loads(YT_CHANNEL_CFG.read_text())
        for ch in cfg.get("channels", []):
            if ch.get("handle") == handle:
                ch["avatar"] = avatar
                YT_CHANNEL_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
                break

    return avatar


def _yt_fetch_channel_avatar_from_html(handle: str) -> str:
    try:
        url = f"https://www.youtube.com/{handle}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")

        # pattern: "avatar":{"thumbnails":[{"url":"https://yt3.googleusercontent.com/..."}
        m = re.search(r'"avatar"\s*:\s*\{"thumbnails"\s*:\s*\[\s*\{"url"\s*:\s*"(https://yt3[^"]+)"', html)
        if not m:
            # fallback: any yt3.googleusercontent.com URL in the page
            m = re.search(r'(https://yt3\.googleusercontent\.com/[A-Za-z0-9_\-=]+)', html)
        return _yt_clean_avatar_url(m.group(1)) if m else ""
    except Exception:
        return ""


def _fetch_remote_yt_videos(handle: str, limit: int | None = None) -> list:
    """用 yt-dlp 拉 YT 頻道影片清單，寫入 _remote_yt_cache。"""
    if not handle.startswith("@"):
        handle = "@" + handle
    cached_videos, _ = load_cached_youtube_videos(handle)
    cached_by_id = {video["id"]: video for video in cached_videos}

    with _remote_cache_lock:
        _remote_yt_loading.add(handle)
        _remote_yt_details_ready.discard(handle)

    videos: list[dict] = []
    try:
        channel_id = _yt_fetch_channel_id(handle)
        rss_dates = _yt_fetch_rss_dates(channel_id) if channel_id else {}
        playlist_args = ["--playlist-items", f"1-{limit}"] if limit and limit > 0 else []

        try:
            r = subprocess.run(
                ["yt-dlp", "--flat-playlist", *playlist_args,
                 "--print", YT_FLAT_VIDEO_PRINT,
                 f"https://www.youtube.com/{handle}/videos"],
                capture_output=True, text=True, timeout=120,
            )
        except Exception:
            return []

        for line in r.stdout.strip().splitlines():
            video = _yt_parse_flat_video_line(line, rss_dates)
            if video:
                cached = cached_by_id.get(video["id"], {})
                if not video.get("upload_date"):
                    video["upload_date"] = cached.get("upload_date", "")
                if not video.get("duration"):
                    video["duration"] = cached.get("duration", "")
                videos.append(video)

        # Publish the full flat playlist first. Then keep updating the same
        # cache while slower per-video metadata fills in dates and durations.
        with _remote_cache_lock:
            _remote_yt_cache[handle] = list(videos)
        save_cached_youtube_videos(handle, videos, details_ready=False)

        missing_detail_ids = [
            v["id"] for v in videos
            if not v.get("upload_date") or not v.get("duration")
        ]
        detail_limit = _yt_parse_detail_limit(len(missing_detail_ids))
        missing_detail_ids = missing_detail_ids[:detail_limit]

        details = _yt_fetch_video_details(missing_detail_ids)
        for video in videos:
            detail = details.get(video["id"], {})
            if not video.get("upload_date"):
                video["upload_date"] = detail.get("upload_date", "")
            if not video.get("duration"):
                video["duration"] = detail.get("duration", "")
        with _remote_cache_lock:
            _remote_yt_cache[handle] = list(videos)
        details_ready = all(v.get("upload_date") and v.get("duration") for v in videos)
        save_cached_youtube_videos(handle, videos, details_ready=details_ready)
        if details_ready:
            with _remote_cache_lock:
                _remote_yt_details_ready.add(handle)
        else:
            with _remote_cache_lock:
                _remote_yt_details_ready.discard(handle)
        return videos
    finally:
        with _remote_cache_lock:
            _remote_yt_loading.discard(handle)


def _backfill_avatars():
    """啟動時在背景補抓所有缺 avatar 的 YT 頻道。"""
    if not YT_CHANNEL_CFG.exists():
        return
    cfg = json.loads(YT_CHANNEL_CFG.read_text())
    missing = [ch for ch in cfg.get("channels", []) if _yt_is_placeholder_avatar(ch.get("avatar", ""))]
    if not missing:
        return
    def _run():
        for ch in missing:
            handle = ch.get("handle", "")
            if not handle:
                continue
            avatar = _yt_fetch_channel_avatar(handle, force=True)
            print(f"[avatar] {handle} → {'ok' if avatar else 'not found'}")
    threading.Thread(target=_run, daemon=True).start()
