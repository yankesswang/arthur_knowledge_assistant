"""Podcast data access and parsing helpers."""

import json
import re
import subprocess
import urllib.request
from pathlib import Path

from config_store import get_podcast_config, load_config
from settings import DATA_DIR
from state import _remote_cache_lock, _remote_pod_cache

# ── Obsidian note helpers ───────────────────────────────────────────────────

def get_note_dir(podcast_id: str) -> Path | None:
    pod = get_podcast_config(podcast_id)
    d = pod.get("note_dir")
    return Path(d) if d else None

def find_note_for_episode(podcast_id: str, episode_label: str) -> Path | None:
    """在 note_dir 搜尋包含集數標籤的 .md 檔（如 EP662）"""
    note_dir = get_note_dir(podcast_id)
    if not note_dir or not note_dir.exists():
        return None
    ep_num = re.sub(r'[^0-9]', '', episode_label)  # "EP662" → "662"
    for f in note_dir.glob("*.md"):
        if ep_num and ep_num in f.name:
            return f
    return None

def parse_md_note(md_path: Path) -> dict:
    """解析 Obsidian .md 筆記，回傳前端所需的結構"""
    text = md_path.read_text(encoding="utf-8")

    # --- frontmatter ---
    fm = {}
    fm_match = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).splitlines():
            m = re.match(r'^(\w+):\s*"?(.+?)"?\s*$', line)
            if m:
                fm[m.group(1)] = m.group(2)
        text_body = text[fm_match.end():]
    else:
        text_body = text

    title = fm.get("title", md_path.stem)
    ep_match = re.search(r'EP\d+', md_path.name)
    episode_label = ep_match.group(0) if ep_match else ""

    # --- TL;DR ---
    tldr = {}
    tldr_block = re.search(r'## TL;DR\n(.*?)(?=\n## |\Z)', text_body, re.DOTALL)
    if tldr_block:
        key_map = {
            "核心主張": "核心主張",
            "關鍵機制": "關鍵機制_問題",
            "重要結論": "重要數字",
            "重要數字": "重要數字",
            "適用條件": "風險_限制",
            "操作建議": "操作建議",
        }
        for line in tldr_block.group(1).splitlines():
            m = re.match(r'- \*\*(.+?)\*\*[：:]\s*(.+)', line)
            if m:
                raw_key = m.group(1).split("/")[0].strip()
                for k, v in key_map.items():
                    if k in raw_key:
                        tldr[v] = m.group(2).strip()
                        break

    # --- 節目資訊 ---
    duration, upload_date, channel = "", "", fm.get("source", "")
    info_block = re.search(r'## 節目資訊\n(.*?)(?=\n## |\Z)', text_body, re.DOTALL)
    if info_block:
        for row in re.finditer(r'\|\s*(.+?)\s*\|\s*(.+?)\s*\|', info_block.group(1)):
            k, v = row.group(1).strip(), row.group(2).strip()
            if "時長" in k: duration = v
            elif "發布" in k: upload_date = v
            elif "頻道" in k: channel = v

    # --- 章節 ---
    sections = []
    for sec in re.finditer(
        r'### (\d+)\.\s*(?:\[(\d+:\d+)\]\s*)?(.*?)\n(.*?)(?=\n### \d+\.|\n## |\Z)',
        text_body, re.DOTALL
    ):
        points = []
        for line in sec.group(4).strip().splitlines():
            if line.strip():
                points.append(line.rstrip())
        sections.append({
            "title": sec.group(3).strip(),
            "start_time": sec.group(2) or "",
            "content_points": points,
        })

    # --- 關鍵洞見 ---
    insights = []
    ins_block = re.search(r'## 關鍵洞見\n(.*?)(?=\n## |\Z)', text_body, re.DOTALL)
    if ins_block:
        for line in ins_block.group(1).splitlines():
            m = re.match(r'- (.+)', line.strip())
            if m:
                insights.append(m.group(1).strip())

    # --- 數據速查 ---
    data_table = []
    tbl_block = re.search(r'## 附[：:]關鍵數據速查\n(.*?)(?=\n## |\Z)', text_body, re.DOTALL)
    if tbl_block:
        for row in re.finditer(r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|', tbl_block.group(1)):
            vals = [row.group(i).strip() for i in (1, 2, 3)]
            if vals[0] and vals[0] not in ("指標", "----", "——"):
                data_table.append({"指標": vals[0], "數值": vals[1], "備註": vals[2]})

    tags = re.findall(r'  - (.+)', fm_match.group(1) if fm_match else "")

    return {
        "title_zh": title,
        "episode_label": episode_label,
        "topic": fm.get("topic", ""),
        "tags": tags,
        "stocks": [],
        "tldr": tldr,
        "sections": sections,
        "key_insights": insights,
        "investment_framework": {},
        "risks": [],
        "data_table": data_table,
        # meta for header
        "_meta": {
            "channel": channel,
            "duration": duration,
            "upload_date": upload_date,
            "episode": episode_label,
        }
    }


# ── Transcript helpers ──────────────────────────────────────────────────────

def get_permanent_transcript(podcast_id: str, episode_label: str) -> Path | None:
    pod = get_podcast_config(podcast_id)
    d = pod.get("transcript_dir")
    if not d:
        return None
    p = Path(d) / f"{episode_label}.txt"
    return p if p.exists() else None

def parse_transcript_txt(path: Path) -> list[dict]:
    segments = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"\[(\d+):(\d+\.\d+)\]\s*(.*)", line)
        if m:
            total = int(m.group(1)) * 60 + float(m.group(2))
            segments.append({
                "time": f"{int(total)//60:02d}:{int(total)%60:02d}",
                "seconds": round(total, 2),
                "text": m.group(3).strip(),
            })
    return segments


