"""Podcast API routes."""

import json
import re
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config_store import get_podcast_config, load_config, save_config
from podcast_jobs import _run_download
from podcast_services import (
    _fetch_rss_meta,
    build_episode_list,
    find_note_for_episode,
    get_permanent_transcript,
    parse_md_note,
    parse_transcript_txt,
)
from reading_routes import _load_inbox, _save_inbox
from settings import DATA_DIR
from state import _jobs, _remote_cache_lock, _remote_pod_cache

router = APIRouter()

# ── API routes ──────────────────────────────────────────────────────────────

@router.get("/api/podcasters")
def list_podcasters():
    """按 podcaster 分組，合併本地 + 遠端集數後回傳"""
    cfg      = load_config()
    local_eps = build_episode_list()  # 本地已有的

    result = []
    for pod in cfg.get("podcasts", []):
        pid      = pod["id"]
        artwork  = pod.get("artwork", "")
        local    = [e for e in local_eps if e["podcast_id"] == pid]
        local_by_num = {e["ep_num"]: e for e in local if e["ep_num"]}

        # 遠端快取（背景抓好的）
        with _remote_cache_lock:
            remote = list(_remote_pod_cache.get(pid, []))

        # 合併：遠端為主，補上本地資訊
        merged: list[dict] = []
        seen_nums: set[str] = set()

        for r in remote:
            ep_num = r.get("ep_num", "")
            local_ep = local_by_num.get(ep_num) if ep_num else None
            merged.append({
                "id":             local_ep["id"] if local_ep else f"{pid}_EP{ep_num or r['title'][:20]}",
                "podcast_id":     pid,
                "episode_label":  f"EP{ep_num}" if ep_num else "",
                "ep_num":         ep_num,
                "title_zh":       local_ep["title_zh"] if local_ep and local_ep.get("title_zh") else r["title"],
                "upload_date":    local_ep["upload_date"] if local_ep and local_ep.get("upload_date") else r.get("date", ""),
                "duration":       r.get("duration", ""),
                "artwork":        r.get("artwork") or artwork,
                "has_note":       bool(local_ep and local_ep.get("has_note")),
                "has_transcript": bool(local_ep and local_ep.get("has_transcript")),
                "has_audio":      bool(local_ep and local_ep.get("has_audio")),
                "is_local":       local_ep is not None,
                "episode_url":    r.get("episode_url", ""),
                "_artwork":       artwork,
                "_pod":           pod.get("name", pid),
            })
            if ep_num:
                seen_nums.add(ep_num)

        # 補上本地有但遠端清單沒有的（如 latest 或超出 limit 的舊集）
        for local_ep in local:
            if local_ep["ep_num"] not in seen_nums:
                merged.append({**local_ep, "is_local": True, "duration": "", "episode_url": "", "_artwork": artwork, "_pod": pod.get("name", pid)})

        # 按 ep_num 降序排列
        merged.sort(key=lambda e: int(e["ep_num"]) if e["ep_num"].isdigit() else 0, reverse=True)

        note_count = sum(1 for e in merged if e["has_note"])
        result.append({
            "id":            pid,
            "name":          pod.get("name", pid),
            "artwork":       artwork,
            "language":      pod.get("language", ""),
            "note_type":     pod.get("note_type", ""),
            "episode_count": len(merged),
            "note_count":    note_count,
            "remote_ready":  bool(remote),
            "episodes":      merged,
        })
    return result


