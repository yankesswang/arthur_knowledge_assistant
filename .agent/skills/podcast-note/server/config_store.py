"""Configuration helpers for the podcast note server."""

import json

from settings import CONFIG_PATH


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def get_podcast_config(podcast_id: str) -> dict:
    cfg = load_config()
    return next((p for p in cfg.get("podcasts", []) if p["id"] == podcast_id), {})
