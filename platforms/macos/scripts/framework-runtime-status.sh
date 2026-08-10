#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
# shellcheck source=../guests/macos/framework-runtimes/versions.env
source "$MACVM_REPO_DIR/guests/macos/framework-runtimes/versions.env"

macvm_require_host

readonly runtime_root="/Users/$MACVM_GUEST_USER/Library/Application Support/macvm-testbed/framework-runtimes"
readonly node_binary="$runtime_root/node/bin/node"
readonly java_binary="$runtime_root/java/Contents/Home/bin/java"
readonly electron_binary="$runtime_root/Electron.app/Contents/MacOS/Electron"

node_actual=''
java_actual=''
electron_actual=''
if macvm_exec /bin/test -x "$node_binary"; then
    node_actual="$(macvm_exec "$node_binary" --version 2>/dev/null || true)"
fi
if macvm_exec /bin/test -x "$java_binary"; then
    java_actual="$(macvm_exec /bin/sh -c \
        '"$1" -version 2>&1 | /usr/bin/head -n 1' _ "$java_binary" || true)"
fi
if macvm_exec /bin/test -x "$electron_binary"; then
    electron_actual="$(macvm_exec "$electron_binary" --version \
        2>/dev/null || true)"
fi
marker_valid=false
if marker="$(macvm_exec /bin/cat "$runtime_root/versions.json" 2>/dev/null)"; then
    if jq -e --arg node "$MACVM_NODE_VERSION" \
            --arg nodeSha256 "$MACVM_NODE_SHA256" \
            --arg java "$MACVM_JAVA_VERSION" \
            --arg javaSha256 "$MACVM_JAVA_SHA256" \
            --arg electron "$MACVM_ELECTRON_VERSION" \
            --arg electronSha256 "$MACVM_ELECTRON_SHA256" \
            '.schema == "macvm-framework-runtimes/v1" and
             .architecture == "arm64" and
             .node == {version:$node,sha256:$nodeSha256} and
             .java.distribution == "Eclipse Temurin" and
             .java.version == $java and .java.sha256 == $javaSha256 and
             .electron == {version:$electron,sha256:$electronSha256}' \
            >/dev/null <<<"$marker"; then
        marker_valid=true
    fi
fi

node_ready=false
java_ready=false
electron_ready=false
[[ "$node_actual" == "v$MACVM_NODE_VERSION" ]] && node_ready=true
java_feature_version="${MACVM_JAVA_VERSION%%+*}"
[[ "$java_actual" == *\"$java_feature_version\"* ]] && java_ready=true
[[ "$electron_actual" == "v$MACVM_ELECTRON_VERSION" ]] \
    && electron_ready=true

jq -n --argjson markerValid "$marker_valid" \
    --arg nodeExpected "$MACVM_NODE_VERSION" --arg nodeActual "$node_actual" \
    --argjson nodeReady "$node_ready" \
    --arg javaExpected "$MACVM_JAVA_VERSION" --arg javaActual "$java_actual" \
    --argjson javaReady "$java_ready" \
    --arg electronExpected "$MACVM_ELECTRON_VERSION" \
    --arg electronActual "$electron_actual" \
    --argjson electronReady "$electron_ready" \
    '{schema:"macvm-framework-runtime-status/v1",architecture:"arm64",
      ready:($markerValid and $nodeReady and $javaReady and $electronReady),
      markerValid:$markerValid,
      node:{expected:$nodeExpected,actual:$nodeActual,ready:$nodeReady},
      java:{expected:$javaExpected,actual:$javaActual,ready:$javaReady},
      electron:{expected:$electronExpected,actual:$electronActual,
                ready:$electronReady}}'
