#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly TESTBED_DIR="${MACVM_TESTBED_DIR:-$REPO_DIR/../macvm-testbed}"
readonly SETTINGS_ID='com.apple.systempreferences'
readonly QUARANTINE_AGENT='CoreServicesUIAgent'
readonly INSTALLER_ID='Installer'
readonly SAFARI_ID='com.apple.Safari'
export MACVM_FORBID_OUTER_UI=true

fail() {
    printf 'macOS artifact workflows failed: %s\n' "$*" >&2
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

snapshot_for_button() {
    local placement="$1" target="$2" label="$3"
    control "$placement" "$(jq -nc --arg target "$target" \
        --arg query "$label" \
        '{operation:"snapshot",target:$target,query:$query,
          maxDepth:24,maxElements:900,projection:"compact"}')"
}

wait_for_button() {
    local placement="$1" target="$2" label="$3" snapshot
    for _ in {1..60}; do
        snapshot="$(snapshot_for_button "$placement" "$target" "$label" \
            2>/dev/null || true)"
        if jq -e --arg label "$label" \
            '.accepted == true and ([.data.elements[]? | select(
              .role == "AXButton" and .label == $label and
              .enabled == true and (.actions | index("AXPress")))] |
              length) == 1' >/dev/null 2>&1 <<<"$snapshot"; then
            printf '%s\n' "$snapshot"
            return 0
        fi
        sleep 0.2
    done
    fail "button '$label' was unavailable on $target"
}

press_named() {
    local placement="$1" target="$2" label="$3" mode="${4:-strict}"
    local snapshot reference result
    snapshot="$(wait_for_button "$placement" "$target" "$label")"
    reference="$(jq -er --arg label "$label" \
        '[.data.elements[] | select(.role == "AXButton" and
          .label == $label and .enabled == true and
          (.actions | index("AXPress")))][0].reference' <<<"$snapshot")"
    result="$(control "$placement" "$(jq -nc --arg reference "$reference" \
        '{operation:"action",reference:$reference,action:"press"}')")"
    if [[ "$mode" == observe-effect ]] && jq -e \
        '.accepted == false and .errorCode == "delivery_failed"' \
        >/dev/null 2>&1 <<<"$result"; then
        return 0
    fi
    require_accepted "$result" "$label press"
}

wait_for_application() {
    local name="$1" result
    for _ in {1..60}; do
        result="$(control remote '{"operation":"applications"}' \
            2>/dev/null || true)"
        if jq -e --arg name "$name" \
            '[.data.applications[]? | select(.name == $name)] | length == 1' \
            >/dev/null 2>&1 <<<"$result"; then
            return 0
        fi
        sleep 0.2
    done
    fail "application '$name' did not become observable"
}

wait_for_bundle_pid() {
    local bundle_id="$1" result pid
    for _ in {1..60}; do
        result="$(control remote '{"operation":"applications"}' \
            2>/dev/null || true)"
        pid="$(jq -r --arg bundle_id "$bundle_id" \
            '[.data.applications[]? | select(.bundleId == $bundle_id)][0]
             .processId // empty' <<<"$result")"
        if [[ -n "$pid" ]]; then
            printf '%s\n' "$pid"
            return 0
        fi
        sleep 0.2
    done
    fail "application bundle '$bundle_id' did not become observable"
}

wait_for_semantic_value() {
    local target="$1" value="$2" snapshot
    for _ in {1..60}; do
        snapshot="$(control remote "$(jq -nc --arg target "$target" \
            --arg query "$value" \
            '{operation:"snapshot",target:$target,query:$query,
              maxDepth:20,maxElements:600,projection:"compact"}')" \
            2>/dev/null || true)"
        if jq -e --arg value "$value" \
            '.accepted == true and ([.data.elements[]? | select(
              .value == $value or .label == $value)] | length) > 0' \
            >/dev/null 2>&1 <<<"$snapshot"; then
            return 0
        fi
        sleep 0.2
    done
    fail "semantic value '$value' was unavailable on $target"
}

