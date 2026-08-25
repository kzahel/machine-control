#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
readonly FACTORY_ROOT="${LINUXVM_FACTORY_LOCAL_ROOT:-$LINUXVM_REPO_DIR/.factory.local}"

usage() {
    cat <<'EOF'
Usage:
  image-factory.sh validate-cloud-image UBUNTU_CLOUD_IMAGE
  image-factory.sh render-seed USERNAME CONTROLLER_PUBLIC_KEY

The source must be an official Ubuntu 24.04 amd64 QCOW2 cloud image. Generated
NoCloud seed media is written under ignored .factory.local storage. The seed
creates a locked, key-only dedicated-appliance account with passwordless sudo,
installs QEMU guest-agent and the Ubuntu GNOME development package profile,
enables GNOME Wayland auto-login, and never contains a private key or password.
EOF
}

validate_cloud_image() {
    if (( $# != 1 )) || [[ ! -f "$1" || ! -r "$1" ]]; then
        printf 'Ubuntu cloud image is absent or unreadable.\n' >&2
        return 1
    fi
    local metadata
    metadata="$(qemu-img info --output json "$1")" || return
    jq -e '.format == "qcow2" and .["virtual-size"] >= 2147483648' \
        <<<"$metadata" >/dev/null || {
        printf 'Ubuntu cloud image must be a plausible QCOW2 image.\n' >&2
        return 1
    }
    printf 'cloud image validated\n'
}

render_seed() {
    if (( $# != 2 )); then usage >&2; return 2; fi
    local username="$1" public_key="$2"
    if [[ ! "$username" =~ ^[a-z_][a-z0-9_-]{0,30}$ ||
          ! -f "$public_key" || ! -r "$public_key" ]]; then
        printf 'Username or controller public key is invalid.\n' >&2
        return 2
    fi
    local key
    key="$(<"$public_key")"
    if [[ ! "$key" =~ ^(ssh-ed25519|ecdsa-sha2-nistp256|ssh-rsa)[[:space:]]+[A-Za-z0-9+/=]+([[:space:]].*)?$ ]]; then
        printf 'Controller public key is not a supported OpenSSH public key.\n' >&2
        return 1
    fi
    for command_name in jq cloud-localds; do
        command -v "$command_name" >/dev/null 2>&1 || {
            printf 'Required command not found: %s\n' "$command_name" >&2
            return 1
        }
    done
    mkdir -p "$FACTORY_ROOT"
    chmod 700 "$FACTORY_ROOT"
    local output="$FACTORY_ROOT/linuxvm-seed.iso"
    if [[ -e "$output" ]]; then
        printf 'Factory seed media already exists; remove it explicitly.\n' >&2
        return 1
    fi
    local staging user_data meta_data
    staging="$(mktemp -d "$FACTORY_ROOT/.seed.XXXXXX")"
    cleanup_seed() { rm -rf -- "$staging"; }
    trap cleanup_seed RETURN
    user_data="$staging/user-data"
    meta_data="$staging/meta-data"
    {
        printf '#cloud-config\n'
        jq -n --arg username "$username" --arg key "$key" '{
          preserve_hostname: false,
          hostname: "linux-test-appliance",
          manage_etc_hosts: true,
          disable_root: true,
          ssh_pwauth: false,
          ssh_deletekeys: true,
          ssh_genkeytypes: ["ed25519", "ecdsa", "rsa"],
          users: [{
            name: $username,
            gecos: "Linux test appliance",
            groups: ["adm", "audio", "cdrom", "dialout", "netdev",
              "plugdev", "sudo", "video"],
            shell: "/bin/bash",
            lock_passwd: true,
            sudo: "ALL=(ALL) NOPASSWD:ALL",
            ssh_authorized_keys: [$key]
          }],
          package_update: true,
          package_upgrade: false,
          packages: ["qemu-guest-agent"],
          write_files: [{
            path: "/etc/gdm3/custom.conf",
            owner: "root:root",
            permissions: "0644",
            content: ("[daemon]\nAutomaticLoginEnable=true\n" +
              "AutomaticLogin=" + $username + "\nWaylandEnable=true\n")
          }],
          runcmd: [
            ["bash", "-lc", ("set -euo pipefail; " +
              "systemctl start qemu-guest-agent.service; " +
              "DEBIAN_FRONTEND=noninteractive apt-get " +
              "-o Dpkg::Options::=--force-confold install -y " +
              "ubuntu-desktop spice-vdagent python3-gi " +
              "gir1.2-atspi-2.0 gnome-screenshot python3-evdev " +
              "python3-pyqt5 wl-clipboard jq git build-essential " +
              "python3-venv; " +
              "snap install chromium; " +
              "systemctl set-default graphical.target; " +
              "systemctl enable gdm3.service; " +
              "systemctl start gdm3.service")]
          ],
          power_state: {mode: "reboot", timeout: 120, condition: true}
        }'
    } >"$user_data"
    jq -n --arg username "$username" '{
      "instance-id": ("machine-control-linux-" + $username),
      "local-hostname": "linux-test-appliance"
    }' >"$meta_data"
    chmod 600 "$user_data" "$meta_data"
    cloud-localds "$output" "$user_data" "$meta_data"
    chmod 600 "$output"
    printf 'seed media rendered in ignored factory storage\n'
}

command="${1:-}"
if [[ -n "$command" ]]; then shift; fi
case "$command" in
    validate-cloud-image) validate_cloud_image "$@" ;;
    render-seed) render_seed "$@" ;;
    help|-h|--help) usage ;;
    *) usage >&2; exit 2 ;;
esac
