#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# load .env if present (project root or server dir)
for envfile in "$SCRIPT_DIR/../.env" "$SCRIPT_DIR/.env"; do
  if [ -f "$envfile" ]; then
    set -a; source "$envfile"; set +a
    echo "Loaded env: $envfile"
    break
  fi
done

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

read_pids() {
  # portable replacement for mapfile — works on bash 3.2 (macOS) and bash 4+ (Linux)
  local _arr_name="$1"
  local line
  local _result=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && _result+=("$line")
  done < <(port_pids | sort -u)
  # use ${_result[@]+"${_result[@]}"} to safely handle empty array under set -u
  eval "${_arr_name}=(\${_result[@]+\"\${_result[@]}\"})"
}

stop_port_listener() {
  local pids=()
  read_pids pids
  if ((${#pids[@]} == 0)); then
    return
  fi

  echo "Port $PORT is already in use by PID(s): ${pids[*]}"
  echo "Stopping existing listener..."
  kill "${pids[@]}" 2>/dev/null || true

  local i remaining=()
  for ((i=0; i<20; i++)); do
    read_pids remaining
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
