#!/usr/bin/env bash
# Register or remove the Machine Control native-messaging host for Chrome.
# Chrome starts the application executable in host mode only for the
# Machine Control extension ID listed in allowed_origins.

set -euo pipefail

readonly HOST_NAME='org.machine_control.browser'
readonly DEFAULT_EXTENSION_ID='ncbfifkjllmnkkjmomjohinigfgdocjc'

app="$HOME/Applications/Machine Control.app"
extension_id="$DEFAULT_EXTENSION_ID"
browser_dir="$HOME/Library/Application Support/Google/Chrome"
uninstall=false
while (( $# )); do
    case "$1" in
        --app) app="$2"; shift 2 ;;
        --extension-id) extension_id="$2"; shift 2 ;;
        # Chrome reads user-level hosts from its user data directory, so a
        # separate profile or Chrome for Testing needs its own registration.
        --browser-dir) browser_dir="$2"; shift 2 ;;
        --uninstall) uninstall=true; shift ;;
        -h|--help)
            printf 'Usage: install-browser.sh [--app PATH] [--extension-id ID] [--browser-dir DIR] [--uninstall]\n'
            exit 0
            ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
    esac
done

manifest="$browser_dir/NativeMessagingHosts/$HOST_NAME.json"
if [[ "$uninstall" == true ]]; then
    /bin/rm -f "$manifest"
    printf 'Removed %s\n' "$manifest"
    exit 0
fi
[[ "$extension_id" =~ ^[a-p]{32}$ ]] || { printf 'Invalid extension ID\n' >&2; exit 2; }
executable="$app/Contents/MacOS/macui"
[[ -x "$executable" ]] || { printf 'Missing %s\n' "$executable" >&2; exit 1; }

/bin/mkdir -p "$(/usr/bin/dirname "$manifest")"
/usr/bin/python3 - "$manifest" "$executable" "$extension_id" "$HOST_NAME" <<'PY'
import json, sys
path, executable, extension_id, name = sys.argv[1:]
with open(path + ".new", "w", encoding="utf-8") as handle:
    json.dump({
        "name": name,
        "description": "Machine Control browser provider",
        "path": executable,
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }, handle, indent=2)
    handle.write("\n")
PY
/bin/mv -f "$manifest.new" "$manifest"
printf 'Registered %s for extension %s\n' "$manifest" "$extension_id"
