"""Inbox and reading-list API routes."""

import json
import re
import time
import urllib.request

from fastapi import APIRouter, HTTPException

from cache_store import get_yt_read_status, set_yt_read_status
from config_store import load_config
from podcast_services import build_episode_list
from settings import INBOX_PATH, READING_LIST_PATH

router = APIRouter()

def _load_inbox() -> list[dict]:
    if INBOX_PATH.exists():
        try:
            return json.loads(INBOX_PATH.read_text())
        except Exception:
            pass
    return []


def _save_inbox(items: list[dict]):
    INBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INBOX_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2))


@router.get("/api/inbox")
def get_inbox():
    """回傳未讀 inbox 通知（只回傳有 note_path 的筆記類條目，按發布日期降序）"""
    from pathlib import Path as _Path
    items = _load_inbox()
    valid = [i for i in items if i.get("note_path") and _Path(i["note_path"]).exists()]
    if len(valid) != len(items):
        _save_inbox(valid)
    valid.sort(key=lambda x: x.get("pub_date") or x.get("ts", 0), reverse=True)
    return valid


@router.post("/api/inbox")
def add_inbox(body: dict):
    """job 完成後寫入 inbox（有新筆記待閱讀）"""
    item_id = body.get("id", "").strip()
    if not item_id:
        raise HTTPException(400, "缺少 id")
    items = _load_inbox()
    if any(i.get("id") == item_id for i in items):
        return {"skipped": item_id}
    body["ts"] = time.time()
    items.insert(0, body)
    _save_inbox(items)
    return {"added": item_id}


@router.post("/api/inbox/{item_id}/dismiss")
def dismiss_inbox(item_id: str):
    """標記某通知為已讀（從 inbox 移除）"""
    items = [i for i in _load_inbox() if i.get("id") != item_id]
    _save_inbox(items)
    return {"dismissed": item_id}


@router.post("/api/inbox/dismiss-all")
def dismiss_all_inbox():
    _save_inbox([])
    return {"dismissed": "all"}


@router.post("/api/check-new-episodes")
def check_new_episodes():
    """
    逐一檢查每個 podcast 的 iTunes 最新集數，
    與本地已知集數比對，有新集數就加入 inbox。
    """
    cfg      = load_config()
    episodes = build_episode_list()
    inbox    = _load_inbox()
    inbox_ids = {i["id"] for i in inbox}

    # 本地已知的 ep_num，按 podcast_id 分組
    local_by_pod: dict[str, set] = {}
    for ep in episodes:
        pid = ep.get("podcast_id", "")
        num = ep.get("ep_num", "")
        if pid and num:
            local_by_pod.setdefault(pid, set()).add(num)

    new_items = []
    for pod in cfg.get("podcasts", []):
        pid      = pod["id"]
        apple_id = pod.get("apple_id", "")
        if not apple_id:
            continue

        try:
            url = (f"https://itunes.apple.com/lookup?id={apple_id}"
                   f"&media=podcast&entity=podcastEpisode&limit=5")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
        except Exception:
            continue

        local_nums = local_by_pod.get(pid, set())

        for item in data.get("results", []):
            if item.get("kind") != "podcast-episode":
                continue
            title   = item.get("trackName", "")
            ep_m    = re.search(r'EP\.?\s*(\d+)', title, re.IGNORECASE)
            ep_num  = ep_m.group(1) if ep_m else None
            date    = item.get("releaseDate", "")[:10]
            ms      = item.get("trackTimeMillis", 0)
            dur     = f"{ms//60000}:{(ms%60000)//1000:02d}" if ms else ""
            item_id = f"{pid}_{ep_num or title[:20]}"

            # 跳過已在 inbox 或本地已有的
            if item_id in inbox_ids:
                continue
            if ep_num and ep_num in local_nums:
                continue

            new_items.append({
                "id":         item_id,
                "podcast_id": pid,
                "podcast":    pod["name"],
                "ep_num":     ep_num,
                "title":      title,
                "date":       date,
                "duration":   dur,
                "artwork":    pod.get("artwork", ""),
                "ts":         time.time(),
            })

    if new_items:
        all_items = new_items + inbox  # 新的放前面
        _save_inbox(all_items)

    return {"checked": len(cfg.get("podcasts", [])), "new": len(new_items)}


@router.get("/api/reading-status")
def get_reading_status():
    """
    解析待看影片與Podcast清單，回傳每個條目的已讀狀態。
    { "note_title": "read" | "unread" }
    ep_num 為 key 方便前端查詢：{ "663": "unread", "662": "read", ... }
    """
    if not READING_LIST_PATH.exists():
        return {}

    result = {}
    text = READING_LIST_PATH.read_text(encoding="utf-8")
    for line in text.splitlines():
        # 匹配 - [x] 或 - [ ] 加 [[...]]
        m = re.match(r'-\s*\[([x ])\]\s*\[\[(.+?)\]\]', line.strip())
        if not m:
            continue
        status     = "read" if m.group(1) == "x" else "unread"
        note_title = m.group(2).strip()
        # 存完整標題
        result[note_title] = status
        # 同時存 EP 號為 key（方便前端按集號查）
        ep_m = re.search(r'EP(\d+)', note_title)
        if ep_m:
            ep_num = ep_m.group(1)
            # 若同 EP 有多個條目，以最新為準
            result[ep_num] = status

    return result


@router.post("/api/reading-status/{ep_num}/read")
def mark_read(ep_num: str):
    """標記指定 EP 為已讀（[x]）—— 僅供 Arthur 使用"""
    if not READING_LIST_PATH.exists():
        raise HTTPException(404, "找不到待看影片與Podcast清單")

    text  = READING_LIST_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    changed = False
    for i, line in enumerate(lines):
        if f"EP{ep_num}" in line or f"EP{ep_num.lstrip('0')}" in line:
            # 把 - [ ] 換成 - [x]
            new_line = re.sub(r'^(\s*-\s*)\[ \]', r'\1[x]', line)
            if new_line != line:
                lines[i] = new_line
                changed  = True

    if not changed:
        raise HTTPException(404, f"在清單中找不到 EP{ep_num}")

    READING_LIST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ep_num": ep_num, "status": "read"}


@router.post("/api/reading-status/{ep_num}/unread")
def mark_unread(ep_num: str):
    """標記指定 EP 為未讀（[ ]）"""
    if not READING_LIST_PATH.exists():
        raise HTTPException(404, "找不到待看影片與Podcast清單")

    text  = READING_LIST_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    changed = False
    for i, line in enumerate(lines):
        if f"EP{ep_num}" in line or f"EP{ep_num.lstrip('0')}" in line:
            new_line = re.sub(r'^(\s*-\s*)\[x\]', r'\1[ ]', line)
            if new_line != line:
                lines[i] = new_line
                changed  = True

    if not changed:
        raise HTTPException(404, f"在清單中找不到 EP{ep_num}")

    READING_LIST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ep_num": ep_num, "status": "unread"}


# ── YouTube 已讀狀態（SQLite）──────────────────────────────────────

@router.get("/api/youtube/read-status")
def yt_get_read_status():
    """回傳所有 YouTube 影片的已讀狀態 {video_id: 'read'|'unread'}"""
    return get_yt_read_status()


@router.post("/api/youtube/read-status/{video_id}/read")
def yt_mark_read(video_id: str):
    set_yt_read_status(video_id, "read")
    return {"video_id": video_id, "status": "read"}


@router.post("/api/youtube/read-status/{video_id}/unread")
def yt_mark_unread(video_id: str):
    set_yt_read_status(video_id, "unread")
    return {"video_id": video_id, "status": "unread"}