@router.post("/api/podcasters")
def add_podcaster(body: dict):
    """
    新增 Podcaster 到 config/podcasts.json
    body: { rss, name?, language?, note_type? }
    """
    rss = (body.get("rss") or "").strip()
    if not rss:
        raise HTTPException(400, "缺少 RSS URL")

    cfg = load_config()
    podcasts = cfg.get("podcasts", [])

    # 重複檢查
    if any(p["rss"] == rss for p in podcasts):
        raise HTTPException(409, "此 RSS 已存在")

    # 名稱：優先用前端傳來的（搜尋結果已有），沒有才呼叫 yt-dlp
    name = (body.get("name") or "").strip()
    if not name:
        meta = _fetch_rss_meta(rss)
        name = meta.get("name", "").strip()
    if not name:
        raise HTTPException(422, "無法取得節目名稱，請手動填寫")

    # 產生唯一 id（英文小寫 + 數字，取自名稱）
    raw_id = re.sub(r'[^a-z0-9]', '', name.lower())[:20] or f"pod{len(podcasts)+1}"
    pod_id = raw_id
    existing_ids = {p["id"] for p in podcasts}
    suffix = 2
    while pod_id in existing_ids:
        pod_id = f"{raw_id}{suffix}"
        suffix += 1

    language  = (body.get("language") or "zh").strip()
    note_type = (body.get("note_type") or "investment").strip()

    import os as _os
    vault_root     = cfg.get("vault_root", _os.environ.get("VAULT_ROOT", str(Path.home() / "Documents" / "arthurwang_DB")))
    podcast_root   = cfg.get("podcast_root", f"{vault_root}/Podcast")
    safe_name      = re.sub(r'[/\\:*?"<>|]', ' ', name).strip()

    note_dir_map   = {"investment": f"{vault_root}/投資"}
    note_dir       = note_dir_map.get(note_type, f"{vault_root}/AI Knowledge")
    transcript_dir = f"{podcast_root}/{safe_name}/transcripts"

    # 建立資料夾
    for d in [transcript_dir]:
        Path(d).mkdir(parents=True, exist_ok=True)

    new_pod = {
        "id":                   pod_id,
        "name":                 name,
        "rss":                  rss,
        "apple_id":             str(body.get("apple_id") or ""),
        "artwork":              str(body.get("artwork") or ""),
        "language":             language,
        "note_type":            note_type,
        "note_dir":             note_dir,
        "transcript_dir":       transcript_dir,
        "reading_list_category": "投資" if note_type == "investment" else "AI Knowledge",
    }

    podcasts.append(new_pod)
    cfg["podcasts"] = podcasts
    save_config(cfg)

    return new_pod


@router.delete("/api/podcasters/{podcast_id}")
def remove_podcaster(podcast_id: str):
    """從 config 移除 podcaster（不刪資料）"""
    cfg = load_config()
    podcasts = cfg.get("podcasts", [])
    new_list = [p for p in podcasts if p["id"] != podcast_id]
    if len(new_list) == len(podcasts):
        raise HTTPException(404, f"找不到 podcast: {podcast_id}")
    cfg["podcasts"] = new_list
    save_config(cfg)
    return {"deleted": podcast_id}


@router.get("/api/podcasters/{podcast_id}/remote-episodes")
def get_remote_episodes(podcast_id: str, limit: int = 50):
    """從 iTunes 取該 podcaster 的遠端集數列表（不需要已下載）"""
    pod = get_podcast_config(podcast_id)
    if not pod:
        raise HTTPException(404, f"找不到 podcast: {podcast_id}")

    apple_id = pod.get("apple_id", "")

    # 優先用 apple_id 查 iTunes
    if apple_id:
        try:
            url = (
                f"https://itunes.apple.com/lookup?id={apple_id}"
                f"&media=podcast&entity=podcastEpisode&limit={limit}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read())

            episodes = []
            for item in data.get("results", []):
                if item.get("kind") != "podcast-episode":
                    continue
                ms = item.get("trackTimeMillis", 0)
                duration = f"{ms//60000}:{(ms%60000)//1000:02d}" if ms else ""
                episodes.append({
                    "title":       item.get("trackName", ""),
                    "date":        item.get("releaseDate", "")[:10],
                    "duration":    duration,
                    "description": (item.get("shortDescription") or item.get("description") or "")[:200],
                    "artwork":     item.get("artworkUrl160") or item.get("artworkUrl60") or "",
                    "episode_url": item.get("episodeUrl") or item.get("previewUrl") or "",
                    "guid":        item.get("episodeGuid", ""),
                })
            return {"source": "itunes", "episodes": episodes}
        except Exception:
            pass  # fallback to yt-dlp

    # Fallback：用 yt-dlp 掃 RSS（較慢）
    try:
        r = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--print",
             "%(playlist_index)s|%(title)s|%(upload_date)s|%(duration)s",
             pod["rss"]],
            capture_output=True, text=True, timeout=30,
        )
        episodes = []
        for line in r.stdout.strip().splitlines():
            parts = line.split("|")
            if len(parts) < 2:
                continue
            ud = parts[2].strip() if len(parts) > 2 else ""
            date_str = f"{ud[:4]}-{ud[4:6]}-{ud[6:]}" if len(ud) == 8 else ""
            dur_s = int(parts[3].strip()) if len(parts) > 3 and parts[3].strip().isdigit() else 0
            episodes.append({
                "title":       parts[1].strip(),
                "date":        date_str,
                "duration":    f"{dur_s//60}:{dur_s%60:02d}" if dur_s else "",
                "description": "",
                "artwork":     "",
                "episode_url": "",
                "guid":        "",
            })
        return {"source": "yt-dlp", "episodes": episodes}
    except Exception as e:
        raise HTTPException(502, f"無法取得集數列表：{e}")


