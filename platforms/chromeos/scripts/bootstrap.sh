#!/bin/bash
# ChromeOS SSH Bootstrap
#
# Run as root on VT2:
#   curl -fSL https://raw.githubusercontent.com/kzahel/machine-control/main/platforms/chromeos/scripts/bootstrap.sh -o /mnt/stateful_partition/bootstrap.sh
#   bash /mnt/stateful_partition/bootstrap.sh
#
# Sets up:
#   - SSH server on port 2223 with key auth
#   - Firewall rules
#   - Automatic SSH startup after network connection when rootfs is writable
#   - Persistent manual start script as an update-safe fallback
#   - Required idle- and lid-suspend inhibition for the dedicated test appliance
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
POWER_POLICY="$SSH_DIR/apply_power_policy.sh"
POWER_POLICY_JOB="/etc/init/chromeos-testbed-power-policy.conf"
POWER_POLICY_OVERRIDE="/etc/init/chromeos-testbed-power-policy.override"
CONTROLLER_PUBKEY="${CHROMEOS_TESTBED_CONTROLLER_PUBKEY:-}"
PORT=2223

# BEGIN setup workflow
usage() {
    echo 'Usage: bash bootstrap.sh [--yes] [--repair-only]'
    echo 'Default: guided first-time setup, including rootfs preparation and reboot.'
    echo '--yes: approve dedicated-appliance setup without prompting.'
    echo '--repair-only: install on this image; never change boot verification or reboot.'
}
AUTO_YES=no
REPAIR_ONLY=no
while [ "$#" -gt 0 ]; do
    case "$1" in
        --yes|-y) AUTO_YES=yes; shift ;;
        --repair-only) REPAIR_ONLY=yes; shift ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; exit 1 ;;
    esac
done

set_setup_state() {
    printf '%s\n' "$1" > "$SSH_DIR/setup-state.next"
    mv "$SSH_DIR/setup-state.next" "$SSH_DIR/setup-state"
}

approve_setup() {
    [ "$REPAIR_ONLY" = yes ] && return 0
    [ "$(cat "$SSH_DIR/setup-approved" 2>/dev/null)" = dedicated-appliance-v1 ] && return 0
    if [ "$AUTO_YES" != yes ]; then
        echo 'Set up this dedicated ChromeOS test appliance?'
        echo 'This authorizes key-only root SSH, developer Python, DevTools,'
        echo 'always-awake operation, and Select-to-speak for desktop control.'
        echo 'If needed, setup disables rootfs verification and reboots.'
        echo 'The controller will also verify automatic SSH with a reboot.'
        echo 'Developer Mode must already be enabled; setup does not enable it or wipe data.'
        if ! read -r -p 'Proceed with setup? [y/N] ' answer; then
            echo 'No input available. Use --yes for an explicitly authorized unattended setup.' >&2
            return 1
        fi
        case "$answer" in y|Y|yes|YES) ;; *) echo 'Setup cancelled.'; return 1 ;; esac
    fi
    printf '%s\n' dedicated-appliance-v1 > "$SSH_DIR/setup-approved"
}

import_controller_keys() {
    local keyfile="$SSH_DIR/controller-key.validate" line
    if [ -z "$CONTROLLER_PUBKEY" ] && [ ! -s "$AUTH_DIR/authorized_keys" ]; then
        echo 'No SSH public key is installed yet.' >&2
        echo 'Supply your laptop SSH public key through CHROMEOS_TESTBED_CONTROLLER_PUBKEY' >&2
        echo 'or use prepare-bootstrap.py on your laptop to package it locally.' >&2
        return 1
    fi
    if [ -n "$CONTROLLER_PUBKEY" ]; then
        # Validate every line before adding any access; a single valid key must
        # not mask malformed lines or authorized_keys options in the input.
        while IFS= read -r line; do
            case "$line" in ssh-*\ *|ecdsa-*\ *|sk-*\ *) ;; *) echo 'Expected OpenSSH public keys without options.' >&2; return 1 ;; esac
            printf '%s\n' "$line" > "$keyfile"
            ssh-keygen -lf "$keyfile" || return 1
        done <<< "$CONTROLLER_PUBKEY"
        while IFS= read -r line; do
            grep -qxF "$line" "$AUTH_DIR/authorized_keys" 2>/dev/null || printf '%s\n' "$line" >> "$AUTH_DIR/authorized_keys"
        done <<< "$CONTROLLER_PUBKEY"
        rm -f "$keyfile"
    fi
    [ -s "$AUTH_DIR/authorized_keys" ] || { echo 'No controller key installed.' >&2; return 1; }
    chmod 600 "$AUTH_DIR/authorized_keys"
}

