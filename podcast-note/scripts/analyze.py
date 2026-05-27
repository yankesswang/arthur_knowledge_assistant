#!/usr/bin/env python3.10
"""
analyze.py — 用 Claude 或 Codex 分析逐字稿 → analysis.json + Obsidian 筆記

策略：
1. 去掉時間戳，完整逐字稿（不截斷）一次送進 LLM
2. LLM 在每個 section 記錄 anchor_text（開頭句子）
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

PODCAST_ROOT   = Path(__file__).resolve().parent.parent
PROJECT_ROOT   = PODCAST_ROOT.parent
SCRIPT_DIR     = PODCAST_ROOT / "scripts"
SKILL_DIR      = PROJECT_ROOT / ".agent" / "skills" / "podcast-note"
SKILL_MD       = SKILL_DIR / "SKILL.md"
CONFIG_PATH    = PODCAST_ROOT / "config" / "podcasts.json"
INSTRUCTIONS   = PROJECT_ROOT / "instructions" / "note-investment.md"
SERVER_DATA    = PROJECT_ROOT / "server" / "data"
CUSTOM_PROMPT  = SERVER_DATA / "custom_prompt.md"
TRANSCRIPTION_SETTINGS_PATH = SERVER_DATA / "transcription_settings.json"

sys.path.insert(0, str(PROJECT_ROOT / "server"))
from claude_lock import claude_cli_lock
from note_generation import get_note_provider, run_codex_exec, validate_analysis_json

LANG_LABELS = {"zh": "繁體中文", "en": "English", "auto": "（依逐字稿語言自動判斷）"}


def get_analysis_language() -> str:
    """從 transcription_settings.json 讀取語言設定，fallback 到 zh。"""
    try:
        if TRANSCRIPTION_SETTINGS_PATH.exists():
            cfg = json.loads(TRANSCRIPTION_SETTINGS_PATH.read_text(encoding="utf-8"))
            return cfg.get("language", "zh")
    except Exception:
        pass
    return "zh"


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


def build_prompt(work_dir: Path, podcast_id: str, clean_transcript: str) -> tuple[str, str]:
    pod      = get_podcast_config(podcast_id)
    pod_name = pod.get("name", podcast_id)
    note_dir = pod.get("note_dir", str(PROJECT_ROOT / "data"))

    # Language: transcription_settings.json > podcasts.json > fallback zh
    lang = get_analysis_language()
    if lang == "auto":
        lang = pod.get("language", "zh")
    lang_label = LANG_LABELS.get(lang, lang)

    skill_md   = SKILL_MD.read_text(encoding="utf-8")
    # Custom prompt takes priority over default note-investment.md
    if CUSTOM_PROMPT.exists():
        _custom = CUSTOM_PROMPT.read_text(encoding="utf-8").strip()
        note_instr = _custom if _custom else (INSTRUCTIONS.read_text(encoding="utf-8") if INSTRUCTIONS.exists() else "")
    elif INSTRUCTIONS.exists():
        note_instr = INSTRUCTIONS.read_text(encoding="utf-8")
    else:
        note_instr = ""

    system_prompt = f"""你正在執行 podcast-note skill，模式：--transcript（從 Step 3 開始）。

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

程式會用 `anchor_text` 自動比對原始逐字稿把時間戳補回去，你不需要填 `start_time`。"""

    user_prompt = f"""## 設定
- PODCAST_ID: {podcast_id}
- PODCAST_NAME: {pod_name}
- WORK_DIR: {work_dir}
- NOTE_DIR: {note_dir}
- LANGUAGE: {lang}
- OUTPUT_LANGUAGE: {lang_label}（筆記輸出語言，標題、摘要、章節內容均使用此語言）

## 完整逐字稿（時間戳已移除，內容完整）

{clean_transcript}

---

## 執行步驟

1. 分析以上逐字稿，依 SKILL.md Step 3 格式產生 analysis.json
2. 在每個 section 加入 `anchor_text`（該段開頭句，字面接近原文）
3. 用 Write tool 寫入：{work_dir}/analysis.json
4. 執行：PODCAST_ID={podcast_id} python3.10 {SCRIPT_DIR}/generate_note.py {work_dir}
5. 執行：PODCAST_ID={podcast_id} python3.10 {SCRIPT_DIR}/update_reading_list.py {work_dir}
6. 回報：筆記路徑、章節數、關鍵洞見數
"""

    return system_prompt, user_prompt


def build_codex_prompt(work_dir: Path, podcast_id: str, clean_transcript: str) -> str:
    pod      = get_podcast_config(podcast_id)
    pod_name = pod.get("name", podcast_id)
    note_dir = pod.get("note_dir", str(PROJECT_ROOT / "data"))

    lang = get_analysis_language()
    if lang == "auto":
        lang = pod.get("language", "zh")
    lang_label = LANG_LABELS.get(lang, lang)

    skill_md = SKILL_MD.read_text(encoding="utf-8")
    if CUSTOM_PROMPT.exists():
        _custom = CUSTOM_PROMPT.read_text(encoding="utf-8").strip()
        note_instr = _custom if _custom else (INSTRUCTIONS.read_text(encoding="utf-8") if INSTRUCTIONS.exists() else "")
    elif INSTRUCTIONS.exists():
        note_instr = INSTRUCTIONS.read_text(encoding="utf-8")
    else:
        note_instr = ""

    info_path = work_dir / "info.json"
    info_json = info_path.read_text(encoding="utf-8") if info_path.exists() else "{}"
    analysis_path = work_dir / "analysis.json"

    return f"""你正在替代原本的 claude -p，執行 podcast-note 的分析步驟。

