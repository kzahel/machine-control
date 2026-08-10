#!/usr/bin/env bash
set -euo pipefail
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
macvm_assert_mutation_target
remote_app="/Users/$MACVM_GUEST_USER/Applications/Machine Control Privacy Fixture.app"
macvm_exec /usr/bin/killall PrivacyConsentFixture >/dev/null 2>&1 || true
macvm_exec /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -u "$remote_app" >/dev/null 2>&1 || true
macvm_exec /bin/rm -rf "$remote_app" \
    "/Users/$MACVM_GUEST_USER/Library/Caches/machine-control-privacy-fixture"
