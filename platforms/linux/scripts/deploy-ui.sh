#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

readonly LINUXVM="$LINUXVM_REPO_DIR/bin/linuxvm"
readonly SOURCE="$LINUXVM_REPO_DIR/guests/ubuntu/ui/linuxui.py"
readonly STAGED="/var/tmp/linuxvm-ui.$$.py"

"$LINUXVM" push "$SOURCE" "$STAGED"
"$LINUXVM" exec -- /usr/bin/install -d -m 0755 "$(dirname "$LINUXVM_UI_REMOTE")"
"$LINUXVM" exec -- /usr/bin/install -m 0755 "$STAGED" "$LINUXVM_UI_REMOTE"

"$LINUXVM" ui health
printf 'LinuxVM AT-SPI helper deployed to %s\n' "$LINUXVM_UI_REMOTE"
