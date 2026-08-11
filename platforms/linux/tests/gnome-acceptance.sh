#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly LINUXVM="$REPO_DIR/bin/linuxvm"

files_unit=""
settings_unit=""
dialog_unit=""
polkit_unit=""
browser_unit=""
a11y_original=""
notification_id=""

control() {
    "$LINUXVM" control "$1"
}

stage() {
    printf '[gnome-acceptance] %s\n' "$1"
}

stop_unit() {
    local unit="${1:-}"
    [[ -n "$unit" ]] || return 0
    "$LINUXVM" user-exec -- /usr/bin/systemctl --user stop "$unit" \
        >/dev/null 2>&1 || true
}

cleanup() {
    control '{"operation":"input.key","key":"escape"}' >/dev/null 2>&1 || true
    control '{"operation":"input.key","key":"escape"}' >/dev/null 2>&1 || true
    "$LINUXVM" fixture stop >/dev/null 2>&1 || true
    "$LINUXVM" fixture qt stop >/dev/null 2>&1 || true
    "$LINUXVM" fixture browser stop >/dev/null 2>&1 || true
    stop_unit "$files_unit"
    stop_unit "$settings_unit"
    stop_unit "$dialog_unit"
    stop_unit "$polkit_unit"
    stop_unit "$browser_unit"
    if [[ "$notification_id" =~ ^[0-9]+$ ]]; then
        "$LINUXVM" user-exec -- /usr/bin/gdbus call --session \
            --dest org.freedesktop.Notifications \
            --object-path /org/freedesktop/Notifications \
            --method org.freedesktop.Notifications.CloseNotification \
            "$notification_id" >/dev/null 2>&1 || true
    fi
    if [[ -n "$a11y_original" ]]; then
        "$LINUXVM" user-exec -- /usr/bin/gsettings set \
            org.gnome.desktop.a11y always-show-universal-access-status \
            "$a11y_original" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

stage 'verify candidate guard and resident health'
guard_status="$($LINUXVM guard-status)"
jq -e '.mutationTargetVerified == true and .outerUIForbidden == true' \
    <<<"$guard_status" >/dev/null
"$LINUXVM" doctor

# GNOME Shell overview, dock, top bar, and notification surfaces.
stage 'exercise GNOME Shell overview, dock, top bar, and notifications'
control '{"operation":"input.key","key":"escape"}' >/dev/null
control '{"operation":"input.key","key":"escape"}' >/dev/null
control '{"operation":"input.key","key":"super"}' >/dev/null
sleep 1
stage 'observe overview and dock semantics'
overview="$(control \
    '{"operation":"snapshot","target":"gnome-shell","maxDepth":14,"maxElements":900}')"
jq -e '
  ([.data.elements[].label] | index("Overview")) != null and
  ([.data.elements[].label] | index("Show Apps")) != null and
  ([.data.elements[].label] | index("Files")) != null
' <<<"$overview" >/dev/null
control '{"operation":"input.key","key":"escape"}' >/dev/null

stage 'observe GNOME top bar semantics'
shell="$(control \
    '{"operation":"snapshot","target":"gnome-shell","maxDepth":12,"maxElements":600}')"
jq -e '
  ([.data.elements[].label] | index("Activities")) != null and
  ([.data.elements[].label] | index("Keyboard")) != null and
  ([.data.elements[].label] | index("System")) != null
' <<<"$shell" >/dev/null

stage 'observe notification semantics'
notification_id="$("$LINUXVM" user-exec -- /usr/bin/notify-send \
    --print-id --urgency=normal \
    --expire-time=120000 'Machine Control Acceptance' \
    'Target-native GNOME notification')"
clock_x="$(jq '[.data.elements[] |
    select(.role == "label" and .bounds.y == 0 and
           .bounds.height > 0 and .bounds.x > 400 and .bounds.x < 900)][0] |
    .bounds.x + (.bounds.width / 2 | floor)' <<<"$shell")"
control "$(jq -nc --argjson x "$clock_x" \
    '{operation:"input.click",x:$x,y:16}')" >/dev/null
sleep 3
notification="$(control \
    '{"operation":"snapshot","target":"gnome-shell","query":"Machine Control Acceptance","maxDepth":20,"maxElements":900}')"
jq -e '.data.elements | any(.label == "Machine Control Acceptance")' \
    <<<"$notification" >/dev/null
"$LINUXVM" user-exec -- /usr/bin/gdbus call --session \
    --dest org.freedesktop.Notifications \
    --object-path /org/freedesktop/Notifications \
    --method org.freedesktop.Notifications.CloseNotification \
    "$notification_id" >/dev/null
notification_id=""
control '{"operation":"input.key","key":"escape"}' >/dev/null

