# Shared helpers for chromeos-testbed scripts
# Source this file: . "$(dirname "$0")/common.sh"

SSH_HOST="${CHROMEBOOK_HOST:-chromeos-testbed}"
CLIENT_PATH="${CHROMEOS_CLIENT_PATH:-/mnt/stateful_partition/c2/client.py}"
REMOTE_PATH_SETUP="export PATH=/bin:/usr/bin:/usr/local/bin:\$PATH"

print_vt2_ssh_instructions() {
    echo "SSH must be restarted manually from VT2 after every reboot:"
    echo
    echo "  1. On the Chromebook, press Ctrl+Alt+F2"
    echo "  2. Log in as chronos"
    echo "  3. sudo -i"
    echo "  4. cd /mnt/stateful_partition/etc/ssh && bash start_sshd.sh"
    echo "  5. Press Ctrl+Alt+F1 to return to GUI"
}
