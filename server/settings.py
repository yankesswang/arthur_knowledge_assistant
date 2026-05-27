"""Filesystem and runtime settings for the podcast note server."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = Path(__file__).resolve().parent
SERVER_DATA_DIR = SERVER_DIR / "data"

SKILL_DIR = PROJECT_ROOT / ".agent" / "skills" / "podcast-note"
PODCAST_ROOT = PROJECT_ROOT / "podcast-note"
PODCAST_SCRIPTS_DIR = PODCAST_ROOT / "scripts"
PODCAST_DATA_DIR = PODCAST_ROOT / "data"

DATA_DIR = PODCAST_DATA_DIR / "episodes"
CONFIG_PATH = PODCAST_ROOT / "config" / "podcasts.json"
STATIC_DIR = SERVER_DIR / "static"
DEFAULT_PROMPT_PATH = PROJECT_ROOT / "instructions" / "note-investment.md"

YT_SKILL_DIR = SKILL_DIR.parent / "transcript-note"
YT_DATA_DIR = YT_SKILL_DIR / "data" / "transcripts"
YT_QUEUE_FILE = YT_SKILL_DIR / "data" / "queue.txt"
YT_PROC_FILE = YT_SKILL_DIR / "data" / "processed_ids.txt"
YT_CHANNEL_CFG = YT_SKILL_DIR / "config" / "channels.json"

_VAULT_ROOT = os.environ.get("VAULT_ROOT", str(Path.home() / "Documents" / "arthurwang_DB"))
YT_NOTE_DIR = Path(os.environ.get("YT_NOTE_DIR", f"{_VAULT_ROOT}/影片筆記"))
READING_LIST_PATH = Path(os.environ.get("READING_LIST_PATH", f"{_VAULT_ROOT}/待看影片與Podcast清單.md"))
INBOX_PATH = SERVER_DATA_DIR / "inbox.json"
CACHE_DB_PATH = SERVER_DATA_DIR / "server_cache.sqlite3"
CUSTOM_PROMPT_PATH = SERVER_DATA_DIR / "custom_prompt.md"
OUTPUT_SETTINGS_PATH = SERVER_DATA_DIR / "output_settings.json"
TRANSCRIPTION_SETTINGS_PATH = SERVER_DATA_DIR / "transcription_settings.json"
GENERATION_SETTINGS_PATH = SERVER_DATA_DIR / "generation_settings.json"
NOTIFICATION_SETTINGS_PATH = SERVER_DATA_DIR / "notification_settings.json"

SERVER_HOST = os.environ.get("HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("PORT", "7654"))
YT_REMOTE_LIMIT = os.environ.get("YT_REMOTE_LIMIT", "all")
YT_DETAIL_LIMIT = os.environ.get("YT_DETAIL_LIMIT", "all")
YT_DETAIL_BATCH_SIZE = int(os.environ.get("YT_DETAIL_BATCH_SIZE", "10"))
YT_DETAIL_WORKERS = int(os.environ.get("YT_DETAIL_WORKERS", "5"))
YT_CACHE_TTL_SECONDS = int(os.environ.get("YT_CACHE_TTL_SECONDS", "86400"))
YT_AUTO_TRANSCRIPT = os.environ.get("YT_AUTO_TRANSCRIPT", "1").strip().lower() not in ("0", "false", "no", "off")
YT_AUTO_TRANSCRIPT_START_DELAY_SECONDS = int(os.environ.get("YT_AUTO_TRANSCRIPT_START_DELAY_SECONDS", "15"))
YT_AUTO_TRANSCRIPT_INTERVAL_SECONDS = int(os.environ.get("YT_AUTO_TRANSCRIPT_INTERVAL_SECONDS", "3600"))
YT_AUTO_TRANSCRIPT_LIMIT_PER_CHANNEL = os.environ.get("YT_AUTO_TRANSCRIPT_LIMIT_PER_CHANNEL", "channel")
