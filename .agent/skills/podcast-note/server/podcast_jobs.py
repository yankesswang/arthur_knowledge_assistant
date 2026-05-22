"""Background podcast processing jobs."""

import json
import os
import re
import subprocess
import time
from pathlib import Path

from config_store import get_podcast_config
from settings import SKILL_DIR
from state import _jobs

DOWNLOAD_SH = SKILL_DIR / "scripts" / "download.sh"

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
