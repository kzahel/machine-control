#!/usr/bin/env bash
# Deploy client.py to ChromeOS device
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SSH_HOST="${CHROMEBOOK_HOST:-chromeos-testbed}"
CLIENT_PATH="${CHROMEOS_CLIENT_PATH:-/mnt/stateful_partition/c2/client.py}"
REMOTE_PATH_SETUP="export PATH=/bin:/usr/bin:/usr/local/bin:\$PATH"

CLIENT_DIR=$(dirname "$CLIENT_PATH")

echo "Deploying client to $SSH_HOST:$CLIENT_DIR..."
ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; mkdir -p $CLIENT_DIR" 2>/dev/null
scp -q "$REPO_DIR/client.py" "$REPO_DIR/drm_screenshot.py" "$SSH_HOST:$CLIENT_DIR/"

# Verify
echo '{"cmd":"ping"}' | ssh "$SSH_HOST" \
    "$REMOTE_PATH_SETUP; LD_LIBRARY_PATH=/usr/local/lib64 python3 $CLIENT_PATH" 2>/dev/null \
    && echo "[OK] client.py deployed and responding" \
    || echo "[FAIL] client.py deployed but not responding"
