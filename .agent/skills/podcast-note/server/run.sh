#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-7654}"

echo "Podcast Note Viewer"
echo "  API + Frontend: http://localhost:$PORT"
echo ""

python3.10 main.py
