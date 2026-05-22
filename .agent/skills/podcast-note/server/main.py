#!/usr/bin/env python3.10
"""
Podcast Note Viewer — FastAPI backend
資料來源：Obsidian 投資筆記（.md）+ data/episodes（音頻、逐字稿）
"""

import contextlib
import json
import os
import re
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

SKILL_DIR   = Path(__file__).parent.parent
DATA_DIR    = SKILL_DIR / "data" / "episodes"
CONFIG_PATH = SKILL_DIR / "config" / "podcasts.json"
STATIC_DIR  = Path(__file__).parent / "static"

YT_SKILL_DIR   = SKILL_DIR.parent / "transcript-note"
YT_DATA_DIR    = YT_SKILL_DIR / "data" / "transcripts"
YT_QUEUE_FILE  = YT_SKILL_DIR / "data" / "queue.txt"
YT_PROC_FILE   = YT_SKILL_DIR / "data" / "processed_ids.txt"
YT_CHANNEL_CFG = YT_SKILL_DIR / "config" / "channels.json"
YT_NOTE_DIR    = Path("/home/trx50/Documents/arthurwang_DB/影片筆記")

app = FastAPI(title="Podcast Note Viewer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Config helpers ──────────────────────────────────────────────────────────

def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}

def get_podcast_config(podcast_id: str) -> dict:
    cfg = load_config()
    return next((p for p in cfg.get("podcasts", []) if p["id"] == podcast_id), {})


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


# ── Job store (in-memory) ───────────────────────────────────────────────────
# { job_id: { status, podcast_id, episode, log, started_at } }
_jobs: dict[str, dict] = {}

DOWNLOAD_SH = SKILL_DIR / "scripts" / "download.sh"


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


_PROGRESS_RE = re.compile(r'\[download\]\s+(\d+(?:\.\d+)?)%\s+of\s+([\d.]+\S+)(?:\s+at\s+([\d.]+\S+))?(?:\s+ETA\s+(\S+))?')