prepare_boot_transition() {
    local root_device root_partition kernel_partition update_operation
    [ "$REPAIR_ONLY" = yes ] && return 0
    update_operation=$(update_engine_client --status 2>/dev/null | awk -F= '$1 == "CURRENT_OP" {print $2}')
    if [ "$update_operation" = UPDATE_STATUS_UPDATED_NEED_REBOOT ]; then
        set_setup_state awaiting-update-reboot
    elif [ "$ROOTFS_WRITABLE" = no ]; then
        root_device=$(rootdev -s) || return 1
        case "$root_device" in /dev/mmcblk*p[35]|/dev/nvme*n*p[35]|/dev/sd?[35]) ;; *) echo 'Cannot safely identify active A/B root partition.' >&2; return 1 ;; esac
        root_partition=${root_device: -1}
        kernel_partition=$((root_partition - 1))
        /usr/share/vboot/bin/make_dev_ssd.sh --remove_rootfs_verification --partitions "$kernel_partition" || return 1
        set_setup_state awaiting-rootfs-reboot
    else
        set_setup_state controller-required
        return 0
    fi
    # Diagnostics print recovery instructions before the EXIT handler reboots.
    BOOTSTRAP_REBOOT=yes
}
# END setup workflow

if [ "$(id -u)" -ne 0 ]; then
    echo "[FAIL] This bootstrap must run as root." >&2
    echo "Run: sudo -i" >&2
    echo "Then re-run the bootstrap command." >&2
    exit 1
fi

# Keep diagnostics private on the device. Do not enable shell xtrace: the
# controller public-key import and future credential handling are not traces.
export PATH=/bin:/usr/bin:/usr/local/bin:/sbin:/usr/sbin:$PATH
umask 077
if ! grep -q '^CHROMEOS_RELEASE_NAME=' /etc/lsb-release 2>/dev/null ||
   [ "$(crossystem devsw_boot 2>/dev/null)" != 1 ]; then
    echo 'This setup requires ChromeOS already in Developer Mode.' >&2
    exit 1
fi
mkdir -p "$SSH_DIR" "$AUTH_DIR"
chmod 700 "$AUTH_DIR"
approve_setup
import_controller_keys
if [ "$REPAIR_ONLY" != yes ]; then
    if [ ! -f "${BASH_SOURCE[0]}" ]; then
        echo 'Download bootstrap.sh to a file before running guided setup.' >&2
        exit 1
    fi
    if [ "${BASH_SOURCE[0]}" != "$SSH_DIR/setup-bootstrap.sh" ]; then
        cp "${BASH_SOURCE[0]}" "$SSH_DIR/setup-bootstrap.sh"
    fi
    chmod 700 "$SSH_DIR/setup-bootstrap.sh"
