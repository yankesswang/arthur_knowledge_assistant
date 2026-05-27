"""Telegram notification — best-effort, silently ignored if not configured."""

import json
import urllib.error
import urllib.request
from pathlib import Path

from settings import NOTIFICATION_SETTINGS_PATH

_MAX_MSG = 4000  # Telegram sendMessage 上限 4096


def _load():
    if NOTIFICATION_SETTINGS_PATH.exists():
        try:
            return json.loads(NOTIFICATION_SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _trunc(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def _tg_post(token: str, method: str, payload: dict) -> bool:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def _build_caption(title: str, note_type: str) -> str:
    """簡短 caption 附在圖片下方（≤900 字）。"""
    icon = "🎙" if note_type == "podcast" else "▶️"
    return f"{icon} <b>{title}</b>"


def _build_detail(title: str, note_type: str, analysis_path: Path | None) -> str:
    """完整內文訊息（TL;DR + 關鍵洞見 + 章節清單）。"""
    icon = "🎙" if note_type == "podcast" else "▶️"
    lines = [f"{icon} <b>{title}</b>"]

    if analysis_path and analysis_path.exists():
        try:
            data = json.loads(analysis_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

        # ── TL;DR ────────────────────────────────────────────────
        tldr = data.get("tldr") or {}
        if isinstance(tldr, dict) and tldr:
            lines.append("")
            lines.append("📌 <b>TL;DR</b>")
            label_map = {
                "核心主張":      "核心主張",
                "關鍵機制_問題": "關鍵機制",
                "重要結論":      "重要結論",
                "重要數字":      "重要數字",
                "操作建議":      "操作建議",
                "適用條件_限制": "適用條件",
                "風險_限制":     "風險限制",
            }
            for raw_key, label in label_map.items():
                val = tldr.get(raw_key, "").strip()
                if val:
                    lines.append(f"• <b>{label}：</b>{_trunc(val, 120)}")

        # ── 關鍵洞見 ─────────────────────────────────────────────
        insights = data.get("key_insights") or []
        if insights:
            lines.append("")
            lines.append("💡 <b>關鍵洞見</b>")
            for i, ins in enumerate(insights[:4], 1):
                lines.append(f"{i}. {_trunc(str(ins), 100)}")

        # ── 章節清單 ─────────────────────────────────────────────
        sections = data.get("sections") or []
        if sections:
            lines.append("")
            lines.append(f"📋 <b>章節（{len(sections)} 段）</b>")
            for sec in sections:
                ts = sec.get("start_time", "")
                t  = sec.get("title", "")
                prefix = f"<code>{ts}</code> " if ts else "• "
                lines.append(f"{prefix}{_trunc(t, 40)}")

    return _trunc("\n".join(lines), _MAX_MSG)


def send_note_done(
    title: str,
    note_type: str = "yt",
    analysis_path: Path | None = None,
    image_url: str = "",
) -> bool:
    """Send Telegram notification when a note finishes.

    If image_url is provided: sendPhoto (with short caption) + sendMessage (full detail).
    Otherwise: sendMessage only.
    """
    cfg = _load()
    token   = cfg.get("telegram_bot_token", "").strip()
    chat_id = cfg.get("telegram_chat_id", "").strip()
    if not token or not chat_id:
        return False

    if image_url:
        # 1️⃣ 先送圖片（帶簡短 caption）
        _tg_post(token, "sendPhoto", {
            "chat_id":    chat_id,
            "photo":      image_url,
            "caption":    _build_caption(title, note_type),
            "parse_mode": "HTML",
        })
        # 2️⃣ 再送完整內容
        detail = _build_detail(title, note_type, analysis_path)
        return _tg_post(token, "sendMessage", {
            "chat_id":    chat_id,
            "text":       detail,
            "parse_mode": "HTML",
        })
    else:
        detail = _build_detail(title, note_type, analysis_path)
        return _tg_post(token, "sendMessage", {
            "chat_id":    chat_id,
            "text":       detail,
            "parse_mode": "HTML",
        })
