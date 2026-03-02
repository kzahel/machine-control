#!/usr/bin/env bash
# Fix SSH access to ChromeOS device after reboot
#
# After a ChromeOS reboot, the firewall rules are reset and sshd stops.
# This script restarts sshd by running start_sshd.sh on the device.
set -euo pipefail

. "$(dirname "$0")/common.sh"

echo "Attempting to restart sshd on $SSH_HOST..."

if ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_HOST" \
    "$REMOTE_PATH_SETUP; bash /mnt/stateful_partition/etc/ssh/start_sshd.sh" 2>/dev/null; then
    echo "[OK] sshd restarted"
else
    echo "[FAIL] Cannot reach $SSH_HOST via SSH."
    echo
    print_vt2_ssh_instructions
    echo
    echo "If start_sshd.sh doesn't exist, the device needs bootstrapping:"
    echo "  sudo -i"
    echo "  curl -sL kyle.graehl.org/chromeos-testbed/bootstrap.sh | bash"
    exit 1
fi