任務：從完整逐字稿產生分析 JSON，並只寫入這個檔案：
{analysis_path}

嚴格限制：
- 只允許修改 {analysis_path}。
- 不要修改 Obsidian vault。
- 不要執行 generate_note.py 或 update_reading_list.py；後處理由呼叫端執行。
- 完成後只用一句話回報 analysis.json 已寫入。

Podcast 設定：
- PODCAST_ID: {podcast_id}
- PODCAST_NAME: {pod_name}
- WORK_DIR: {work_dir}
- NOTE_DIR: {note_dir}
- OUTPUT_LANGUAGE: {lang_label}

輸出 JSON schema 必須符合 podcast-note/scripts/generate_note.py 期待：
{{
  "title_zh": "繁體中文筆記標題，建議含日期、節目、集數、主題",
  "note_type": "investment",
  "topic": "主題",
  "tags": ["..."],
  "stocks": ["股票代號或台股代碼"],
  "tldr": {{
    "核心主張": "...",
    "關鍵機制_問題": "...",
    "重要數字": "...",
    "風險_限制": "...",
    "操作建議": "..."
  }},
  "sections": [
    {{
      "title": "章節標題",
      "anchor_text": "直接摘自逐字稿、可用於時間戳回填的開頭句",
      "start_time": "",
      "content_points": [
        "- **概念**：重點",
        "    - **子觀點**：推理、數字、限制"
      ]
    }}
  ],
  "key_insights": ["..."],
  "data_table": [{{"指標":"...", "數值":"...", "備註":"..."}}],
  "investment_framework": {{}},
  "risks": []
}}

品質要求：
- 使用 {lang_label}。
- JSON 必須可被 Python json.loads 解析，不要加 markdown code fence。
- sections 以 5-8 個邏輯段落為主。
- 每節 4-8 個 bullet，保留投資推理鏈，不只摘要。
- anchor_text 必須直接摘自逐字稿，便於後處理比對時間戳。
- 保留具體數字、公司、股票、時間點與限制條件。
- 不要自行換算、補數字或把含糊表述改成更精確的數字；逐字稿含糊時照原文保留。

投資筆記格式規範：
{note_instr}

Podcast Skill 指示：
{skill_md}

Podcast metadata:
{info_json}

完整逐字稿（時間戳已移除，內容完整）：
{clean_transcript}
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

    provider = get_note_provider()
    print(f"→ 筆記生成 provider：{provider}", flush=True)

    if provider == "codex":
        prompt = build_codex_prompt(work_dir, args.podcast, clean)
        returncode = run_codex_exec(
            prompt,
            project_root=PROJECT_ROOT,
            progress_label="Codex",
            usage_job_id=os.environ.get("JOB_ID", f"manual:{work_dir.name}"),
            usage_job_type="podcast_note",
            usage_source_title=f"{args.podcast}/{work_dir.name}",
        )
        if returncode != 0:
            print(f"\n✗ Codex 分析失敗（exit {returncode}）", file=sys.stderr)
            sys.exit(returncode)
        try:
            validate_analysis_json(work_dir / "analysis.json")
        except Exception as exc:
            print(f"\n✗ Codex 產生的 analysis.json 無效：{exc}", file=sys.stderr)
            sys.exit(1)
    else:
        system_prompt, user_prompt = build_prompt(work_dir, args.podcast, clean)

        with claude_cli_lock(
            f"podcast:{args.podcast}:{work_dir.name}",
            on_wait=lambda: print("PROGRESS:5:等待 Claude CLI 空檔", flush=True),
            on_acquired=lambda: print("PROGRESS:5:啟動中", flush=True),
        ):
            proc = subprocess.Popen(
                [
                    "claude", "-p", user_prompt,
                    "--system-prompt", system_prompt,
                    "--model", "claude-haiku-4-5-20251001",
                    "--dangerously-skip-permissions",
                    "--add-dir", str(PROJECT_ROOT),
                    "--output-format", "stream-json",
                    "--verbose",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env={**os.environ, "PODCAST_ID": args.podcast},
            )

            seen_assistant = False
            seen_tokens = False
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
                    if not seen_tokens and usage.get("output_tokens", 0) > 0:
                        seen_tokens = True
                        print("PROGRESS:30:分析中", flush=True)
                    for block in ev.get("message", {}).get("content", []) or []:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            name = block.get("name", "")
                            if name == "Write":
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

        if proc.returncode != 0:
            print(f"\n✗ 分析失敗（exit {proc.returncode}）", file=sys.stderr)
            sys.exit(proc.returncode)

    # 事後補回時間戳
    analysis_path = work_dir / "analysis.json"
    if analysis_path.exists():
        backfill_timestamps(analysis_path, segments)
        # 重新跑 generate_note 讓時間戳進筆記
        subprocess.run(
            ["python3.10", str(SCRIPT_DIR / "generate_note.py"), str(work_dir)],
            env={**os.environ, "PODCAST_ID": args.podcast},
        )
        if provider == "codex":
            subprocess.run(
                ["python3.10", str(SCRIPT_DIR / "update_reading_list.py"), str(work_dir)],
                env={**os.environ, "PODCAST_ID": args.podcast},
            )

    note_path_file = work_dir / "note_path.txt"
    if note_path_file.exists():
        print(f"\n✓ 完成，筆記：{note_path_file.read_text().strip()}")


if __name__ == "__main__":
    main()
