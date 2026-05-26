"""SQLite-backed cache for slow remote metadata."""

import sqlite3
import time
from pathlib import Path

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


def get_cost_summary() -> dict:
    init_cache_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT job_id, job_type, source_title, duration_minutes, cost_usd, ts FROM cost_log ORDER BY ts DESC"
        ).fetchall()
        total = conn.execute("SELECT COALESCE(SUM(cost_usd),0) FROM cost_log").fetchone()[0]
    return {
        "total_usd": round(float(total), 4),
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
