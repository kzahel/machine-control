#!/bin/bash
# ChromeOS SSH Bootstrap
#
# Run as root on VT2:
#   curl -fsSL https://kzahel.github.io/chromeos-testbed/bootstrap.sh | bash
#
# Sets up:
#   - SSH server on port 2223 with key auth
#   - Firewall rules
#   - Automatic SSH startup after network connection when rootfs is writable
#   - Persistent manual start script as an update-safe fallback
#   - Remote debugging (if rootfs is writable)

set -e

SSH_DIR="/mnt/stateful_partition/etc/ssh"
AUTH_DIR="$SSH_DIR/root_ssh"
SSHD_CONFIG="$SSH_DIR/sshd_config"
SSHD_PID="$SSH_DIR/sshd.pid"
AUTOSTART_JOB="/etc/init/openssh-server.conf"
FAILED_AUTOSTART_JOB="/etc/init/chromeos-testbed-sshd.conf"
FAILED_AUTOSTART_BACKUP="$SSH_DIR/failed-chromeos-testbed-sshd.conf"
SYSTEM_AUTOSTART_BACKUP="$SSH_DIR/original-openssh-server.conf"
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

# Create a persistent manual fallback. Prefer the automatic Upstart job when
# it is present in the writable rootfs.
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

# Prefer the Upstart-managed listener when its rootfs job is installed.
if [ -f /etc/init/openssh-server.conf ] &&
   grep -qx 'author "chromeos-testbed"' /etc/init/openssh-server.conf &&
   grep -q '/mnt/stateful_partition/etc/ssh/sshd_config' /etc/init/openssh-server.conf; then
    initctl reload-configuration
    if status openssh-server 2>/dev/null | grep -q "start/running"; then
        restart openssh-server
    else
        start openssh-server
    fi
    echo "[+] sshd on port 2223 is managed by Upstart"
    exit 0
fi

# The merged custom job does not receive its boot event on every ChromeOS
# release, but remains usable as a manual fallback until bootstrap migrates it.
if [ -f /etc/init/chromeos-testbed-sshd.conf ] &&
   grep -qx 'author "chromeos-testbed"' /etc/init/chromeos-testbed-sshd.conf &&
   grep -q '/mnt/stateful_partition/etc/ssh/sshd_config' /etc/init/chromeos-testbed-sshd.conf; then
    initctl reload-configuration
    if status chromeos-testbed-sshd 2>/dev/null | grep -q "start/running"; then
        restart chromeos-testbed-sshd
    else
        start chromeos-testbed-sshd
    fi
    echo "[WARN] sshd is using the incompatible Upstart job; re-run bootstrap"
    exit 0
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

# Install an Upstart job when the rootfs is writable. This device reliably
# emits shill-connected after the network and firewall are ready. The job file
# can be replaced by OS updates; the stateful start script remains the fallback
# and bootstrap reinstalls it.
ROOTFS_WRITABLE=no
if touch /etc/.chromeos-testbed-probe 2>/dev/null; then
    rm -f /etc/.chromeos-testbed-probe
    ROOTFS_WRITABLE=yes

    # Preserve an OS-owned openssh-server job before installing the testbed
    # version. Repeated testbed bootstraps do not overwrite this backup.
    if [ -f "$AUTOSTART_JOB" ] &&
       ! grep -qx 'author "chromeos-testbed"' "$AUTOSTART_JOB" &&
       [ ! -f "$SYSTEM_AUTOSTART_BACKUP" ]; then
        cp -p "$AUTOSTART_JOB" "$SYSTEM_AUTOSTART_BACKUP"
    fi

    cat > "$AUTOSTART_JOB" << 'JOB'
description "ChromeOS testbed SSH server"
author "chromeos-testbed"

# shill emits this event whenever ChromeOS obtains network connectivity.
start on shill-connected
stop on stopping system-services or starting halt or starting reboot
respawn
respawn limit 3 10
oom score never

