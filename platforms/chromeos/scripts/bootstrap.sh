#!/bin/bash
# ChromeOS SSH Bootstrap
#
# Run as root on VT2:
#   curl -sL kyle.graehl.org/chromeos-testbed/bootstrap.sh | bash
#
# Sets up:
#   - SSH server on port 2223 with key auth
#   - Firewall rules
#   - Persistent start script for reboots
#   - Remote debugging (if rootfs is writable)

set -e

SSH_DIR="/mnt/stateful_partition/etc/ssh"
AUTH_DIR="$SSH_DIR/root_ssh"
PUBKEY="ssh-ed25519 PUBLIC_KEY_PLACEHOLDER testbed-user@controller-host"
PORT=2223

echo "[+] ChromeOS testbed bootstrap"
echo

# --- SSH Setup ---
echo "[1/4] Setting up SSH..."

mkdir -p "$AUTH_DIR"
chmod 700 "$AUTH_DIR"

# Generate host keys if needed
[ -f "$SSH_DIR/ssh_host_ed25519_key" ] || ssh-keygen -t ed25519 -f "$SSH_DIR/ssh_host_ed25519_key" -N "" -q
[ -f "$SSH_DIR/ssh_host_rsa_key" ] || ssh-keygen -t rsa -b 4096 -f "$SSH_DIR/ssh_host_rsa_key" -N "" -q

# Add authorized key
echo "$PUBKEY" > "$AUTH_DIR/authorized_keys"
chmod 600 "$AUTH_DIR/authorized_keys"

# Create start script for reboots
cat > "$SSH_DIR/start_sshd.sh" << 'SCRIPT'
#!/bin/bash
iptables -I INPUT 3 -p tcp --dport 2223 -j ACCEPT 2>/dev/null
pkill -f "sshd.*-p 2223" 2>/dev/null
/usr/sbin/sshd -p 2223 -o AuthorizedKeysFile=/mnt/stateful_partition/etc/ssh/root_ssh/authorized_keys -o StrictModes=no
IP=$(ip addr show wlan0 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d/ -f1)
[ -z "$IP" ] && IP=$(ip addr show eth0 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d/ -f1)
echo "[+] sshd on port 2223 - Connect: ssh -p 2223 root@$IP"
SCRIPT
chmod +x "$SSH_DIR/start_sshd.sh"

# Start sshd now
iptables -I INPUT 3 -p tcp --dport $PORT -j ACCEPT
pkill -f "sshd.*-p $PORT" 2>/dev/null || true
/usr/sbin/sshd -p $PORT -o AuthorizedKeysFile="$AUTH_DIR/authorized_keys" -o StrictModes=no

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
    echo "    /usr/share/vboot/bin/make_dev_ssd.sh --remove_rootfs_verification --partitions 4"
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
