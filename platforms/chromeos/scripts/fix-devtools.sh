#!/usr/bin/env bash
# Fix Chrome DevTools remote debugging on ChromeOS
#
# After a ChromeOS update, rootfs verification gets re-enabled and
# /etc/chrome_dev.conf gets reset. This script re-adds the debugging flag.
set -euo pipefail

. "$(dirname "$0")/common.sh"

AUTO_YES=false
[[ "${1:-}" == "-y" ]] && AUTO_YES=true

wait_for_devtools() {
    echo "Waiting up to 30 seconds for Chrome DevTools..."
    if ssh -o ConnectTimeout=5 "$SSH_HOST" "$REMOTE_PATH_SETUP; bash -s" <<'REMOTE_WAIT'
deadline=$((SECONDS + 30))
while ! awk '$2 ~ /:2406$/ && $4 == "0A" { found=1 } END { exit !found }' /proc/net/tcp; do
    [ "$SECONDS" -lt "$deadline" ] || exit 1
    sleep 1
done
REMOTE_WAIT
    then
        echo "[OK] Port 9222 is now listening"
        return 0
    fi
    echo "[FAIL] DevTools did not start within 30 seconds; inspect Chrome logs."
    return 1
}

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
        wait_for_devtools
        exit $?
    fi
fi

# Try to write the flag
echo "Adding --remote-debugging-port=9222 to chrome_dev.conf..."
WRITE_RESULT=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; echo '--remote-debugging-port=9222' >> /etc/chrome_dev.conf 2>&1 && echo SUCCESS || echo FAIL" 2>/dev/null)

if echo "$WRITE_RESULT" | grep -q "SUCCESS"; then
    echo "[OK] Flag added to chrome_dev.conf"
    echo "Restarting Chrome UI..."
    ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; restart ui" 2>/dev/null
    wait_for_devtools
else
    echo "[FAIL] Cannot write to /etc/chrome_dev.conf — rootfs verification is enabled."
    echo
    echo "Fixing this requires removing rootfs verification and rebooting."
    echo "After this update-repair reboot, SSH may need VT2 recovery if the"
    echo "rootfs update replaced the automatic Upstart job."
    if [[ "$AUTO_YES" != true ]]; then
        echo
        read -r -p "Proceed? [y/N] " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            echo "Aborted."
            exit 1
        fi
    fi
    echo
    echo "Detecting active kernel partition..."
    # ChromeOS A/B: root partition 3 → kernel partition 2, root partition 5 → kernel partition 4
    KERN_PART=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; ROOTDEV=\$(rootdev -s); PARTNUM=\${ROOTDEV##*p}; echo \$((PARTNUM - 1))" 2>/dev/null)
    if [ -z "$KERN_PART" ] || [ "$KERN_PART" -lt 2 ] || [ "$KERN_PART" -gt 4 ]; then
        echo "[FAIL] Could not detect kernel partition (got: ${KERN_PART:-empty})"
        exit 1
    fi
    echo "Removing rootfs verification on partition $KERN_PART..."
    ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; /usr/share/vboot/bin/make_dev_ssd.sh --remove_rootfs_verification --partitions $KERN_PART" 2>/dev/null
    echo "Rebooting device..."
    ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; reboot" || true
    echo
    print_vt2_ssh_instructions
    echo
    echo "Then from your dev machine:"
    echo "  chromeos fix-devtools"
    exit 1
fi
