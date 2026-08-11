#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly CLIENT="$REPO_DIR/bin/machine-control"
readonly TARGET="${1:-}"

case "$TARGET" in
    windows|macos|linux) ;;
    *)
        printf 'Usage: live-desktop-conformance.sh windows|macos|linux\n' >&2
        exit 2
        ;;
esac

export WINVM_FORBID_OUTER_UI=true
export MACVM_FORBID_OUTER_UI=true
export LINUXVM_FORBID_OUTER_UI=true

temporary="$(mktemp -d "${TMPDIR:-/tmp}/machine-control-common.XXXXXX")"
artifact_output="$temporary/capture.png"
fixture_started=false
fixture_target=''
window_id=''
guest_artifact=''
artifact_handle=''

mc() {
    "$CLIENT" --target "$TARGET" "$@"
}

fail() {
    printf 'Common %s conformance failed: %s\n' "$TARGET" "$*" >&2
    exit 1
}

require_accepted() {
    local result="$1" label="$2"
    jq -e '.schema == "machine-control/v0" and .accepted == true and
        .hostInterference == "none"' <<<"$result" >/dev/null || {
        jq . <<<"$result" >&2 || true
        fail "$label was not accepted without host interference"
    }
}

cleanup() {
    set +e
    case "$TARGET" in
        windows)
            if [[ -n "$window_id" ]]; then
                mc desktop call "$(jq -cn --argjson window "$window_id" \
                    '{operation:"window.close",windowId:$window}')" \
                    >/dev/null 2>&1
            fi
            if [[ -n "$guest_artifact" ]]; then
                mc os -- "Remove-Item -LiteralPath \
                    \"\$env:ProgramData\\MachineControl\\artifacts\\$guest_artifact.png\" \
                    -Force -ErrorAction SilentlyContinue" >/dev/null 2>&1
            fi
            ;;
        macos)
            if [[ "$fixture_started" == true ]]; then
                mc desktop call "$(jq -cn --arg target "$fixture_target" \
                    '{operation:"application.terminate",target:$target}')" \
                    >/dev/null 2>&1
            fi
            if [[ -n "$guest_artifact" ]]; then
                mc os -- /bin/rm -f "$guest_artifact" >/dev/null 2>&1
            fi
            ;;
        linux)
            mc testbed -- fixture stop >/dev/null 2>&1
            if [[ -n "$guest_artifact" ]]; then
                mc os -- /usr/bin/rm -f "$guest_artifact" >/dev/null 2>&1
            fi
            ;;
    esac
    find "$temporary" -type f -delete 2>/dev/null || true
    find "$temporary" -depth -type d -empty -delete 2>/dev/null || true
}
trap cleanup EXIT

target_status="$(mc target status)"
jq -e '.accepted == true and .data.powerState == "running"' \
    <<<"$target_status" >/dev/null || fail 'target is not running'

doctor="$(mc target doctor)"
jq -e '.ready == true and .states.outer == "prohibited"' \
    <<<"$doctor" >/dev/null || fail 'doctor did not report guarded readiness'

remote_status="$(mc desktop status)"
local_status="$(mc desktop call-local '{"operation":"status"}')"
require_accepted "$remote_status" 'outside status'
require_accepted "$local_status" 'guest-local status'
remote_generation="$(jq -r '.generation' <<<"$remote_status")"
local_generation="$(jq -r '.generation' <<<"$local_status")"
[[ "$remote_generation" == "$local_generation" ]] ||
    fail 'local and outside generations differ'

capabilities="$(mc desktop capabilities)"
require_accepted "$capabilities" 'capabilities'