# Files exposes a rich GTK4 application/window/sidebar tree.
stage 'exercise Files semantics and lifecycle'
files="$(control \
    '{"operation":"application.launch","command":["/usr/bin/nautilus","--new-window"],"expectTarget":"org.gnome.Nautilus","timeoutSeconds":12}')"
jq -e '.accepted == true and .effect == "application_observed"' \
    <<<"$files" >/dev/null
files_unit="$(jq -r '.data.unit' <<<"$files")"
files_tree="$(control \
    '{"operation":"snapshot","target":"org.gnome.Nautilus","maxDepth":14,"maxElements":800}')"
jq -e '
  ([.data.elements[].label] | index("Home")) != null and
  ([.data.elements[].label] | index("Sidebar")) != null
' <<<"$files_tree" >/dev/null
control "$(jq -nc --arg unit "$files_unit" \
    '{operation:"application.terminate",unit:$unit}')" >/dev/null
files_unit=""

# Settings has useful semantics but zeroed GTK4 element coordinates on this
# profile. Maximize its known 1280x800 appliance surface before visual input,
# prove the gsettings effect independently, and restore it immediately.
stage 'exercise Settings semantics, capture, and visual fallback'
control '{"operation":"application.terminate","target":"gnome-control-center"}' \
    >/dev/null 2>&1 || true
settings="$(control \
    '{"operation":"application.launch","command":["/usr/bin/gnome-control-center","universal-access"],"expectTarget":"gnome-control-center","timeoutSeconds":12}')"
settings_unit="$(jq -r '.data.unit' <<<"$settings")"
jq -e '.accepted == true and .effect == "application_observed"' \
    <<<"$settings" >/dev/null
control \
    '{"operation":"application.activate","desktopId":"org.gnome.Settings","target":"gnome-control-center","timeoutSeconds":12}' \
    >/dev/null
control '{"operation":"input.key","key":"alt+f10"}' >/dev/null
sleep 1
settings_tree="$(control \
    '{"operation":"snapshot","target":"gnome-control-center","maxDepth":20,"maxElements":1200}')"
jq -e '
  ([.data.elements[].label] | index("Accessibility")) != null and
  ([.data.elements[].label] | index("Always Show Accessibility Menu")) != null and
  ([.data.elements[].label] | index("Seeing")) != null
' <<<"$settings_tree" >/dev/null
settings_capture="$(control \
    '{"operation":"capture","target":"display"}')"
jq -e '.accepted == true and .data.artifact.width == 1280 and
       .data.artifact.height == 800' <<<"$settings_capture" >/dev/null
a11y_original="$($LINUXVM user-exec -- /usr/bin/gsettings get \
    org.gnome.desktop.a11y always-show-universal-access-status)"
control '{"operation":"input.click","x":1064,"y":128}' >/dev/null
sleep 1
a11y_changed="$($LINUXVM user-exec -- /usr/bin/gsettings get \
    org.gnome.desktop.a11y always-show-universal-access-status)"
test "$a11y_changed" != "$a11y_original"
control '{"operation":"input.click","x":1064,"y":128}' >/dev/null
sleep 1
test "$($LINUXVM user-exec -- /usr/bin/gsettings get \
    org.gnome.desktop.a11y always-show-universal-access-status)" = \
    "$a11y_original"

# A regular transient file chooser is semantic and dismissible in-target.
stage 'exercise a transient file chooser'
dialog="$(control \
    '{"operation":"application.launch","command":["/usr/bin/zenity","--file-selection","--title=Machine Control File Chooser"],"expectTarget":"zenity","timeoutSeconds":12}')"
dialog_unit="$(jq -r '.data.unit' <<<"$dialog")"
dialog_tree="$(control \
    '{"operation":"snapshot","target":"zenity","maxDepth":16,"maxElements":800}')"
jq -e '.data.elements | any(.label == "Cancel")' <<<"$dialog_tree" >/dev/null
control '{"operation":"input.key","key":"escape"}' >/dev/null
sleep 1
test "$($LINUXVM user-exec -- /usr/bin/systemctl --user is-active \
    "$dialog_unit" 2>/dev/null || true)" != active
dialog_unit=""

# Polkit is a separate authorization UI. Detect it and prove secret-free
# cancellation; root administration remains the explicit qemu-ga channel.
stage 'exercise a polkit authorization prompt'
polkit="$(control \
    '{"operation":"application.launch","command":["/usr/bin/pkexec","/usr/bin/true"]}')"
polkit_unit="$(jq -r '.data.unit' <<<"$polkit")"
sleep 1
authentication="$(control \
    '{"operation":"snapshot","query":"Authentication","maxDepth":14,"maxElements":900}')"
