#!/bin/bash
# ChromeOS SSH Bootstrap
#
# Run as root on VT2:
#   curl -fsSL https://kzahel.github.io/chromeos-testbed/bootstrap.sh | bash
#
# Sets up:
#   - SSH server on port 2223 with key auth
#   - Firewall rules
#   - Persistent start script for reboots
#   - Remote debugging (if rootfs is writable)

set -e

SSH_DIR="/mnt/stateful_partition/etc/ssh"
AUTH_DIR="$SSH_DIR/root_ssh"
SSHD_CONFIG="$SSH_DIR/sshd_config"
SSHD_PID="$SSH_DIR/sshd.pid"
# Linux laptop (controller-host): machines/laptop/id_ed25519.pub in the dotfiles repo.
LAPTOP_PUBKEY="ssh-ed25519 PUBLIC_KEY_PLACEHOLDER controller@example.invalid"
PORT=2223

if [ "$(id -u)" -ne 0 ]; then
    echo "[FAIL] This bootstrap must run as root." >&2
    echo "Run: sudo -i" >&2
    echo "Then re-run the bootstrap command." >&2
    exit 1
fi

echo "[+] ChromeOS testbed bootstrap"
echo

# --- SSH Setup ---
echo "[1/4] Setting up SSH..."

mkdir -p "$AUTH_DIR"
chmod 700 "$AUTH_DIR"

# Generate host keys if needed
[ -f "$SSH_DIR/ssh_host_ed25519_key" ] || ssh-keygen -t ed25519 -f "$SSH_DIR/ssh_host_ed25519_key" -N "" -q
[ -f "$SSH_DIR/ssh_host_rsa_key" ] || ssh-keygen -t rsa -b 4096 -f "$SSH_DIR/ssh_host_rsa_key" -N "" -q
chmod 600 "$SSH_DIR/ssh_host_ed25519_key" "$SSH_DIR/ssh_host_rsa_key"

# Preserve any existing access and ensure the Linux laptop key is authorized.
touch "$AUTH_DIR/authorized_keys"
if ! grep -qxF "$LAPTOP_PUBKEY" "$AUTH_DIR/authorized_keys"; then
    printf '%s\n' "$LAPTOP_PUBKEY" >> "$AUTH_DIR/authorized_keys"
fi
chmod 600 "$AUTH_DIR/authorized_keys"

# Keep the entire sshd configuration on the stateful partition. Without an
# explicit -f, ChromeOS sshd tries to read /etc/ssh/sshd_config, which may be
# inaccessible after changing rootfs verification.
cat > "$SSHD_CONFIG" << CONFIG
Port $PORT
ListenAddress 0.0.0.0
HostKey $SSH_DIR/ssh_host_ed25519_key
HostKey $SSH_DIR/ssh_host_rsa_key
AuthorizedKeysFile $AUTH_DIR/authorized_keys
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin yes
StrictModes no
PidFile $SSHD_PID
Subsystem sftp internal-sftp
CONFIG
chmod 600 "$SSHD_CONFIG"

# Create start script for reboots
cat > "$SSH_DIR/start_sshd.sh" << 'SCRIPT'
#!/bin/bash
set -e
SSH_DIR=/mnt/stateful_partition/etc/ssh
SSHD_CONFIG="$SSH_DIR/sshd_config"
SSHD_PID="$SSH_DIR/sshd.pid"

if [ "$(id -u)" -ne 0 ]; then
    echo "[FAIL] start_sshd.sh must run as root. Run: sudo -i" >&2
    exit 1
fi

iptables -C INPUT -p tcp --dport 2223 -j ACCEPT 2>/dev/null ||
    iptables -I INPUT 3 -p tcp --dport 2223 -j ACCEPT

if [ -r "$SSHD_PID" ]; then
    kill "$(cat "$SSHD_PID")" 2>/dev/null || true
    rm -f "$SSHD_PID"
fi
pkill -f "sshd.*$SSHD_CONFIG" 2>/dev/null || true

/usr/sbin/sshd -t -f "$SSHD_CONFIG"
/usr/sbin/sshd -f "$SSHD_CONFIG"
IP=$(ip addr show wlan0 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d/ -f1)
[ -z "$IP" ] && IP=$(ip addr show eth0 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d/ -f1)
echo "[+] sshd on port 2223 - Connect: ssh -p 2223 root@$IP"
SCRIPT
chmod +x "$SSH_DIR/start_sshd.sh"

# Start sshd now
bash "$SSH_DIR/start_sshd.sh"

echo "    SSH ready on port $PORT"

# --- Remote Debugging ---
echo "[2/4] Configuring remote debugging..."

if touch /etc/.chromeos-testbed-probe 2>/dev/null; then
    rm -f /etc/.chromeos-testbed-probe
    if ! grep -q "remote-debugging-port" /etc/chrome_dev.conf 2>/dev/null; then
        echo "--remote-debugging-port=9222" >> /etc/chrome_dev.conf
        echo "    Added --remote-debugging-port=9222 to chrome_dev.conf"
        echo "    Run 'restart ui' to activate (will restart Chrome)"
    else
        echo "    Remote debugging already configured"
    fi
else
    echo "    [SKIP] Rootfs is read-only. To enable remote debugging later:"
    ROOTDEV=$(rootdev -s); PARTNUM=${ROOTDEV##*p}; KERN_PART=$((PARTNUM - 1))
    echo "    /usr/share/vboot/bin/make_dev_ssd.sh --remove_rootfs_verification --partitions $KERN_PART"
    echo "    reboot"
    echo "    Then run: chromeos fix-devtools"
fi

# --- Dev password ---
echo "[3/4] Developer password..."
if [ -f /mnt/stateful_partition/etc/devmode.passwd ]; then
    echo "    Developer password already set"
else
    echo "    [SKIP] No developer password. Set with: chromeos-setdevpasswd"
fi

# --- Summary ---
echo "[4/4] Done!"
echo

IP=$(ip addr show wlan0 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d/ -f1)
[ -z "$IP" ] && IP=$(ip addr show eth0 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d/ -f1)

echo "=========================================="
echo "SSH:       ssh -p $PORT root@$IP"
echo "After every reboot, restart SSH from VT2 (Ctrl+Alt+F2):"
echo "  Log in as chronos, then:"
echo "  sudo -i"
echo "  cd $SSH_DIR && bash start_sshd.sh"
echo
echo "Add to ~/.ssh/config on your dev machine:"
echo "  Host chromeos-testbed"
echo "    HostName $IP"
echo "    Port $PORT"
echo "    User root"
echo "=========================================="