authorize_sheet() {
    local requester="$1" context_id="$2" description="$3"
    local requirement="${4:-required}" result lease attempts=30
    [[ "$requirement" == optional ]] && attempts=5
    for ((attempt = 0; attempt < attempts; attempt++)); do
        result="$(control remote "$(jq -nc --arg requester "$requester" \
            --arg context_id "$context_id" \
            '{operation:"authorization.begin",expectedRequester:$requester,
              contextId:$context_id,timeoutMs:120000}')" \
            2>/dev/null || true)"
        if jq -e '.accepted == true' >/dev/null 2>&1 <<<"$result"; then
            break
        fi
        sleep 0.2
    done
    if [[ "$requirement" == optional ]] &&
            ! jq -e '.accepted == true' >/dev/null 2>&1 <<<"$result"; then
        return 1
    fi
    require_accepted "$result" "$description authorization lease"
    lease="$(jq -er '.data.leaseId' <<<"$result")"
    printf '\nEnter the guest administrator credential for %s.\n' \
        "$description" >&2
    result="$($TESTBED_DIR/bin/macvm authorization-submit "$lease")"
    require_accepted "$result" "$description authorization submission"
    jq -e '.delivery == "confirmed" and .effect == "confirmed" and
           .data.sheetDismissed == true' >/dev/null <<<"$result" \
        || { jq . <<<"$result" >&2; fail "$description authorization had no effect"; }
}

guest_cleanup() {
    "$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
        'root="$HOME/Library/Caches/machine-control-artifact-workflows";
         /usr/bin/killall -9 CoreServicesUIAgent 2>/dev/null || true;
         if test -f "$root/server.pid"; then
             kill "$(cat "$root/server.pid")" 2>/dev/null || true;
         fi;
         /usr/bin/hdiutil detach /Volumes/MachineControlCorpus >/dev/null 2>&1 || true;
         rm -f "$HOME/Downloads/surface-download.txt";
         rm -rf "$root"' >/dev/null 2>&1 || true
    "$TESTBED_DIR/bin/macvm" exec /usr/bin/sudo -n /bin/rm -rf \
        '/Library/Application Support/MachineControlCorpus' \
        >/dev/null 2>&1 || true
    "$TESTBED_DIR/bin/macvm" exec /usr/bin/sudo -n /usr/sbin/pkgutil \
        --forget org.machine-control.harmless >/dev/null 2>&1 || true
}

cleanup() {
    local target
    for target in 'Quarantine Probe' "$QUARANTINE_AGENT" "$INSTALLER_ID"; do
        control remote "$(jq -nc --arg target "$target" \
            '{operation:"application.terminate",target:$target}')" \
            >/dev/null 2>&1 || true
    done
    if [[ "${settings_was_running:-true}" == false ]]; then
        control remote "$(jq -nc --arg target "$SETTINGS_ID" \
            '{operation:"application.terminate",target:$target}')" \
            >/dev/null 2>&1 || true
    fi
    if [[ "${safari_was_running:-true}" == false ]]; then
        control remote "$(jq -nc --arg target "$SAFARI_ID" \
            '{operation:"application.terminate",target:$target}')" \
            >/dev/null 2>&1 || true
    fi
    guest_cleanup
}
trap cleanup EXIT

[[ -x "$TESTBED_DIR/bin/macvm" ]] || fail "missing macvm-testbed at $TESTBED_DIR"
command -v jq >/dev/null || fail 'jq is required'
[[ -t 0 && -t 1 ]] || fail 'package authorization requires an interactive terminal'
if "$TESTBED_DIR/bin/macvm" screenshot >/dev/null 2>&1; then
    fail 'outer screenshot was available during artifact acceptance'
fi

