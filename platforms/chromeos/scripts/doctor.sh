#!/usr/bin/env bash
# Health check for ChromeOS development device
set -uo pipefail

. "$(dirname "$0")/common.sh"

pass=0
fail=0

ok() {
    echo "[OK]   $1"
    ((pass++))
}

fail() {
    echo "[FAIL] $1"
    [ -n "${2:-}" ] && echo "       Fix: $2"
    ((fail++))
}

warn() {
    echo "[WARN] $1"
    [ -n "${2:-}" ] && echo "       $2"
}

echo "Checking ChromeOS device ($SSH_HOST)..."
echo

# 1. SSH connectivity
if ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_HOST" "echo ok" &>/dev/null; then
    ok "SSH connection to $SSH_HOST"
else
    fail "Cannot connect to $SSH_HOST via SSH" "chromeos fix-ssh"
    echo
    echo "Cannot proceed without SSH. Fix SSH first."
    exit 1
fi

# 2. Check rootfs writability
ROOTFS_WRITABLE=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; touch /etc/.chromeos-testbed-probe 2>/dev/null && rm -f /etc/.chromeos-testbed-probe && echo yes || echo no" 2>/dev/null)
if [ "$ROOTFS_WRITABLE" = "yes" ]; then
    ok "Rootfs is writable"
else
    fail "Rootfs is read-only (rootfs verification enabled)" \
         "chromeos fix-devtools"
fi

# 3. Remote debugging configured
DEVTOOLS_CONFIGURED=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; /bin/cat /etc/chrome_dev.conf 2>/dev/null" | grep -c "remote-debugging-port" || true)
if [ "$DEVTOOLS_CONFIGURED" -gt 0 ]; then
    ok "Remote debugging configured in chrome_dev.conf"
else
    fail "Remote debugging not configured" "chromeos fix-devtools"
fi

# 4. DevTools port listening
DEVTOOLS_LISTENING=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; /bin/cat /proc/net/tcp 2>/dev/null" | awk '{print $2}' | grep -ci ":2406" || true)
# 9222 decimal = 0x2406
if [ "$DEVTOOLS_LISTENING" -gt 0 ]; then
    ok "DevTools port 9222 listening"
else
    if [ "$DEVTOOLS_CONFIGURED" -gt 0 ]; then
        fail "DevTools port 9222 not listening (configured but not active)" \
             "ssh $SSH_HOST 'restart ui' (will restart Chrome)"
    else
        fail "DevTools port 9222 not listening" "chromeos fix-devtools"
    fi
fi

# 5. Remote Python
PYTHON_PATH=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; command -v python3" 2>/dev/null || true)
if [ -n "$PYTHON_PATH" ]; then
    ok "Remote Python available at $PYTHON_PATH"
else
    fail "Remote python3 not found on configured PATH" \
         "Check REMOTE_PATH_SETUP; expected /usr/local/bin/python3 or /usr/bin/python3"
fi

# 6. client.py deployed
CLIENT_EXISTS=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; test -f $CLIENT_PATH && echo yes || echo no" 2>/dev/null)
if [ "$CLIENT_EXISTS" = "yes" ]; then
    ok "client.py deployed at $CLIENT_PATH"
else
    warn "client.py not deployed" "Run: chromeos deploy"
fi

# 7. Touchscreen (only if client.py and Python are available)
if [ "$CLIENT_EXISTS" = "yes" ] && [ -n "$PYTHON_PATH" ]; then
    TS_INFO=$(echo '{"cmd":"info"}' | ssh "$SSH_HOST" \
        "$REMOTE_PATH_SETUP; LD_LIBRARY_PATH=/usr/local/lib64 python3 $CLIENT_PATH" 2>/dev/null || true)
    if echo "$TS_INFO" | python3 -c "import sys,json; r=json.load(sys.stdin); assert r.get('touch_max',[0])[0]>0" 2>/dev/null; then
        TOUCH_MAX=$(echo "$TS_INFO" | python3 -c "import sys,json; r=json.load(sys.stdin); print(f'{r[\"touch_max\"][0]}x{r[\"touch_max\"][1]}')" 2>/dev/null)
        LAYOUT=$(echo "$TS_INFO" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('keyboard',{}).get('layout','unknown'))" 2>/dev/null)
        ok "Touchscreen detected (${TOUCH_MAX}), keyboard: ${LAYOUT}"
    else
        warn "Could not detect touchscreen" "Touchscreen may not be available (e.g., Chromebox)"
    fi
fi

# 8. SSH tunnel for devtools (local check)
if curl -s --connect-timeout 2 http://localhost:9222/json/version &>/dev/null; then
    ok "DevTools tunnel active (localhost:9222)"
else
    warn "No local DevTools tunnel (optional)" \
         "The chromeos CLI connects on-device. For other local CDP tools: ssh -NL 9222:127.0.0.1:9222 $SSH_HOST"
fi

# Summary
echo
echo "---"
echo "$pass passed, $fail failed"
[ "$fail" -gt 0 ] && exit 1
exit 0
