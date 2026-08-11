#!/usr/bin/env bash
# Health check for ChromeOS development device
set -uo pipefail

. "$(dirname "$0")/common.sh"

OUTPUT_FORMAT="${CHROMEOS_OUTPUT:-text}"
pass=0
fail=0
results=()

text_mode() {
    [[ "$OUTPUT_FORMAT" != "json" ]]
}

record() {
    results+=("$1" "$2" "${3:-}" "${4:-}")
}

ok() {
    record ok "$1" "${2:-}"
    text_mode && echo "[OK]   $1"
    ((pass++))
}

fail() {
    record fail "$1" "" "${2:-}"
    if text_mode; then
        echo "[FAIL] $1"
        [ -n "${2:-}" ] && echo "       Fix: $2"
    fi
    ((fail++))
}

warn() {
    record warn "$1" "${2:-}"
    if text_mode; then
        echo "[WARN] $1"
        [ -n "${2:-}" ] && echo "       $2"
    fi
}

emit_summary() {
    if text_mode; then
        echo
        echo "---"
        echo "$pass passed, $fail failed"
        return
    fi
    python3 - "$SSH_HOST" "$pass" "$fail" "${results[@]}" <<'PY'
import json
import sys

host, passed, failed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
fields = sys.argv[4:]
checks = []
for i in range(0, len(fields), 4):
    status, name, detail, fix = fields[i:i + 4]
    item = {"status": status, "name": name}
    if detail:
        item["detail"] = detail
    if fix:
        item["fix"] = fix
    checks.append(item)
print(json.dumps({
    "ok": failed == 0,
    "host": host,
    "passed": passed,
    "failed": failed,
    "checks": checks,
}))
PY
}

if text_mode; then
    echo "Checking ChromeOS device ($SSH_HOST)..."
    echo
fi

# 1. SSH connectivity
if ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_HOST" "echo ok" &>/dev/null; then
    ok "SSH connection to $SSH_HOST"
else
    fail "Cannot connect to $SSH_HOST via SSH" "chromeos fix-ssh"
    text_mode && echo
    text_mode && echo "Cannot proceed without SSH. Fix SSH first."
    emit_summary
    exit 1
fi

# Warn before a pending A/B update consumes the next boot and replaces the
# rootfs-resident SSH and DevTools configuration.
UPDATE_OPERATION=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; \
update_engine_client --status 2>/dev/null | awk -F= '\$1 == \"CURRENT_OP\" { print \$2; exit }'" \
    2>/dev/null || true)
if [ "$UPDATE_OPERATION" = "UPDATE_STATUS_UPDATED_NEED_REBOOT" ]; then
    warn "ChromeOS update is waiting for reboot" \
         "After the reboot, recover SSH from VT2 and run: chromeos post-update --repair"
fi

SSH_FALLBACK=$(ssh "$SSH_HOST" \
    "test -r /mnt/stateful_partition/etc/ssh/start_sshd.sh && echo yes || echo no" \
    2>/dev/null || true)
if [ "$SSH_FALLBACK" = "yes" ]; then
    ok "Stateful VT2 SSH fallback is available"
else
    fail "Stateful VT2 SSH fallback is missing" \
         "Re-run the current bootstrap from VT2 before rebooting"
fi

# 2. Check reboot-persistent SSH management
SSH_AUTOSTART=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; \
if [ -f /etc/init/openssh-server.conf ] && \
   grep -qx 'author \"chromeos-testbed\"' /etc/init/openssh-server.conf && \
   grep -qx 'start on shill-connected' /etc/init/openssh-server.conf; then \
  if status openssh-server 2>/dev/null | grep -q 'start/running'; then echo running; \
  else echo stopped; fi; \
elif [ -f /etc/init/chromeos-testbed-sshd.conf ] && \
     grep -qx 'author \"chromeos-testbed\"' /etc/init/chromeos-testbed-sshd.conf; then \
  if status chromeos-testbed-sshd 2>/dev/null | grep -q 'start/running'; then echo incompatible-running; \
  else echo incompatible-stopped; fi; \
