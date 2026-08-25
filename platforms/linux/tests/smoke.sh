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
python3 -m py_compile "$REPO_DIR/guests/ubuntu/ui/linuxcontrol.py"
python3 -m py_compile "$REPO_DIR/guests/ubuntu/input/linuxinputd.py"
python3 -m py_compile \
    "$REPO_DIR/guests/ubuntu/fixtures/control_fixture.py"
python3 -m py_compile \
    "$REPO_DIR/guests/ubuntu/fixtures/qt_fixture.py"
python3 -m py_compile \
    "$REPO_DIR/guests/ubuntu/fixtures/browser_fixture.py"
if command -v swiftc >/dev/null 2>&1; then
    swiftc -typecheck "$REPO_DIR/providers/utm-macos/host-control.swift"
    swiftc -typecheck "$REPO_DIR/providers/utm-macos/normalize-screenshot.swift"
elif [[ "$(uname -s)" == Darwin ]]; then
    printf 'swiftc is required to validate the macOS UTM provider.\n' >&2
    exit 1
fi

help_output="$("$LINUXVM" help)"
[[ "$help_output" == *'gui-launch'* ]]
[[ "$help_output" == *'deploy-resident'* ]]
[[ "$help_output" == *'artifact ID'* ]]
[[ "$help_output" == *'fixture [gtk|qt|browser] ACTION'* ]]
guard_status="$("$LINUXVM" guard-status)"
jq -e '.mutationGuardRequired == false or
       .mutationTargetVerified == true' <<<"$guard_status" >/dev/null
for command in screenshot click drag type key scan window-info; do
    if LINUXVM_FORBID_OUTER_UI=true "$LINUXVM" "$command" \
            >/dev/null 2>&1; then
        printf 'Outer-UI guard allowed linuxvm %s\n' "$command" >&2
        exit 1
    fi
done
LINUXVM_FORBID_OUTER_UI=true "$LINUXVM" status >/dev/null
LINUXVM_FORBID_OUTER_UI=true "$LINUXVM" host-state >/dev/null
"$LINUXVM" doctor

remote_status="$($LINUXVM control '{"operation":"status"}')"
local_status="$($LINUXVM control-local '{"operation":"status"}')"
jq -e '.schema == "machine-control/v0" and .accepted == true and
       .actualRoute == "guest.user/linux.atspi" and
       .data.captureState == "ready" and .data.inputState == "ready" and
       .hostInterference == "none"' <<<"$remote_status" >/dev/null
test "$(jq -r '.generation' <<<"$remote_status")" = \
    "$(jq -r '.generation' <<<"$local_status")"

lifecycle_launch="$($LINUXVM control \
    '{"operation":"application.launch","command":["/usr/bin/zenity","--info","--title=Lifecycle Fixture","--text=Resident lifecycle fixture"],"expectTarget":"zenity"}')"
jq -e '.accepted == true and .actualRoute ==
       "guest.user/linux.systemd-atspi" and
       .effect == "application_observed"' <<<"$lifecycle_launch" >/dev/null
lifecycle_unit="$(jq -r '.data.unit' <<<"$lifecycle_launch")"
lifecycle_stop="$($LINUXVM control "$(jq -nc --arg unit "$lifecycle_unit" \
    '{operation:"application.terminate",unit:$unit}')")"
jq -e '.accepted == true and .effect == "application_terminated"' \
    <<<"$lifecycle_stop" >/dev/null

capture="$($LINUXVM control '{"operation":"capture","target":"display"}')"
jq -e '.accepted == true and
       .actualRoute == "guest.user/gnome-screenshot" and
       .fidelity == "pixel_full_display" and
       .data.artifact.mediaType == "image/png" and
       .data.artifact.width > 0 and .data.artifact.height > 0' \
    <<<"$capture" >/dev/null
capture_id="$(jq -r '.data.artifact.id' <<<"$capture")"
capture_path="$($LINUXVM artifact "$capture_id")"
test -s "$capture_path"
test "$(shasum -a 256 "$capture_path" | awk '{print $1}')" = \
    "$(jq -r '.data.artifact.sha256' <<<"$capture")"

cleanup_fixture() {
    "$LINUXVM" fixture stop >/dev/null 2>&1 || true
}
trap cleanup_fixture EXIT
"$LINUXVM" fixture reset
for _ in {1..30}; do
    if fixture_state="$($LINUXVM fixture state 2>/dev/null)" &&
            jq -e '.lastEvent == "ready"' >/dev/null <<<"$fixture_state"; then
        break
    fi
    sleep 0.2
