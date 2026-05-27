"""SQLite-backed cache for slow remote metadata."""

import json
import sqlite3
import time

from settings import CACHE_DB_PATH


def _connect() -> sqlite3.Connection:
    CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_cache_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS youtube_channel_cache (
                handle TEXT PRIMARY KEY,
                fetched_at REAL NOT NULL,
                details_ready INTEGER NOT NULL DEFAULT 0,
                video_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS youtube_video_cache (
                handle TEXT NOT NULL,
                video_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                title_zh TEXT NOT NULL DEFAULT '',
                upload_date TEXT NOT NULL DEFAULT '',
                duration TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                thumbnail TEXT NOT NULL DEFAULT '',
                updated_at REAL NOT NULL,
                PRIMARY KEY (handle, video_id)
            );

            CREATE INDEX IF NOT EXISTS idx_youtube_video_cache_handle_pos
                ON youtube_video_cache(handle, position);

            CREATE TABLE IF NOT EXISTS youtube_read_status (
                video_id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'unread',
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cost_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                job_type TEXT NOT NULL DEFAULT '',
                source_title TEXT NOT NULL DEFAULT '',
                duration_minutes REAL NOT NULL DEFAULT 0,
                cost_usd REAL NOT NULL DEFAULT 0,
                ts REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS llm_usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL DEFAULT '',
                job_id TEXT NOT NULL DEFAULT '',
                job_type TEXT NOT NULL DEFAULT '',
                source_title TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cached_input_tokens INTEGER NOT NULL DEFAULT 0,
                reasoning_output_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL DEFAULT '{}',
                ts REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_llm_usage_provider_ts
                ON llm_usage_log(provider, ts DESC);

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                color TEXT NOT NULL DEFAULT '#7c6af7',
                sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS source_categories (
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                category_name TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (source_type, source_id)
            );

            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT '',
                source_id TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '',
                phase TEXT NOT NULL DEFAULT '',
                progress REAL NOT NULL DEFAULT 0,
                started_at REAL NOT NULL DEFAULT 0,
                finished_at REAL,
                updated_at REAL NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_started_at
                ON jobs(started_at DESC);

            CREATE TABLE IF NOT EXISTS youtube_queue (
                video_id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                added_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_youtube_queue_added_at
                ON youtube_queue(added_at);

            CREATE TABLE IF NOT EXISTS inbox_items (
                item_id TEXT PRIMARY KEY,
                item_type TEXT NOT NULL DEFAULT '',
                source_id TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                note_path TEXT NOT NULL DEFAULT '',
                pub_date TEXT NOT NULL DEFAULT '',
                ts REAL NOT NULL,
                dismissed_at REAL,
                payload_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_inbox_items_active
                ON inbox_items(dismissed_at, pub_date DESC, ts DESC);
            """
        )
        # seed default categories if empty
        count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if count == 0:
            defaults = [
                ("投資", "#4ade80", 0),
                ("AI / 技術", "#60a5fa", 1),
                ("產業分析", "#fbbf24", 2),
                ("創業", "#f87171", 3),
                ("其他", "#8b8fa8", 4),
            ]
            conn.executemany(
                "INSERT OR IGNORE INTO categories(name, color, sort_order) VALUES(?,?,?)",
                defaults,
            )


def get_yt_read_status() -> dict[str, str]:
    init_cache_db()
    with _connect() as conn:
        rows = conn.execute("SELECT video_id, status FROM youtube_read_status").fetchall()
    return {row["video_id"]: row["status"] for row in rows}


def set_yt_read_status(video_id: str, status: str) -> None:
    init_cache_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO youtube_read_status(video_id, status, updated_at)
            VALUES(?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at
            """,
            (video_id, status, time.time()),
        )


def load_cached_youtube_videos(handle: str) -> tuple[list[dict], dict]:
    init_cache_db()
    with _connect() as conn:
        meta_row = conn.execute(
            """
            SELECT handle, fetched_at, details_ready, video_count
            FROM youtube_channel_cache
            WHERE handle = ?
            """,
            (handle,),
        ).fetchone()
        rows = conn.execute(
            """
            SELECT video_id, title, title_zh, upload_date, duration, url, thumbnail
            FROM youtube_video_cache
            WHERE handle = ?
            ORDER BY position ASC
            """,
            (handle,),
        ).fetchall()

    videos = [
        {
            "id": row["video_id"],
            "title": row["title"],
            "title_zh": row["title_zh"] or row["title"],
            "upload_date": row["upload_date"],
            "duration": row["duration"],
            "url": row["url"],
            "thumbnail": row["thumbnail"],
        }
        for row in rows
    ]
    meta = dict(meta_row) if meta_row else {}
    if meta:
        meta["details_ready"] = bool(meta.get("details_ready"))
    return videos, meta


def save_cached_youtube_videos(handle: str, videos: list[dict], *, details_ready: bool) -> None:
    init_cache_db()
    now = time.time()
    video_ids = [v.get("id", "") for v in videos if v.get("id")]

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO youtube_channel_cache(handle, fetched_at, details_ready, video_count)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(handle) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                details_ready = excluded.details_ready,
                video_count = excluded.video_count
            """,
            (handle, now, 1 if details_ready else 0, len(video_ids)),
        )

        for position, video in enumerate(videos):
            video_id = video.get("id", "")
            if not video_id:
                continue
            title = video.get("title", "")
            conn.execute(
                """
                INSERT INTO youtube_video_cache(
                    handle, video_id, position, title, title_zh, upload_date,
                    duration, url, thumbnail, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(handle, video_id) DO UPDATE SET
                    position = excluded.position,
                    title = excluded.title,
                    title_zh = excluded.title_zh,
                    upload_date = excluded.upload_date,
                    duration = excluded.duration,
                    url = excluded.url,
                    thumbnail = excluded.thumbnail,
                    updated_at = excluded.updated_at
                """,
                (
                    handle,
                    video_id,
                    position,
                    title,
                    video.get("title_zh") or title,
                    video.get("upload_date", ""),
                    video.get("duration", ""),
                    video.get("url", ""),
                    video.get("thumbnail", ""),
                    now,
                ),
            )

        if video_ids:
            placeholders = ",".join("?" for _ in video_ids)
            conn.execute(
                f"""
                DELETE FROM youtube_video_cache
                WHERE handle = ? AND video_id NOT IN ({placeholders})
                """,
                (handle, *video_ids),
            )
        else:
            conn.execute("DELETE FROM youtube_video_cache WHERE handle = ?", (handle,))


def is_youtube_cache_fresh(handle: str, ttl_seconds: int) -> bool:
    if ttl_seconds <= 0:
        return False
    _, meta = load_cached_youtube_videos(handle)
    fetched_at = float(meta.get("fetched_at") or 0)
    return fetched_at > 0 and (time.time() - fetched_at) < ttl_seconds


def log_transcript_cost(job_id: str, job_type: str, source_title: str, duration_minutes: float, cost_usd: float) -> None:
    init_cache_db()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO cost_log(job_id, job_type, source_title, duration_minutes, cost_usd, ts) VALUES(?,?,?,?,?,?)",
            (job_id, job_type, source_title, duration_minutes, cost_usd, time.time()),
        )


def _usage_int(data: dict, *keys: str) -> int:
    for key in keys:
        value = data.get(key)
        if isinstance(value, dict):
            continue
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            continue
    return 0


def log_llm_usage(
    *,
    provider: str,
    job_id: str,
    job_type: str,
    source_title: str,
    usage: dict,
    model: str = "",
) -> None:
    """Persist one LLM usage event emitted by a CLI run."""
    if not usage:
        return

    input_details = usage.get("input_token_details") or {}
    output_details = usage.get("output_token_details") or {}
    if not isinstance(input_details, dict):
        input_details = {}
    if not isinstance(output_details, dict):
        output_details = {}
    input_tokens = _usage_int(usage, "input_tokens", "prompt_tokens")
    output_tokens = _usage_int(usage, "output_tokens", "completion_tokens")
    cached_input_tokens = _usage_int(
        usage,
        "cached_input_tokens",
        "cached_tokens",
    ) or _usage_int(input_details, "cached_tokens")
    reasoning_output_tokens = _usage_int(
        usage,
        "reasoning_output_tokens",
        "reasoning_tokens",
    ) or _usage_int(output_details, "reasoning_tokens")
    total_tokens = _usage_int(usage, "total_tokens") or input_tokens + output_tokens

    init_cache_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO llm_usage_log(
                provider, job_id, job_type, source_title, model,
                input_tokens, output_tokens, cached_input_tokens,
                reasoning_output_tokens, total_tokens, raw_json, ts
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                provider,
                job_id,
                job_type,
                source_title,
                model or usage.get("model", "") or "",
                input_tokens,
                output_tokens,
                cached_input_tokens,
                reasoning_output_tokens,
                total_tokens,
                json.dumps(usage, ensure_ascii=False, sort_keys=True),
                time.time(),
            ),
        )


def get_llm_usage_summary(provider: str = "codex") -> dict:
    from datetime import datetime, timezone, timedelta

    init_cache_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT provider, job_id, job_type, source_title, model,
                   input_tokens, output_tokens, cached_input_tokens,
                   reasoning_output_tokens, total_tokens, ts
            FROM llm_usage_log
            WHERE provider = ?
            ORDER BY ts DESC
            """,
            (provider,),
        ).fetchall()

    tz8 = timezone(timedelta(hours=8))
    today = datetime.now(tz8).date()
    daily: dict[str, dict] = {}
    by_type: dict[str, int] = {}
    today_totals = {
        "runs": 0,
        "inputTokens": 0,
        "outputTokens": 0,
        "cachedInputTokens": 0,
        "reasoningOutputTokens": 0,
        "totalTokens": 0,
    }
    all_totals = dict(today_totals)

    for r in rows:
        dt = datetime.fromtimestamp(r["ts"], tz=tz8)
        delta = (today - dt.date()).days
        all_totals["runs"] += 1
        all_totals["inputTokens"] += r["input_tokens"]
        all_totals["outputTokens"] += r["output_tokens"]
        all_totals["cachedInputTokens"] += r["cached_input_tokens"]
        all_totals["reasoningOutputTokens"] += r["reasoning_output_tokens"]
        all_totals["totalTokens"] += r["total_tokens"]

        if delta == 0:
            today_totals["runs"] += 1
            today_totals["inputTokens"] += r["input_tokens"]
            today_totals["outputTokens"] += r["output_tokens"]
            today_totals["cachedInputTokens"] += r["cached_input_tokens"]
            today_totals["reasoningOutputTokens"] += r["reasoning_output_tokens"]
            today_totals["totalTokens"] += r["total_tokens"]

        if delta < 14:
            key = dt.strftime("%m/%d")
            if key not in daily:
                daily[key] = {"runs": 0, "totalTokens": 0}
            daily[key]["runs"] += 1
            daily[key]["totalTokens"] += r["total_tokens"]

        jt = r["job_type"] or "unknown"
        by_type[jt] = by_type.get(jt, 0) + r["total_tokens"]

    daily_list = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        key = d.strftime("%m/%d")
        if key in daily:
            daily_list.append({"date": key, **daily[key]})

    return {
        "provider": provider,
        "today": today_totals,
        "total": all_totals,
        "daily": daily_list,
        "by_type": [
            {"type": k, "totalTokens": v}
            for k, v in sorted(by_type.items(), key=lambda x: -x[1])
        ],
        "entries": [
            {
                "job_id": r["job_id"],
                "job_type": r["job_type"],
                "source_title": r["source_title"],
                "model": r["model"],
                "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"],
                "cached_input_tokens": r["cached_input_tokens"],
                "reasoning_output_tokens": r["reasoning_output_tokens"],
                "total_tokens": r["total_tokens"],
                "ts": r["ts"],
            }
            for r in rows[:100]
        ],
    }


def get_cost_summary() -> dict:
    import time as _time
    from datetime import datetime, timezone, timedelta
    init_cache_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT job_id, job_type, source_title, duration_minutes, cost_usd, ts FROM cost_log ORDER BY ts DESC"
        ).fetchall()
        total = conn.execute("SELECT COALESCE(SUM(cost_usd),0) FROM cost_log").fetchone()[0]

    tz8 = timezone(timedelta(hours=8))
    today = datetime.now(tz8).date()
    daily: dict[str, dict] = {}   # "MM/DD" -> {costUSD, minutes}
    by_type: dict[str, float] = {}  # job_type -> costUSD

    for r in rows:
        dt = datetime.fromtimestamp(r["ts"], tz=tz8)
        delta = (today - dt.date()).days
        if delta < 14:
            key = dt.strftime("%m/%d")
            if key not in daily:
                daily[key] = {"costUSD": 0.0, "minutes": 0.0}
            daily[key]["costUSD"] += r["cost_usd"]
            daily[key]["minutes"] += r["duration_minutes"]
        jt = r["job_type"] or "unknown"
        by_type[jt] = by_type.get(jt, 0) + r["cost_usd"]

    daily_list = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        key = d.strftime("%m/%d")
        if key in daily:
            daily_list.append({"date": key, "costUSD": round(daily[key]["costUSD"], 4), "minutes": round(daily[key]["minutes"], 2)})

    return {
        "total_usd": round(float(total), 4),
        "daily": daily_list,
        "by_type": [{"type": k, "costUSD": round(v, 4)} for k, v in sorted(by_type.items(), key=lambda x: -x[1])],
        "entries": [
            {
                "job_id": r["job_id"],
                "job_type": r["job_type"],
                "source_title": r["source_title"],
                "duration_minutes": round(r["duration_minutes"], 2),
                "cost_usd": round(r["cost_usd"], 4),
                "ts": r["ts"],
            }
            for r in rows
        ],
    }


# ── Categories ───────────────────────────────────────────────────────────────

def get_categories() -> list[dict]:
    init_cache_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, name, color, sort_order FROM categories ORDER BY sort_order, id"
        ).fetchall()
    return [{"id": r["id"], "name": r["name"], "color": r["color"], "sort_order": r["sort_order"]} for r in rows]


