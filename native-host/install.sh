#!/usr/bin/env bash
# Install AlphaNote Native Messaging Host
# Usage: bash install.sh [--extension-id <id>]
# After loading the unpacked extension in Chrome, paste its ID here or pass as arg.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_PATH="$SCRIPT_DIR/host.py"
chmod +x "$HOST_PATH"

# Extension ID — update this after loading the extension in Chrome
EXTENSION_ID="${1:-YOUR_EXTENSION_ID_HERE}"

MANIFEST='{
  "name": "com.alphanote.host",
  "description": "AlphaNote native host — yt-dlp + whisper + claude",
  "path": "'"$HOST_PATH"'",
  "type": "stdio",
  "allowed_origins": ["chrome-extension://'"$EXTENSION_ID"'/"]
}'

# Chrome on Linux
CHROME_DIR="$HOME/.config/google-chrome/NativeMessagingHosts"
# Chromium on Linux
CHROMIUM_DIR="$HOME/.config/chromium/NativeMessagingHosts"

install_to() {
  mkdir -p "$1"
  echo "$MANIFEST" > "$1/com.alphanote.host.json"
  echo "✓ Installed to $1"
}

install_to "$CHROME_DIR"
[ -d "$HOME/.config/chromium" ] && install_to "$CHROMIUM_DIR"

echo ""
echo "✓ Native host installed."
echo "  Host path : $HOST_PATH"
echo "  Extension : $EXTENSION_ID"
echo ""
echo "If you haven't loaded the extension yet:"
echo "  1. Go to chrome://extensions"
echo "  2. Enable Developer mode"
echo "  3. Load unpacked → select chrome-extension/"
echo "  4. Copy the Extension ID"
echo "  5. Re-run: bash install.sh <extension-id>"
