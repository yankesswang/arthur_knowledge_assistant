"""Startup remote metadata prefetching."""

import json

from cache_store import is_youtube_cache_fresh
from config_store import load_config
from podcast_services import _fetch_remote_pod_episodes
from settings import YT_CACHE_TTL_SECONDS, YT_CHANNEL_CFG, YT_REMOTE_LIMIT
from youtube_services import _fetch_remote_yt_videos, _load_remote_yt_cache_from_db


def _parse_remote_limit(value) -> int | None:
    """Return None for all videos, or a positive playlist item limit."""
    raw = str(value).strip().lower()
    if raw in ("", "none", "all", "0", "-1"):
        return None
    try:
        limit = int(raw)
    except ValueError:
        return 50
    return limit if limit > 0 else None

def _prefetch_all_remote():
    """Server 啟動時背景預抓所有頻道/podcast 的遠端清單。"""
    cfg = load_config()
    for pod in cfg.get("podcasts", []):
        try:
            _fetch_remote_pod_episodes(pod["id"])
            print(f"[remote] podcast {pod['id']} fetched")
        except Exception as e:
            print(f"[remote] podcast {pod['id']} error: {e}")

    if YT_CHANNEL_CFG.exists():
        yt_cfg = json.loads(YT_CHANNEL_CFG.read_text())
        for ch in yt_cfg.get("channels", []):
            handle = ch.get("handle", "")
            if not handle:
                continue
            try:
                cached, meta = _load_remote_yt_cache_from_db(handle)
                if cached and meta.get("details_ready") and is_youtube_cache_fresh(handle, YT_CACHE_TTL_SECONDS):
                    print(f"[remote] yt {handle} loaded from db ({len(cached)} videos)")
                    continue
                display_limit = ch.get("display_limit", YT_REMOTE_LIMIT)
                _fetch_remote_yt_videos(handle, _parse_remote_limit(display_limit))
                print(f"[remote] yt {handle} fetched")
            except Exception as e:
                print(f"[remote] yt {handle} error: {e}")