def add_category(name: str, color: str = "#7c6af7") -> dict:
    init_cache_db()
    with _connect() as conn:
        max_order = conn.execute("SELECT COALESCE(MAX(sort_order),0) FROM categories").fetchone()[0]
        conn.execute(
            "INSERT INTO categories(name, color, sort_order) VALUES(?,?,?)",
            (name.strip(), color, max_order + 1),
        )
        row = conn.execute("SELECT id, name, color, sort_order FROM categories WHERE name=?", (name.strip(),)).fetchone()
    return {"id": row["id"], "name": row["name"], "color": row["color"], "sort_order": row["sort_order"]}


def update_category(cat_id: int, name: str | None = None, color: str | None = None) -> bool:
    init_cache_db()
    with _connect() as conn:
        if name is not None:
            conn.execute("UPDATE categories SET name=? WHERE id=?", (name.strip(), cat_id))
        if color is not None:
            conn.execute("UPDATE categories SET color=? WHERE id=?", (color, cat_id))
    return True


def delete_category(cat_id: int) -> bool:
    init_cache_db()
    with _connect() as conn:
        name_row = conn.execute("SELECT name FROM categories WHERE id=?", (cat_id,)).fetchone()
        if not name_row:
            return False
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        conn.execute("UPDATE source_categories SET category_name='' WHERE category_name=?", (name_row["name"],))
    return True


