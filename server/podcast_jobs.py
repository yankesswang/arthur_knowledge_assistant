"""Background podcast processing jobs."""

import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from cache_store import save_job_snapshot
from config_store import get_podcast_config
from note_generation import get_note_provider
from settings import DATA_DIR, PODCAST_SCRIPTS_DIR, TRANSCRIPTION_SETTINGS_PATH
from state import _jobs

def get_transcription_settings():
    import json as _json
    if TRANSCRIPTION_SETTINGS_PATH.exists():
        try:
            return _json.loads(TRANSCRIPTION_SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"mode": "local"}

DOWNLOAD_SH = PODCAST_SCRIPTS_DIR / "download.sh"

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
    save_job_snapshot(job)

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
            save_job_snapshot(job)
            return

        log("✓ 下載完成")

        # ── Step 2: 轉錄 ──────────────────────────────────────
        work_dir = DATA_DIR / f"{podcast_id}_ep{episode}"
        audio    = next(work_dir.glob("audio.*"), None)
        if not audio:
            job["status"] = "error"
            job["phase"]  = "找不到音頻"
            log("✗ 找不到音頻檔，無法轉錄")
            job["finished_at"] = time.time()
            save_job_snapshot(job)
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

        job["phase"]    = "轉錄中"
        job["progress"] = 0
        transcribe_mode = get_transcription_settings().get("mode", "local")

        if duration_s:
            duration_min = duration_s / 60
            job["estimated_minutes"] = round(duration_min, 1)
            job["estimated_cost_usd"] = round(duration_min * 0.006, 4)
            # 估計轉錄時間：API 模式約 60s 固定；local 依模型速度估
            if transcribe_mode == "api":
                job["estimated_transcribe_secs"] = max(60, int(duration_min * 2))
            else:
                speed_factor = {"medium": 8, "small": 12, "base": 20, "large-v2": 4, "large-v3": 4}.get(model, 8)
                job["estimated_transcribe_secs"] = max(10, int(duration_s / speed_factor))
        log(f"→ 開始轉錄（模型：{model}）")

        pod_cfg = get_podcast_config(podcast_id)
        lang    = pod_cfg.get("language", "zh")

        transcribe_cmd = [
            "python3.10",
            str(PODCAST_SCRIPTS_DIR / "transcribe.py"),
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
        wall_start = time.time()
        for t_line in t_proc.stdout:
            t_line = t_line.rstrip()
            if not t_line:
                continue
            if t_line.startswith("TRANSCRIPT_COST:"):
                parts_cost = t_line.split(":")
                if len(parts_cost) == 3:
                    try:
                        job["transcript_minutes"] = float(parts_cost[1])
                        job["transcript_cost_usd"] = float(parts_cost[2])
                    except ValueError:
                        pass
                continue
            log(t_line)
            tm = _TRANSCRIBE_RE.search(t_line)
            if tm:
                elapsed_s = float(tm.group(1))
                if duration_s > 0:
                    job["progress"] = min(99, elapsed_s / duration_s * 100)
                    # 用實際速度動態更新剩餘時間估算
                    wall_elapsed = time.time() - wall_start
                    if elapsed_s > 5 and wall_elapsed > 0:
                        actual_speed = elapsed_s / wall_elapsed  # x realtime
                        remaining_audio = duration_s - elapsed_s
                        eta_secs = int(remaining_audio / actual_speed)
                        job["estimated_transcribe_secs"] = eta_secs
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
            save_job_snapshot(job)
            return

        log("✓ 轉錄完成")
        job["progress"] = 100

        # 把費用寫入持久 DB
        if job.get("transcript_cost_usd", 0) > 0:
            from cache_store import log_transcript_cost
            pod_cfg2 = get_podcast_config(podcast_id)
            source_title = pod_cfg2.get("name", podcast_id) if pod_cfg2 else podcast_id
            log_transcript_cost(
                job_id=job_id,
                job_type="pod_download",
                source_title=f"{source_title} EP{episode}",
                duration_minutes=job.get("transcript_minutes", 0),
                cost_usd=job["transcript_cost_usd"],
            )

        # ── Step 3: 等待 user 確認是否產生筆記 ──────────────
        ev = threading.Event()
        job["status"]             = "waiting"
        job["phase"]              = "awaiting_analyze_confirm"
        job["_analyze_event"]     = ev
        job["_work_dir"]          = str(work_dir)
        job["_episode_label"]     = episode_label
        log("⏸ 等待確認是否產生筆記...")
        save_job_snapshot(job)

        confirmed = ev.wait(timeout=3600)  # 最多等 1 小時
        if not confirmed or not job.get("_analyze_confirmed"):
            job["status"]      = "done"
            job["phase"]       = "轉錄完成（未產生筆記）"
            job["finished_at"] = time.time()
            save_job_snapshot(job)
            return

        # ── Step 4: LLM 分析逐字稿 → 筆記 ──────────────────
        provider = get_note_provider()
        job["status"]   = "running"
        job["phase"]    = "分析中"
        job["progress"] = 0
        job["provider"]  = provider
        log(f"→ 呼叫 {provider.title()} 分析逐字稿...")
        save_job_snapshot(job)

        analyze_script = PODCAST_SCRIPTS_DIR / "analyze.py"
        a_proc = subprocess.Popen(
            ["python3.10", str(analyze_script), str(job["_work_dir"]), "--podcast", podcast_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            env={**_os.environ, "PODCAST_ID": podcast_id, "JOB_ID": job_id},
        )

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
    save_job_snapshot(job)