fi
BOOTSTRAP_REBOOT=no
BOOTSTRAP_LOG="$SSH_DIR/bootstrap.log"
BOOTSTRAP_REPORT="$SSH_DIR/bootstrap-report.txt"
BOOTSTRAP_FAILED_LINE=none
touch "$BOOTSTRAP_LOG" "$BOOTSTRAP_REPORT"
chmod 600 "$BOOTSTRAP_LOG" "$BOOTSTRAP_REPORT"
exec 3>&1 4>&2
# BEGIN bootstrap diagnostics
bootstrap_diagnostics() {
    local result="$1" addresses listener banner input_first
    set +e
    trap - ERR EXIT
    exec 1>&3 2>&4
    addresses=$(ip -o -4 addr show scope global 2>/dev/null | awk '{print $2 "=" $4}' | paste -sd ' ' -)
    listener=$(ss -lntp 2>/dev/null | awk '$4 ~ /:2223$/')
    banner=$(ssh-keyscan -T 3 -p "$PORT" 127.0.0.1 2>/dev/null)
    SSH_LOCAL_STATUS=FAIL
    if printf '%s\n' "$banner" | grep -q ' ssh-\| ecdsa-'; then
        SSH_LOCAL_STATUS=OK
    fi
    input_first=$(iptables -S INPUT 2>/dev/null | awk '/^-A / { print; exit }')
    {
        echo "BOOTSTRAP DIAGNOSTICS v2"
        echo "exit=$result failed_line=${BOOTSTRAP_FAILED_LINE:-none}"
        echo "host=$(hostname) addresses=$addresses"
        echo "rootfs_writable=${ROOTFS_WRITABLE:-unknown}"
        echo "power_applied=${POWER_POLICY_READY:-unknown} power_guard=${POWER_POLICY_GUARD_READY:-unknown}"
        echo "python_ready=${PYTHON_READY:-unknown}"
        echo "local_ssh=$SSH_LOCAL_STATUS"
        echo "--- listeners ---"
        ss -lntp 2>&1
        echo "--- SSH configuration validation ---"
        /usr/sbin/sshd -t -f "$SSHD_CONFIG" 2>&1
        echo "sshd_config_exit=$?"
        echo "--- network addresses and routes ---"
        ip -o addr show 2>&1
        ip route show 2>&1
        echo "--- INPUT rules and packet counters ---"
        iptables -nvL INPUT --line-numbers 2>&1
        echo "--- OUTPUT rules and packet counters ---"
        iptables -nvL OUTPUT --line-numbers 2>&1
        echo "--- all IPv4 filter chains ---"
        iptables -S 2>&1
        echo "--- root image and release ---"
        rootdev -s 2>&1
        cat /etc/lsb-release 2>&1
        echo "--- power policy evidence ---"
        tail -n 5 "$SSH_DIR/power-policy.log" 2>&1
        echo "--- bootstrap output ---"
        cat "$BOOTSTRAP_LOG"
    } > "$BOOTSTRAP_REPORT" 2>&1
    echo
    echo "========== BOOTSTRAP RESULT v2 =========="
    if [ "${BOOTSTRAP_REBOOT:-no}" = yes ]; then
        echo "SETUP: reboot required; progress saved"
    elif [ "$result" -eq 0 ] && [ "$SSH_LOCAL_STATUS" = OK ]; then
        echo "SETUP: completed locally; remote access not yet verified"
    else
        echo "SETUP: INCOMPLETE (exit $result, failed line ${BOOTSTRAP_FAILED_LINE:-none})"
    fi
    echo "NETWORK: ${addresses:-no global IPv4 address found}"
    echo "SSH LOCAL HANDSHAKE: $SSH_LOCAL_STATUS (127.0.0.1:$PORT)"
    if [ -n "$listener" ]; then
        echo "SSH LISTENER: $listener"
    else
        echo "SSH LISTENER: NOT FOUND (or ss unavailable)"
    fi
    echo "FIRST INPUT RULE: ${input_first:-unavailable}"
    echo "ROOTFS WRITABLE: ${ROOTFS_WRITABLE:-unknown}"
    echo "POWER: applied=${POWER_POLICY_READY:-unknown} guard=${POWER_POLICY_GUARD_READY:-unknown}"
    echo "PYTHON RUNTIME: ${PYTHON_READY:-not checked}"
    if [ "${ROOTFS_WRITABLE:-unknown}" = no ]; then
        echo "PERSISTENCE: pending writable-rootfs setup"
    fi
    echo "LOG: $BOOTSTRAP_LOG"
    echo "REPORT: $BOOTSTRAP_REPORT"
    if [ -n "${CHROMEOS_TESTBED_REPORT_URL:-}" ]; then
        if curl -fsS --connect-timeout 3 --max-time 15 \
            -H 'Content-Type: text/plain' --data-binary "@$BOOTSTRAP_REPORT" \
            "$CHROMEOS_TESTBED_REPORT_URL" >/dev/null 2>&1; then
            echo "REPORT DELIVERY: OK - controller has the full diagnostics"
        else
            echo "REPORT DELIVERY: FAILED - photograph this result block"
        fi
    else
        echo "Photograph this result block if remote SSH is unavailable."
    fi
    echo "SETUP PHASE: $(cat "$SSH_DIR/setup-state" 2>/dev/null || echo repair-only)"
    if [ "${BOOTSTRAP_REBOOT:-no}" = yes ]; then
        echo 'Rebooting. After boot, return to VT2 as root and run:'
        echo "  bash $SSH_DIR/start_sshd.sh"
        echo 'Then the controller can finish with: chromeos setup'
        echo "========================================"
        if ! reboot; then
            echo "[FAIL] Could not reboot. Progress is saved; inspect the system reboot error."
            exit 1
        fi
        exit 2
    fi
    echo 'Continue on the controller with: chromeos setup'
    echo "========================================"
    [ "$SSH_LOCAL_STATUS" = OK ] || result=1
    exit "$result"
}
# END bootstrap diagnostics

