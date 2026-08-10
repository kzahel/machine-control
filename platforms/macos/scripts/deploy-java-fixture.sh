#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

macvm_require_host
macvm_assert_mutation_target

readonly source_file="$MACVM_REPO_DIR/guests/macos/java-fixture/MachineControlJavaFixture.java"
readonly runtime_root="/Users/$MACVM_GUEST_USER/Library/Application Support/macvm-testbed/framework-runtimes"
readonly build_root="/Users/$MACVM_GUEST_USER/Library/Application Support/macvm-testbed/java-fixture-build"
readonly remote_source="$build_root/MachineControlJavaFixture.java"
readonly remote_app="/Users/$MACVM_GUEST_USER/Applications/Machine Control Java Fixture.app"
readonly java_home="$runtime_root/java/Contents/Home"

"$SCRIPT_DIR/framework-runtime-status.sh" \
    | jq -e '.ready == true' >/dev/null \
    || { printf 'Install framework runtimes before deploying fixtures.\n' >&2; exit 1; }

macvm_exec /bin/rm -rf "$build_root" "$remote_app"
macvm_exec /bin/mkdir -p "$build_root/classes" "$build_root/input"
macvm_exec -i /usr/bin/tee "$remote_source" < "$source_file" >/dev/null
macvm_exec "$java_home/bin/javac" -d "$build_root/classes" "$remote_source"
macvm_exec "$java_home/bin/jar" --create \
    --file "$build_root/input/fixture.jar" \
    --main-class MachineControlJavaFixture \
    -C "$build_root/classes" .
macvm_exec "$java_home/bin/jpackage" --type app-image \
    --name 'Machine Control Java Fixture' \
    --app-version 1.0.0 \
    --input "$build_root/input" \
    --main-jar fixture.jar \
    --main-class MachineControlJavaFixture \
    --mac-package-identifier org.machine-control.java-fixture \
    --dest "/Users/$MACVM_GUEST_USER/Applications"
macvm_exec /usr/bin/codesign --force --deep --sign - \
    --identifier org.machine-control.java-fixture "$remote_app"
macvm_exec \
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -f "$remote_app"
macvm_exec /bin/rm -rf "$build_root"

printf 'Deployed %s\n' "$remote_app"
