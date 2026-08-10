#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

for script in \
    bin/macui \
    bin/macvm \
    providers/tart-macos/provider.sh \
    providers/tart-macos/screenshot \
    scripts/common.sh \
    scripts/deploy-ui.sh \
    scripts/deploy-fixture.sh \
    scripts/deploy-admin-fixture.sh \
    scripts/reset-admin-fixture.sh \
    scripts/remove-admin-fixture.sh \
    scripts/submit-authorization.sh \
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
    >/dev/null

/usr/bin/swiftc -typecheck providers/tart-macos/host-control.swift
/usr/bin/swiftc -typecheck providers/tart-macos/normalize-screenshot.swift
/usr/bin/swiftc -typecheck -framework SystemConfiguration \
    guests/macos/ui/macui.swift
/usr/bin/swiftc -typecheck guests/macos/fixture/MachineControlFixture.swift
/usr/bin/swiftc -typecheck -framework AppKit \
    guests/macos/admin-fixture/AdminAuthorizationFixture.swift

bin/macvm help >/dev/null
bin/macui help >/dev/null
bin/macvm doctor

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