trap 'BOOTSTRAP_FAILED_LINE=$LINENO' ERR
trap 'bootstrap_diagnostics "$?"' EXIT
echo "ChromeOS bootstrap v2: running checks; final report follows."
exec > "$BOOTSTRAP_LOG" 2>&1
echo "[+] ChromeOS testbed bootstrap"
echo

# --- SSH Setup ---
echo "[1/5] Setting up SSH..."

mkdir -p "$AUTH_DIR"
chmod 700 "$AUTH_DIR"

# Generate host keys if needed
[ -f "$SSH_DIR/ssh_host_ed25519_key" ] || ssh-keygen -t ed25519 -f "$SSH_DIR/ssh_host_ed25519_key" -N "" -q
[ -f "$SSH_DIR/ssh_host_rsa_key" ] || ssh-keygen -t rsa -b 4096 -f "$SSH_DIR/ssh_host_rsa_key" -N "" -q
chmod 600 "$SSH_DIR/ssh_host_ed25519_key" "$SSH_DIR/ssh_host_rsa_key"

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

# Keep the dedicated test appliance available for remote control while idle or
# closed. The powerd preferences live on the stateful partition, and the helper
# also reapplies the embedded-controller lid override on every SSH boot path.
cat > "$POWER_POLICY" << 'SCRIPT'
#!/bin/bash
set -u

PATH=/bin:/usr/bin:/usr/local/bin:/usr/sbin:/sbin
POWER_DIR=/var/lib/power_manager
LOG=/mnt/stateful_partition/etc/ssh/power-policy.log
SOURCE="${1:-manual}"
RELOAD="${2:-}"
changed=no
status_value=ready

mkdir -p "$POWER_DIR" || status_value=failed

if [ "$(cat "$POWER_DIR/disable_idle_suspend" 2>/dev/null)" != 1 ]; then
    printf '1\n' > "$POWER_DIR/disable_idle_suspend" || status_value=failed
    changed=yes
fi
if [ "$(cat "$POWER_DIR/use_lid" 2>/dev/null)" != 0 ]; then
    printf '0\n' > "$POWER_DIR/use_lid" || status_value=failed
    changed=yes
fi

if ! command -v ectool >/dev/null 2>&1 ||
   ! ectool forcelidopen 1 >/dev/null 2>&1; then
    status_value=failed
fi