@router.get("/api/rss-preview")
def rss_preview(rss: str):
    """預覽 RSS 節目資訊（給前端表單用）"""
    if not rss:
        raise HTTPException(400, "缺少 rss 參數")
    meta = _fetch_rss_meta(rss)
    return meta


@router.get("/api/search-podcasts")
def search_podcasts(q: str, limit: int = 8):
    """用 iTunes Search API 搜尋 Podcast 節目，回傳名稱 + RSS"""
    if not q or len(q.strip()) < 2:
        raise HTTPException(400, "搜尋關鍵字太短")
    url = (
        "https://itunes.apple.com/search?"
        + urllib.parse.urlencode({"media": "podcast", "term": q.strip(), "limit": limit})
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        results = []
        for p in data.get("results", []):
            feed = p.get("feedUrl", "")
            if not feed:
                continue
            results.append({
                "name":          p.get("collectionName", ""),
                "artist":        p.get("artistName", ""),
                "rss":           feed,
                "apple_id":      p.get("collectionId", ""),
                "episode_count": p.get("trackCount", 0),
                "artwork":       p.get("artworkUrl600") or p.get("artworkUrl100", ""),
                "genres":        p.get("genres", []),
            })
        return results
    except Exception as e:
        raise HTTPException(502, f"搜尋失敗：{e}")


@router.get("/api/episodes")
def list_episodes():
    return build_episode_list()


@router.post("/api/download")
def start_download(body: dict):
    """
    觸發背景下載。
    body: { podcast_id: str, episode: str }  (episode = "latest" | "663" | "EP663")
    回傳: { job_id: str }
    """
    podcast_id = body.get("podcast_id", "")
    episode    = body.get("episode", "latest")

    if not podcast_id:
        raise HTTPException(400, "缺少 podcast_id")

    pod_cfg = get_podcast_config(podcast_id)
    if not pod_cfg:
        raise HTTPException(404, f"找不到 podcast: {podcast_id}")

    # 正規化集數：把 "EP663" → "663"，"latest" 維持
    ep_norm = re.sub(r'^EP', '', episode.strip(), flags=re.IGNORECASE) if episode.lower() != "latest" else "latest"

    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "job_id":     job_id,
        "type":       "pod_download",
        "podcast_id": podcast_id,
        "episode":    ep_norm,
        "status":     "pending",
        "log":        [],
        "started_at": time.time(),
    }

    t = threading.Thread(target=_run_download, args=(job_id, podcast_id, ep_norm), daemon=True)
    t.start()

    return {"job_id": job_id, "podcast_id": podcast_id, "episode": ep_norm}


def _enrich_job(job: dict) -> dict:
    """補上 title 欄位（從 info.json 取，供前端顯示用），並過濾不可序列化的私有欄位。"""
    out = {k: v for k, v in job.items() if not k.startswith("_")}
    if not out.get("title"):
        video_id = out.get("video_id", "")
        if video_id:
            from settings import YT_DATA_DIR
            info_path = YT_DATA_DIR / video_id / "info.json"
            if info_path.exists():
                try:
                    title = json.loads(info_path.read_text()).get("title", "")
                    if title:
                        out["title"] = title
                except Exception:
                    pass
    return out


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    """查詢下載進度"""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"找不到 job: {job_id}")
    return _enrich_job(job)


@router.get("/api/jobs")
def list_jobs():
    """列出所有 jobs（最新 20 個）"""
    jobs = sorted(_jobs.values(), key=lambda j: j["started_at"], reverse=True)[:20]
    return [_enrich_job(j) for j in jobs]



@router.get("/api/episodes/{episode_id}/note")
def get_note(episode_id: str):
    """回傳 Obsidian .md 筆記解析結果"""
    parts = episode_id.split("_", 1)
    podcast_id    = parts[0]
    episode_label = parts[1] if len(parts) == 2 else episode_id

    note_path = find_note_for_episode(podcast_id, episode_label)
    if not note_path:
        raise HTTPException(404, "此集尚無筆記")
    return parse_md_note(note_path)


