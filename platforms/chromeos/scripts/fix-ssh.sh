#!/usr/bin/env bash
# Fix SSH access to ChromeOS device after reboot
#
# After a ChromeOS reboot, the firewall rules are reset and sshd stops.
# This script restarts sshd by running start_sshd.sh on the device.
set -euo pipefail

SSH_HOST="${CHROMEBOOK_HOST:-chromeos-testbed}"

echo "Attempting to restart sshd on $SSH_HOST..."

if ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_HOST" \
    "export PATH=/bin:/usr/bin:/usr/local/bin:\$PATH; bash /mnt/stateful_partition/etc/ssh/start_sshd.sh" 2>/dev/null; then
    echo "[OK] sshd restarted"
else
    echo "[FAIL] Cannot reach $SSH_HOST via SSH."
    echo
    echo "Manual fix — run these commands on the Chromebook VT2 (Ctrl+Alt+F2):"
    echo
    echo "  1. Log in as chronos"
    echo "  2. sudo bash /mnt/stateful_partition/etc/ssh/start_sshd.sh"
    echo
    echo "If start_sshd.sh doesn't exist, the device needs bootstrapping:"
    echo "  sudo bash"
    echo "  curl -sL kyle.graehl.org/chromeos-testbed/bootstrap.sh | bash"
    exit 1
fi
