#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly PYTHON="${PYTHON:-python3}"

find "$REPO_DIR/bin" "$REPO_DIR/scripts" "$REPO_DIR/providers" \
    "$REPO_DIR/guests" "$REPO_DIR/tests" -type f \
    \( -name '*.sh' -o -perm -u+x \) -print0 | \
    xargs -0 file | awk -F: '/shell script/ { print $1 }' | \
    while IFS= read -r script; do bash -n "$script"; done

"$PYTHON" -m py_compile \
    "$REPO_DIR/guests/ubuntu/ui/linuxui.py" \
    "$REPO_DIR/guests/ubuntu/ui/linuxcontrol.py" \
    "$REPO_DIR/guests/ubuntu/input/linuxinputd.py" \
    "$REPO_DIR/guests/ubuntu/fixtures/control_fixture.py" \
    "$REPO_DIR/guests/ubuntu/fixtures/qt_fixture.py" \
    "$REPO_DIR/guests/ubuntu/fixtures/browser_fixture.py"

"$REPO_DIR/bin/linuxvm" help >/dev/null
printf 'Linux native static checks passed\n'
