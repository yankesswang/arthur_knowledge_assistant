#!/usr/bin/env python3
"""
AlphaNote Native Messaging Host

Chrome calls this process when the extension sends a native message.
Reads one JSON message from stdin, executes the requested job, streams
progress back via stdout, then exits.

Message format (extension → host):
  { "type": "analyze_yt", "url": "...", "vault_root": "...", "settings": {...} }
  { "type": "ping" }

Response format (host → extension), one JSON object per line:
  { "type": "progress", "phase": "下載中", "pct": 20 }
  { "type": "done",     "note_path": "/path/to/note.md" }
  { "type": "error",    "message": "..." }
"""

import json
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

# ── Native Messaging I/O ──────────────────────────────────────────────────────
# Chrome prefixes each message with a 4-byte little-endian length.

def read_message() -> dict:
    raw_len = sys.stdin.buffer.read(4)
    if len(raw_len) < 4:
        sys.exit(0)
    msg_len = struct.unpack('<I', raw_len)[0]
    return json.loads(sys.stdin.buffer.read(msg_len))


def send(obj: dict):
    data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('<I', len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def progress(phase: str, pct: int):
    send({"type": "progress", "phase": phase, "pct": pct})


# ── Helpers ───────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PROJECT_ROOT / 'podcast-note' / 'scripts'


def run(cmd: list[str], env=None, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True,
        env={**os.environ, **(env or {})},
        cwd=cwd,
    )


# ── Job: analyze YouTube video ────────────────────────────────────────────────

def analyze_yt(url: str, vault_root: str, settings: dict):
    with tempfile.TemporaryDirectory(prefix='alphanote_') as tmp:
        work_dir = Path(tmp)

        # 1. Download audio
        progress('下載中', 10)
        audio_path = work_dir / 'audio.m4a'
        dl = run([
            'yt-dlp', '-x', '--audio-format', 'm4a',
            '-o', str(audio_path),
            '--write-info-json',
            '--no-playlist',
            url,
        ])
        if dl.returncode != 0:
            send({"type": "error", "message": f"yt-dlp 失敗：{dl.stderr[-300:]}"})
            return

        # pick actual downloaded file (yt-dlp may add suffix)
        audio_files = list(work_dir.glob('*.m4a')) + list(work_dir.glob('*.webm')) + list(work_dir.glob('*.mp3'))
        if not audio_files:
            send({"type": "error", "message": "找不到下載的音頻檔"})
            return
        audio_path = audio_files[0]

        # 2. Transcribe
        progress('轉錄中', 35)
        mode = settings.get('transcription_mode', 'local')
        model = settings.get('whisper_model', 'medium')
        lang  = settings.get('language', 'zh')

        tr_cmd = [
            'python3.10', str(SCRIPTS / 'transcribe.py'),
            str(work_dir),
            '--lang', lang,
            '--mode', mode,
        ]
        if mode == 'local':
            tr_cmd += ['--model', model]

        tr_env = {}
        if settings.get('openai_api_key'):
            tr_env['OPENAI_API_KEY'] = settings['openai_api_key']

        tr = run(tr_cmd, env=tr_env)
        if tr.returncode != 0:
            send({"type": "error", "message": f"轉錄失敗：{tr.stderr[-300:]}"})
            return

        # 3. Analyze with claude -p
        progress('分析中', 60)
        podcast_id = settings.get('podcast_id', 'gooaye')
        an_env = {
            'VAULT_ROOT': vault_root,
            'PODCAST_ID': podcast_id,
        }
        if settings.get('openai_api_key'):
            an_env['OPENAI_API_KEY'] = settings['openai_api_key']

        an = run(
            ['python3.10', str(SCRIPTS / 'analyze.py'), str(work_dir), '--podcast', podcast_id],
            env=an_env,
        )
        if an.returncode != 0:
            send({"type": "error", "message": f"分析失敗：{an.stderr[-300:]}"})
            return

        # 4. Report note path
        note_path_file = work_dir / 'note_path.txt'
        note_path = note_path_file.read_text().strip() if note_path_file.exists() else ''
        progress('完成', 100)
        send({"type": "done", "note_path": note_path})


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    msg = read_message()

    if msg.get('type') == 'ping':
        send({"type": "pong", "version": "1.0.0"})
        return

    if msg.get('type') == 'analyze_yt':
        analyze_yt(
            url=msg['url'],
            vault_root=msg.get('vault_root', str(Path.home() / 'Documents' / 'arthurwang_DB')),
            settings=msg.get('settings', {}),
        )
        return

    send({"type": "error", "message": f"未知 message type: {msg.get('type')}"})


if __name__ == '__main__':
    main()
