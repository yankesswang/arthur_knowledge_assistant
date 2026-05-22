#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-7654}"

port_pids() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true
    return
  fi

  if command -v fuser >/dev/null 2>&1; then
    fuser -n tcp "$PORT" 2>/dev/null || true
    return
  fi

  if command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null \
      | awk -v port=":$PORT" '$4 ~ port "$" { gsub(/.*pid=/, "", $0); gsub(/,.*/, "", $0); if ($0 ~ /^[0-9]+$/) print $0 }' \
      || true
  fi
}

stop_port_listener() {
  mapfile -t pids < <(port_pids | sort -u)
  if ((${#pids[@]} == 0)); then
    return
  fi

  echo "Port $PORT is already in use by PID(s): ${pids[*]}"
  echo "Stopping existing listener..."
  kill "${pids[@]}" 2>/dev/null || true

  for _ in {1..20}; do
    mapfile -t remaining < <(port_pids | sort -u)
    if ((${#remaining[@]} == 0)); then
      echo "Port $PORT released."
      return
    fi
    sleep 0.1
  done

  echo "Listener did not stop cleanly; forcing kill."
  kill -9 "${pids[@]}" 2>/dev/null || true
}

stop_port_listener

echo "Podcast Note Viewer"
echo "  API + Frontend: http://localhost:$PORT"
echo ""

python3.10 main.py
