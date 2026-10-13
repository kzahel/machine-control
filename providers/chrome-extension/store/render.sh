#!/usr/bin/env bash
# Render Chrome Web Store screenshots and the promo tile from the shipped
# side panel with fictional mock data. Usage: render.sh CHROMIUM OUTPUT_DIR
# CHROMIUM may be any headless-capable Chromium, such as Playwright's
# chrome-headless-shell.
set -euo pipefail

browser=${1:?Chromium executable required}
output=$(mkdir -p "${2:?output directory required}" && cd "$2" && pwd)
root=$(cd "$(dirname "$0")/.." && pwd)
port=$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
python3 -m http.server "$port" --bind 127.0.0.1 --directory "$root" >/dev/null 2>&1 &
server=$!
profile=$(mktemp -d)
trap 'kill "$server"; rm -rf "$profile"' EXIT
sleep 0.5

shot() {
  "$browser" --headless --hide-scrollbars --force-device-scale-factor=1 \
    --user-data-dir="$profile" --virtual-time-budget=3000 \
    --window-size="$2" --screenshot="$output/$1" "http://127.0.0.1:$port/$3" >/dev/null 2>&1
  echo "$output/$1"
}

shot screenshot-1-live.png 1280,800 \
  'store/screenshot.html?scene=live&caption=See%20what%20your%20agent%20is%20doing%2C%20live'
shot screenshot-2-setup.png 1280,800 'store/screenshot.html?scene=setup'
shot screenshot-3-devtools.png 1280,800 \
  'store/screenshot.html?scene=devtools&caption=Full%20DevTools%20access%20is%20a%20separate%2C%20visible%20grant'
shot promo-small-440x280.png 440,280 store/promo.html