# ── Episode list: scan data/episodes AND Obsidian notes ────────────────────

def build_episode_list() -> list[dict]:
    """合併 data/episodes 目錄 + Obsidian 投資筆記，去重，回傳統一清單"""
    episodes = {}

    # 1. 掃 data/episodes（取得音頻、逐字稿狀態）
    if DATA_DIR.exists():
        for ep_dir in DATA_DIR.iterdir():
            if not ep_dir.is_dir():
                continue
            parts = ep_dir.name.split("_", 1)
            podcast_id    = parts[0]
            episode_label = parts[1] if len(parts) == 2 else ""
            ep_num = re.sub(r'[^0-9]', '', episode_label)

            perm_t = get_permanent_transcript(podcast_id, episode_label)
            has_t  = perm_t is not None or (ep_dir / "transcript.txt").exists()

            episodes[ep_num] = {
                "id": ep_dir.name,
                "podcast_id": podcast_id,
                "episode_label": episode_label,
                "ep_num": ep_num,
                "has_audio": (ep_dir / "audio.mp3").exists(),
                "has_transcript": has_t,
                "has_note": False,
                "title_zh": episode_label or ep_dir.name,
                "upload_date": "",
            }

    # 2. 掃 Obsidian 投資筆記（掃所有 podcast）
    cfg = load_config()
    for pod in cfg.get("podcasts", []):
        note_dir = Path(pod.get("note_dir", ""))
        if not note_dir.exists():
            continue
        for md in note_dir.glob("*.md"):
            ep_m = re.search(r'EP(\d+)', md.name)
            if not ep_m:
                continue
            ep_num = ep_m.group(1)
            ep_label = f"EP{ep_num}"

            if ep_num not in episodes:
                episodes[ep_num] = {
                    "id": f"{pod['id']}_{ep_label}",
                    "podcast_id": pod["id"],
                    "episode_label": ep_label,
                    "ep_num": ep_num,
                    "has_audio": False,
                    "has_transcript": get_permanent_transcript(pod["id"], ep_label) is not None,
                    "has_note": True,
                    "title_zh": "",
                    "upload_date": "",
                }

            # 快速取標題 + 播出日期（從節目資訊表格取「發布」欄）
            try:
                text = md.read_text(encoding="utf-8")
                t_m = re.search(r'^title:\s*"?(.+?)"?\s*$', text[:400], re.MULTILINE)
                if t_m:
                    episodes[ep_num]["title_zh"] = t_m.group(1)
                    episodes[ep_num]["has_note"] = True
                    episodes[ep_num]["note_path"] = str(md)
                # 播出日期：優先讀節目資訊表格的「發布」欄
                pub_m = re.search(r'\|\s*發布\s*\|\s*(.+?)\s*\|', text)
                if pub_m:
                    episodes[ep_num]["upload_date"] = pub_m.group(1).strip()
                else:
                    # fallback：frontmatter date
                    d_m = re.search(r'^date:\s*"?(.+?)"?\s*$', text[:400], re.MULTILINE)
                    if d_m:
                        episodes[ep_num]["upload_date"] = d_m.group(1)
            except Exception:
                pass

    return sorted(episodes.values(), key=lambda e: int(e["ep_num"]) if e["ep_num"].isdigit() else 0, reverse=True)


