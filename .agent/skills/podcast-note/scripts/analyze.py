#!/usr/bin/env python3.10
"""
analyze.py — 用 claude -p 分析逐字稿 → 產生 analysis.json + Obsidian 筆記 + 更新待閱讀清單

改良版：
- 不截斷逐字稿，改由 Claude 用 Read tool 分段讀取
- 同時塞入 note-investment.md 格式規範
- Claude 用 Bash tool 呼叫 generate_note.py 和 update_reading_list.py
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_DIR    = Path(__file__).parent.parent
SKILL_MD     = SKILL_DIR / "SKILL.md"
CONFIG_PATH  = SKILL_DIR / "config" / "podcasts.json"
PROJECT_ROOT = SKILL_DIR.parent.parent
INSTRUCTIONS = PROJECT_ROOT / "instructions" / "note-investment.md"


def get_podcast_config(podcast_id: str) -> dict:
    try:
        cfg = json.loads(CONFIG_PATH.read_text())
        return next((p for p in cfg["podcasts"] if p["id"] == podcast_id), {})
    except Exception:
        return {}


def build_prompt(work_dir: Path, podcast_id: str, transcript_path: Path) -> str:
    pod = get_podcast_config(podcast_id)
    pod_name  = pod.get("name", podcast_id)
    note_dir  = pod.get("note_dir", str(PROJECT_ROOT / "data"))
    lang      = pod.get("language", "zh")

    skill_md_content = SKILL_MD.read_text(encoding="utf-8")

    note_instruction = ""
    if INSTRUCTIONS.exists():
        note_instruction = INSTRUCTIONS.read_text(encoding="utf-8")

    transcript_lines = transcript_path.read_text(encoding="utf-8").splitlines()
    total_lines = len(transcript_lines)

    return f"""你正在執行 podcast-note skill，模式：--transcript（從 Step 3 開始）。

## 設定
- PODCAST_ID: {podcast_id}
- PODCAST_NAME: {pod_name}
- WORK_DIR: {work_dir}
- TRANSCRIPT_PATH: {transcript_path}
- TRANSCRIPT_LINES: {total_lines} 行
- NOTE_DIR: {note_dir}
- LANGUAGE: {lang}

## 投資筆記格式規範（note-investment.md）

{note_instruction}

---

## Podcast Skill 指示（SKILL.md Step 3–5）

{skill_md_content}

---

## 執行指示

逐字稿共 {total_lines} 行，存放於：{transcript_path}

**請依序執行：**

### Step 3 — 分析逐字稿
用 Read tool 分段讀取逐字稿（建議每次讀 400–500 行），步驟：
1. 先讀前段（offset=0, limit=500）摘出重點
2. 繼續讀中段、後段，補充重點
3. 廣告段落（前 2 分鐘）跳過
4. 合成完整分析，產生 JSON 結構
5. 用 Write tool 將 analysis.json 寫入：{work_dir}/analysis.json

### Step 4 — 產生 Obsidian 筆記
執行：
```
PODCAST_ID={podcast_id} python3.10 {SKILL_DIR}/scripts/generate_note.py {work_dir}
```
筆記存入：{note_dir}/

### Step 5 — 更新待閱讀清單
執行：
```
PODCAST_ID={podcast_id} python3.10 {SKILL_DIR}/scripts/update_reading_list.py {work_dir}
```

完成後回報：筆記路徑、章節數、關鍵洞見數。
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir")
    parser.add_argument("--podcast", default="gooaye")
    args = parser.parse_args()

    work_dir        = Path(args.work_dir)
    transcript_path = work_dir / "transcript.txt"

    if not transcript_path.exists():
        print(f"ERROR: 找不到逐字稿 {transcript_path}", file=sys.stderr)
        sys.exit(1)

    prompt = build_prompt(work_dir, args.podcast, transcript_path)
    print(f"→ 呼叫 claude -p（逐字稿 {len(transcript_path.read_text().splitlines())} 行，Read tool 分段讀取）", flush=True)

    proc = subprocess.Popen(
        [
            "claude", "-p", prompt,
            "--dangerously-skip-permissions",
            "--add-dir", str(PROJECT_ROOT),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env={**os.environ, "PODCAST_ID": args.podcast},
    )

    for line in proc.stdout:
        print(line, end="", flush=True)

    proc.wait()

    if proc.returncode == 0:
        print("\n✓ 分析完成")
        note_path_file = work_dir / "note_path.txt"
        if note_path_file.exists():
            print(f"筆記：{note_path_file.read_text().strip()}")
    else:
        print(f"\n✗ 分析失敗（exit {proc.returncode}）", file=sys.stderr)
        sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
