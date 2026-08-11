#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly TESTBED_DIR="${MACVM_TESTBED_DIR:-$REPO_DIR/platforms/macos}"
readonly FIXTURE_ID='org.machine-control.fixture'
readonly TEMP_DIR="$(/usr/bin/mktemp -d /tmp/machine-control-macos-visual.XXXXXX)"
export MACVM_FORBID_OUTER_UI=true

guest_artifacts=()

fail() {
    printf 'macOS visual fallback failed: %s\n' "$*" >&2
    exit 1
}

control() {
    local placement="$1" request="$2"
    case "$placement" in
        remote) "$TESTBED_DIR/bin/macvm" control "$request" ;;
        local) "$TESTBED_DIR/bin/macvm" control-local "$request" ;;
        *) fail "unknown placement $placement" ;;
    esac
}

fixture_state() {
    "$TESTBED_DIR/bin/macvm" fixture-state
}

cleanup() {
    local path
    control remote "$(jq -nc --arg target "$FIXTURE_ID" \
        '{operation:"application.terminate",target:$target}')" \
        >/dev/null 2>&1 || true
    for path in "${guest_artifacts[@]}"; do
        "$TESTBED_DIR/bin/macvm" exec /bin/rm -f "$path" >/dev/null 2>&1 || true
    done
    /bin/rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

require_accepted() {
    local result="$1" label="$2"
    jq -e '.schema == "machine-control/v0" and .accepted == true and
           .hostInterference == "none"' >/dev/null <<<"$result" || {
        jq . <<<"$result" >&2 || true
        fail "$label was not accepted as target-resident"
    }
}

wait_for_fixture() {
    local expression="$1" label="$2" state
    for _ in {1..20}; do
        state="$(fixture_state 2>/dev/null || true)"
        if jq -e "$expression" >/dev/null 2>&1 <<<"$state"; then
            printf '%s\n' "$state"
            return 0
        fi
        sleep 0.1
    done
    fail "fixture oracle did not record $label"
}

run_display_capture() {
    local placement="$1" result guest_path local_path width height image_width image_height
    result="$(control "$placement" '{"operation":"capture","scope":"display"}')"
    require_accepted "$result" "$placement full-display capture"
    jq -e '.actualRoute == "guest.user/macos.quartz" and
           .fidelity == "full_display" and
           .coordinateSpace == "display_pixels" and
           .data.inputCoordinateSpace == "global_display_points" and
           .data.display.scaleX > 0 and .data.display.scaleY > 0' \
        >/dev/null <<<"$result" || fail "$placement display metadata was incomplete"
    guest_path="$(jq -er '.data.artifactPath' <<<"$result")"
    guest_artifacts+=("$guest_path")
    local_path="$TEMP_DIR/$placement-display.png"
    "$TESTBED_DIR/bin/macvm" artifact-fetch "$guest_path" "$local_path" >/dev/null
    width="$(jq -r '.data.display.pixelWidth' <<<"$result")"
    height="$(jq -r '.data.display.pixelHeight' <<<"$result")"
    image_width="$(/usr/bin/sips -g pixelWidth "$local_path" | awk '/pixelWidth/ {print $2}')"
    image_height="$(/usr/bin/sips -g pixelHeight "$local_path" | awk '/pixelHeight/ {print $2}')"
    [[ "$image_width" == "$width" && "$image_height" == "$height" ]] \
        || fail "$placement PNG dimensions disagreed with display metadata"
}

