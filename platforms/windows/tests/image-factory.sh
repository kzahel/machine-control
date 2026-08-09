#!/usr/bin/env bash

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary="$(mktemp -d /tmp/winvm-image-factory-test.XXXXXX)"
trap 'rm -rf -- "$temporary"' EXIT
secret="$temporary/secret"
public_key="$temporary/controller.pub"
printf 'fixture&ampersand!42\n' > "$secret"
chmod 600 "$secret"
printf 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFixtureOnly factory@test\n' > \
    "$public_key"

WINVM_FACTORY_LOCAL_ROOT="$temporary/output" \
    "$REPO_DIR/scripts/image-factory.sh" render-seed \
    arm64 fixture 1 "$secret" "$public_key" >/dev/null
test -f "$temporary/output/winvm-seed.iso"
hdiutil pmap "$temporary/output/winvm-seed.iso" >/dev/null

chmod 644 "$secret"
if WINVM_FACTORY_LOCAL_ROOT="$temporary/wrong-mode" \
    "$REPO_DIR/scripts/image-factory.sh" render-seed \
    arm64 fixture 1 "$secret" "$public_key" >/dev/null 2>&1; then
    printf 'World-readable secret file unexpectedly produced answer media.\n' >&2
    exit 1
fi

if "$REPO_DIR/scripts/image-factory.sh" validate-media \
    "$temporary/missing.iso" >/dev/null 2>&1; then
    printf 'Missing installation media unexpectedly validated.\n' >&2
    exit 1
fi

printf 'Image-factory tests passed.\n'