@router.get("/api/episodes/{episode_id}/transcript")
def get_transcript(episode_id: str):
    """回傳逐字稿（優先 Podcast 永久目錄，fallback data/episodes）"""
    parts = episode_id.split("_", 1)
    podcast_id    = parts[0]
    episode_label = parts[1] if len(parts) == 2 else episode_id

    txt_path = get_permanent_transcript(podcast_id, episode_label)
    if txt_path is None:
        work_txt = DATA_DIR / episode_id / "transcript.txt"
        if work_txt.exists():
            txt_path = work_txt
    if txt_path is None:
        raise HTTPException(404, "此集尚無逐字稿")

    segments = parse_transcript_txt(txt_path)
    duration = None
    json_path = DATA_DIR / episode_id / "transcript.json"
    if json_path.exists():
        duration = json.loads(json_path.read_text()).get("duration")

    return {"segments": segments, "duration": duration, "source": str(txt_path)}


@router.get("/api/episodes/{episode_id}/audio")
def get_audio(episode_id: str):
    audio_path = DATA_DIR / episode_id / "audio.mp3"
    if not audio_path.exists():
        raise HTTPException(404, "此集無音頻檔案")
    return FileResponse(str(audio_path), media_type="audio/mpeg",
                        headers={"Accept-Ranges": "bytes"})


@router.get("/api/config")
def get_config():
    return load_config()


@router.get("/api/podcasts")
def list_podcasts():
    """Alias for /api/podcasters — used by frontend"""
    return list_podcasters()


