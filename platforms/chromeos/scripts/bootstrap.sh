#!/bin/bash
# Compatibility entry. The self-contained recommended script is activate.sh.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -r "$SCRIPT_DIR/activate.sh" ]; then
    exec bash "$SCRIPT_DIR/activate.sh" "$@"
fi
# Legacy standalone downloads follow main, just like the old bootstrap URL.
# For a revision-pinned download, fetch that revision's activate.sh directly.
case "${1:-}" in
    --help|-h) echo 'Use activate.sh [--yes | --ssh-only] [--repair-only].'; exit 0 ;;
esac
umask 077
staged=$(mktemp /mnt/stateful_partition/activate-download.XXXXXX)
trap 'rm -f "$staged"' EXIT
curl -fSL https://raw.githubusercontent.com/kzahel/machine-control/main/platforms/chromeos/scripts/activate.sh -o "$staged"
bash -n "$staged"
bash "$staged" "$@"