def _fetch_rss_meta(rss_url: str) -> dict:
    """用 yt-dlp 從 RSS 取節目名稱（取第一集 metadata）"""
    try:
        r = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--playlist-items", "1",
             "--print", "%(playlist_title)s|%(uploader)s|%(playlist_count)s", rss_url],
            capture_output=True, text=True, timeout=20,
        )
        line = r.stdout.strip().split("\n")[0] if r.stdout.strip() else ""
        parts = line.split("|")
        title   = parts[0].strip() if len(parts) > 0 else ""
        uploader = parts[1].strip() if len(parts) > 1 else ""
        count   = parts[2].strip() if len(parts) > 2 else ""
        name = title if title and title != "NA" else uploader
        return {"name": name, "episode_count_hint": count}
    except Exception:
        return {"name": "", "episode_count_hint": ""}


def _fetch_remote_pod_episodes(podcast_id: str, limit: int = 200) -> list:
    """從 iTunes / RSS 拉全部集數，回傳 list of dicts。結果寫入 _remote_pod_cache。"""
    pod = get_podcast_config(podcast_id)
    if not pod:
        return []
    apple_id = pod.get("apple_id", "")
    episodes = []
    if apple_id:
        try:
            url = (f"https://itunes.apple.com/lookup?id={apple_id}"
                   f"&media=podcast&entity=podcastEpisode&limit={limit}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            for item in data.get("results", []):
                if item.get("kind") != "podcast-episode":
                    continue
                ms  = item.get("trackTimeMillis", 0)
                dur = f"{ms//60000}:{(ms%60000)//1000:02d}" if ms else ""
                title = item.get("trackName", "")
                ep_m  = re.search(r'EP\.?\s*(\d+)', title, re.IGNORECASE)
                episodes.append({
                    "title":       title,
                    "ep_num":      ep_m.group(1) if ep_m else "",
                    "date":        item.get("releaseDate", "")[:10],
                    "duration":    dur,
                    "artwork":     item.get("artworkUrl160") or pod.get("artwork", ""),
                    "episode_url": item.get("episodeUrl") or item.get("previewUrl") or "",
                    "guid":        item.get("episodeGuid", ""),
                })
        except Exception:
            pass
    if not episodes:
        try:
            r = subprocess.run(
                ["yt-dlp", "--flat-playlist", "--print",
                 "%(playlist_index)s|%(title)s|%(upload_date)s|%(duration)s",
                 pod["rss"]],
                capture_output=True, text=True, timeout=40,
            )
            for line in r.stdout.strip().splitlines():
                parts = line.split("|")
                if len(parts) < 2:
                    continue
                ud    = parts[2].strip() if len(parts) > 2 else ""
                dur_s = int(parts[3].strip()) if len(parts) > 3 and parts[3].strip().isdigit() else 0
                title = parts[1].strip()
                ep_m  = re.search(r'EP\.?\s*(\d+)', title, re.IGNORECASE)
                episodes.append({
                    "title":       title,
                    "ep_num":      ep_m.group(1) if ep_m else "",
                    "date":        f"{ud[:4]}-{ud[4:6]}-{ud[6:]}" if len(ud) == 8 else "",
                    "duration":    f"{dur_s//60}:{dur_s%60:02d}" if dur_s else "",
                    "artwork":     pod.get("artwork", ""),
                    "episode_url": "",
                    "guid":        "",
                })
        except Exception:
            pass
    with _remote_cache_lock:
        _remote_pod_cache[podcast_id] = episodes
    return episodes
