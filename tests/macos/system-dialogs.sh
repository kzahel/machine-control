#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly TESTBED_DIR="${MACVM_TESTBED_DIR:-$REPO_DIR/platforms/macos}"
readonly FIXTURE_ID='org.machine-control.fixture'
export MACVM_FORBID_OUTER_UI=true

fail() {
    printf 'macOS system dialogs failed: %s\n' "$*" >&2
    exit 1
}

control() {
    local placement="$1" request="$2"
    case "$placement" in
        remote) "$TESTBED_DIR/bin/macvm" control "$request" ;;
        local) "$TESTBED_DIR/bin/macvm" control-local "$request" ;;
        *) fail "unknown placement: $placement" ;;
    esac
}

require_accepted() {
    local result="$1" label="$2"
    jq -e '.schema == "machine-control/v0" and .accepted == true and
           .hostInterference == "none"' >/dev/null <<<"$result" || {
        jq . <<<"$result" >&2 || true
        fail "$label was not accepted"
    }
}

fixture_state() { "$TESTBED_DIR/bin/macvm" fixture-state; }

reset_fixture_state() {
    "$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
        'root="$HOME/Library/Caches/machine-control-fixture";
         rm -f "$root/state.json" "$root/relaunch.pending"'
}

wait_for_state() {
    local expression="$1" label="$2" state
    for _ in {1..50}; do
        state="$(fixture_state 2>/dev/null || true)"
        if jq -e "$expression" >/dev/null 2>&1 <<<"$state"; then
            return 0
        fi
        sleep 0.1
    done
    fail "fixture oracle did not record $label"
}

press_named() {
    local placement="$1" target="$2" label="$3"
    local snapshot reference result
    snapshot="$(control "$placement" "$(jq -nc --arg target "$target" \
        --arg query "$label" \
        '{operation:"snapshot",target:$target,query:$query,
          maxDepth:20,maxElements:500,projection:"compact"}')")"
    require_accepted "$snapshot" "$label snapshot"
    reference="$(jq -er --arg label "$label" \
        '[.data.elements[] | select(.role == "AXButton" and
          .label == $label and .enabled == true and
          (.actions | index("AXPress")))][0].reference' <<<"$snapshot")" \
        || fail "button '$label' was unavailable"
    result="$(control "$placement" "$(jq -nc --arg reference "$reference" \
        '{operation:"action",reference:$reference,action:"press"}')")"
    require_accepted "$result" "$label press"
}

select_panel_item() {
    local placement="$1" item="$2" target_button="$3"
    local snapshot reference x y result
    snapshot="$(control "$placement" "$(jq -nc --arg target "$FIXTURE_ID" \
        --arg query "$item" \
        '{operation:"snapshot",target:$target,query:$query,
          maxDepth:24,maxElements:900,projection:"compact"}')")"
    require_accepted "$snapshot" "$item panel snapshot"
    reference="$(jq -er --arg item "$item" \
        '[.data.elements[] | select(.role == "AXTextField" and
          .value == $item and (.bounds.width // 0) > 0)][0].reference' \
        <<<"$snapshot")" || fail "panel item '$item' was unavailable"
    x="$(jq -er --arg reference "$reference" \
        '.data.elements[] | select(.reference == $reference) |
         (.bounds.x + (.bounds.width / 2) | floor)' <<<"$snapshot")"
    y="$(jq -er --arg reference "$reference" \
        '.data.elements[] | select(.reference == $reference) |
         (.bounds.y + (.bounds.height / 2) | floor)' <<<"$snapshot")"
    result="$(control "$placement" "$(jq -nc --arg target "$FIXTURE_ID" \
        --argjson x "$x" --argjson y "$y" \
        '{operation:"input.click",target:$target,provider:"macos-native",
          coordinateSpace:"global_display_points",x:$x,y:$y}')")"
    require_accepted "$result" "$item panel selection"
    press_named "$placement" "$FIXTURE_ID" "$target_button"
}

cleanup() {
    control remote "$(jq -nc --arg target "$FIXTURE_ID" \
        '{operation:"application.terminate",target:$target}')" \
        >/dev/null 2>&1 || true
    reset_fixture_state >/dev/null 2>&1 || true
    "$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
        'rm -rf "$HOME/Documents/MachineControlSurfaceCorpus"' \
        >/dev/null 2>&1 || true
}
trap cleanup EXIT

