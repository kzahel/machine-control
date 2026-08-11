#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly BOOTSTRAP="$REPO_DIR/scripts/bootstrap-windows.sh"
readonly FIXTURE_TESTBED="$REPO_DIR/tests/fixtures/asserted-testbed"

if "$BOOTSTRAP" fixture-target win-arm64 >/dev/null 2>&1; then
    printf 'Bootstrap unexpectedly accepted an unattested target.\n' >&2
    exit 1
fi

result="$($BOOTSTRAP --testbed "$FIXTURE_TESTBED" \
    --check-target fixture-target win-arm64)"
[[ "$result" == 'target assertion passed' ]]

runtime_result="$($BOOTSTRAP --testbed "$FIXTURE_TESTBED" \
    --check-target --profile runtime fixture-target win-x64)"
[[ "$runtime_result" == 'target assertion passed' ]]

if "$BOOTSTRAP" --testbed "$FIXTURE_TESTBED" --check-target \
        --profile unsupported fixture-target win-arm64 >/dev/null 2>&1; then
    printf 'Bootstrap unexpectedly accepted an unknown profile.\n' >&2
    exit 1
fi

if "$BOOTSTRAP" --testbed "$FIXTURE_TESTBED" \
    --check-target wrong-target win-arm64 >/dev/null 2>&1; then
    printf 'Bootstrap unexpectedly accepted a mismatched SSH alias.\n' >&2
    exit 1
fi

if "$BOOTSTRAP" --testbed "$FIXTURE_TESTBED" \
    --allow-unattested-target fixture-target win-arm64 >/dev/null 2>&1; then
    printf 'Bootstrap unexpectedly accepted conflicting target modes.\n' >&2
    exit 1
fi

printf 'Bootstrap target-safety tests passed.\n'
