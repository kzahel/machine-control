#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly LINUXVM="$REPO_DIR/bin/linuxvm"

find "$REPO_DIR/bin" "$REPO_DIR/scripts" "$REPO_DIR/providers" \
    "$REPO_DIR/guests" "$REPO_DIR/tests" -type f \
    \( -name '*.sh' -o -perm -u+x \) -print0 | \
    xargs -0 file | awk -F: '/shell script/ { print $1 }' | \
    while IFS= read -r script; do bash -n "$script"; done

python3 -m py_compile "$REPO_DIR/guests/ubuntu/ui/linuxui.py"
swiftc -typecheck "$REPO_DIR/providers/utm-macos/host-control.swift"
swiftc -typecheck "$REPO_DIR/providers/utm-macos/normalize-screenshot.swift"

help_output="$("$LINUXVM" help)"
[[ "$help_output" == *'gui-launch'* ]]
"$LINUXVM" doctor

artifact_dir="$REPO_DIR/.artifacts/smoke"
mkdir -p "$artifact_dir"
"$LINUXVM" screenshot "$artifact_dir/guest.png" >/dev/null
test -s "$artifact_dir/guest.png"

completion="$($LINUXVM exec -- /usr/bin/bash -lc \
    'printf "start:"; sleep 2; printf "finish"')"
test "$completion" = 'start:finish'

desktop_user="$($LINUXVM desktop-user)"
user_id="$($LINUXVM user-exec -- /usr/bin/id -un)"
test "$desktop_user" = "$user_id"

gui_unit="$("$LINUXVM" gui-launch -- /usr/bin/bash -lc \
    'test -n "$WAYLAND_DISPLAY" -o -n "$DISPLAY"; sleep 120')"
[[ "$gui_unit" =~ ^linuxvm-gui-[0-9]+\.[0-9]+\.[0-9]+\.service$ ]]
"$LINUXVM" user-exec -- /usr/bin/systemctl --user is-active "$gui_unit" >/dev/null
test "$("$LINUXVM" user-exec -- /usr/bin/systemctl --user show \
    --property=ExitType --value "$gui_unit")" = 'cgroup'
"$LINUXVM" user-exec -- /usr/bin/systemctl --user stop "$gui_unit"

ui_health="$($LINUXVM ui health)"
jq -e '.atspiAvailable == true and .applicationCount > 0' \
    <<<"$ui_health" >/dev/null
"$LINUXVM" ui apps >/dev/null
"$LINUXVM" ui tree --app gnome-shell --depth 4 --limit 100 >/dev/null

local_probe="$(mktemp /tmp/linuxvm-push.XXXXXX)"
pulled_probe="$(mktemp /tmp/linuxvm-pull.XXXXXX)"
printf 'linuxvm-file-roundtrip\n' >"$local_probe"
remote_probe="/var/tmp/linuxvm-file-roundtrip.$$"
"$LINUXVM" push "$local_probe" "$remote_probe"
"$LINUXVM" pull "$remote_probe" "$pulled_probe" >/dev/null
cmp "$local_probe" "$pulled_probe"
"$LINUXVM" exec -- /usr/bin/rm -f "$remote_probe"
rm -f "$local_probe" "$pulled_probe"

printf 'LinuxVM smoke test passed; screenshot: %s\n' "$artifact_dir/guest.png"
