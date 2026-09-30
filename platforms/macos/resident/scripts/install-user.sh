#!/usr/bin/env bash
# Install or remove Machine Control.app for the current user: the bundle in
# ~/Applications and a per-user Aqua LaunchAgent serving the resident socket.
# The same installation serves VM guests and physical hosts. Deployment
# policy is separate and root-owned; see install-policy.sh.

set -euo pipefail

readonly LABEL='org.machine-control.resident'
readonly APP_NAME='Machine Control.app'
readonly SUPPORT_DIR="$HOME/Library/Application Support/MachineControl"
readonly SOCKET="$SUPPORT_DIR/control.sock"
readonly LOG_DIR="$HOME/Library/Logs/MachineControl"
readonly AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"
readonly INSTALLED_APP="$HOME/Applications/$APP_NAME"
readonly DOMAIN="gui/$(/usr/bin/id -u)"

usage() {
    cat <<'USAGE'
Usage: install-user.sh --app PATH     Install or update from a built bundle
       install-user.sh --uninstall    Stop and remove the LaunchAgent
       install-user.sh --uninstall --remove-app
USAGE
}

stop_agent() {
    /bin/launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
    /bin/rm -f "$SOCKET"
}

source_app=''
uninstall=false
remove_app=false
while (( $# )); do
    case "$1" in
        --app) source_app="$2"; shift 2 ;;
        --uninstall) uninstall=true; shift ;;
        --remove-app) remove_app=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

if [[ "$uninstall" == true ]]; then
    stop_agent
    /bin/rm -f "$AGENT"
    if [[ "$remove_app" == true ]]; then /bin/rm -rf "$INSTALLED_APP"; fi
    printf 'Removed Machine Control LaunchAgent%s\n' \
        "$([[ "$remove_app" == true ]] && printf ' and application')"
    exit 0
fi
[[ -n "$source_app" && -d "$source_app/Contents" ]] || { usage >&2; exit 2; }
/usr/bin/codesign --verify --strict "$source_app"

stop_agent
/bin/mkdir -p "$HOME/Applications" "$SUPPORT_DIR" "$LOG_DIR" "$(/usr/bin/dirname "$AGENT")"
/bin/chmod 700 "$SUPPORT_DIR"
if [[ "$(cd "$source_app" && pwd -P)" != "$(cd "$INSTALLED_APP" 2>/dev/null && pwd -P || true)" ]]; then
    /bin/rm -rf "$INSTALLED_APP.new"
    /usr/bin/ditto "$source_app" "$INSTALLED_APP.new"
    /bin/rm -rf "$INSTALLED_APP"
    /bin/mv "$INSTALLED_APP.new" "$INSTALLED_APP"
fi

escape() { printf '%s' "$1" | /usr/bin/sed -e 's/[\\&|]/\\&/g'; }
temporary="$(/usr/bin/mktemp "${TMPDIR:-/tmp}/mc-agent.XXXXXX")"
trap '/bin/rm -f -- "$temporary"' EXIT
/usr/bin/sed \
    -e "s|__MC_RESIDENT_BINARY__|$(escape "$INSTALLED_APP/Contents/MacOS/macui")|g" \
    -e "s|__MC_RESIDENT_SOCKET__|$(escape "$SOCKET")|g" \
    -e "s|__MC_RESIDENT_LOG__|$(escape "$LOG_DIR/resident.log")|g" \
    "$INSTALLED_APP/Contents/Resources/$LABEL.plist.in" >"$temporary"
/usr/bin/plutil -lint "$temporary" >/dev/null
/usr/bin/install -m 600 "$temporary" "$AGENT"
/bin/launchctl bootstrap "$DOMAIN" "$AGENT"
/bin/launchctl kickstart -k "$DOMAIN/$LABEL" >/dev/null

client="$INSTALLED_APP/Contents/MacOS/macui"
for _ in {1..50}; do
    if "$client" request "$SOCKET" '{"operation":"status"}' >/dev/null 2>&1; then
        printf 'Machine Control is running; socket: %s\n' "$SOCKET"
        exit 0
    fi
    /bin/sleep 0.1
done
printf 'Machine Control did not become ready; see %s\n' "$LOG_DIR/resident.log" >&2
exit 1