def _run_download(job_id: str, podcast_id: str, episode: str):
    job = _jobs[job_id]
    job["status"]   = "running"
    job["log"]      = []
    job["progress"] = 0        # 0-100
    job["size"]     = ""
    job["speed"]    = ""
    job["eta"]      = ""
    job["phase"]    = "準備中"  # 準備中 / 解析 / 下載中 / 完成

    def log(line: str):
        job["log"].append(line)

    def parse_progress(raw: str):
        m = _PROGRESS_RE.search(raw)
        if m:
            job["progress"] = float(m.group(1))
            job["size"]     = m.group(2) or ""
            job["speed"]    = m.group(3) or ""
            job["eta"]      = m.group(4) or ""
            job["phase"]    = "下載中"
        elif "[info]" in raw and "Downloading" in raw:
            job["phase"] = "解析中"
        elif "[download] Downloading item" in raw:
            job["phase"] = "下載中"

    try:
        # Step 1: 用 download.sh 下載（stdbuf 解除緩衝讓 \r progress 即時送出）
        cmd = ["stdbuf", "-o0", "-e0", "bash", str(DOWNLOAD_SH), podcast_id, episode]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )

        buf = b""
        while True:
            ch = proc.stdout.read(1)
            if not ch:
                break
            if ch in (b"\r", b"\n"):
                line = buf.decode("utf-8", errors="replace").strip()
                buf = b""
                if line:
                    parse_progress(line)
                    if not _PROGRESS_RE.search(line):
                        log(line)
            else:
                buf += ch
        if buf.strip():
            line = buf.decode("utf-8", errors="replace").strip()
            if line:
                parse_progress(line)
                if not _PROGRESS_RE.search(line):
                    log(line)

        proc.wait()
        if proc.returncode != 0:
            job["status"] = "error"
            job["phase"]  = "下載失敗"
            log(f"✗ 下載失敗（exit {proc.returncode}）")
            job["finished_at"] = time.time()
            return

        log("✓ 下載完成")

        # ── Step 2: 轉錄 ──────────────────────────────────────
        work_dir = SKILL_DIR / "data" / "episodes" / f"{podcast_id}_ep{episode}"
        audio    = next(work_dir.glob("audio.*"), None)
        if not audio:
            job["status"] = "error"
            job["phase"]  = "找不到音頻"
            log("✗ 找不到音頻檔，無法轉錄")
            job["finished_at"] = time.time()
            return

        # 從 env.sh 取 EPISODE_LABEL（如 EP663）
        env_sh = work_dir / "env.sh"
        episode_label = episode
        if env_sh.exists():
            for l in env_sh.read_text().splitlines():
                m = re.search(r'EPISODE_TITLE="([^"]*)"', l)
                if m:
                    ep_m = re.search(r'EP\d+', m.group(1))
                    if ep_m:
                        episode_label = ep_m.group(0)
                        break

        # 選模型（依 VRAM）
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            free_mb = int(r.stdout.strip().split()[0])
            model = "medium" if free_mb >= 3000 else ("small" if free_mb >= 1500 else "base")
        except Exception:
            model = "small"

        job["phase"]    = "轉錄中"
        job["progress"] = 0
        log(f"→ 開始轉錄（模型：{model}）")

        # 預先取音頻時長（從 meta.json 或 ffprobe）
        duration_s: float = 0.0
        meta_path = work_dir / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                dur = meta.get("duration") or meta.get("duration_string") or 0
                if isinstance(dur, (int, float)):
                    duration_s = float(dur)
            except Exception:
                pass
        if not duration_s:
            try:
                ff = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json",
                     "-show_format", str(audio)],
                    capture_output=True, text=True, timeout=10,
                )
                duration_s = float(json.loads(ff.stdout)["format"]["duration"])
            except Exception:
                pass

        pod_cfg = get_podcast_config(podcast_id)
        lang    = pod_cfg.get("language", "zh")

        transcribe_cmd = [
            "python3.10",
            str(SKILL_DIR / "scripts" / "transcribe.py"),
            str(work_dir),
            "--lang",    lang,
            "--model",   model,
            "--device",  "auto",
            "--episode", episode_label,
        ]

        _TRANSCRIBE_RE = re.compile(r'\[\s*([\d.]+)s\]')

        import os as _os
        t_env = {
            **_os.environ,
            "PODCAST_ID": podcast_id,
            "LD_LIBRARY_PATH": (
                str(Path.home() / ".local/lib/python3.10/site-packages/nvidia/cudnn/lib")
                + ":" + _os.environ.get("LD_LIBRARY_PATH", "")
            ),
        }

        t_proc = subprocess.Popen(
            transcribe_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            env=t_env,
        )
        elapsed_s = 0.0
        for t_line in t_proc.stdout:
            t_line = t_line.rstrip()
            if not t_line:
                continue
            log(t_line)
            tm = _TRANSCRIBE_RE.search(t_line)
            if tm:
                elapsed_s = float(tm.group(1))
                if duration_s > 0:
                    job["progress"] = min(99, elapsed_s / duration_s * 100)
            # 備用：從轉錄完成行取時長
            dur_m = re.search(r'音頻\s+([\d.]+)\s*分', t_line)
            if dur_m and not duration_s:
                duration_s = float(dur_m.group(1)) * 60

        t_proc.wait()
        if t_proc.returncode != 0:
            job["status"] = "error"
            job["phase"]  = "轉錄失敗"
            log(f"✗ 轉錄失敗（exit {t_proc.returncode}）")
            job["finished_at"] = time.time()
            return

        log("✓ 轉錄完成")

        # ── Step 3: Claude 分析逐字稿 → 筆記 ────────────────
        job["phase"]    = "分析中"
        job["progress"] = 0
        log("→ 呼叫 Claude 分析逐字稿...")

        analyze_script = SKILL_DIR / "scripts" / "analyze.py"
        a_proc = subprocess.Popen(
            ["python3.10", str(analyze_script), str(work_dir), "--podcast", podcast_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            env={**_os.environ, "PODCAST_ID": podcast_id},
        )

        # 模擬進度（分析階段沒有精確進度，用 indeterminate）
        job["progress"] = 0

        for a_line in a_proc.stdout:
            a_line = a_line.rstrip()
            if not a_line:
                continue
            log(a_line)
            # 偵測到筆記產生
            if "筆記已寫入" in a_line or "筆記：" in a_line:
                job["progress"] = 90

        a_proc.wait()
        if a_proc.returncode == 0:
            job["status"]   = "done"
            job["progress"] = 100
            job["phase"]    = "完成"
            log("✓ 筆記產生完成")
        else:
            job["status"] = "error"
            job["phase"]  = "分析失敗"
            log(f"✗ 分析失敗（exit {a_proc.returncode}）")

    except Exception as e:
        job["status"] = "error"
        job["phase"]  = "失敗"
        job["log"].append(f"✗ 例外：{e}")

    job["finished_at"] = time.time()


# ── API routes ──────────────────────────────────────────────────────────────

@app.get("/api/podcasters")
def list_podcasters():
    """按 podcaster 分組，回傳封面頁所需資料"""
    cfg = load_config()
    episodes = build_episode_list()

    result = []
    for pod in cfg.get("podcasts", []):
        pid = pod["id"]
        pod_eps = [e for e in episodes if e["podcast_id"] == pid]
        note_count       = sum(1 for e in pod_eps if e["has_note"])
        transcript_count = sum(1 for e in pod_eps if e["has_transcript"])
        result.append({
            "id":               pid,
            "name":             pod.get("name", pid),
            "artwork":          pod.get("artwork", ""),
            "language":         pod.get("language", ""),
            "note_type":        pod.get("note_type", ""),
            "episode_count":    len(pod_eps),
            "note_count":       note_count,
            "transcript_count": transcript_count,
            "latest_episode":   pod_eps[0] if pod_eps else None,
            "episodes":         pod_eps,
        })
    return result


@app.post("/api/podcasters")
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

    vault_root     = cfg.get("vault_root", "/home/trx50/Documents/arthurwang_DB")
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
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    return new_pod


@app.delete("/api/podcasters/{podcast_id}")
def remove_podcaster(podcast_id: str):
    """從 config 移除 podcaster（不刪資料）"""
    cfg = load_config()
    podcasts = cfg.get("podcasts", [])
    new_list = [p for p in podcasts if p["id"] != podcast_id]
    if len(new_list) == len(podcasts):
        raise HTTPException(404, f"找不到 podcast: {podcast_id}")
    cfg["podcasts"] = new_list
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"deleted": podcast_id}


