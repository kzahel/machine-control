#!/usr/bin/env bash
# Fix Chrome DevTools remote debugging on ChromeOS
#
# After a ChromeOS update, rootfs verification gets re-enabled and
# /etc/chrome_dev.conf gets reset. This script re-adds the debugging flag.
set -euo pipefail

. "$(dirname "$0")/common.sh"

echo "Checking remote debugging on $SSH_HOST..."

# Check SSH
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_HOST" "echo ok" &>/dev/null; then
    echo "[FAIL] Cannot connect to $SSH_HOST. Fix SSH first: chromeos fix-ssh"
    exit 1
fi

# Check if already configured
CONFIGURED=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; /bin/cat /etc/chrome_dev.conf 2>/dev/null" | grep -c "remote-debugging-port" || true)
if [ "$CONFIGURED" -gt 0 ]; then
    echo "[OK] --remote-debugging-port=9222 already in chrome_dev.conf"

    # Check if port is actually listening
    LISTENING=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; /bin/cat /proc/net/tcp 2>/dev/null" | awk '{print $2}' | grep -ci ":2406" || true)
    if [ "$LISTENING" -gt 0 ]; then
        echo "[OK] Port 9222 is listening"
        exit 0
    else
        echo "Port 9222 not listening. Restarting Chrome UI..."
        ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; restart ui" 2>/dev/null
        echo "Waiting for Chrome to restart..."
        sleep 5
        LISTENING=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; /bin/cat /proc/net/tcp 2>/dev/null" | awk '{print $2}' | grep -ci ":2406" || true)
        if [ "$LISTENING" -gt 0 ]; then
            echo "[OK] Port 9222 is now listening"
            exit 0
        else
            echo "[WARN] Port 9222 still not listening after restart. May need more time."
            exit 1
        fi
    fi
fi

# Try to write the flag
echo "Adding --remote-debugging-port=9222 to chrome_dev.conf..."
WRITE_RESULT=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; echo '--remote-debugging-port=9222' >> /etc/chrome_dev.conf 2>&1 && echo SUCCESS || echo FAIL" 2>/dev/null)

if echo "$WRITE_RESULT" | grep -q "SUCCESS"; then
    echo "[OK] Flag added to chrome_dev.conf"
    echo "Restarting Chrome UI..."
    ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; restart ui" 2>/dev/null
    echo "Waiting for Chrome to restart..."
    sleep 5

    LISTENING=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; /bin/cat /proc/net/tcp 2>/dev/null" | awk '{print $2}' | grep -ci ":2406" || true)
    if [ "$LISTENING" -gt 0 ]; then
        echo "[OK] Port 9222 is now listening"
    else
        echo "[WARN] Port 9222 not yet listening. Chrome may still be starting up."
    fi
else
    echo "[FAIL] Cannot write to /etc/chrome_dev.conf — rootfs verification is enabled."
    echo
    echo "Removing rootfs verification via SSH (device will reboot)..."
    ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; /usr/share/vboot/bin/make_dev_ssd.sh --remove_rootfs_verification --partitions 4" 2>/dev/null
    echo "Rebooting device..."
    ssh "$SSH_HOST" "reboot" 2>/dev/null || true
    echo
    print_vt2_ssh_instructions
    echo
    echo "Then from your dev machine:"
    echo "  chromeos fix-devtools"
    exit 1
fi
