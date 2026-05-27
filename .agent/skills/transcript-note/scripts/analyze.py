#!/usr/bin/env python3.10
"""
analyze.py — 用 Claude 或 Codex 分析 condensed.txt → analysis.json + Obsidian 筆記 + 更新待看影片與Podcast清單
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
PROJECT_ROOT = SKILL_DIR.parent.parent.parent.resolve()

sys.path.insert(0, str(PROJECT_ROOT / "server"))
from claude_lock import claude_cli_lock
from note_generation import get_note_provider, run_codex_exec, validate_analysis_json


def build_prompt(video_id: str, work_dir: Path) -> tuple[str, str]:
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

    system_prompt = f"""你正在執行 transcript-note skill，直接從 Action 2 開始（逐字稿已備妥）。

請依照以下 SKILL.md 的指示：
1. 執行 Action 2：分析 condensed.txt，將結果以 Write 工具寫入 {{work_dir}}/analysis.json
2. 執行 Action 3：bash {SKILL_DIR}/scripts/finalize.sh {{video_id}}

SKILL.md 內容：
{skill_md}"""

    user_prompt = f"""設定：
- VIDEO_ID: {video_id}
- WORK_DIR: {work_dir}
- CONDENSED_PATH: {condensed_path}
- TRANSCRIPT_SOURCE: {transcript_source}
- 影片標題: {info.get("title", "")}
- 頻道: {info.get("channel", "")}
- 時長: {info.get("duration", "")}

請執行：
1. Action 2：分析 condensed.txt，以 Write 工具寫入 {work_dir}/analysis.json
2. Action 3：bash {SKILL_DIR}/scripts/finalize.sh {video_id}

---
逐字稿（condensed.txt）：
{condensed}
"""

    return system_prompt, user_prompt


def build_codex_prompt(video_id: str, work_dir: Path) -> str:
    condensed_path = work_dir / "condensed.txt"
    info_path      = work_dir / "info.json"

    if not condensed_path.exists():
        print(f"ERROR: 找不到 {condensed_path}", file=sys.stderr)
        sys.exit(1)

    skill_md  = SKILL_MD.read_text(encoding="utf-8")
    condensed = condensed_path.read_text(encoding="utf-8")
    info      = info_path.read_text(encoding="utf-8") if info_path.exists() else "{}"

    src_file = work_dir / "transcript_source.txt"
    transcript_source = src_file.read_text().strip() if src_file.exists() else "unknown"
    analysis_path = work_dir / "analysis.json"

    return f"""你正在替代原本的 claude -p，執行 transcript-note 的分析步驟。

任務：從壓縮逐字稿產生分析 JSON，並只寫入這個檔案：
{analysis_path}

嚴格限制：
- 只允許修改 {analysis_path}。
- 不要修改 Obsidian vault。
- 不要執行 finalize.sh、generate_note.py、update_reading_list.py 或 update_index.py；後處理由呼叫端執行。
- 完成後只用一句話回報 analysis.json 已寫入。

設定：
- VIDEO_ID: {video_id}
- WORK_DIR: {work_dir}
- CONDENSED_PATH: {condensed_path}
- TRANSCRIPT_SOURCE: {transcript_source}

輸出 JSON schema 必須符合 transcript-note/scripts/generate_note.py 期待：
{{
  "title_zh": "影片中文標題（保留英文專有名詞）",
  "note_type": "A",
  "topic": "技術主題",
  "tags": ["核心技術1", "核心技術2"],
  "tldr": {{
    "核心主張": "這份筆記在講什麼（一句話）",
    "關鍵機制_問題": "核心問題是什麼，為什麼重要",
    "重要結論": "最重要的洞見或結論（帶具體數字）",
    "適用條件_限制": "什麼情況下這些結論成立"
  }},
  "sections": [
    {{
      "title": "章節標題（繁體中文，5-24字）",
      "start_time": "MM:SS 或 HH:MM:SS",
      "content_points": [
        "- **概念名稱**：一句話定義",
        "    - **子觀點**：說明內容（保留推理過程）"
      ]
    }}
  ],
  "key_insights": ["洞見1（不超過60字）", "洞見2"],
  "data_table": [{{"指標": "...", "數值": "...", "備註": "..."}}],
  "reading_list_category": "AI Agent 工程 | LLM 技術 / 論文 | Claude Code / 開發工具 | 產業與策略 | 創業 | 投資 | 量化交易 | 知識創作"
}}

