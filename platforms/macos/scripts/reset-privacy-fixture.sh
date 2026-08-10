#!/usr/bin/env bash
set -euo pipefail
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
readonly bundle_id='org.machine-control.privacy-fixture'
readonly requested="${1:-all}"
case "$requested" in
    all) services=(Accessibility ScreenCapture ListenEvent AppleEvents Camera Microphone SystemPolicyDocumentsFolder SystemPolicyDownloadsFolder SystemPolicyAllFiles) ;;
    accessibility) services=(Accessibility) ;;
    screen-recording) services=(ScreenCapture) ;;
    input-monitoring) services=(ListenEvent) ;;
    automation) services=(AppleEvents) ;;
    camera) services=(Camera) ;;
    microphone) services=(Microphone) ;;
    documents-folder) services=(SystemPolicyDocumentsFolder) ;;
    downloads-folder) services=(SystemPolicyDownloadsFolder) ;;
    full-disk-access) services=(SystemPolicyAllFiles) ;;
    local-network)
        printf '%s\n' 'Local Network has no supported tccutil reset; use System Settings' >&2
        exit 2
        ;;
    *) printf 'Unknown privacy service: %s\n' "$requested" >&2; exit 2 ;;
esac
macvm_exec /usr/bin/killall PrivacyConsentFixture >/dev/null 2>&1 || true
for service in "${services[@]}"; do
    macvm_exec /usr/bin/tccutil reset "$service" "$bundle_id"
done
macvm_exec /bin/rm -f "/Users/$MACVM_GUEST_USER/Library/Caches/machine-control-privacy-fixture/state.json"