done
jq -e '.lastEvent == "ready"' >/dev/null <<<"$fixture_state"

semantic_snapshot="$($LINUXVM control \
    '{"operation":"snapshot","target":"machine-control-fixture","query":"Semantic Increment"}')"
semantic_reference="$(jq -r \
    '.data.elements[] | select(.label == "Semantic Increment") | .reference' \
    <<<"$semantic_snapshot")"
semantic_action="$(jq -nc --arg reference "$semantic_reference" \
    '{operation:"action",reference:$reference,action:"press"}')"
"$LINUXVM" control "$semantic_action" >/dev/null
jq -e '.semanticPresses == 1' <<<"$($LINUXVM fixture state)" >/dev/null

fixture_snapshot="$($LINUXVM control \
    '{"operation":"snapshot","target":"machine-control-fixture"}')"
canvas_x="$(jq \
    '.data.elements[] | select(.label == "Visual Canvas") |
     .bounds.x + (.bounds.width / 2 | floor)' <<<"$fixture_snapshot")"
canvas_y="$(jq \
    '.data.elements[] | select(.label == "Visual Canvas") |
     .bounds.y + (.bounds.height / 2 | floor)' <<<"$fixture_snapshot")"
text_x="$(jq \
    '.data.elements[] | select(.label == "Fixture Text") |
     .bounds.x + (.bounds.width / 2 | floor)' <<<"$fixture_snapshot")"
text_y="$(jq \
    '.data.elements[] | select(.label == "Fixture Text") |
     .bounds.y + (.bounds.height / 2 | floor)' <<<"$fixture_snapshot")"

host_before="$($LINUXVM host-state | jq -cS .)"
"$LINUXVM" control "$(jq -nc --argjson x "$canvas_x" --argjson y "$canvas_y" \
    '{operation:"input.click",x:$x,y:$y,button:"left"}')" >/dev/null
host_after="$($LINUXVM host-state | jq -cS .)"
test "$host_before" = "$host_after"
jq -e '.visualClicks == 1 and .dragReleases == 1' \
    <<<"$($LINUXVM fixture state)" >/dev/null

"$LINUXVM" control-local \
    "$(jq -nc --argjson x "$text_x" --argjson y "$text_y" \
    '{operation:"input.click",x:$x,y:$y}')" >/dev/null
fixture_text='Hello, 世界 👋'
"$LINUXVM" control "$(jq -nc --arg text "$fixture_text" \
    '{operation:"input.text",text:$text}')" >/dev/null
"$LINUXVM" control '{"operation":"input.key","key":"enter"}' >/dev/null
jq -e --arg text "$fixture_text" \
    '.text == $text and .lastKey == "Return"' \
    <<<"$($LINUXVM fixture state)" >/dev/null

"$LINUXVM" control "$(jq -nc \
    --argjson x1 "$((canvas_x - 80))" --argjson y1 "$canvas_y" \
    --argjson x2 "$((canvas_x + 80))" --argjson y2 "$((canvas_y + 60))" \
    '{operation:"input.drag",x1:$x1,y1:$y1,x2:$x2,y2:$y2}')" >/dev/null
"$LINUXVM" control "$(jq -nc --argjson x "$canvas_x" --argjson y "$canvas_y" \
    '{operation:"input.scroll",x:$x,y:$y,dy:-2}')" >/dev/null
fixture_state="$($LINUXVM fixture state)"
jq -e '.dragReleases >= 2 and .scrollY != 0' <<<"$fixture_state" >/dev/null

window_capture="$($LINUXVM control \
    '{"operation":"capture","target":"active_window"}')"
jq -e '.accepted == true and .fidelity == "pixel_exact_active_window" and
       .data.artifact.width < 1280 and .data.artifact.height < 800' \
    <<<"$window_capture" >/dev/null
cleanup_fixture
trap - EXIT

artifact_message='outer screenshot prohibited'
if [[ "$(jq -r '.outerUIForbidden' <<<"$guard_status")" == false ]]; then
    artifact_dir="$REPO_DIR/.artifacts/smoke"
    mkdir -p "$artifact_dir"
    "$LINUXVM" screenshot "$artifact_dir/guest.png" >/dev/null
    test -s "$artifact_dir/guest.png"
    artifact_message="screenshot: $artifact_dir/guest.png"
fi

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

printf 'LinuxVM smoke test passed; %s\n' "$artifact_message"
