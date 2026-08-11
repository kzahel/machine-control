#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
# shellcheck source=../guests/macos/framework-runtimes/versions.env
source "$MACVM_REPO_DIR/guests/macos/framework-runtimes/versions.env"

macvm_require_host
macvm_assert_mutation_target

readonly runtime_root="/Users/$MACVM_GUEST_USER/Library/Application Support/macvm-testbed/framework-runtimes"
readonly download_root="$runtime_root/.downloads"
readonly staging_root="$runtime_root/.staging"

download_and_verify() {
    local archive="$1" url="$2" sha256="$3"
    local remote="$download_root/$archive"
    macvm_exec /usr/bin/curl --fail --location --retry 3 \
        --silent --show-error --output "$remote" "$url"
    local actual
    actual="$(macvm_exec /usr/bin/shasum -a 256 "$remote" | /usr/bin/awk '{print $1}')"
    if [[ "$actual" != "$sha256" ]]; then
        printf 'Checksum mismatch for %s: expected %s, received %s\n' \
            "$archive" "$sha256" "$actual" >&2
        return 1
    fi
}

macvm_exec /bin/rm -rf "$staging_root"
macvm_exec /bin/mkdir -p "$download_root" "$staging_root"

download_and_verify "$MACVM_NODE_ARCHIVE" "$MACVM_NODE_URL" \
    "$MACVM_NODE_SHA256"
macvm_exec /usr/bin/tar -xzf "$download_root/$MACVM_NODE_ARCHIVE" \
    -C "$staging_root"
macvm_exec /bin/rm -rf "$runtime_root/node"
macvm_exec /bin/mv \
    "$staging_root/node-v$MACVM_NODE_VERSION-darwin-arm64" \
    "$runtime_root/node"

download_and_verify "$MACVM_JAVA_ARCHIVE" "$MACVM_JAVA_URL" \
    "$MACVM_JAVA_SHA256"
macvm_exec /usr/bin/tar -xzf "$download_root/$MACVM_JAVA_ARCHIVE" \
    -C "$staging_root"
macvm_exec /bin/rm -rf "$runtime_root/java"
macvm_exec /bin/mv "$staging_root/$MACVM_JAVA_ARCHIVE_ROOT" \
    "$runtime_root/java"

download_and_verify "$MACVM_ELECTRON_ARCHIVE" "$MACVM_ELECTRON_URL" \
    "$MACVM_ELECTRON_SHA256"
macvm_exec /usr/bin/ditto -x -k \
    "$download_root/$MACVM_ELECTRON_ARCHIVE" "$staging_root/electron"
macvm_exec /bin/rm -rf "$runtime_root/Electron.app"
macvm_exec /bin/mv "$staging_root/electron/Electron.app" \
    "$runtime_root/Electron.app"

marker="$(jq -n \
    --arg node "$MACVM_NODE_VERSION" --arg nodeSha256 "$MACVM_NODE_SHA256" \
    --arg java "$MACVM_JAVA_VERSION" --arg javaSha256 "$MACVM_JAVA_SHA256" \
    --arg electron "$MACVM_ELECTRON_VERSION" \
    --arg electronSha256 "$MACVM_ELECTRON_SHA256" \
    '{schema:"macvm-framework-runtimes/v1",architecture:"arm64",
      node:{version:$node,sha256:$nodeSha256},
      java:{distribution:"Eclipse Temurin",version:$java,sha256:$javaSha256},
      electron:{version:$electron,sha256:$electronSha256}}')"
macvm_exec -i /usr/bin/tee "$runtime_root/versions.json" \
    <<<"$marker" >/dev/null
macvm_exec /bin/rm -rf "$download_root" "$staging_root"

"$MACVM_REPO_DIR/scripts/framework-runtime-status.sh" \
    | jq -e '.ready == true' >/dev/null
printf 'Installed and verified the pinned ARM64 framework runtimes.\n'