[[ -x "$TESTBED_DIR/bin/macvm" ]] || fail "missing macvm-testbed at $TESTBED_DIR"
command -v jq >/dev/null || fail 'jq is required'
if "$TESTBED_DIR/bin/macvm" screenshot >/dev/null 2>&1; then
    fail 'outer screenshot was available during system-dialog acceptance'
fi

"$TESTBED_DIR/bin/macvm" deploy-fixture >/dev/null
control remote "$(jq -nc --arg target "$FIXTURE_ID" \
    '{operation:"application.terminate",target:$target}')" \
    >/dev/null 2>&1 || true
reset_fixture_state
"$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
    'root="$HOME/Documents/MachineControlSurfaceCorpus";
     rm -rf "$root"; mkdir -p "$root/surface-folder";
     printf "%s\n" "machine-control surface input" > "$root/surface-input.txt"'
host_before="$($TESTBED_DIR/bin/macvm host-state)"

launch="$(control remote "$(jq -nc --arg app "$FIXTURE_ID" \
    '{operation:"application.launch",applicationId:$app}')")"
require_accepted "$launch" 'fixture launch'
wait_for_state '.surfaceEffect != null' 'initial surface state'

press_named remote "$FIXTURE_ID" 'Open File'
wait_for_state '.surfaceEvent == "open_file" and
                .surfaceEffect == "presented"' 'open panel presentation'
select_panel_item local 'surface-input.txt' Open
wait_for_state '.surfaceEvent == "open_file" and
                .surfaceEffect == "opened" and
                .selectedName == "surface-input.txt"' 'opened file effect'

press_named local "$FIXTURE_ID" 'Choose Folder'
wait_for_state '.surfaceEvent == "choose_folder" and
                .surfaceEffect == "presented"' 'folder panel presentation'
select_panel_item remote surface-folder Choose
wait_for_state '.surfaceEvent == "choose_folder" and
                .surfaceEffect == "chosen" and
                .selectedName == "surface-folder"' 'chosen folder effect'

press_named remote "$FIXTURE_ID" 'Save File'
wait_for_state '.surfaceEvent == "save_file" and
                .surfaceEffect == "presented"' 'save panel presentation'
press_named local "$FIXTURE_ID" Save
wait_for_state '.surfaceEvent == "save_file" and
                .surfaceEffect == "saved" and
                .selectedName == "surface-output.txt"' 'saved file effect'
"$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
    'path="$HOME/Documents/MachineControlSurfaceCorpus/surface-output.txt";
     value="$(cat "$path")"; test "$value" = "machine-control surface output"' \
    || fail 'saved file contents did not match the fixture oracle'

press_named local "$FIXTURE_ID" 'Nested Sheet'
wait_for_state '.surfaceEvent == "nested_sheet" and
                .surfaceEffect == "presented"' 'nested sheet presentation'
press_named remote "$FIXTURE_ID" Continue
wait_for_state '.surfaceEvent == "nested_sheet" and
                .surfaceEffect == "continued"' 'nested sheet effect'

press_named remote "$FIXTURE_ID" 'Relaunch Request'
wait_for_state '.surfaceEvent == "relaunch" and
                .surfaceEffect == "presented"' 'relaunch sheet presentation'
press_named local "$FIXTURE_ID" Relaunch
wait_for_state '.surfaceEffect == "relaunch_requested"' 'relaunch request effect'
sleep 1
launch="$(control local "$(jq -nc --arg app "$FIXTURE_ID" \
    '{operation:"application.launch",applicationId:$app}')")"
require_accepted "$launch" 'fixture relaunch'
wait_for_state '.surfaceEffect == "relaunch_completed"' 'completed relaunch effect'

host_after="$($TESTBED_DIR/bin/macvm host-state)"
[[ "$(jq -S . <<<"$host_before")" == "$(jq -S . <<<"$host_after")" ]] \
    || fail 'system dialogs changed the host cursor or frontmost application'

printf 'macOS native panels, nested sheets, and relaunch passed.\n'