def get_source_category(source_type: str, source_id: str) -> str:
    init_cache_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT category_name FROM source_categories WHERE source_type=? AND source_id=?",
            (source_type, source_id),
        ).fetchone()
    return row["category_name"] if row else ""


def set_source_category(source_type: str, source_id: str, category_name: str) -> None:
    init_cache_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO source_categories(source_type, source_id, category_name)
            VALUES(?,?,?)
            ON CONFLICT(source_type, source_id) DO UPDATE SET category_name=excluded.category_name
            """,
            (source_type, source_id, category_name),
        )


def get_all_source_categories(source_type: str) -> dict[str, str]:
    """Return {source_id: category_name} for all sources of given type."""
    init_cache_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT source_id, category_name FROM source_categories WHERE source_type=?",
            (source_type,),
        ).fetchall()
    return {r["source_id"]: r["category_name"] for r in rows}


# ── Jobs ─────────────────────────────────────────────────────────────────────

def _public_job_payload(job: dict) -> dict:
    """Return a JSON-safe snapshot without process-local private fields."""
    public = {k: v for k, v in job.items() if not k.startswith("_")}
    try:
        json.dumps(public, ensure_ascii=False)
        return public
    except TypeError:
        return json.loads(json.dumps(public, ensure_ascii=False, default=str))


def save_job_snapshot(job: dict) -> None:
    job_id = str(job.get("job_id") or "")
    if not job_id:
        return
    payload = _public_job_payload(job)
    source_type = "youtube" if payload.get("video_id") else ("podcast" if payload.get("podcast_id") else "")
    source_id = str(payload.get("video_id") or payload.get("podcast_id") or "")
    now = time.time()

    init_cache_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs(
                job_id, job_type, source_type, source_id, title, status,
                phase, progress, started_at, finished_at, updated_at, payload_json
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(job_id) DO UPDATE SET
                job_type=excluded.job_type,
                source_type=excluded.source_type,
                source_id=excluded.source_id,
                title=excluded.title,
                status=excluded.status,
                phase=excluded.phase,
                progress=excluded.progress,
                started_at=excluded.started_at,
                finished_at=excluded.finished_at,
                updated_at=excluded.updated_at,
                payload_json=excluded.payload_json
            """,
            (
                job_id,
                str(payload.get("type") or ""),
                source_type,
                source_id,
                str(payload.get("title") or ""),
                str(payload.get("status") or ""),
                str(payload.get("phase") or ""),
                float(payload.get("progress") or 0),
                float(payload.get("started_at") or now),
                payload.get("finished_at"),
                now,
                json.dumps(payload, ensure_ascii=False),
            ),
        )


