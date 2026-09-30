#!/usr/bin/env bash
# Install or remove the root-owned deployment policy. Run with sudo.
# Without a policy file the resident behaves as a personal workstation.

set -euo pipefail

readonly POLICY_DIR='/Library/Application Support/MachineControl'
readonly POLICY="$POLICY_DIR/policy.json"
readonly PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "${1:-}" in
    appliance|unattended)
        source_policy="${2:-$PACKAGE_DIR/policies/$1.json}"
        [[ -f "$source_policy" ]] || { printf 'Missing %s\n' "$source_policy" >&2; exit 1; }
        [[ "$(/usr/bin/id -u)" == 0 ]] || { printf 'Run with sudo\n' >&2; exit 1; }
        /usr/bin/install -d -o root -g wheel -m 755 "$POLICY_DIR"
        /usr/bin/install -o root -g wheel -m 644 "$source_policy" "$POLICY.new"
        /bin/mv -f "$POLICY.new" "$POLICY"
        printf 'Installed %s policy; restart the resident to apply it\n' "$1"
        ;;
    workstation|--remove)
        [[ "$(/usr/bin/id -u)" == 0 ]] || { printf 'Run with sudo\n' >&2; exit 1; }
        /bin/rm -f "$POLICY"
        printf 'Removed deployment policy; the resident defaults to workstation\n'
        ;;
    *)
        printf 'Usage: sudo install-policy.sh appliance|unattended|workstation\n' >&2
        exit 2
        ;;
esac