@app.get("/api/podcasters/{podcast_id}/remote-episodes")
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


@app.get("/api/rss-preview")
def rss_preview(rss: str):
    """預覽 RSS 節目資訊（給前端表單用）"""
    if not rss:
        raise HTTPException(400, "缺少 rss 參數")
    meta = _fetch_rss_meta(rss)
    return meta


@app.get("/api/search-podcasts")
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


@app.get("/api/episodes")
def list_episodes():
    return build_episode_list()


@app.post("/api/download")
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
        "podcast_id": podcast_id,
        "episode":    ep_norm,
        "status":     "pending",
        "log":        [],
        "started_at": time.time(),
    }

    t = threading.Thread(target=_run_download, args=(job_id, podcast_id, ep_norm), daemon=True)
    t.start()

    return {"job_id": job_id, "podcast_id": podcast_id, "episode": ep_norm}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    """查詢下載進度"""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"找不到 job: {job_id}")
    return job


@app.get("/api/jobs")
def list_jobs():
    """列出所有 jobs（最新 20 個）"""
    return sorted(_jobs.values(), key=lambda j: j["started_at"], reverse=True)[:20]



@app.get("/api/episodes/{episode_id}/note")
def get_note(episode_id: str):
    """回傳 Obsidian .md 筆記解析結果"""
    parts = episode_id.split("_", 1)
    podcast_id    = parts[0]
    episode_label = parts[1] if len(parts) == 2 else episode_id

    note_path = find_note_for_episode(podcast_id, episode_label)
    if not note_path:
        raise HTTPException(404, "此集尚無筆記")
    return parse_md_note(note_path)


@app.get("/api/episodes/{episode_id}/transcript")
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


@app.get("/api/episodes/{episode_id}/audio")
def get_audio(episode_id: str):
    audio_path = DATA_DIR / episode_id / "audio.mp3"
    if not audio_path.exists():
        raise HTTPException(404, "此集無音頻檔案")
    return FileResponse(str(audio_path), media_type="audio/mpeg",
                        headers={"Accept-Ranges": "bytes"})


@app.get("/api/config")
def get_config():
    return load_config()


READING_LIST_PATH = Path("/home/trx50/Documents/arthurwang_DB/待閱讀清單.md")
INBOX_PATH        = SKILL_DIR / "data" / "inbox.json"


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


@app.get("/api/inbox")
def get_inbox():
    """回傳未讀 inbox 通知"""
    return _load_inbox()


@app.post("/api/inbox/{item_id}/dismiss")
def dismiss_inbox(item_id: str):
    """標記某通知為已讀（從 inbox 移除）"""
    items = [i for i in _load_inbox() if i.get("id") != item_id]
    _save_inbox(items)
    return {"dismissed": item_id}


@app.post("/api/inbox/dismiss-all")
def dismiss_all_inbox():
    _save_inbox([])
    return {"dismissed": "all"}


@app.post("/api/check-new-episodes")
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