品質要求：
- 使用繁體中文。
- JSON 必須可被 Python json.loads 解析，不要加 markdown code fence。
- sections 優先依照 info.json 的 YouTube chapters 分段；若無 chapters，推斷 5-8 個邏輯段落。
- 每節 5-10 bullet，保留推理鏈，不只摘要結論。
- 保留逐字稿中的具體數字、比例、時間、公司、產品名、工具名與英文專有名詞。
- 不要自行換算、補數字或把含糊表述改成更精確的數字；逐字稿含糊時，照原文語氣保留。

transcript-note skill 原始規範：
{skill_md}

影片 metadata：
{info}

逐字稿（condensed.txt）：
{condensed}
"""


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze.py <video_id>", file=sys.stderr)
        sys.exit(1)

    video_id = sys.argv[1]
    work_dir = SKILL_DIR / "data" / "transcripts" / video_id

    if not work_dir.exists():
        print(f"ERROR: 找不到 work_dir {work_dir}", file=sys.stderr)
        sys.exit(1)

    provider = get_note_provider()
    print(f"→ 筆記生成 provider：{provider}", flush=True)

    if provider == "codex":
        analysis_path = work_dir / "analysis.json"
        if not analysis_path.exists():
            analysis_path.write_text("{}", encoding="utf-8")
        print(f"→ 呼叫 Codex 分析逐字稿（{video_id}）...", flush=True)
        prompt = build_codex_prompt(video_id, work_dir)
        source_title = video_id
        info_path = work_dir / "info.json"
        if info_path.exists():
            try:
                source_title = json.loads(info_path.read_text(encoding="utf-8")).get("title") or video_id
            except Exception:
                pass
        returncode = run_codex_exec(
            prompt,
            project_root=PROJECT_ROOT,
            progress_label="Codex",
            usage_job_id=os.environ.get("JOB_ID", f"manual:yt:{video_id}"),
            usage_job_type="youtube_note",
            usage_source_title=source_title,
        )
        if returncode != 0:
            print(f"\n✗ Codex 分析失敗（exit {returncode}）", file=sys.stderr)
            sys.exit(returncode)
        try:
            validate_analysis_json(work_dir / "analysis.json")
        except Exception as exc:
            print(f"\n✗ Codex 產生的 analysis.json 無效：{exc}", file=sys.stderr)
            sys.exit(1)
        print("PROGRESS:98:後處理中", flush=True)
        final_proc = subprocess.run(
            ["bash", str(SKILL_DIR / "scripts" / "finalize.sh"), video_id],
            env=os.environ.copy(),
        )
        if final_proc.returncode != 0:
            print(f"\n✗ 後處理失敗（exit {final_proc.returncode}）", file=sys.stderr)
            sys.exit(final_proc.returncode)
    else:
        system_prompt, user_prompt = build_prompt(video_id, work_dir)

        print(f"→ 呼叫 claude -p 分析逐字稿（{video_id}）...", flush=True)
        print("PROGRESS:5:啟動中", flush=True)

        with claude_cli_lock(
            f"transcript:{video_id}",
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
                env=os.environ.copy(),
            )

            seen_assistant = False
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

    print("\n✓ 分析完成", flush=True)
    note_path_file = work_dir / "note_path.txt"
    if note_path_file.exists():
        print(f"筆記：{note_path_file.read_text().strip()}")


if __name__ == "__main__":
    main()