def _job_from_row(row: sqlite3.Row) -> dict:
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except Exception:
        payload = {}
    payload.setdefault("job_id", row["job_id"])
    payload.setdefault("type", row["job_type"])
    payload.setdefault("status", row["status"])
    payload.setdefault("phase", row["phase"])
    payload.setdefault("progress", row["progress"])
    payload.setdefault("started_at", row["started_at"])
    if row["finished_at"] is not None:
        payload.setdefault("finished_at", row["finished_at"])
    payload["_persisted"] = True
    payload["_updated_at"] = row["updated_at"]
    return payload


def load_job_snapshot(job_id: str) -> dict | None:
    init_cache_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    return _job_from_row(row) if row else None


def list_job_snapshots(limit: int = 20) -> list[dict]:
    init_cache_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_job_from_row(row) for row in rows]


# ── YouTube queue ────────────────────────────────────────────────────────────

def load_youtube_queue() -> list[str]:
    init_cache_db()
    with _connect() as conn:
        rows = conn.execute("SELECT url FROM youtube_queue ORDER BY added_at").fetchall()
    return [row["url"] for row in rows]


def add_youtube_queue_url(video_id: str, url: str) -> bool:
    if not video_id or not url:
        return False
    now = time.time()
    init_cache_db()
    with _connect() as conn:
        existing = conn.execute(
            "SELECT 1 FROM youtube_queue WHERE video_id=?",
            (video_id,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO youtube_queue(video_id, url, added_at, updated_at)
            VALUES(?,?,?,?)
            ON CONFLICT(video_id) DO UPDATE SET
                url=excluded.url,
                updated_at=excluded.updated_at
            """,
            (video_id, url, now, now),
        )
    return existing is None


def remove_youtube_queue_video(video_id: str) -> None:
    if not video_id:
        return
    init_cache_db()
    with _connect() as conn:
        conn.execute("DELETE FROM youtube_queue WHERE video_id=?", (video_id,))


def remove_youtube_queue_url(url: str) -> None:
    if not url:
        return
    init_cache_db()
    with _connect() as conn:
        conn.execute("DELETE FROM youtube_queue WHERE url=?", (url,))


# ── Inbox ────────────────────────────────────────────────────────────────────

def load_inbox_items() -> list[dict]:
    init_cache_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM inbox_items
            WHERE dismissed_at IS NULL
            ORDER BY COALESCE(NULLIF(pub_date, ''), ts) DESC, ts DESC
            """
        ).fetchall()
    items = []
    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except Exception:
            payload = {}
        payload.setdefault("id", row["item_id"])
        payload.setdefault("type", row["item_type"])
        payload.setdefault("title", row["title"])
        payload.setdefault("note_path", row["note_path"])
        payload.setdefault("pub_date", row["pub_date"])
        payload.setdefault("ts", row["ts"])
        items.append(payload)
    return items


def inbox_has_any_items() -> bool:
    init_cache_db()
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM inbox_items LIMIT 1").fetchone()
    return row is not None


def save_inbox_item(item: dict) -> bool:
    item_id = str(item.get("id") or "").strip()
    if not item_id:
        return False
    payload = json.loads(json.dumps(item, ensure_ascii=False, default=str))
    ts = float(payload.get("ts") or time.time())
    item_type = str(payload.get("type") or "")
    source_id = str(payload.get("video_id") or payload.get("podcast_id") or "")

    init_cache_db()
    with _connect() as conn:
        existing = conn.execute(
            "SELECT 1 FROM inbox_items WHERE item_id=? AND dismissed_at IS NULL",
            (item_id,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO inbox_items(
                item_id, item_type, source_id, title, note_path, pub_date, ts,
                dismissed_at, payload_json
            )
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(item_id) DO UPDATE SET
                item_type=excluded.item_type,
                source_id=excluded.source_id,
                title=excluded.title,
                note_path=excluded.note_path,
                pub_date=excluded.pub_date,
                ts=excluded.ts,
                dismissed_at=NULL,
                payload_json=excluded.payload_json
            """,
            (
                item_id,
                item_type,
                source_id,
                str(payload.get("title") or ""),
                str(payload.get("note_path") or ""),
                str(payload.get("pub_date") or payload.get("date") or ""),
                ts,
                None,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
    return existing is None


def replace_inbox_items(items: list[dict]) -> None:
    init_cache_db()
    active_ids = [str(item.get("id") or "").strip() for item in items if item.get("id")]
    with _connect() as conn:
        if active_ids:
            placeholders = ",".join("?" for _ in active_ids)
            conn.execute(
                f"UPDATE inbox_items SET dismissed_at=? WHERE dismissed_at IS NULL AND item_id NOT IN ({placeholders})",
                (time.time(), *active_ids),
            )
        else:
            conn.execute("UPDATE inbox_items SET dismissed_at=? WHERE dismissed_at IS NULL", (time.time(),))
    for item in items:
        save_inbox_item(item)


def dismiss_inbox_item(item_id: str) -> None:
    init_cache_db()
    with _connect() as conn:
        conn.execute("UPDATE inbox_items SET dismissed_at=? WHERE item_id=?", (time.time(), item_id))


def dismiss_all_inbox_items() -> None:
    init_cache_db()
    with _connect() as conn:
        conn.execute("UPDATE inbox_items SET dismissed_at=? WHERE dismissed_at IS NULL", (time.time(),))