@app.get("/api/reading-status")
def get_reading_status():
    """
    解析待閱讀清單，回傳每個條目的已讀狀態。
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


@app.post("/api/reading-status/{ep_num}/read")
def mark_read(ep_num: str):
    """標記指定 EP 為已讀（[x]）—— 僅供 Arthur 使用"""
    if not READING_LIST_PATH.exists():
        raise HTTPException(404, "找不到待閱讀清單")

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


@app.post("/api/reading-status/{ep_num}/unread")
def mark_unread(ep_num: str):
    """標記指定 EP 為未讀（[ ]）"""
    if not READING_LIST_PATH.exists():
        raise HTTPException(404, "找不到待閱讀清單")

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


# ── YouTube helpers ─────────────────────────────────────────────────────────

def _yt_load_channels() -> list[dict]:
    if not YT_CHANNEL_CFG.exists():
        return []
    return json.loads(YT_CHANNEL_CFG.read_text()).get("channels", [])

def _yt_load_queue() -> list[str]:
    if not YT_QUEUE_FILE.exists():
        return []
    return [l.strip() for l in YT_QUEUE_FILE.read_text().splitlines() if l.strip()]

def _yt_load_processed() -> set[str]:
    if not YT_PROC_FILE.exists():
        return set()
    return {l.strip() for l in YT_PROC_FILE.read_text().splitlines() if l.strip()}

def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from any URL format."""
    patterns = [
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"youtube\.com/watch\?.*v=([A-Za-z0-9_-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
        r"youtube\.com/live/([A-Za-z0-9_-]{11})",
        r"youtube\.com/embed/([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return ""

def _yt_read_obsidian_note(md_path: str) -> dict:
    """從 Obsidian .md 取 title、channel、upload_date、topic、tags。"""
    try:
        text = Path(md_path).read_text(encoding="utf-8", errors="ignore")
        fm   = {}
        m    = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
        if m:
            for line in m.group(1).splitlines():
                kv = re.match(r'^(\w+):\s*"?(.+?)"?\s*$', line)
                if kv:
                    fm[kv.group(1)] = kv.group(2)
        tags = re.findall(r'  - (.+)', m.group(1) if m else "")
        tags = [t for t in tags if t not in ("影片筆記", "YouTube", "逐字稿筆記")]
        return {
            "title":      fm.get("title", ""),
            "channel":    fm.get("source", ""),
            "date":       fm.get("date", ""),
            "topic":      fm.get("topic", ""),
            "tags":       tags,
        }
    except Exception:
        return {}


def _yt_scan_videos() -> list[dict]:
    """Scan data/transcripts/ and match with Obsidian notes."""
    videos = []
    if not YT_DATA_DIR.exists():
        return videos

    processed = _yt_load_processed()

    for vid_dir in sorted(YT_DATA_DIR.iterdir(), reverse=True):
        if not vid_dir.is_dir():
            continue
        video_id = vid_dir.name

        info_path      = vid_dir / "info.json"
        analysis_path  = vid_dir / "analysis.json"
        condensed_path = vid_dir / "condensed.txt"
        note_ptr_path  = vid_dir / "note_path.txt"   # migration script 建立的指標

        info     = json.loads(info_path.read_text())     if info_path.exists()     else {}
        analysis = json.loads(analysis_path.read_text()) if analysis_path.exists() else {}

        # 優先讀 note_path.txt 指向的 Obsidian 筆記
        note_path   = None
        note_meta   = {}
        if note_ptr_path.exists():
            candidate = note_ptr_path.read_text().strip()
            if Path(candidate).exists():
                note_path = candidate
                note_meta = _yt_read_obsidian_note(candidate)

        # fallback: 掃 YT_NOTE_DIR（舊邏輯）
        if note_path is None and YT_NOTE_DIR.exists():
            for md in YT_NOTE_DIR.glob("**/*.md"):
                try:
                    if video_id in md.read_text(encoding="utf-8", errors="ignore"):
                        note_path = str(md)
                        note_meta = _yt_read_obsidian_note(note_path)
                        break
                except Exception:
                    pass

        # title: analysis > obsidian note > info.json
        title_zh    = (analysis.get("title_zh")
                       or note_meta.get("title")
                       or info.get("title", video_id))
        channel     = info.get("channel") or note_meta.get("channel", "")
        upload_date = info.get("upload_date") or note_meta.get("date", "")
        topic       = analysis.get("topic") or note_meta.get("topic", "")
        tags = analysis.get("tags") or note_meta.get("tags", [])

        # transcript source: "cc" | "whisper" | "description" | "none"
        src_path = vid_dir / "transcript_source.txt"
        transcript_source = src_path.read_text().strip() if src_path.exists() else (
            "cc" if condensed_path.exists() else "none"
        )
        # condensed.txt starting with "[Description" means description-only fallback
        if condensed_path.exists() and transcript_source == "none":
            first = condensed_path.read_text(encoding="utf-8", errors="ignore")[:30]
            transcript_source = "description" if "[Description" in first else "cc"

        videos.append({
            "id":               video_id,
            "title_zh":         title_zh,
            "channel":          channel,
            "upload_date":      upload_date,
            "has_analysis":     analysis_path.exists(),
            "has_transcript":   condensed_path.exists() and transcript_source in ("cc", "whisper"),
            "transcript_source": transcript_source,
            "has_note":         note_path is not None,
            "note_path":        note_path,
            "url":              f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail":        f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
            "topic":            topic,
            "tags":             tags,
            "reading_list_category": analysis.get("reading_list_category", ""),
            "is_processed":     video_id in processed,
        })

    return videos

def _yt_parse_note(video_id: str) -> dict:
    """Parse analysis.json（or Obsidian .md）+ info.json into frontend-ready dict."""
    vid_dir       = YT_DATA_DIR / video_id
    analysis_path = vid_dir / "analysis.json"
    info_path     = vid_dir / "info.json"
    note_ptr_path = vid_dir / "note_path.txt"

    analysis = json.loads(analysis_path.read_text()) if analysis_path.exists() else {}
    info     = json.loads(info_path.read_text())     if info_path.exists()     else {}

    # 若沒有 analysis.json，從 Obsidian .md 建構等效資料
    if not analysis and note_ptr_path.exists():
        md_path = note_ptr_path.read_text().strip()
        if Path(md_path).exists():
            analysis = _yt_build_analysis_from_md(md_path, video_id)

    return {
        "title_zh":     analysis.get("title_zh") or info.get("title", video_id),
        "topic":        analysis.get("topic", ""),
        "tags":         analysis.get("tags", []),
        "tldr":         analysis.get("tldr", {}),
        "sections":     analysis.get("sections", []),
        "key_insights": analysis.get("key_insights", []),
        "data_table":   analysis.get("data_table", []),
        "_meta": {
            "channel":    info.get("channel", ""),
            "duration":   info.get("duration", ""),
            "upload_date": info.get("upload_date", ""),
            "video_id":   video_id,
            "url":        f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail":  f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        },
    }


def _yt_build_analysis_from_md(md_path: str, video_id: str) -> dict:
    """從 Obsidian .md 建構 analysis-like dict（供 detail view 使用）。"""
    try:
        text = Path(md_path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}

    # frontmatter
    fm, body = {}, text
    fm_m = re.match(r'^---\n(.*?)\n---\n?', text, re.DOTALL)
    if fm_m:
        body = text[fm_m.end():]
        for line in fm_m.group(1).splitlines():
            kv = re.match(r'^(\w+):\s*"?(.+?)"?\s*$', line)
            if kv:
                fm[kv.group(1)] = kv.group(2)
        tags = [t for t in re.findall(r'  - (.+)', fm_m.group(1))
                if t not in ("影片筆記", "YouTube", "逐字稿筆記")]
    else:
        tags = []

    # TL;DR block
    tldr = {}
    tldr_block = re.search(r'## TL;DR\n(.*?)(?=\n## |\Z)', body, re.DOTALL)
    if tldr_block:
        key_map = {
            "核心主張": "核心主張", "關鍵機制": "關鍵機制_問題",
            "重要結論": "重要數字", "重要數字": "重要數字",
            "適用條件": "風險_限制", "操作建議": "操作建議",
        }
        for line in tldr_block.group(1).splitlines():
            m2 = re.match(r'- \*\*(.+?)\*\*[：:]\s*(.+)', line)
            if m2:
                raw_key = m2.group(1).split("/")[0].strip()
                for k, v in key_map.items():
                    if k in raw_key:
                        tldr[v] = m2.group(2).strip()
                        break

    # sections（### N. ...）
    sections = []
    for sec in re.finditer(
        r'### (\d+)\.\s*(?:\[(\d+:\d+)\]\s*)?(.*?)\n(.*?)(?=\n### \d+\.|\n## |\Z)',
        body, re.DOTALL
    ):
        points = [l.rstrip() for l in sec.group(4).strip().splitlines() if l.strip()]
        sections.append({"title": sec.group(3).strip(), "start_time": sec.group(2) or "", "content_points": points})

    # key insights
    insights = []
    ins_m = re.search(r'## 關鍵洞見\n(.*?)(?=\n## |\Z)', body, re.DOTALL)
    if ins_m:
        for line in ins_m.group(1).splitlines():
            m3 = re.match(r'- (.+)', line.strip())
            if m3:
                insights.append(m3.group(1))

    # data table
    data_table = []
    tbl_m = re.search(r'## 附[：:]關鍵數據速查\n(.*?)(?=\n## |\Z)', body, re.DOTALL)
    if tbl_m:
        for row in re.finditer(r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|', tbl_m.group(1)):
            vals = [row.group(i).strip() for i in (1, 2, 3)]
            if vals[0] and vals[0] not in ("指標", "----", "——"):
                data_table.append({"指標": vals[0], "數值": vals[1], "備註": vals[2]})

    return {
        "title_zh":     fm.get("title", ""),
        "topic":        fm.get("topic", ""),
        "tags":         tags,
        "tldr":         tldr,
        "sections":     sections,
        "key_insights": insights,
        "data_table":   data_table,
    }

def _yt_parse_condensed(video_id: str) -> list[dict]:
    """Parse condensed.txt into segments list."""
    path = YT_DATA_DIR / video_id / "condensed.txt"
    if not path.exists():
        return []
    segments = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*)", line)
        if m:
            ts = m.group(1)
            parts = ts.split(":")
            if len(parts) == 3:
                seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else:
                seconds = int(parts[0]) * 60 + int(parts[1])
            segments.append({
                "time":    ts,
                "seconds": seconds,
                "text":    m.group(2).strip(),
            })
    return segments


def _yt_fetch_rss_dates(channel_id: str) -> dict[str, str]:
    """從 YouTube RSS feed 取最新 15 支影片的發布日期（video_id → YYYY-MM-DD）。"""
    try:
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            xml = r.read().decode("utf-8", errors="ignore")
        dates = {}
        for entry in re.findall(r'<entry>(.*?)</entry>', xml, re.DOTALL):
            vid = re.search(r'<yt:videoId>(.*?)</yt:videoId>', entry)
            pub = re.search(r'<published>(.*?)</published>', entry)
            if vid and pub:
                dates[vid.group(1).strip()] = pub.group(1).strip()[:10]
        return dates
    except Exception:
        return {}


def _yt_fetch_channel_avatar(handle: str) -> str:
    """從頻道頁面 HTML 擷取頻道頭像 URL，並快取到 channels.json。"""
    # 先從 config 讀快取
    if YT_CHANNEL_CFG.exists():
        cfg = json.loads(YT_CHANNEL_CFG.read_text())
        for ch in cfg.get("channels", []):
            if ch.get("handle") == handle and ch.get("avatar"):
                return ch["avatar"]

    try:
        url = f"https://www.youtube.com/{handle}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")

        # pattern: "avatar":{"thumbnails":[{"url":"https://yt3.googleusercontent.com/..."}
        m = re.search(r'"avatar"\s*:\s*\{"thumbnails"\s*:\s*\[\s*\{"url"\s*:\s*"(https://yt3[^"]+)"', html)
        if not m:
            # fallback: any yt3.googleusercontent.com URL in the page
            m = re.search(r'(https://yt3\.googleusercontent\.com/[A-Za-z0-9_\-=]+)', html)
        avatar = m.group(1) if m else ""

        # 寫回快取
        if avatar and YT_CHANNEL_CFG.exists():
            cfg = json.loads(YT_CHANNEL_CFG.read_text())
            for ch in cfg.get("channels", []):
                if ch.get("handle") == handle:
                    ch["avatar"] = avatar
                    YT_CHANNEL_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
                    break

        return avatar
    except Exception:
        return ""


# ── YouTube API routes ───────────────────────────────────────────────────────

@app.get("/api/youtube/channels/{handle}/remote-videos")
def yt_remote_videos(handle: str, limit: int = 30):
    """用 yt-dlp 抓頻道影片列表，比對本地已處理狀態"""
    handle = urllib.parse.unquote(handle)
    if not handle.startswith("@"):
        handle = "@" + handle

    channel_url = f"https://www.youtube.com/{handle}/videos"
    try:
        r = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--playlist-items", f"1-{limit}",
             "--print", "%(id)s|%(title)s|%(upload_date)s|%(duration)s",
             channel_url],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0 and not r.stdout.strip():
            raise HTTPException(502, f"yt-dlp 失敗：{r.stderr[:200]}")
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "yt-dlp 超時，請稍後再試")

    processed  = _yt_load_processed()
    local_ids  = {d.name for d in YT_DATA_DIR.iterdir() if d.is_dir()} if YT_DATA_DIR.exists() else set()
    queued_ids = {_extract_video_id(u) for u in _yt_load_queue()} - {""}

    # 取得 channel_id（先查 config 快取，再用 yt-dlp 抓）
    channel_id = ""
    if YT_CHANNEL_CFG.exists():
        for ch in json.loads(YT_CHANNEL_CFG.read_text()).get("channels", []):
            if ch.get("handle") == handle and ch.get("channel_id"):
                channel_id = ch["channel_id"]
                break

    if not channel_id:
        try:
            r2 = subprocess.run(
                ["yt-dlp", "--flat-playlist", "--playlist-items", "1",
                 "--print", "%(playlist_channel_id)s",
                 f"https://www.youtube.com/{handle}/videos"],
                capture_output=True, text=True, timeout=15,
            )
            cid = r2.stdout.strip().splitlines()[0].strip() if r2.stdout.strip() else ""
            if cid and cid != "NA":
                channel_id = cid
                # 快取到 channels.json
                if YT_CHANNEL_CFG.exists():
                    cfg = json.loads(YT_CHANNEL_CFG.read_text())
                    for ch in cfg.get("channels", []):
                        if ch.get("handle") == handle:
                            ch["channel_id"] = channel_id
                            YT_CHANNEL_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
                            break
        except Exception:
            pass

    # 用 RSS 取最新 15 支的日期（channel_id → RSS feed）
    rss_dates: dict[str, str] = {}
    if channel_id:
        rss_dates = _yt_fetch_rss_dates(channel_id)

    videos = []
    for line in r.stdout.strip().splitlines():
        parts = line.split("|")
        if len(parts) < 2:
            continue
        video_id = parts[0].strip()
        title    = parts[1].strip()
        dur_raw  = parts[3].strip() if len(parts) > 3 else ""
        try:
            dur_s = int(float(dur_raw)) if dur_raw and dur_raw not in ("NA", "") else 0
        except ValueError:
            dur_s = 0
        duration = f"{dur_s // 60}:{dur_s % 60:02d}" if dur_s else ""

        # 日期：優先 RSS，其次 yt-dlp 欄位（通常是 NA），最後空字串
        ud = parts[2].strip() if len(parts) > 2 else ""
        upload_date = (
            rss_dates.get(video_id)
            or (f"{ud[:4]}-{ud[4:6]}-{ud[6:]}" if len(ud) == 8 else "")
        )

        has_local     = video_id in local_ids
        analysis_path = YT_DATA_DIR / video_id / "analysis.json"
        title_zh      = title
        if has_local and analysis_path.exists():
            try:
                title_zh = json.loads(analysis_path.read_text()).get("title_zh") or title
            except Exception:
                pass

        videos.append({
            "id":           video_id,
            "title":        title,
            "title_zh":     title_zh,
            "upload_date":  upload_date,
            "duration":     duration,
            "url":          f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail":    f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
            "has_local":    has_local,
            "has_analysis": has_local and analysis_path.exists(),
            "is_processed": video_id in processed,
            "is_queued":    video_id in queued_ids,
        })

    # 取頻道頭像（優先從 cache，cache miss 則同步抓一次）
    avatar = _yt_fetch_channel_avatar(handle)

    return {"handle": handle, "videos": videos, "avatar": avatar, "channel_id": channel_id}