if [ "$changed" = yes ] || [ "$RELOAD" = --reload ]; then
    if status powerd 2>/dev/null | grep -q 'start/running'; then
        restart powerd >/dev/null 2>&1 || status_value=failed
    else
        status_value=failed
    fi
fi

if [ "$(cat "$POWER_DIR/disable_idle_suspend" 2>/dev/null)" != 1 ] ||
   [ "$(cat "$POWER_DIR/use_lid" 2>/dev/null)" != 0 ]; then
    status_value=failed
fi

printf '%s boot_id=%s source=%s status=%s\n' \
    "$(date -Is)" \
    "$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || echo unknown)" \
    "$SOURCE" \
    "$status_value" >> "$LOG"

[ "$status_value" = ready ]
SCRIPT
chmod 700 "$POWER_POLICY"

POWER_POLICY_READY=no
if bash "$POWER_POLICY" bootstrap --reload; then
    POWER_POLICY_READY=yes
fi

# Create a persistent manual fallback. Prefer the automatic Upstart job when
# it is present in the writable rootfs.
cat > "$SSH_DIR/start_sshd.sh" << 'SCRIPT'
#!/bin/bash
set -e
SSH_DIR=/mnt/stateful_partition/etc/ssh
SSHD_CONFIG="$SSH_DIR/sshd_config"
SSHD_PID="$SSH_DIR/sshd.pid"
POWER_POLICY="$SSH_DIR/apply_power_policy.sh"

if [ "$(id -u)" -ne 0 ]; then
    echo "[FAIL] start_sshd.sh must run as root. Run: sudo -i" >&2
    exit 1
fi

if [ -r "$POWER_POLICY" ]; then
    if ! bash "$POWER_POLICY" manual --reload; then
        echo "[WARN] Closed-lid power policy could not be applied; re-run bootstrap" >&2
    fi
else
    echo "[WARN] Closed-lid power policy helper is missing; re-run bootstrap" >&2
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

# An existing rule can sit behind ChromeOS's terminating reject/drop rule.
# Move our exact allow rule to the front, including on repeated bootstrap.
while iptables -D INPUT -p tcp --dport 2223 -j ACCEPT 2>/dev/null; do :; done
iptables -I INPUT 1 -p tcp --dport 2223 -j ACCEPT

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
POWER_POLICY_GUARD_READY=no
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
  POWER_POLICY="$SSH_DIR/apply_power_policy.sh"

  power_policy_status=failed
  if [ -r "$POWER_POLICY" ] && bash "$POWER_POLICY" upstart; then
    power_policy_status=ready
  fi

  /usr/sbin/sshd -t -f "$SSHD_CONFIG"

  for cmd in iptables ip6tables; do
    # Existence alone does not prove reachability: a preceding deny wins.
    # Remove old copies and install one allow before ChromeOS's deny rules.
    while "$cmd" -w -D INPUT -p tcp --dport 2223 -j ACCEPT 2>/dev/null; do :; done
    attempt=0
    until "$cmd" -w -I INPUT 1 -p tcp --dport 2223 -j ACCEPT 2>/dev/null; do
      attempt=$((attempt + 1))
      [ "$attempt" -ge 5 ] && exit 1
      sleep 1
    done
    "$cmd" -w -C INPUT -p tcp --dport 2223 -j ACCEPT
  done

  printf '%s boot_id=%s uptime=%s events=%s power_policy=%s\n' \
    "$(date -Is)" \
    "$(cat /proc/sys/kernel/random/boot_id)" \
    "$(cut -d' ' -f1 /proc/uptime)" \
    "${UPSTART_EVENTS:-manual}" \
    "$power_policy_status" >> "$START_LOG"

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

    # Reassert the dedicated-appliance baseline whenever powerd starts. This
    # heals an accidental preference reset or EC override change without
    # waiting for a reboot, SSH restart, or agent-driven repair.
    cat > "$POWER_POLICY_JOB" << 'POWER_JOB'
description "ChromeOS testbed always-awake power policy"
author "chromeos-testbed"

start on started powerd
stop on stopping system-services or starting halt or starting reboot
task

