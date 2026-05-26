"""Process-local state stores.

These stores are intentionally in-memory. They keep the current lightweight
single-user behavior, while keeping state ownership out of route modules.
"""

import threading

# { job_id: { status, podcast_id, episode, log, started_at } }
_jobs: dict[str, dict] = {}

# Remote episode/video caches, refreshed in background at startup.
_remote_pod_cache: dict[str, list] = {}
_remote_yt_cache: dict[str, list] = {}
_remote_yt_loading: set[str] = set()
_remote_yt_details_ready: set[str] = set()
_remote_cache_lock = threading.Lock()