@app.get("/api/youtube/channels")
def yt_list_channels():
    channels = _yt_load_channels()
    videos   = _yt_scan_videos()

    result = []
    for ch in channels:
        handle = ch.get("handle", "")
        name   = ch.get("name", handle)
        ch_videos = [v for v in videos if v["channel"].lower() == name.lower()
                     or v["channel"].replace(" ", "").lower() == name.replace(" ", "").lower()]
        result.append({
            "handle":      handle,
            "name":        name,
            "enabled":     ch.get("enabled", True),
            "limit":       ch.get("limit", 5),
            "avatar":      ch.get("avatar", ""),
            "video_count": len(ch_videos),
            "note_count":  sum(1 for v in ch_videos if v["has_note"]),
            "videos":      ch_videos,
        })

    # videos not matched to any configured channel
    known_names = {ch.get("name", "").lower() for ch in channels}
    other_videos = [v for v in videos
                    if v["channel"].lower() not in known_names
                    and v["channel"].replace(" ", "").lower() not in
                        {n.replace(" ", "") for n in known_names}]
    if other_videos:
        result.append({
            "handle":      "",
            "name":        "其他頻道",
            "enabled":     True,
            "limit":       0,
            "video_count": len(other_videos),
            "note_count":  sum(1 for v in other_videos if v["has_note"]),
            "videos":      other_videos,
        })

    return result