script
  POWER_POLICY=/mnt/stateful_partition/etc/ssh/apply_power_policy.sh
  if [ ! -r "$POWER_POLICY" ] || ! bash "$POWER_POLICY" powerd-started; then
    logger -t chromeos-testbed-power-policy \
      "failed to reapply the required always-awake policy"
    exit 1
  fi
end script
POWER_JOB
    chmod 644 "$POWER_POLICY_JOB"
    rm -f "$POWER_POLICY_OVERRIDE"
    POWER_POLICY_GUARD_READY=yes
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
    echo "    SSH start requested (automatic after network connection); verifying at exit"
else
    bash "$SSH_DIR/start_sshd.sh"
    echo "    SSH start requested (manual fallback; rootfs is read-only); verifying at exit"
fi

echo "[2/5] Verifying closed-lid availability..."
if [ "$POWER_POLICY_READY" = yes ] && [ "$POWER_POLICY_GUARD_READY" = yes ]; then
    echo "    Idle and lid suspend are disabled and guarded for the dedicated test appliance"
else
    echo "    [FAIL] Could not apply and guard the required closed-lid power policy"
fi

# --- Remote Debugging ---
echo "[3/5] Configuring remote debugging..."

if [ "$ROOTFS_WRITABLE" = yes ]; then
    if ! grep -q "remote-debugging-port" /etc/chrome_dev.conf 2>/dev/null; then
        echo "--remote-debugging-port=9222" >> /etc/chrome_dev.conf
        echo "    Added --remote-debugging-port=9222 to chrome_dev.conf"
        echo "    Run 'restart ui' to activate (will restart Chrome)"
    else
        echo "    Remote debugging already configured"
    fi
else
    echo "    Remote debugging requires writable-rootfs preparation."
fi

# --- Target runtime ---
echo "[4/5] Preparing Python runtime and developer access..."
PYTHON_READY=no
if LD_LIBRARY_PATH=/usr/local/lib64 python3 -c 'import ssl, ctypes, fcntl, json' >/dev/null 2>&1; then
    PYTHON_READY=yes
else
    echo "    Installing ChromeOS developer bootstrap packages for Python..."
    if command -v dev_install >/dev/null 2>&1 &&
       LD_LIBRARY_PATH=/usr/local/lib64 dev_install --only_bootstrap --yes; then
        if LD_LIBRARY_PATH=/usr/local/lib64 python3 -c 'import ssl, ctypes, fcntl, json'; then
            PYTHON_READY=yes
        fi
    fi
fi
if [ "$PYTHON_READY" = yes ]; then
    echo "    Python runtime is usable with the platform CLI library path"
else
    echo "    [FAIL] Python runtime is unavailable; inspect the developer installer output above"
fi

# --- Dev password ---
if [ -f /mnt/stateful_partition/etc/devmode.passwd ]; then
    echo "    Developer password already set"
else
    echo "    [SKIP] No developer password. Set with: chromeos-setdevpasswd"
fi

# Record which immutable ChromeOS root image this bootstrap prepared. The
# marker survives A/B updates, allowing post-update audit to distinguish a
# repaired image from state merely restored by the manual SSH fallback.
PREPARED_RELEASE=$(awk -F= '$1 == "CHROMEOS_RELEASE_VERSION" { print $2; exit }' /etc/lsb-release)
printf '%s\n' "${PREPARED_RELEASE:-unknown}" > "$SSH_DIR/prepared-release"

# Guided setup owns boot transitions; repair-only never changes boot state.
prepare_boot_transition
if [ "$BOOTSTRAP_REBOOT" = yes ]; then
    exit 2
fi

# The EXIT report verifies the listener and local SSH handshake and clearly
# separates current reachability from reboot persistence.
if [ "$POWER_POLICY_READY" != yes ] || [ "$POWER_POLICY_GUARD_READY" != yes ] ||
   [ "$PYTHON_READY" != yes ]; then
    exit 1
fi