run_input_surface() {
    local placement="$1" state x y x1 x2 before_move before_down before_drag
    local before_up before_scroll result
    state="$(fixture_state)"
    x="$(jq '.surfaceBounds.x + (.surfaceBounds.width / 2) | floor' <<<"$state")"
    y="$(jq '.surfaceBounds.y + (.surfaceBounds.height / 2) | floor' <<<"$state")"
    x1="$(jq '.surfaceBounds.x + 40 | floor' <<<"$state")"
    x2="$(jq '.surfaceBounds.x + .surfaceBounds.width - 40 | floor' <<<"$state")"
    before_move="$(jq '.mouseMoveCount' <<<"$state")"
    before_down="$(jq '.mouseDownCount' <<<"$state")"
    before_drag="$(jq '.mouseDragCount' <<<"$state")"
    before_up="$(jq '.mouseUpCount' <<<"$state")"
    before_scroll="$(jq '.scrollEventCount' <<<"$state")"

    for result in \
        "$(control "$placement" "$(jq -nc --arg target "$FIXTURE_ID" \
            --argjson x "$x" --argjson y "$y" \
            '{operation:"input.move",target:$target,x:$x,y:$y,
              coordinateSpace:"global_display_points"}')")" \
        "$(control "$placement" "$(jq -nc --arg target "$FIXTURE_ID" \
            --argjson x "$x" --argjson y "$y" \
            '{operation:"input.click",target:$target,x:$x,y:$y,
              coordinateSpace:"global_display_points"}')")" \
        "$(control "$placement" "$(jq -nc --arg target "$FIXTURE_ID" \
            --argjson x "$x1" --argjson y "$y" --argjson x2 "$x2" \
            '{operation:"input.drag",target:$target,x:$x,y:$y,x2:$x2,y2:$y,
              coordinateSpace:"global_display_points"}')")" \
        "$(control "$placement" "$(jq -nc --arg target "$FIXTURE_ID" \
            --argjson x "$x" --argjson y "$y" \
            '{operation:"input.move",target:$target,x:$x,y:$y}')")" \
        "$(control "$placement" "$(jq -nc --arg target "$FIXTURE_ID" \
            '{operation:"input.scroll",target:$target,deltaY:80}')")"; do
        require_accepted "$result" "$placement visual input"
        jq -e '.actualRoute == "guest.user/macos.coregraphics" and
               .delivery == "confirmed"' >/dev/null <<<"$result" \
            || fail "$placement visual input used the wrong route"
    done

    wait_for_fixture ".mouseMoveCount > $before_move and
        .mouseDownCount >= ($before_down + 2) and
        .mouseDragCount > $before_drag and
        .mouseUpCount >= ($before_up + 2) and
        .scrollEventCount > $before_scroll and .scrollDeltaY != 0" \
        "$placement move, click, drag, and scroll effects" >/dev/null
}

[[ -x "$TESTBED_DIR/bin/macvm" ]] || fail "missing macvm-testbed at $TESTBED_DIR"
command -v jq >/dev/null || fail 'jq is required'

# Prove the fail-closed boundary before exercising the accepted routes.
if "$TESTBED_DIR/bin/macvm" screenshot >/dev/null 2>&1; then
    fail 'outer screenshot was available during acceptance'
fi

"$TESTBED_DIR/bin/macvm" deploy-fixture >/dev/null
control remote "$(jq -nc --arg target "$FIXTURE_ID" \
    '{operation:"application.terminate",target:$target}')" >/dev/null 2>&1 || true
launch="$(control remote "$(jq -nc --arg app "$FIXTURE_ID" \
    '{operation:"application.launch",applicationId:$app}')")"
require_accepted "$launch" 'fixture launch'
wait_for_fixture '.surfaceBounds.width > 0 and .surfaceBounds.height > 0' \
    'visual surface geometry' >/dev/null

snapshot="$(control remote "$(jq -nc --arg target "$FIXTURE_ID" \
    '{operation:"snapshot",target:$target,maxDepth:12,maxElements:160}')")"
require_accepted "$snapshot" 'fixture semantic snapshot'
jq -e '[.data.elements[] | select(.identifier == "fixture.visual-surface")] |
       length == 0' \
    >/dev/null <<<"$snapshot" \
    || fail 'custom surface unexpectedly exposed a semantic control'

host_before="$($TESTBED_DIR/bin/macvm host-state)"
run_display_capture remote
run_display_capture local
run_input_surface remote
run_input_surface local
host_after="$($TESTBED_DIR/bin/macvm host-state)"
[[ "$(jq -S . <<<"$host_before")" == "$(jq -S . <<<"$host_after")" ]] \
    || fail 'resident operations changed the host cursor or frontmost application'

unsupported="$(control remote "$(jq -nc --arg target "$FIXTURE_ID" \
    '{operation:"input.drag",provider:"cua",target:$target,
      x:10,y:10,x2:20,y2:20}')")"
jq -e '.accepted == false and .actualRoute == "guest.user/macos.cua" and
       .errorCode == "provider_unsupported" and .fallbackUsed == false' \
    >/dev/null <<<"$unsupported" || fail 'explicit Cua drag did not fail closed'

unsupported="$(control remote \
    '{"operation":"capture","scope":"display","provider":"cua"}')"
jq -e '.accepted == false and .actualRoute == "guest.user/macos.cua" and
       .errorCode == "provider_unsupported" and .fallbackUsed == false' \
    >/dev/null <<<"$unsupported" || fail 'explicit Cua display capture did not fail closed'

printf 'macOS Aqua visual fallback passed (remote and local).\n'