@app.get("/api/youtube/videos")
def yt_list_videos():
    return _yt_scan_videos()


@app.get("/api/youtube/videos/{video_id}/note")
def yt_get_note(video_id: str):
    vid_dir = YT_DATA_DIR / video_id
    has_analysis  = (vid_dir / "analysis.json").exists()
    has_note_ptr  = (vid_dir / "note_path.txt").exists() and Path(
        (vid_dir / "note_path.txt").read_text().strip()
    ).exists()
    if not has_analysis and not has_note_ptr:
        raise HTTPException(404, "此影片尚無分析結果")
    return _yt_parse_note(video_id)


@app.post("/api/youtube/videos/{video_id}/analyze")
def yt_start_analyze(video_id: str):
    """觸發 claude -p 自動分析逐字稿 → 產生 analysis.json + Obsidian 筆記"""
    vid_dir        = YT_DATA_DIR / video_id
    condensed_path = vid_dir / "condensed.txt"
    src_path       = vid_dir / "transcript_source.txt"

    if not condensed_path.exists():
        raise HTTPException(404, "此影片尚無逐字稿（condensed.txt）")

    transcript_source = src_path.read_text().strip() if src_path.exists() else "unknown"
    if transcript_source == "none":
        raise HTTPException(422, "逐字稿來源為 none（description fallback），建議先執行 Whisper 轉錄")

    analyze_script = YT_SKILL_DIR / "scripts" / "analyze.py"
    if not analyze_script.exists():
        raise HTTPException(500, f"找不到 analyze.py：{analyze_script}")

    job_id = f"yt-{video_id[:8]}-{str(uuid.uuid4())[:4]}"
    _jobs[job_id] = {
        "job_id":     job_id,
        "type":       "yt_analyze",
        "video_id":   video_id,
        "status":     "pending",
        "phase":      "排隊中",
        "progress":   0,
        "log":        [],
        "started_at": time.time(),
    }

    def _run():
        job = _jobs[job_id]
        job["status"] = "running"
        job["phase"]  = "分析中"

        def log(line):
            job["log"].append(line)

        try:
            proc = subprocess.Popen(
                ["python3.10", str(analyze_script), video_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=os.environ.copy(),
                cwd=str(YT_SKILL_DIR),
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    log(line)
            proc.wait()

            if proc.returncode == 0:
                job["status"]   = "done"
                job["phase"]    = "完成"
                job["progress"] = 100
                note_ptr = vid_dir / "note_path.txt"
                if note_ptr.exists():
                    log(f"筆記：{note_ptr.read_text().strip()}")
            else:
                job["status"] = "error"
                job["phase"]  = "分析失敗"
        except Exception as e:
            job["status"] = "error"
            job["phase"]  = "失敗"
            log(f"✗ 例外：{e}")

        job["finished_at"] = time.time()

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return {"job_id": job_id, "video_id": video_id}


@app.get("/api/youtube/videos/{video_id}/transcript")
def yt_get_transcript(video_id: str):
    segments = _yt_parse_condensed(video_id)
    if not segments:
        raise HTTPException(404, "此影片無壓縮逐字稿")
    info_path = YT_DATA_DIR / video_id / "info.json"
    duration  = json.loads(info_path.read_text()).get("duration") if info_path.exists() else None
    return {"segments": segments, "duration": duration, "video_id": video_id}


@app.get("/api/youtube/queue")
def yt_get_queue():
    return {"queue": _yt_load_queue(), "processed_count": len(_yt_load_processed())}


@app.post("/api/youtube/queue")
def yt_add_to_queue(body: dict):
    url = (body.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "缺少 url")
    video_id = _extract_video_id(url)
    if not video_id:
        raise HTTPException(422, "無法解析 YouTube video ID，請確認網址格式")

    processed = _yt_load_processed()
    if video_id in processed:
        raise HTTPException(409, f"此影片已處理過（{video_id}）")

    queue = _yt_load_queue()
    if url in queue or any(video_id in q for q in queue):
        raise HTTPException(409, "此影片已在佇列中")

    YT_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with YT_QUEUE_FILE.open("a", encoding="utf-8") as f:
        f.write(url + "\n")

    return {"video_id": video_id, "url": url, "queue_size": len(queue) + 1}


@app.delete("/api/youtube/queue")
def yt_clear_queue_item(body: dict):
    url = (body.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "缺少 url")
    queue = _yt_load_queue()
    new_q = [q for q in queue if q != url]
    YT_QUEUE_FILE.write_text("\n".join(new_q) + ("\n" if new_q else ""), encoding="utf-8")
    return {"removed": url, "queue_size": len(new_q)}


@app.get("/api/youtube/search-channels")
def yt_search_channels(q: str, limit: int = 8):
    """用 yt-dlp 搜尋 YouTube 頻道，回傳去重的頻道清單（含頭像、handle）"""
    if not q or len(q.strip()) < 2:
        raise HTTPException(400, "搜尋關鍵字太短")
    try:
        r = subprocess.run(
            ["yt-dlp", f"ytsearch{limit * 3}:{q.strip()}",
             "--flat-playlist",
             "--print", "%(channel)s|%(channel_id)s|%(uploader_id)s"],
            capture_output=True, text=True, timeout=20,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "搜尋超時")

    seen_ids: set[str] = set()
    results  = []
    for line in r.stdout.strip().splitlines():
        parts = line.split("|")
        if len(parts) < 3:
            continue
        name       = parts[0].strip()
        channel_id = parts[1].strip()
        uploader   = parts[2].strip()  # @Handle

        if not channel_id or channel_id in seen_ids:
            continue
        seen_ids.add(channel_id)

        handle = uploader if uploader.startswith("@") else f"@{uploader}"
        results.append({
            "name":       name,
            "handle":     handle,
            "channel_id": channel_id,
            "thumbnail":  f"https://img.youtube.com/vi/_placeholder/default.jpg",
        })
        if len(results) >= limit:
            break

    return results


@app.post("/api/youtube/channels")
def yt_add_channel(body: dict):
    raw    = (body.get("handle") or "").strip()
    name   = (body.get("name") or "").strip()
    if not raw:
        raise HTTPException(400, "缺少 handle（如 @ChannelName）")

    # 若使用者貼了完整 URL，自動抽出 @handle 部分
    url_match = re.search(r'youtube\.com/(@[A-Za-z0-9_\-\.]+)', raw)
    if url_match:
        handle = url_match.group(1)
    else:
        handle = raw if raw.startswith("@") else "@" + raw

    # handle 只允許 @英數字底線連字號，拒絕含 URL 或空格的值
    if not re.match(r'^@[A-Za-z0-9_\-\.]{2,50}$', handle):
        raise HTTPException(422, f"無效的 handle 格式：{handle}（應為 @ChannelName）")

    YT_CHANNEL_CFG.parent.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(YT_CHANNEL_CFG.read_text()) if YT_CHANNEL_CFG.exists() else {"channels": []}
    channels = cfg.get("channels", [])

    if any(c["handle"] == handle for c in channels):
        raise HTTPException(409, f"頻道 {handle} 已存在")

    channel_id = (body.get("channel_id") or "").strip()
    avatar     = (body.get("avatar") or "").strip()
    new_ch = {
        "handle":     handle,
        "name":       name or handle.lstrip("@"),
        "limit":      5,
        "enabled":    True,
        **({"channel_id": channel_id} if channel_id else {}),
        **({"avatar":     avatar}     if avatar     else {}),
    }
    channels.append(new_ch)
    cfg["channels"] = channels
    YT_CHANNEL_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return new_ch


@app.delete("/api/youtube/channels/{handle}")
def yt_remove_channel(handle: str):
    handle = urllib.parse.unquote(handle)
    if not YT_CHANNEL_CFG.exists():
        raise HTTPException(404, "頻道設定不存在")
    cfg      = json.loads(YT_CHANNEL_CFG.read_text())
    channels = cfg.get("channels", [])
    new_list = [c for c in channels if c["handle"] != handle]
    if len(new_list) == len(channels):
        raise HTTPException(404, f"找不到頻道 {handle}")
    cfg["channels"] = new_list
    YT_CHANNEL_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"deleted": handle}


@app.get("/api/podcasts")
def list_podcasts():
    """Alias for /api/podcasters — used by frontend"""
    return list_podcasters()


@app.get("/api/episodes/{episode_id}/note-raw")
def get_note_raw(episode_id: str):
    """回傳 Obsidian .md 筆記的原始文字"""
    parts = episode_id.split("_", 1)
    podcast_id    = parts[0]
    episode_label = parts[1] if len(parts) == 2 else episode_id
    note_path = find_note_for_episode(podcast_id, episode_label)
    if not note_path:
        raise HTTPException(404, "此集尚無筆記")
    return {"markdown": note_path.read_text(encoding="utf-8"), "path": str(note_path)}


def _backfill_avatars():
    """啟動時在背景補抓所有缺 avatar 的 YT 頻道。"""
    if not YT_CHANNEL_CFG.exists():
        return
    cfg = json.loads(YT_CHANNEL_CFG.read_text())
    missing = [ch for ch in cfg.get("channels", []) if not ch.get("avatar")]
    if not missing:
        return
    def _run():
        for ch in missing:
            handle = ch.get("handle", "")
            if not handle:
                continue
            avatar = _yt_fetch_channel_avatar(handle)
            print(f"[avatar] {handle} → {'ok' if avatar else 'not found'}")
    threading.Thread(target=_run, daemon=True).start()


@contextlib.asynccontextmanager
async def lifespan(_app):
    _backfill_avatars()
    yield

app.router.lifespan_context = lifespan


@app.post("/api/youtube/channels/refresh-avatars")
def yt_refresh_avatars():
    """手動觸發補抓所有缺 avatar 的頻道（背景執行）。"""
    _backfill_avatars()
    return {"status": "started"}


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=7654, reload=True)
