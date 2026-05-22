#!/usr/bin/env python3.10
"""
analyze.py — 用 claude -p 分析逐字稿 → analysis.json + Obsidian 筆記

策略：
1. 去掉時間戳，完整逐字稿（不截斷）一次送進 claude -p
2. Claude 在每個 section 記錄 anchor_text（開頭句子）
3. 分析完後用 anchor_text 模糊比對原始逐字稿，補回 start_time
"""

import argparse
import difflib
import json
import os
import re
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


def strip_timestamps(transcript_path: Path) -> str:
    """去掉時間戳，只留純文字（約壓縮 50%）"""
    lines = []
    for line in transcript_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r'\[\d+:\d+\.\d+\]\s*(.*)', line.strip())
        if m and m.group(1):
            lines.append(m.group(1).strip())
    return "\n".join(lines)


def build_timestamp_index(transcript_path: Path) -> list[tuple[float, str]]:
    """建立 [(seconds, text)] 索引，供事後比對用"""
    segments = []
    for line in transcript_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r'\[(\d+):(\d+\.\d+)\]\s*(.*)', line.strip())
        if m and m.group(3).strip():
            t = int(m.group(1)) * 60 + float(m.group(2))
            segments.append((t, m.group(3).strip()))
    return segments


def find_timestamp(anchor: str, segments: list[tuple[float, str]]) -> str:
    """用 anchor_text 模糊比對逐字稿，回傳 MM:SS"""
    if not anchor or not segments:
        return ""
    texts = [s[1] for s in segments]
    matches = difflib.get_close_matches(anchor, texts, n=1, cutoff=0.35)
    if matches:
        idx = texts.index(matches[0])
        t = segments[idx][0]
        return f"{int(t)//60:02d}:{int(t)%60:02d}"
    # fallback：子字串掃描
    anchor_short = anchor[:15]
    for t, text in segments:
        if anchor_short in text:
            return f"{int(t)//60:02d}:{int(t)%60:02d}"
    return ""


def backfill_timestamps(analysis_path: Path, segments: list[tuple[float, str]]):
    """讀 analysis.json，用 anchor_text 補回 start_time"""
    data = json.loads(analysis_path.read_text(encoding="utf-8"))
    changed = False
    for sec in data.get("sections", []):
        if sec.get("start_time"):
            continue  # 已有時間戳，跳過
        anchor = sec.get("anchor_text", "")
        if not anchor:
            # 從 content_points 第一行取文字
            pts = sec.get("content_points", [])
            if pts:
                anchor = re.sub(r'\*\*.*?\*\*[：:]?\s*', '', pts[0])[:30].strip()
        if anchor:
            ts = find_timestamp(anchor, segments)
            if ts:
                sec["start_time"] = ts
                changed = True
    if changed:
        analysis_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"✓ 時間戳已補回（{sum(1 for s in data['sections'] if s.get('start_time'))} / {len(data['sections'])} 段）")


def build_prompt(work_dir: Path, podcast_id: str, clean_transcript: str) -> str:
    pod      = get_podcast_config(podcast_id)
    pod_name = pod.get("name", podcast_id)
    note_dir = pod.get("note_dir", str(PROJECT_ROOT / "data"))
    lang     = pod.get("language", "zh")

    skill_md      = SKILL_MD.read_text(encoding="utf-8")
    note_instr    = INSTRUCTIONS.read_text(encoding="utf-8") if INSTRUCTIONS.exists() else ""

    return f"""你正在執行 podcast-note skill，模式：--transcript（從 Step 3 開始）。

## 設定
- PODCAST_ID: {podcast_id}
- PODCAST_NAME: {pod_name}
- WORK_DIR: {work_dir}
- NOTE_DIR: {note_dir}
- LANGUAGE: {lang}

## 投資筆記格式規範（note-investment.md）

{note_instr}

---

## Podcast Skill 指示（SKILL.md Step 3–5）

{skill_md}

---

## 特別注意：anchor_text 欄位

逐字稿的時間戳已被移除（為了讓你可以讀完整內容）。
請在每個 section 的 JSON 中加入 `anchor_text` 欄位，填入該段落**開頭最具代表性的一句話**（直接從逐字稿摘取，字面要接近原文），例如：

```json
{{
  "title": "市場展望",
  "anchor_text": "下禮拜就正式進入5月的第一個交易日",
  "start_time": "",
  "content_points": [...]
}}
```

程式會用 `anchor_text` 自動比對原始逐字稿把時間戳補回去，你不需要填 `start_time`。

---

## 完整逐字稿（時間戳已移除，內容完整）

{clean_transcript}

---

## 執行步驟

1. 分析以上逐字稿，依 SKILL.md Step 3 格式產生 analysis.json
2. 在每個 section 加入 `anchor_text`（該段開頭句，字面接近原文）
3. 用 Write tool 寫入：{work_dir}/analysis.json
4. 執行：PODCAST_ID={podcast_id} python3.10 {SKILL_DIR}/scripts/generate_note.py {work_dir}
5. 執行：PODCAST_ID={podcast_id} python3.10 {SKILL_DIR}/scripts/update_reading_list.py {work_dir}
6. 回報：筆記路徑、章節數、關鍵洞見數
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

    # 建立時間戳索引（供事後補回）
    segments = build_timestamp_index(transcript_path)

    # 去時間戳，完整送入
    clean = strip_timestamps(transcript_path)
    orig_chars  = transcript_path.stat().st_size
    clean_chars = len(clean.encode("utf-8"))
    print(f"→ 逐字稿：{orig_chars:,} bytes → 去時間戳後 {clean_chars:,} bytes（{clean_chars/orig_chars:.0%}），完整不截斷", flush=True)

    prompt = build_prompt(work_dir, args.podcast, clean)

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

    if proc.returncode != 0:
        print(f"\n✗ 分析失敗（exit {proc.returncode}）", file=sys.stderr)
        sys.exit(proc.returncode)

    # 事後補回時間戳
    analysis_path = work_dir / "analysis.json"
    if analysis_path.exists():
        backfill_timestamps(analysis_path, segments)
        # 重新跑 generate_note 讓時間戳進筆記
        subprocess.run(
            ["python3.10", str(SKILL_DIR / "scripts" / "generate_note.py"), str(work_dir)],
            env={**os.environ, "PODCAST_ID": args.podcast},
        )

    note_path_file = work_dir / "note_path.txt"
    if note_path_file.exists():
        print(f"\n✓ 完成，筆記：{note_path_file.read_text().strip()}")


if __name__ == "__main__":
    main()