pre-start script
  SSH_DIR=/mnt/stateful_partition/etc/ssh
  SSHD_CONFIG="$SSH_DIR/sshd_config"
  SSHD_PID="$SSH_DIR/sshd.pid"
  START_LOG="$SSH_DIR/startup.log"

  /usr/sbin/sshd -t -f "$SSHD_CONFIG"

  for cmd in iptables ip6tables; do
    attempt=0
    while ! "$cmd" -w -C INPUT -p tcp --dport 2223 -j ACCEPT 2>/dev/null; do
      attempt=$((attempt + 1))
      "$cmd" -w -I INPUT 3 -p tcp --dport 2223 -j ACCEPT 2>/dev/null || true
      [ "$attempt" -ge 5 ] && break
      sleep 1
    done
    "$cmd" -w -C INPUT -p tcp --dport 2223 -j ACCEPT
  done

  printf '%s boot_id=%s uptime=%s events=%s\n' \
    "$(date -Is)" \
    "$(cat /proc/sys/kernel/random/boot_id)" \
    "$(cut -d' ' -f1 /proc/uptime)" \
    "${UPSTART_EVENTS:-manual}" >> "$START_LOG"

  if [ -r "$SSHD_PID" ]; then
    kill "$(cat "$SSHD_PID")" 2>/dev/null || true
    rm -f "$SSHD_PID"
  fi
  pkill -f "sshd.*$SSHD_CONFIG" 2>/dev/null || true
end script

exec /usr/sbin/sshd -D -f /mnt/stateful_partition/etc/ssh/sshd_config

post-stop script
  iptables -w -D INPUT -p tcp --dport 2223 -j ACCEPT 2>/dev/null || true
  ip6tables -w -D INPUT -p tcp --dport 2223 -j ACCEPT 2>/dev/null || true
end script
JOB
    chmod 644 "$AUTOSTART_JOB"
    initctl reload-configuration

    # The alternate custom job selected during the rebase did not start on
    # this ChromeOS release. Migrate it so two respawning listeners cannot
    # compete for the same stateful pid file and port.
    if [ -f "$FAILED_AUTOSTART_JOB" ] &&
       grep -qx 'author "chromeos-testbed"' "$FAILED_AUTOSTART_JOB" &&
       grep -q '/mnt/stateful_partition/etc/ssh/sshd_config' "$FAILED_AUTOSTART_JOB"; then
        if status chromeos-testbed-sshd 2>/dev/null | grep -q "start/running"; then
            stop chromeos-testbed-sshd
        fi
        mv "$FAILED_AUTOSTART_JOB" "$FAILED_AUTOSTART_BACKUP"
        initctl reload-configuration
        echo "    Replaced incompatible SSH startup job (backup: $FAILED_AUTOSTART_BACKUP)"
    fi

    if status openssh-server 2>/dev/null | grep -q "start/running"; then
        restart openssh-server
    else
        start openssh-server
    fi
    echo "    SSH ready on port $PORT (automatic after network connection)"
else
    bash "$SSH_DIR/start_sshd.sh"
    echo "    SSH ready on port $PORT (manual fallback; rootfs is read-only)"
fi

# --- Remote Debugging ---
echo "[2/4] Configuring remote debugging..."

if [ "$ROOTFS_WRITABLE" = yes ]; then
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
if [ "$ROOTFS_WRITABLE" = yes ]; then
    echo "After reboot, SSH starts automatically once ChromeOS joins the network."
    echo "ChromeOS updates may remove the boot job; re-run bootstrap if needed."
else
    echo "After reboot, restart SSH from VT2 (Ctrl+Alt+F2):"
    echo "  Log in as chronos, then:"
    echo "  sudo -i"
    echo "  cd $SSH_DIR && bash start_sshd.sh"
fi
echo "ChromeOS still waits at the profile sign-in screen after reboot."
echo "From the dev machine, run: chromeos login"
echo
echo "Add to ~/.ssh/config on your dev machine:"
echo "  Host chromeos-testbed"
echo "    HostName $IP"
echo "    Port $PORT"
echo "    User root"
echo "=========================================="
