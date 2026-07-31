#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
install_homebrew=0

usage() {
    cat <<'EOF'
Usage: bootstrap-guest.sh [--install-homebrew]

Install and register the Tart guest daemon and interactive-user agent.
Run this from Terminal.app inside the logged-in macOS guest.

--install-homebrew permits this script to run Homebrew's official network
installer when brew is absent. Without it, the script prints the command and
stops so the user can inspect and run that installer deliberately.
EOF
}

case "${1:-}" in
    '') ;;
    --install-homebrew) install_homebrew=1 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
esac

if [[ "$(uname -s)" != "Darwin" ]]; then
    printf 'This bootstrap must run inside the macOS guest\n' >&2
    exit 1
fi
if [[ "$EUID" -eq 0 ]]; then
    printf 'Run as the logged-in desktop user, not root\n' >&2
    exit 1
fi
if [[ "$(stat -f %Su /dev/console)" != "$USER" ]]; then
    printf 'Run from Terminal.app in the active graphical login session\n' >&2
    exit 1
fi

printf 'Requesting one administrator authorization for guest setup...\n'
sudo -v

if ! xcode-select -p >/dev/null 2>&1; then
    xcode-select --install || true
    printf 'Complete the Command Line Tools installer, then rerun this script.\n' >&2
    exit 1
fi

if [[ -x /opt/homebrew/bin/brew ]]; then
    brew=/opt/homebrew/bin/brew
elif command -v brew >/dev/null 2>&1; then
    brew="$(command -v brew)"
else
    if (( ! install_homebrew )); then
        cat >&2 <<'EOF'
Homebrew is required. Inspect and run its official installer, or rerun with
--install-homebrew to authorize this script to invoke it:

/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
EOF
        exit 1
    fi
    NONINTERACTIVE=1 /bin/bash -c \
        "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    brew=/opt/homebrew/bin/brew
fi

"$brew" install cirruslabs/cli/tart-guest-agent
agent_path="$("$brew" --prefix)/bin/tart-guest-agent"
guest_home="$HOME"

scratch="$(mktemp -d /tmp/macvm-bootstrap.XXXXXX)"
trap 'rm -rf "$scratch"' EXIT

render_plist() {
    local source="$1" output="$2"
    sed \
        -e "s|__AGENT_PATH__|$agent_path|g" \
        -e "s|__GUEST_HOME__|$guest_home|g" \
        "$source" > "$output"
    plutil -lint "$output" >/dev/null
}

agent_plist="$scratch/org.cirruslabs.tart-guest-agent.plist"
daemon_plist="$scratch/org.cirruslabs.tart-guest-daemon.plist"
render_plist "$SCRIPT_DIR/org.cirruslabs.tart-guest-agent.plist.in" "$agent_plist"
render_plist "$SCRIPT_DIR/org.cirruslabs.tart-guest-daemon.plist.in" "$daemon_plist"

sudo install -o root -g wheel -m 0644 "$daemon_plist" \
    /Library/LaunchDaemons/org.cirruslabs.tart-guest-daemon.plist
sudo install -o root -g wheel -m 0644 "$agent_plist" \
    /Library/LaunchAgents/org.cirruslabs.tart-guest-agent.plist

sudo launchctl bootout system/org.cirruslabs.tart-guest-daemon 2>/dev/null || true
launchctl bootout "gui/$UID/org.cirruslabs.tart-guest-agent" 2>/dev/null || true
sudo launchctl bootstrap system \
    /Library/LaunchDaemons/org.cirruslabs.tart-guest-daemon.plist
launchctl bootstrap "gui/$UID" \
    /Library/LaunchAgents/org.cirruslabs.tart-guest-agent.plist

sudo launchctl print system/org.cirruslabs.tart-guest-daemon >/dev/null
launchctl print "gui/$UID/org.cirruslabs.tart-guest-agent" >/dev/null

cat <<'EOF'

Tart guest services are running. On the host, continue with:

  bin/macvm doctor
  bin/macvm deploy-ui
  bin/macvm authorize-ui

The final Accessibility grant is an explicit macOS consent action. Follow
docs/bootstrap.md; do not modify the TCC database directly.
EOF
