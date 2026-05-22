#!/usr/bin/env python3.10
"""
analyze.py — 用 claude -p 分析 condensed.txt → analysis.json + Obsidian 筆記 + 更新待看影片與Podcast清單
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
    print("PROGRESS:5:啟動中", flush=True)

    proc = subprocess.Popen(
        [
            "claude", "-p", prompt,
            "--dangerously-skip-permissions",
            "--add-dir", str(SKILL_DIR.parent.parent),  # project root
            "--output-format", "stream-json",
            "--verbose",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        env=os.environ.copy(),
    )

    seen_assistant = False
    write_count = 0
    bash_count = 0
    for line in proc.stdout:
        line = line.rstrip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            print(line, flush=True)
            continue

        t = ev.get("type", "")
        if t == "system" and ev.get("subtype") == "init":
            print("PROGRESS:5:啟動中", flush=True)
        elif t == "assistant":
            if not seen_assistant:
                seen_assistant = True
                print("PROGRESS:15:分析逐字稿中", flush=True)
            usage = ev.get("message", {}).get("usage", {})
            out_tokens = usage.get("output_tokens", 0)
            if out_tokens:
                p = min(65, 15 + int(out_tokens / 120))
                print(f"PROGRESS:{p}:分析中（{out_tokens} tokens）", flush=True)
            for block in ev.get("message", {}).get("content", []) or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name", "")
                    if name == "Write":
                        write_count += 1
                        print("PROGRESS:70:寫入 analysis.json", flush=True)
                    elif name in ("Bash", "bash"):
                        bash_count += 1
                        print(f"PROGRESS:{75 + min(bash_count * 5, 15)}:執行後處理腳本", flush=True)
        elif t == "result":
            if ev.get("subtype") == "success":
                print("PROGRESS:95:Claude 完成", flush=True)
            else:
                err = ev.get("result", "") or ev.get("subtype", "")
                print(f"✗ claude 失敗：{err}", flush=True)

    proc.wait()

    if proc.returncode == 0:
        print("PROGRESS:98:後處理中", flush=True)
        print("\n✓ 分析完成", flush=True)
        note_path_file = work_dir / "note_path.txt"
        if note_path_file.exists():
            print(f"筆記：{note_path_file.read_text().strip()}")
    else:
        print(f"\n✗ 分析失敗（exit {proc.returncode}）", file=sys.stderr)
        sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