inventory="$(control remote '{"operation":"applications"}')"
require_accepted "$inventory" 'baseline application inventory'
safari_was_running=false
settings_was_running=false
jq -e '[.data.applications[] | select(.bundleIdentifier == "com.apple.Safari")]
       | length > 0' >/dev/null <<<"$inventory" && safari_was_running=true
jq -e '[.data.applications[] | select(
       .bundleIdentifier == "com.apple.systempreferences")] | length > 0' \
    >/dev/null <<<"$inventory" && settings_was_running=true

for target in 'Quarantine Probe' "$QUARANTINE_AGENT" "$INSTALLER_ID"; do
    control remote "$(jq -nc --arg target "$target" \
        '{operation:"application.terminate",target:$target}')" \
        >/dev/null 2>&1 || true
done
guest_cleanup
host_before="$($TESTBED_DIR/bin/macvm host-state)"
"$TESTBED_DIR/bin/macvm" deploy-fixture >/dev/null
"$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
    'root="$HOME/Library/Caches/machine-control-artifact-workflows";
     mkdir -p "$root";
     /usr/bin/ditto "$HOME/Applications/Machine Control Fixture.app" "$root/Quarantine Probe.app";
     stamp="$(date +%s)";
     /usr/libexec/PlistBuddy -c "Set :CFBundleName Quarantine Probe" -c "Set :CFBundleVersion $stamp" "$root/Quarantine Probe.app/Contents/Info.plist";
     /usr/bin/codesign --force --deep --sign - --identifier org.machine-control.quarantine-probe "$root/Quarantine Probe.app";
     /usr/bin/xattr -w com.apple.quarantine "0081;00000000;Safari;machine-control" "$root/Quarantine Probe.app";
     nohup /usr/bin/open "$root/Quarantine Probe.app" >/dev/null 2>&1 &'
wait_for_button remote "$QUARANTINE_AGENT" Done >/dev/null
wait_for_semantic_value "$QUARANTINE_AGENT" '“Quarantine Probe” Not Opened'
press_named local "$QUARANTINE_AGENT" Done
"$TESTBED_DIR/bin/macvm" exec /usr/bin/open \
    'x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension'
press_named remote "$SETTINGS_ID" 'Open Anyway'
press_named local "$QUARANTINE_AGENT" 'Open Anyway'
if authorize_sheet 'Privacy & Security' gatekeeper-open-anyway \
        'Gatekeeper Open Anyway' optional; then
    :
fi
wait_for_application 'Quarantine Probe'
control remote '{"operation":"application.terminate","target":"Quarantine Probe"}' \
    >/dev/null 2>&1 || true

"$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
    'root="$HOME/Library/Caches/machine-control-artifact-workflows";
     mkdir -p "$root/image-source";
     printf "%s\n" "machine-control disk image" > "$root/image-source/Read Me.txt";
     /usr/bin/hdiutil create -quiet -volname MachineControlCorpus -srcfolder "$root/image-source" -format UDZO "$root/MachineControlCorpus.dmg";
     /usr/bin/open "$root/MachineControlCorpus.dmg"'
for _ in {1..30}; do
    "$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
        'value="$(cat "/Volumes/MachineControlCorpus/Read Me.txt" 2>/dev/null)";
         test "$value" = "machine-control disk image"' \
        >/dev/null 2>&1 && break
    sleep 0.5
done
"$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
    'value="$(cat "/Volumes/MachineControlCorpus/Read Me.txt")";
     test "$value" = "machine-control disk image"' \
    || fail 'mounted disk-image contents did not match'
wait_for_semantic_value Finder MachineControlCorpus
"$TESTBED_DIR/bin/macvm" exec /usr/bin/hdiutil detach \
    /Volumes/MachineControlCorpus >/dev/null

