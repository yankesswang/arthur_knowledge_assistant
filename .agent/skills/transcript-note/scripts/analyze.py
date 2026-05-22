#!/usr/bin/env python3.10
"""
analyze.py — 用 claude -p 分析 condensed.txt → analysis.json + Obsidian 筆記 + 更新待閱讀清單
用法：python3.10 analyze.py <video_id>
      work_dir 自動推導為 <SKILL_DIR>/data/transcripts/<video_id>
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
SKILL_MD  = SKILL_DIR / "SKILL.md"


def build_prompt(video_id: str, work_dir: Path) -> str:
    condensed_path = work_dir / "condensed.txt"
    info_path      = work_dir / "info.json"

    if not condensed_path.exists():
        print(f"ERROR: 找不到 {condensed_path}", file=sys.stderr)
        sys.exit(1)

    skill_md  = SKILL_MD.read_text(encoding="utf-8")
    condensed = condensed_path.read_text(encoding="utf-8")
    info      = json.loads(info_path.read_text()) if info_path.exists() else {}

    if len(condensed) > 80000:
        condensed = condensed[:80000] + "\n\n[... 逐字稿截斷，以上為前段內容 ...]"

    src_file = work_dir / "transcript_source.txt"
    transcript_source = src_file.read_text().strip() if src_file.exists() else "unknown"

    prompt = f"""你正在執行 transcript-note skill，直接從 Action 2 開始（逐字稿已備妥）。

設定：
- VIDEO_ID: {video_id}
- WORK_DIR: {work_dir}
- CONDENSED_PATH: {condensed_path}
- TRANSCRIPT_SOURCE: {transcript_source}
- 影片標題: {info.get("title", "")}
- 頻道: {info.get("channel", "")}
- 時長: {info.get("duration", "")}

請依照以下 SKILL.md 的指示：
1. 執行 Action 2：分析 condensed.txt，將結果以 Write 工具寫入 {work_dir}/analysis.json
2. 執行 Action 3：bash {SKILL_DIR}/scripts/finalize.sh {video_id}

SKILL.md 內容：
{skill_md}

---
逐字稿（condensed.txt）：
{condensed}
"""
    return prompt


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze.py <video_id>", file=sys.stderr)
        sys.exit(1)

    video_id = sys.argv[1]
    work_dir = SKILL_DIR / "data" / "transcripts" / video_id

    if not work_dir.exists():
        print(f"ERROR: 找不到 work_dir {work_dir}", file=sys.stderr)
        sys.exit(1)

    prompt = build_prompt(video_id, work_dir)

    print(f"→ 呼叫 claude -p 分析逐字稿（{video_id}）...", flush=True)

    proc = subprocess.Popen(
        [
            "claude", "-p", prompt,
            "--dangerously-skip-permissions",
            "--add-dir", str(SKILL_DIR.parent.parent),  # project root
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=os.environ.copy(),
    )

    for line in proc.stdout:
        print(line, end="", flush=True)

    proc.wait()

    if proc.returncode == 0:
        print("\n✓ 分析完成", flush=True)
        note_path_file = work_dir / "note_path.txt"
        if note_path_file.exists():
            print(f"筆記：{note_path_file.read_text().strip()}")
    else:
        print(f"\n✗ 分析失敗（exit {proc.returncode}）", file=sys.stderr)
        sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
