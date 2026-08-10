#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

macvm_require_host
macvm_assert_mutation_target

remote_cache="/Users/$MACVM_GUEST_USER/Library/Caches/machine-control-admin-fixture"
"$MACVM_TART" exec "$MACVM_NAME" /bin/rm -rf "$remote_cache"