"$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
    'root="$HOME/Library/Caches/machine-control-artifact-workflows";
     mkdir -p "$root/web";
     printf "%s\n" "machine-control browser download" > "$root/web/surface-download.txt";
     printf "%s\n" "<html><body><a href=\"surface-download.txt\" download>Download fixture</a></body></html>" > "$root/web/index.html";
     rm -f "$HOME/Downloads/surface-download.txt";
     nohup /usr/bin/python3 -m http.server 8765 --bind 0.0.0.0 --directory "$root/web" > "$root/server.log" 2>&1 &
     echo $! > "$root/server.pid"'
web_host="machine-control-$(date +%s)-$$.localhost"
"$TESTBED_DIR/bin/macvm" exec /usr/bin/open -a Safari \
    "http://$web_host:8765/"
safari_target="$(wait_for_bundle_pid "$SAFARI_ID")"
for _ in {1..30}; do
    snapshot="$(control remote "$(jq -nc --arg target "$safari_target" \
        '{operation:"snapshot",target:$target,query:"Download fixture",
          maxDepth:20,maxElements:500,projection:"compact"}')" \
        2>/dev/null || true)"
    link_reference="$(jq -r '[.data.elements[]? | select(
        .role == "AXLink" and .label == "Download fixture")][0]
        .reference // empty' <<<"$snapshot")"
    [[ -n "$link_reference" ]] && break
    sleep 0.2
done
[[ -n "${link_reference:-}" ]] || fail 'Safari download link was unavailable'
result="$(control local "$(jq -nc --arg reference "$link_reference" \
    '{operation:"action",reference:$reference,action:"press"}')")"
require_accepted "$result" 'Safari download link'
press_named remote "$safari_target" Allow
for _ in {1..30}; do
    "$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
        'value="$(cat "$HOME/Downloads/surface-download.txt" 2>/dev/null)";
         test "$value" = "machine-control browser download"' \
        >/dev/null 2>&1 && break
    sleep 0.5
done
"$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
    'value="$(cat "$HOME/Downloads/surface-download.txt")";
     test "$value" = "machine-control browser download"' \
    || fail 'Safari download contents did not match'

"$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
    'root="$HOME/Library/Caches/machine-control-artifact-workflows";
     rm -rf "$root/package-root" "$root/MachineControlCorpus.pkg";
     mkdir -p "$root/package-root/Library/Application Support/MachineControlCorpus";
     printf "%s\n" "machine-control package installed" > "$root/package-root/Library/Application Support/MachineControlCorpus/package-marker.txt";
     /usr/bin/pkgbuild --quiet --root "$root/package-root" --identifier org.machine-control.harmless --version 1 --install-location / "$root/MachineControlCorpus.pkg";
     /usr/bin/open "$root/MachineControlCorpus.pkg"'
press_named remote "$INSTALLER_ID" Continue observe-effect
wait_for_button remote "$INSTALLER_ID" Install >/dev/null
press_named local "$INSTALLER_ID" Install
authorize_sheet Installer harmless-package-install 'harmless package installation'
for _ in {1..60}; do
    "$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
        'path="/Library/Application Support/MachineControlCorpus/package-marker.txt";
         value="$(cat "$path" 2>/dev/null)";
         test "$value" = "machine-control package installed"' \
        >/dev/null 2>&1 && break
    sleep 0.5
done
"$TESTBED_DIR/bin/macvm" exec /bin/sh -c \
    'path="/Library/Application Support/MachineControlCorpus/package-marker.txt";
     value="$(cat "$path")";
     test "$value" = "machine-control package installed"' \
    || fail 'installed package marker did not match'
wait_for_semantic_value "$INSTALLER_ID" 'The installation was successful.'
press_named remote "$INSTALLER_ID" Close

host_after="$($TESTBED_DIR/bin/macvm host-state)"
[[ "$(jq -S . <<<"$host_before")" == "$(jq -S . <<<"$host_after")" ]] \
    || fail 'artifact workflows changed the host cursor or frontmost application'

printf 'macOS quarantine, disk image, download, and installer passed.\n'
