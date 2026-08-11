#!/usr/bin/env bash

set -euo pipefail

mode="${1:-}"
if [[ -n "$mode" && "$mode" != "--static" ]]; then
    printf 'Usage: tests/smoke.sh [--static]\n' >&2
    exit 2
fi

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary="$(mktemp -d /tmp/macvm-workspace-smoke.XXXXXX)"
trap 'rm -rf -- "$temporary"' EXIT
cd "$REPO_DIR"

for script in \
    bin/macui \
    bin/macvm \
    providers/tart-macos/provider.sh \
    providers/tart-macos/workspace.sh \
    providers/tart-macos/screenshot \
    scripts/common.sh \
    scripts/deploy-ui.sh \
    scripts/deploy-fixture.sh \
    scripts/deploy-admin-fixture.sh \
    scripts/deploy-privacy-fixture.sh \
    scripts/deploy-swiftui-fixture.sh \
    scripts/deploy-electron-fixture.sh \
    scripts/deploy-java-fixture.sh \
    scripts/framework-runtime-status.sh \
    scripts/install-framework-runtimes.sh \
    scripts/reset-admin-fixture.sh \
    scripts/remove-fixture.sh \
    scripts/remove-admin-fixture.sh \
    scripts/reset-privacy-fixture.sh \
    scripts/remove-privacy-fixture.sh \
    scripts/remove-swiftui-fixture.sh \
    scripts/remove-electron-fixture.sh \
    scripts/remove-java-fixture.sh \
    scripts/submit-authorization.sh \
    scripts/fetch-artifact.sh \
    scripts/doctor-json.sh \
    scripts/doctor.sh \
    guests/macos/ui/machine-control \
    guests/macos/bootstrap/bootstrap-guest.sh; do
    /bin/bash -n "$script"
done

/usr/bin/plutil -lint \
    guests/macos/bootstrap/org.cirruslabs.tart-guest-agent.plist.in \
    guests/macos/bootstrap/org.cirruslabs.tart-guest-daemon.plist.in \
    guests/macos/ui/Info.plist \
    guests/macos/fixture/Info.plist \
    guests/macos/admin-fixture/Info.plist \
    guests/macos/privacy-fixture/Info.plist \
    guests/macos/swiftui-fixture/Info.plist \
    >/dev/null

/usr/bin/swiftc -typecheck providers/tart-macos/host-control.swift
/usr/bin/swiftc -typecheck providers/tart-macos/normalize-screenshot.swift
/usr/bin/swiftc -typecheck -framework SystemConfiguration \
    guests/macos/ui/macui.swift
/usr/bin/swiftc -typecheck guests/macos/fixture/MachineControlFixture.swift
/usr/bin/swiftc -typecheck -framework AppKit \
    guests/macos/admin-fixture/AdminAuthorizationFixture.swift
/usr/bin/swiftc -typecheck -framework AppKit -framework ApplicationServices \
    -framework AVFoundation -framework Network -framework ScreenCaptureKit \
    -framework UserNotifications \
    guests/macos/privacy-fixture/PrivacyConsentFixture.swift
/usr/bin/swiftc -typecheck -parse-as-library -framework SwiftUI \
    guests/macos/swiftui-fixture/SwiftUIFixture.swift

/usr/bin/python3 -m json.tool \
    guests/macos/electron-fixture/package.json >/dev/null
for file in guests/macos/electron-fixture/main.js \
    guests/macos/electron-fixture/preload.js; do
    test -s "$file"
done
test -s guests/macos/java-fixture/MachineControlJavaFixture.java
source guests/macos/framework-runtimes/versions.env
[[ "$MACVM_NODE_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$MACVM_JAVA_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$MACVM_ELECTRON_SHA256" =~ ^[0-9a-f]{64}$ ]]

bin/macvm help >/dev/null
bin/macui help >/dev/null
workspace_caps="$(env \
    MACVM_CONFIG_FILE=/dev/null \
    MACVM_TART=/usr/bin/true \
    MACVM_NAME=fixture-development \
    MACVM_WORKSPACE_STATE_DIR="$temporary/capabilities" \
    MACVM_WORKSPACE_DEVELOPMENT_PROVEN=false \
    bin/macvm workspace-capabilities --json)"
jq -e '.schema == "machine-control-workspace-capabilities/v0" and
    .intents.persistent.availability == "unavailable"' \
    <<<"$workspace_caps" >/dev/null

workspace_handle="$(python3 "$REPO_DIR/../../providers/workspaces/receipts.py" \
    --state-dir "$temporary/selection" create \
    --provider tart-macos --intent isolated \
    --mechanism filesystem_cow_clone \
    --retention discardOnRelease --cleanup release --state running \
    --target-name fixture-workspace --target-id fixture-workspace \
    --source-name fixture-base --source-id fixture-base)"
selection="$({ env \
    MACVM_CONFIG_FILE=/dev/null \
    MACVM_WORKSPACE_STATE_DIR="$temporary/selection" \
    MACHINE_CONTROL_WORKSPACE_HANDLE="$workspace_handle" \
    bash -c 'source "$1"; printf "%s|%s|%s\n" "$MACVM_NAME" "$MACVM_EXPECTED_NAME" "$MACVM_TARGET_ROLE"' \
        _ "$REPO_DIR/scripts/common.sh"; } 2>/dev/null)"
[[ "$selection" == 'fixture-workspace|fixture-workspace|disposable' ]]
if MACVM_FORBID_OUTER_UI=true bin/macvm screenshot >/dev/null 2>&1; then
    printf 'Outer-UI guard allowed a Tart screenshot\n' >&2
    exit 1
fi
for command in click drag type key; do
    if MACVM_FORBID_OUTER_UI=true bin/macvm "$command" >/dev/null 2>&1; then
        printf 'Outer-UI guard allowed macvm %s\n' "$command" >&2
        exit 1
    fi
done
if [[ "$mode" == "--static" ]]; then
    printf 'macOS native static checks passed\n'
    exit 0
fi
MACVM_FORBID_OUTER_UI=true bin/macvm status >/dev/null
bin/macvm doctor
bin/macvm doctor --json | /usr/bin/jq -e \
    '.schema == "machine-control-doctor/v0" and .ready == true' >/dev/null

artifact_dir="$REPO_DIR/.artifacts/smoke"
/bin/mkdir -p "$artifact_dir"
bin/macvm screenshot "$artifact_dir/guest.png" >/dev/null
bin/macvm exec /usr/bin/sw_vers >/dev/null
bin/macvm ui health | /usr/bin/jq -e 'has("accessibilityTrusted")' >/dev/null
bin/macvm ui apps >/dev/null
if bin/macvm ui health | /usr/bin/jq -e '.accessibilityTrusted == true' \
        >/dev/null; then
    bin/macvm ui windows --app Finder >/dev/null
    bin/macvm ui tree --app Finder --interactive --depth 6 --limit 100 \
        >/dev/null
fi
bin/macvm control '{"operation":"status"}' \
    | /usr/bin/jq -e '.accepted == true and .data.semanticState == "ready"' \
    >/dev/null

printf 'MacVM smoke test passed; screenshot: %s\n' "$artifact_dir/guest.png"