jq -e '.data.elements | any(.label == "Authentication Required")' \
    <<<"$authentication" >/dev/null
authenticate="$(control \
    '{"operation":"snapshot","query":"Authenticate","maxDepth":14,"maxElements":900}')"
jq -e '.data.elements | any(.label == "Authenticate")' \
    <<<"$authenticate" >/dev/null
control '{"operation":"input.key","key":"escape"}' >/dev/null
sleep 1
test "$($LINUXVM user-exec -- /usr/bin/systemctl --user is-active \
    "$polkit_unit" 2>/dev/null || true)" != active
polkit_unit=""

# Qt/XWayland publishes native semantics after its explicit accessibility
# profile is enabled. Unnamed native action slots are accepted only when the
# deterministic effect oracle changes.
stage 'exercise Qt semantics and independent effect observation'
"$LINUXVM" fixture qt reset
sleep 1
qt_snapshot="$(control \
    '{"operation":"snapshot","target":"machine-control-qt-fixture","maxDepth":16,"maxElements":900}')"
qt_reference="$(jq -r '.data.elements[] |
    select(.label == "Qt Semantic Increment") | .reference' \
    <<<"$qt_snapshot")"
qt_text_reference="$(jq -r '.data.elements[] |
    select(.label == "Qt Fixture Text") | .reference' \
    <<<"$qt_snapshot")"
control "$(jq -nc --arg reference "$qt_text_reference" \
    --arg value 'Qt semantic value' \
    '{operation:"set_value",reference:$reference,value:$value}')" >/dev/null
control "$(jq -nc --arg reference "$qt_reference" \
    '{operation:"action",reference:$reference,action:"press"}')" >/dev/null
sleep 1
jq -e '.semanticPresses == 1 and .text == "Qt semantic value"' \
    <<<"$($LINUXVM fixture qt state)" >/dev/null
"$LINUXVM" fixture qt stop

# Chromium supplies browser semantics for grounding and the resident virtual
# HID fallback for controls whose AT-SPI action names are incomplete.
stage 'exercise Chromium semantics, Unicode input, and visual fallback'
"$LINUXVM" fixture browser reset
home="$($LINUXVM exec -- /usr/bin/bash -lc \
    'user=$(loginctl list-sessions --no-legend | awk '\''$6 == "active" {print $3; exit}'\''); getent passwd "$user" | cut -d: -f6')"
browser_request="$(jq -nc --arg profile \
    "$home/.cache/linuxvm-testbed/chromium-acceptance-profile" '
    {operation:"application.launch",command:[
      "/snap/bin/chromium","--force-renderer-accessibility","--no-first-run",
      "--disable-default-apps",("--user-data-dir=" + $profile),
      "http://127.0.0.1:8765/"
    ],expectTarget:"Chromium",timeoutSeconds:20}')"
browser="$(control "$browser_request")"
browser_unit="$(jq -r '.data.unit' <<<"$browser")"
jq -e '.accepted == true and .effect == "application_observed"' \
    <<<"$browser" >/dev/null
browser_tree="$(control \
    '{"operation":"snapshot","target":"Chromium","query":"Browser","maxDepth":20,"maxElements":1400}')"
button_reference="$(jq -r '.data.elements[] |
    select(.label == "Browser Semantic Increment") | .reference' \
    <<<"$browser_tree")"
control "$(jq -nc --arg reference "$button_reference" \
    '{operation:"action",reference:$reference,action:"press"}')" >/dev/null
sleep 1
jq -e '.semanticPresses == 1' \
    <<<"$($LINUXVM fixture browser state)" >/dev/null

text_reference="$(jq -r '.data.elements[] |
    select(.label == "Browser Fixture Text") | .reference' \
    <<<"$browser_tree")"
control "$(jq -nc --arg reference "$text_reference" \
    '{operation:"focus",reference:$reference}')" >/dev/null
control '{"operation":"input.text","text":"Browser 世界"}' >/dev/null
canvas_x="$(jq '.data.elements[] |
    select(.label == "Browser Visual Canvas") |
    .bounds.x + (.bounds.width / 2 | floor)' <<<"$browser_tree")"
canvas_y="$(jq '.data.elements[] |
    select(.label == "Browser Visual Canvas") |
    .bounds.y + (.bounds.height / 2 | floor)' <<<"$browser_tree")"
control "$(jq -nc --argjson x "$canvas_x" --argjson y "$canvas_y" \
    '{operation:"input.click",x:$x,y:$y}')" >/dev/null
sleep 1
browser_state="$($LINUXVM fixture browser state)"
jq -e '.text == "Browser 世界" and .visualClicks == 1' \
    <<<"$browser_state" >/dev/null

cleanup
trap - EXIT
printf 'GNOME Wayland system and framework acceptance passed.\n'
