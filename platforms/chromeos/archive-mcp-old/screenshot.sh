#!/usr/bin/env bash
# Take a screenshot of the Chromebook and save it locally.
#
# Usage:
#   ./screenshot.sh              # saves to /tmp/chromebook-screenshot.png, prints path
#   ./screenshot.sh output.png   # saves to output.png, prints path
#
# Prerequisites:
#   - SSH access to "chromeos-testbed" (key-based, no password prompt)
#   - client.py deployed (this script auto-deploys it)

set -euo pipefail

SSH_HOST="${CHROMEBOOK_HOST:-chromeos-testbed}"
CLIENT_PATH="/mnt/stateful_partition/c2/client.py"
REMOTE_PATH="export PATH=/bin:/usr/bin:/usr/local/bin:\$PATH"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="${1:-/tmp/chromebook-screenshot.png}"

# Deploy client.py
ssh "$SSH_HOST" "$REMOTE_PATH; mkdir -p /mnt/stateful_partition/c2" 2>/dev/null
scp -q "$SCRIPT_DIR/client.py" "$SSH_HOST:$CLIENT_PATH"

# Send screenshot command, read JSON response
RESPONSE=$(echo '{"cmd":"screenshot"}' | \
  ssh "$SSH_HOST" "$REMOTE_PATH; LD_LIBRARY_PATH=/usr/local/lib64 python3 $CLIENT_PATH" 2>/dev/null)

# Check for error
if echo "$RESPONSE" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if 'image' in r else 1)" 2>/dev/null; then
  # Extract base64 image and decode to file
  echo "$RESPONSE" | python3 -c "
import sys, json, base64
r = json.load(sys.stdin)
sys.stdout.buffer.write(base64.b64decode(r['image']))
" > "$OUTPUT"
  echo "$OUTPUT"
else
  ERROR=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error','Unknown error'))" 2>/dev/null || echo "No response from client")
  echo "Error: $ERROR" >&2
  exit 1
fi
