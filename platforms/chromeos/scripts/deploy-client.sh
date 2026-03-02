#!/usr/bin/env bash
# Deploy client.py to ChromeOS device
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SSH_HOST="${CHROMEBOOK_HOST:-chromeos-testbed}"
CLIENT_PATH="${CHROMEOS_CLIENT_PATH:-/mnt/stateful_partition/c2/client.py}"
REMOTE_PATH_SETUP="export PATH=/bin:/usr/bin:/usr/local/bin:\$PATH"

echo "Deploying client.py to $SSH_HOST:$CLIENT_PATH..."
ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; mkdir -p $(dirname "$CLIENT_PATH")" 2>/dev/null
scp -q "$REPO_DIR/client.py" "$SSH_HOST:$CLIENT_PATH"

# Verify
echo '{"cmd":"ping"}' | ssh "$SSH_HOST" \
    "$REMOTE_PATH_SETUP; LD_LIBRARY_PATH=/usr/local/lib64 python3 $CLIENT_PATH" 2>/dev/null \
    && echo "[OK] client.py deployed and responding" \
    || echo "[FAIL] client.py deployed but not responding"
