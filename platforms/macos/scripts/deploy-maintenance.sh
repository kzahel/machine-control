#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

macvm_require_host
macvm_assert_candidate_target

source_file="$MACVM_REPO_DIR/guests/macos/bootstrap/post-update.sh"
remote_file="$(macvm_remote_post_update_script)"
macvm_exec /bin/mkdir -p "$(/usr/bin/dirname "$remote_file")"
macvm_exec -i /usr/bin/tee "$remote_file" <"$source_file" >/dev/null
macvm_exec /bin/chmod 700 "$remote_file"
macvm_exec /bin/bash -n "$remote_file"
printf 'Installed macOS maintenance support\n'