@router.post("/api/episodes/{episode_id}/analyze")
def analyze_episode(episode_id: str):
    """
    用 analyze.py + claude -p 從逐字稿產生筆記。
    需要已有逐字稿（永久目錄或 data/episodes）。
    回傳 { job_id }
    """
    parts = episode_id.split("_", 1)
    podcast_id    = parts[0]
    episode_label = parts[1] if len(parts) == 2 else episode_id

    pod_cfg = get_podcast_config(podcast_id)
    if not pod_cfg:
        raise HTTPException(404, f"找不到 podcast: {podcast_id}")

    transcript_path = get_permanent_transcript(podcast_id, episode_label)
    if transcript_path is None:
        work_txt = DATA_DIR / episode_id / "transcript.txt"
        if work_txt.exists():
            transcript_path = work_txt
    if transcript_path is None:
        raise HTTPException(404, "此集尚無逐字稿，無法產生筆記")

    work_dir = transcript_path.parent if transcript_path.parent != Path(pod_cfg.get("transcript_dir", "")) else DATA_DIR / episode_id
    if not work_dir.exists():
        work_dir = transcript_path.parent

    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "job_id":     job_id,
        "type":       "pod_analyze",
        "podcast_id": podcast_id,
        "episode":    episode_label,
        "status":     "pending",
        "phase":      "準備中",
        "progress":   0,
        "log":        [],
        "started_at": time.time(),
    }

    def _run_analyze(job_id, work_dir, podcast_id):
        import os, subprocess as sp
        from settings import SKILL_DIR
        job = _jobs[job_id]
        job["status"] = "running"
        job["phase"]  = "準備中"
        analyze_script = SKILL_DIR / "scripts" / "analyze.py"
        proc = sp.Popen(
            ["python3.10", str(analyze_script), str(work_dir), "--podcast", podcast_id],
            stdout=sp.PIPE, stderr=sp.STDOUT, bufsize=1, text=True,
            env={**os.environ, "PODCAST_ID": podcast_id},
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            if line.startswith("PROGRESS:"):
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    try:
                        job["progress"] = int(parts[1])
                    except ValueError:
                        pass
                    if len(parts) >= 3:
                        job["phase"] = parts[2]
            else:
                job["log"].append(line)
        proc.wait()
        if proc.returncode == 0:
            job["status"]   = "done"
            job["phase"]    = "完成"
            job["progress"] = 100
            # 寫入 inbox
            pod_cfg2 = get_podcast_config(podcast_id)
            note_path = find_note_for_episode(podcast_id, episode_label)
            # 從筆記標題取發布日期
            pub_date = ""
            if note_path:
                import re as _re
                m = _re.match(r'^(\d{4}-\d{2}-\d{2})', note_path.stem)
                if m:
                    pub_date = m.group(1)
            title = note_path.stem if note_path else episode_label
            inbox_item = {
                "id":         f"podcast:{podcast_id}:{episode_label}",
                "type":       "podcast",
                "podcast_id": podcast_id,
                "podcast":    pod_cfg2.get("name", podcast_id),
                "episode":    episode_label,
                "title":      title,
                "note_path":  str(note_path) if note_path else "",
                "artwork":    pod_cfg2.get("artwork", ""),
                "pub_date":     pub_date,
                "note_created": int(note_path.stat().st_ctime) if note_path else 0,
            }
            items = _load_inbox()
            if not any(i.get("id") == inbox_item["id"] for i in items):
                inbox_item["ts"] = time.time()
                items.insert(0, inbox_item)
                _save_inbox(items)
        else:
            job["status"] = "error"
            job["phase"]  = "分析失敗"
        job["finished_at"] = time.time()

    t = threading.Thread(target=_run_analyze, args=(job_id, work_dir, podcast_id), daemon=True)
    t.start()

    return {"job_id": job_id, "podcast_id": podcast_id, "episode": episode_label}


@router.get("/api/episodes/{episode_id}/note-raw")
def get_note_raw(episode_id: str):
    """回傳 Obsidian .md 筆記的原始文字"""
    parts = episode_id.split("_", 1)
    podcast_id    = parts[0]
    episode_label = parts[1] if len(parts) == 2 else episode_id
    note_path = find_note_for_episode(podcast_id, episode_label)
    if not note_path:
        raise HTTPException(404, "此集尚無筆記")
    return {"markdown": note_path.read_text(encoding="utf-8"), "path": str(note_path)}


def _apply_highlight(content: str, text: str) -> str | None:
    """在 content 裡找 text 並包上 ==...==，回傳新內容；找不到回傳 None。"""
    import re as _re
    if f"=={text}==" in content:
        return content  # already highlighted
    if text in content:
        return content.replace(text, f"=={text}==", 1)
    # 前端選到的是 rendered text，可能缺少 markdown 符號（**、_、`）
    # 用 re.escape 後在 word boundary 找，允許中間有 markdown inline 符號
    escaped = _re.escape(text)
    # 允許文字前後有 **, *, _, ` 等 inline markdown 符號
    pattern = _re.sub(r'\\ ', r'[\\*_`~]*\\s*[\\*_`~]*', escaped)
    m = _re.search(pattern, content)
    if m:
        matched = m.group(0)
        if f"=={matched}==" not in content:
            return content[:m.start()] + f"=={matched}==" + content[m.end():]
    return None


@router.patch("/api/episodes/{episode_id}/highlight")
def highlight_episode(episode_id: str, body: dict):
    """在 .md 裡把選取的文字包上或移除 ==...==（Obsidian 螢光筆語法）"""
    text   = (body.get("text") or "").strip()
    remove = body.get("remove", False)
    if not text:
        raise HTTPException(400, "缺少 text")
    parts = episode_id.split("_", 1)
    podcast_id    = parts[0]
    episode_label = parts[1] if len(parts) == 2 else episode_id
    note_path = find_note_for_episode(podcast_id, episode_label)
    if not note_path:
        raise HTTPException(404, "此集尚無筆記")
    content = note_path.read_text(encoding="utf-8")
    if remove:
        if f"=={text}==" not in content:
            return {"status": "not_found"}
        note_path.write_text(content.replace(f"=={text}==", text, 1), encoding="utf-8")
        return {"status": "removed"}
    new_content = _apply_highlight(content, text)
    if new_content is None:
        raise HTTPException(422, "在筆記中找不到此文字")
    if new_content == content:
        return {"status": "already_highlighted"}
    note_path.write_text(new_content, encoding="utf-8")
    return {"status": "ok"}


@router.delete("/api/episodes/{episode_id}/note")
def delete_episode_note(episode_id: str):
    """刪除 Obsidian 筆記檔案"""
    parts = episode_id.split("_", 1)
    podcast_id    = parts[0]
    episode_label = parts[1] if len(parts) == 2 else episode_id
    note_path = find_note_for_episode(podcast_id, episode_label)
    if not note_path:
        raise HTTPException(404, "此集尚無筆記")
    note_path.unlink()
    return {"deleted": str(note_path)}