case "$TARGET" in
    windows)
        fixture_target='Machine Control Medium Fixture'
        mc os -- \
            '$ErrorActionPreference = "SilentlyContinue"; Get-Process machine-control-medium-fixture | Stop-Process -Force; Remove-Item "$env:LOCALAPPDATA\MachineControl\conformance\counter.json" -Force; exit 0' \
            >/dev/null
        launch="$(mc desktop application launch \
            --executable 'C:\ProgramData\MachineControl\runtime\fixtures\machine-control-medium-fixture.exe')"
        require_accepted "$launch" 'fixture launch'
        window_id="$(jq -er \
            '.data.windows[] | select(.visible == true) | .hwnd' \
            <<<"$launch" | head -n 1)" || fail 'launch returned no window'
        process_id="$(jq -er '.data.processId' <<<"$launch")"
        snapshot="$(mc desktop call "$(jq -cn \
            --argjson window "$window_id" --argjson process "$process_id" \
            '{operation:"snapshot",windowId:$window,processId:$process,
              query:"Increment counter",projection:"compact",
              maxDepth:10,maxElements:40}')")"
        button_label='Increment counter'
        ;;
    macos)
        fixture_target='org.machine-control.fixture'
        mc testbed -- deploy-fixture >/dev/null
        mc desktop call "$(jq -cn --arg target "$fixture_target" \
            '{operation:"application.terminate",target:$target}')" \
            >/dev/null 2>&1 || true
        launch="$(mc desktop application launch \
            --application-id "$fixture_target")"
        require_accepted "$launch" 'fixture launch'
        fixture_started=true
        snapshot="$(mc desktop snapshot --target "$fixture_target" \
            --query Increment --projection compact --max-depth 12 \
            --max-elements 80)"
        button_label='Increment'
        ;;
    linux)
        fixture_target='machine-control-fixture'
        mc testbed -- fixture reset >/dev/null
        fixture_started=true
        snapshot="$(mc desktop snapshot --target "$fixture_target" \
            --query 'Semantic Increment' --projection compact \
            --max-depth 12 --max-elements 80)"
        button_label='Semantic Increment'
        ;;
esac

require_accepted "$snapshot" 'semantic snapshot'
reference="$(jq -er --arg label "$button_label" \
    '.data.elements[] |
     select((.label // .name // .n // "") == $label) |
     (.reference // .r)' <<<"$snapshot" | head -n 1)" ||
    fail 'semantic snapshot returned no button reference'

action="$(mc desktop action --reference "$reference" --action press)"
require_accepted "$action" 'semantic button action'

effect_confirmed=false
for _ in {1..30}; do
    case "$TARGET" in
        windows)
            state="$(mc os -- \
                'if (Test-Path "$env:LOCALAPPDATA\MachineControl\conformance\counter.json") { Get-Content "$env:LOCALAPPDATA\MachineControl\conformance\counter.json" -Raw }' \
                2>/dev/null || true)"
            jq -e '.counter == 1' <<<"$state" >/dev/null 2>&1 &&
                effect_confirmed=true
            ;;
        macos)
            state="$(mc testbed -- fixture-state 2>/dev/null || true)"
            jq -e '.count == 1' <<<"$state" >/dev/null 2>&1 &&
                effect_confirmed=true
            ;;
        linux)
            state="$(mc testbed -- fixture state 2>/dev/null || true)"
            jq -e '.semanticPresses == 1' <<<"$state" >/dev/null 2>&1 &&
                effect_confirmed=true
            ;;
    esac
    [[ "$effect_confirmed" == true ]] && break
    sleep 0.1
done
[[ "$effect_confirmed" == true ]] || fail 'independent button effect was absent'

unicode_effect=unsupported_by_fixture
if [[ "$TARGET" == macos ]]; then
    text_snapshot="$(mc desktop snapshot --target "$fixture_target" \
        --projection compact --max-depth 12 --max-elements 120)"
    text_reference="$(jq -er \
        '.data.elements[] | select(.role == "AXTextField") | .reference' \
        <<<"$text_snapshot" | head -n 1)"
    mc desktop action --reference "$text_reference" --action focus >/dev/null
    mc desktop input text 'Hello, 世界' >/dev/null
    for _ in {1..30}; do
        state="$(mc testbed -- fixture-state 2>/dev/null || true)"
        if jq -e '.text == "Hello, 世界"' <<<"$state" >/dev/null 2>&1; then
            unicode_effect=confirmed
            break
        fi
        sleep 0.1
    done