else echo missing; fi" 2>/dev/null || true)
case "$SSH_AUTOSTART" in
    running)
        ok "SSH starts through openssh-server after network connection"
        ;;
    stopped)
        warn "SSH autostart is installed but not running" \
             "Run: chromeos fix-ssh"
        ;;
    incompatible-running)
        warn "SSH uses the incompatible chromeos-testbed-sshd startup job" \
             "Re-run the current bootstrap to restore reliable post-reboot startup"
        ;;
    incompatible-stopped)
        warn "Incompatible SSH autostart is installed but not running" \
             "Re-run the current bootstrap to replace and restart it"
        ;;
    *)
        warn "SSH autostart is not installed" \
             "Re-run the current bootstrap from VT2; manual start_sshd.sh remains available"
        ;;
esac

# 3. ChromeOS user session
SESSION_MOUNTED=$(ssh "$SSH_HOST" \
    "$REMOTE_PATH_SETUP; cryptohome --action=is_mounted" 2>/dev/null | tail -n 1 | tr -d '\r')
if [ "$SESSION_MOUNTED" = "true" ]; then
    ok "ChromeOS user session active"
else
    warn "ChromeOS is waiting at sign-in; browser and Crostini automation are unavailable" \
         "Run: chromeos login (or pipe an approved secret source to chromeos login --pin-stdin)"
fi

# 4. Check rootfs writability
ROOTFS_WRITABLE=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; touch /etc/.chromeos-testbed-probe 2>/dev/null && rm -f /etc/.chromeos-testbed-probe && echo yes || echo no" 2>/dev/null)
if [ "$ROOTFS_WRITABLE" = "yes" ]; then
    ok "Rootfs is writable"
else
    fail "Rootfs is read-only (rootfs verification enabled)" \
         "chromeos fix-devtools"
fi

# 5. Remote debugging configured
DEVTOOLS_CONFIGURED=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; /bin/cat /etc/chrome_dev.conf 2>/dev/null" | grep -c "remote-debugging-port" || true)
if [ "$DEVTOOLS_CONFIGURED" -gt 0 ]; then
    ok "Remote debugging configured in chrome_dev.conf"
else
    fail "Remote debugging not configured" "chromeos fix-devtools"
fi

# 6. DevTools port listening
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

# 7. Remote Python
PYTHON_PATH=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; command -v python3" 2>/dev/null || true)
if [ -n "$PYTHON_PATH" ]; then
    ok "Remote Python available at $PYTHON_PATH"
else
    fail "Remote python3 not found on configured PATH" \
         "Check REMOTE_PATH_SETUP; expected /usr/local/bin/python3 or /usr/bin/python3"
fi

# 8. client.py deployed
CLIENT_EXISTS=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; test -f $CLIENT_PATH && echo yes || echo no" 2>/dev/null)
if [ "$CLIENT_EXISTS" = "yes" ]; then
    ok "client.py deployed at $CLIENT_PATH"
else
    warn "client.py not deployed" "Run: chromeos deploy"
fi

# 9. Touchscreen (only if client.py and Python are available)
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

# 10. SSH tunnel for devtools (local check)
if curl -s --connect-timeout 2 http://localhost:9222/json/version &>/dev/null; then
    ok "DevTools tunnel active (localhost:9222)"
else
    warn "No local DevTools tunnel (optional)" \
         "The chromeos CLI connects on-device. For other local CDP tools: ssh -NL 9222:127.0.0.1:9222 $SSH_HOST"
fi

# 11. ARCVM ADB readiness (optional)
if ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; command -v adb >/dev/null" &>/dev/null; then
    ADB_DEVICES=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; adb devices -l" 2>/dev/null || true)
    ADB_STATE=$(echo "$ADB_DEVICES" | awk '$1 == "127.0.0.1:5555" { print $2; exit }')
    case "$ADB_STATE" in
        device)
            ok "ARCVM ADB connected at 127.0.0.1:5555"
            ;;
        unauthorized)
            warn "ARCVM ADB is waiting for authorization" \
                 "Run: chromeos adb-authorize"
            ;;
        offline)
            warn "ARCVM ADB is offline" "Run: chromeos adb-connect"
            ;;
        *)
            warn "ARCVM ADB is not connected (optional)" \
                 "Run: chromeos adb-connect"
            ;;
    esac
else
    warn "ADB command is not available (optional)"
fi

emit_summary
[ "$fail" -gt 0 ] && exit 1
exit 0
