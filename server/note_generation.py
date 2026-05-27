"""Shared note-generation provider settings and Codex CLI helpers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import contextlib
import fcntl
import time
from collections.abc import Iterator
from pathlib import Path

from settings import GENERATION_SETTINGS_PATH, SERVER_DATA_DIR

VALID_NOTE_PROVIDERS = {"claude", "codex"}
DEFAULT_NOTE_PROVIDER = "claude"
DEFAULT_CODEX_MAX_CONCURRENT = 1


def normalize_note_provider(value: str | None) -> str:
    provider = (value or "").strip().lower()
    if provider in VALID_NOTE_PROVIDERS:
        return provider
    return DEFAULT_NOTE_PROVIDER


def get_note_provider() -> str:
    """Return selected note-generation provider.

    NOTE_GENERATION_PROVIDER can override the persisted setting for one process.
    """
    env_provider = os.environ.get("NOTE_GENERATION_PROVIDER")
    if env_provider:
        return normalize_note_provider(env_provider)

    try:
        if GENERATION_SETTINGS_PATH.exists():
            data = json.loads(GENERATION_SETTINGS_PATH.read_text(encoding="utf-8"))
            return normalize_note_provider(data.get("provider"))
    except Exception:
        pass
    return DEFAULT_NOTE_PROVIDER


def codex_exec_command(project_root: Path) -> list[str]:
    return [
        "codex",
        "--sandbox",
        "workspace-write",
        "-a",
        "never",
        "--cd",
        str(project_root),
        "exec",
        "--json",
        "-",
    ]


def _codex_max_concurrent() -> int:
    try:
        value = int(os.environ.get("CODEX_MAX_CONCURRENT", DEFAULT_CODEX_MAX_CONCURRENT))
    except ValueError:
        return DEFAULT_CODEX_MAX_CONCURRENT
    return max(1, value)


def _codex_slot_path(slot: int) -> Path:
    return SERVER_DATA_DIR / f"codex_cli.{slot}.lock"


@contextlib.contextmanager
def codex_cli_lock(label: str) -> Iterator[None]:
    SERVER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    slot_files = [
        _codex_slot_path(i).open("a+", encoding="utf-8")
        for i in range(_codex_max_concurrent())
    ]
    acquired_fd = None
    try:
        for fh in slot_files:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired_fd = fh
                break
            except BlockingIOError:
                continue

        if acquired_fd is None:
            print("PROGRESS:5:等待 Codex CLI 空檔", flush=True)
            fcntl.flock(slot_files[0].fileno(), fcntl.LOCK_EX)
            acquired_fd = slot_files[0]

        acquired_fd.seek(0)
        acquired_fd.truncate()
        acquired_fd.write(
            f"pid={os.getpid()} label={label} acquired_at={time.time():.3f}\n"
        )
        acquired_fd.flush()
        yield
    finally:
        if acquired_fd is not None:
            fcntl.flock(acquired_fd.fileno(), fcntl.LOCK_UN)
        for fh in slot_files:
            fh.close()


def run_codex_exec(
    prompt: str,
    *,
    project_root: Path,
    progress_label: str = "Codex",
    usage_job_id: str = "",
    usage_job_type: str = "",
    usage_source_title: str = "",
) -> int:
    """Run Codex CLI with a prompt on stdin and relay compact progress lines."""
    with codex_cli_lock(progress_label):
        print(f"PROGRESS:5:啟動 {progress_label}", flush=True)
        try:
            proc = subprocess.Popen(
                codex_exec_command(project_root),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=os.environ.copy(),
            )
        except FileNotFoundError:
            print("ERROR: 找不到 codex CLI，請先確認 codex 指令可用。", file=sys.stderr)
            return 127

        assert proc.stdin is not None
        assert proc.stdout is not None

        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
        except BrokenPipeError:
            pass

        seen_agent = False
        saw_file_change = False
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                if "WARN" not in line:
                    print(line, flush=True)
                continue

            event_type = ev.get("type", "")
            item = ev.get("item") or {}
            item_type = item.get("type", "")

            if event_type == "item.completed" and item_type == "agent_message":
                if not seen_agent:
                    seen_agent = True
                    print("PROGRESS:15:Codex 分析逐字稿中", flush=True)
            elif item_type == "file_change":
                if not saw_file_change:
                    saw_file_change = True
                    print("PROGRESS:70:Codex 寫入 analysis.json", flush=True)
            elif event_type == "turn.completed":
                usage = ev.get("usage") or {}
                input_tokens = usage.get("input_tokens")
                output_tokens = usage.get("output_tokens")
                total_tokens = usage.get("total_tokens")
                if usage:
                    try:
                        input_count = int(input_tokens or 0)
                    except (TypeError, ValueError):
                        input_count = 0
                    try:
                        output_count = int(output_tokens or 0)
                    except (TypeError, ValueError):
                        output_count = 0
                    try:
                        total_count = int(total_tokens or input_count + output_count)
                    except (TypeError, ValueError):
                        total_count = input_count + output_count
                    print(
                        "Codex usage: "
                        f"input={input_count}, "
                        f"output={output_count}, "
                        f"total={total_count}",
                        flush=True,
                    )
                    try:
                        from cache_store import log_llm_usage

                        log_llm_usage(
                            provider="codex",
                            job_id=usage_job_id,
                            job_type=usage_job_type,
                            source_title=usage_source_title,
                            model=ev.get("model", "") or usage.get("model", "") or "",
                            usage=usage,
                        )
                    except Exception as exc:
                        print(f"WARN: Codex usage 寫入失敗：{exc}", flush=True)
                print("PROGRESS:95:Codex 完成", flush=True)

        proc.wait()
        return proc.returncode


def validate_analysis_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"找不到 analysis.json：{path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("analysis.json 必須是 JSON object")
    if not isinstance(data.get("sections", []), list):
        raise ValueError("analysis.json sections 必須是 list")
    return data