elif [[ "$TARGET" == linux ]]; then
    text_snapshot="$(mc desktop snapshot --target "$fixture_target" \
        --query 'Fixture Text' --projection compact --max-depth 12 \
        --max-elements 40)"
    text_reference="$(jq -er \
        '.data.elements[] | select(.label == "Fixture Text") | .reference' \
        <<<"$text_snapshot" | head -n 1)"
    mc desktop action --reference "$text_reference" --action focus >/dev/null
    mc desktop input text 'Hello, 世界' >/dev/null
    mc desktop input key enter >/dev/null
    for _ in {1..30}; do
        state="$(mc testbed -- fixture state 2>/dev/null || true)"
        if jq -e '.text == "Hello, 世界"' <<<"$state" >/dev/null 2>&1; then
            unicode_effect=confirmed
            break
        fi
        sleep 0.1
    done
fi
if [[ "$TARGET" != windows && "$unicode_effect" != confirmed ]]; then
    fail 'Unicode input effect was absent'
fi

case "$TARGET" in
    windows)
        capture="$(mc desktop capture --scope window \
            --window-id "$window_id")"
        guest_artifact="$(jq -er '.data.artifactId' <<<"$capture")"
        ;;
    macos)
        capture="$(mc desktop capture --scope window \
            --target "$fixture_target")"
        guest_artifact="$(jq -er '.data.artifactPath' <<<"$capture")"
        ;;
    linux)
        capture="$(mc desktop capture --scope window \
            --target active_window)"
        guest_artifact="$(jq -er '.data.artifact.guestPath' <<<"$capture")"
        artifact_handle="$(jq -er '.data.artifact.id' <<<"$capture")"
        ;;
esac
require_accepted "$capture" 'target-native capture'
artifact_handle="${artifact_handle:-$guest_artifact}"
artifact="$(mc desktop artifact "$artifact_handle" "$artifact_output")"
jq -e '.accepted == true' <<<"$artifact" >/dev/null ||
    fail 'artifact fetch failed'
[[ -s "$artifact_output" ]] || fail 'fetched artifact is empty'
png_magic="$(od -An -tx1 -N8 "$artifact_output" | tr -d ' \n')"
[[ "$png_magic" == 89504e470d0a1a0a ]] ||
    fail 'fetched artifact is not PNG'

jq -cn \
    --arg target "$TARGET" \
    --arg profile "$(jq -r '.target.profile' <<<"$doctor")" \
    --arg status_route "$(jq -r '.actualRoute' <<<"$remote_status")" \
    --arg snapshot_route "$(jq -r '.actualRoute' <<<"$snapshot")" \
    --arg action_route "$(jq -r '.actualRoute' <<<"$action")" \
    --arg capture_route "$(jq -r '.actualRoute' <<<"$capture")" \
    --arg unicode_effect "$unicode_effect" \
    --argjson doctor_ms "$(jq '.adapter.elapsedMs' <<<"$doctor")" \
    --argjson snapshot_bytes "$(jq '.client.resultBytes' <<<"$snapshot")" \
    --argjson snapshot_ms "$(jq '.client.transportElapsedMs' <<<"$snapshot")" \
    --argjson action_ms "$(jq '.client.transportElapsedMs' <<<"$action")" \
    --argjson capture_ms "$(jq '.client.transportElapsedMs' <<<"$capture")" \
    --argjson artifact_bytes "$(wc -c <"$artifact_output" | tr -d ' ')" \
    '{
        schema:"machine-control-common-desktop-conformance/v0",
        target:$target,
        profile:$profile,
        passed:true,
        outerUIForbidden:true,
        localRemoteGenerationEqual:true,
        independentEffect:true,
        unicodeEffect:$unicode_effect,
        routes:{
            status:$status_route,
            snapshot:$snapshot_route,
            action:$action_route,
            capture:$capture_route
        },
        metrics:{
            doctorMs:$doctor_ms,
            snapshotResultBytes:$snapshot_bytes,
            snapshotTransportMs:$snapshot_ms,
            actionTransportMs:$action_ms,
            captureTransportMs:$capture_ms,
            artifactBytes:$artifact_bytes
        }
    }'
