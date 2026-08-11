#!/usr/bin/env bash

# Shared configuration. Keep this safe to source under `set -e` and `set -u`.

LINUXVM_REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LINUXVM_CONFIG_FILE="${LINUXVM_CONFIG_FILE:-$LINUXVM_REPO_DIR/config.local}"

# Preserve non-empty process-environment values so callers can tighten local
# configuration for one command, especially the fail-closed outer-UI guard.
linuxvm_config_names=(
    LINUXVM_PROVIDER
    LINUXVM_UTM_NAME
    LINUXVM_UTMCTL
    LINUXVM_DESKTOP_USER
    LINUXVM_DISPLAY_WIDTH
    LINUXVM_DISPLAY_HEIGHT
    LINUXVM_BOOT_TIMEOUT
    LINUXVM_SHUTDOWN_TIMEOUT
    LINUXVM_EXEC_TIMEOUT
    LINUXVM_REMOTE_ROOT
    LINUXVM_UI_REMOTE
    LINUXVM_REQUIRE_MUTATION_GUARD
    LINUXVM_TARGET_ROLE
    LINUXVM_EXPECTED_NAME
    LINUXVM_EXPECTED_UUID
    LINUXVM_FORBID_OUTER_UI
)
linuxvm_environment_values=()
for linuxvm_config_name in "${linuxvm_config_names[@]}"; do
    linuxvm_environment_values+=(
        "$(printenv "$linuxvm_config_name" 2>/dev/null || true)"
    )
done

if [[ -f "$LINUXVM_CONFIG_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$LINUXVM_CONFIG_FILE"
fi

for linuxvm_config_index in "${!linuxvm_config_names[@]}"; do
    linuxvm_environment_value="${linuxvm_environment_values[$linuxvm_config_index]}"
    if [[ -n "$linuxvm_environment_value" ]]; then
        printf -v "${linuxvm_config_names[$linuxvm_config_index]}" \
            '%s' "$linuxvm_environment_value"
    fi
done
unset linuxvm_config_index linuxvm_config_name linuxvm_config_names
unset linuxvm_environment_value linuxvm_environment_values

LINUXVM_PROVIDER="${LINUXVM_PROVIDER:-utm-macos}"
LINUXVM_UTM_NAME="${LINUXVM_UTM_NAME:-Linux}"
LINUXVM_UTMCTL="${LINUXVM_UTMCTL:-/Applications/UTM.app/Contents/MacOS/utmctl}"
LINUXVM_DESKTOP_USER="${LINUXVM_DESKTOP_USER:-}"
LINUXVM_DISPLAY_WIDTH="${LINUXVM_DISPLAY_WIDTH:-1280}"
LINUXVM_DISPLAY_HEIGHT="${LINUXVM_DISPLAY_HEIGHT:-800}"
LINUXVM_BOOT_TIMEOUT="${LINUXVM_BOOT_TIMEOUT:-120}"
LINUXVM_SHUTDOWN_TIMEOUT="${LINUXVM_SHUTDOWN_TIMEOUT:-120}"
LINUXVM_EXEC_TIMEOUT="${LINUXVM_EXEC_TIMEOUT:-300}"
LINUXVM_REMOTE_ROOT="${LINUXVM_REMOTE_ROOT:-/var/tmp/linuxvm-testbed}"
LINUXVM_UI_REMOTE="${LINUXVM_UI_REMOTE:-/usr/local/libexec/linuxvm-testbed/linuxui.py}"
LINUXVM_REQUIRE_MUTATION_GUARD="${LINUXVM_REQUIRE_MUTATION_GUARD:-false}"
LINUXVM_TARGET_ROLE="${LINUXVM_TARGET_ROLE:-unspecified}"
LINUXVM_EXPECTED_NAME="${LINUXVM_EXPECTED_NAME:-}"
LINUXVM_EXPECTED_UUID="${LINUXVM_EXPECTED_UUID:-}"
LINUXVM_FORBID_OUTER_UI="${LINUXVM_FORBID_OUTER_UI:-false}"

export LINUXVM_REPO_DIR LINUXVM_CONFIG_FILE LINUXVM_PROVIDER
export LINUXVM_UTM_NAME LINUXVM_UTMCTL LINUXVM_DESKTOP_USER
export LINUXVM_DISPLAY_WIDTH LINUXVM_DISPLAY_HEIGHT
export LINUXVM_BOOT_TIMEOUT LINUXVM_SHUTDOWN_TIMEOUT LINUXVM_EXEC_TIMEOUT
export LINUXVM_REMOTE_ROOT LINUXVM_UI_REMOTE
export LINUXVM_REQUIRE_MUTATION_GUARD LINUXVM_TARGET_ROLE
export LINUXVM_EXPECTED_NAME LINUXVM_EXPECTED_UUID LINUXVM_FORBID_OUTER_UI

linuxvm_provider_path() {
    printf '%s/providers/%s/provider.sh\n' "$LINUXVM_REPO_DIR" "$LINUXVM_PROVIDER"
}

linuxvm_require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Required command not found: %s\n' "$1" >&2
        return 1
    fi
}

linuxvm_selected_uuid() {
    "$LINUXVM_UTMCTL" list | /usr/bin/awk -v expected="$LINUXVM_UTM_NAME" '
        NR > 1 {
            uuid = $1
            $1 = ""
            $2 = ""
            sub(/^[[:space:]]+/, "")
            if ($0 == expected) {
                print uuid
                exit
            }
        }'
}

linuxvm_assert_mutation_target() {
    if [[ "$LINUXVM_REQUIRE_MUTATION_GUARD" != "true" ]]; then
        return 0
    fi
    if [[ -z "$LINUXVM_EXPECTED_NAME" ||
          "$LINUXVM_UTM_NAME" != "$LINUXVM_EXPECTED_NAME" ]]; then
        printf 'Refusing mutation: selected VM does not match the expected name\n' >&2
        return 1
    fi
    if [[ -z "$LINUXVM_EXPECTED_UUID" ||
          "$(linuxvm_selected_uuid)" != "$LINUXVM_EXPECTED_UUID" ]]; then
        printf 'Refusing mutation: selected VM does not match the expected UUID\n' >&2
        return 1
    fi
    case "$LINUXVM_TARGET_ROLE" in
        candidate|disposable) ;;
        *)
            printf 'Refusing mutation: target role is not candidate/disposable\n' >&2
            return 1
            ;;
    esac
}

linuxvm_assert_outer_ui_allowed() {
    if [[ "$LINUXVM_FORBID_OUTER_UI" == "true" ]]; then
        printf 'Outer UTM capture/input is prohibited for this operation\n' >&2
        return 1
    fi
}
