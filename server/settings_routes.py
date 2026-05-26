"""Settings API — custom prompt read/write + output mode."""

import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = PROJECT_ROOT / ".agent" / "skills" / "podcast-note"
DEFAULT_PROMPT_PATH = PROJECT_ROOT / "instructions" / "note-investment.md"
CUSTOM_PROMPT_PATH = SKILL_DIR / "data" / "custom_prompt.md"
OUTPUT_SETTINGS_PATH = SKILL_DIR / "data" / "output_settings.json"
TRANSCRIPTION_SETTINGS_PATH = SKILL_DIR / "data" / "transcription_settings.json"

DEFAULT_OUTPUT = {
    "mode": "obsidian",       # "obsidian" | "folder"
    "folder_path": "~/Documents/AlphaNote",
}

DEFAULT_TRANSCRIPTION = {
    "mode": "local",          # "local" | "api"
    "openai_api_key": "",
    "whisper_model": "medium", # for local mode
    "language": "zh",         # zh | en | auto
}


class PromptBody(BaseModel):
    content: str


class OutputSettingsBody(BaseModel):
    mode: str           # "obsidian" or "folder"
    folder_path: str = "~/Documents/AlphaNote"


class TranscriptionSettingsBody(BaseModel):
    mode: str           # "local" or "api"
    openai_api_key: str = ""
    whisper_model: str = "medium"
    language: str = "zh"  # zh | en | auto


@router.get("/api/settings/prompt", response_class=PlainTextResponse)
async def get_prompt():
    """Return custom prompt if saved (non-empty), otherwise the default note-investment.md."""
    if CUSTOM_PROMPT_PATH.exists():
        content = CUSTOM_PROMPT_PATH.read_text(encoding="utf-8").strip()
        if content:
            return content
    if DEFAULT_PROMPT_PATH.exists():
        return DEFAULT_PROMPT_PATH.read_text(encoding="utf-8")
    return ""


@router.post("/api/settings/prompt")
async def save_prompt(body: PromptBody):
    """Persist custom prompt to data/custom_prompt.md."""
    CUSTOM_PROMPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CUSTOM_PROMPT_PATH.write_text(body.content, encoding="utf-8")
    return {"ok": True}


@router.delete("/api/settings/prompt")
async def reset_prompt():
    """Delete custom prompt, reverting to default."""
    if CUSTOM_PROMPT_PATH.exists():
        CUSTOM_PROMPT_PATH.unlink()
    return {"ok": True}


# ── Output settings ───────────────────────────────────────────────────────────

@router.get("/api/settings/output")
async def get_output_settings():
    """Return current output mode + folder path."""
    if OUTPUT_SETTINGS_PATH.exists():
        return json.loads(OUTPUT_SETTINGS_PATH.read_text(encoding="utf-8"))
    return DEFAULT_OUTPUT


@router.post("/api/settings/output")
async def save_output_settings(body: OutputSettingsBody):
    """Persist output mode setting."""
    OUTPUT_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {"mode": body.mode, "folder_path": body.folder_path}
    OUTPUT_SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


# ── Transcription settings ────────────────────────────────────────────────────

@router.get("/api/settings/transcription")
async def get_transcription_settings():
    if TRANSCRIPTION_SETTINGS_PATH.exists():
        data = json.loads(TRANSCRIPTION_SETTINGS_PATH.read_text(encoding="utf-8"))
        # mask key for display
        if data.get("openai_api_key"):
            data["openai_api_key_set"] = True
            data["openai_api_key"] = ""
        return data
    return {**DEFAULT_TRANSCRIPTION, "openai_api_key_set": False}


@router.post("/api/settings/transcription")
async def save_transcription_settings(body: TranscriptionSettingsBody):
    TRANSCRIPTION_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if TRANSCRIPTION_SETTINGS_PATH.exists():
        existing = json.loads(TRANSCRIPTION_SETTINGS_PATH.read_text(encoding="utf-8"))
    # preserve existing key if new value is blank (user didn't re-enter it)
    api_key = body.openai_api_key or existing.get("openai_api_key", "")
    data = {"mode": body.mode, "openai_api_key": api_key, "whisper_model": body.whisper_model, "language": body.language}
    TRANSCRIPTION_SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}
