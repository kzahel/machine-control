#!/usr/bin/env bash

set -euo pipefail

readonly PROVIDER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../scripts/common.sh
source "$PROVIDER_DIR/../../scripts/common.sh"

readonly LIBVIRT_CORE="$LINUXVM_REPO_DIR/../../providers/libvirt-linux/libvirt_provider.py"
readonly LIBVIRT_FACTORY="$LINUXVM_REPO_DIR/../../providers/libvirt-linux/domain_factory.py"

export MC_LIBVIRT_URI="$LINUXVM_LIBVIRT_URI"
export MC_LIBVIRT_DOMAIN_NAME="$LINUXVM_LIBVIRT_DOMAIN_NAME"
export MC_LIBVIRT_EXPECTED_UUID="$LINUXVM_EXPECTED_UUID"
export MC_LIBVIRT_NETWORK="$LINUXVM_LIBVIRT_NETWORK"
export MC_LIBVIRT_POOL="$LINUXVM_LIBVIRT_POOL"
export MC_LIBVIRT_VIRSH="$LINUXVM_LIBVIRT_VIRSH"
export MC_LIBVIRT_QEMU="$LINUXVM_LIBVIRT_QEMU"
export MC_LIBVIRT_BOOT_TIMEOUT="$LINUXVM_BOOT_TIMEOUT"
export MC_LIBVIRT_SHUTDOWN_TIMEOUT="$LINUXVM_SHUTDOWN_TIMEOUT"
export MC_LIBVIRT_EXEC_TIMEOUT="$LINUXVM_EXEC_TIMEOUT"
export MC_LIBVIRT_MIN_FREE_BYTES="$LINUXVM_LIBVIRT_MIN_FREE_BYTES"
export MC_LIBVIRT_POOL_PATH="$LINUXVM_WORKSPACE_STORAGE_PATH"
export MC_LIBVIRT_REQUIRE_SECURE_BOOT=false
export MC_LIBVIRT_REQUIRE_TPM2=false

usage() {
    cat <<'EOF'
Usage: provider.sh COMMAND [ARG...]

Internal libvirt/QEMU/KVM-on-Linux provider. Use bin/linuxvm instead.
EOF
}

core() {
    "$LIBVIRT_CORE" "$@"
}

factory() {
    MC_LIBVIRT_FACTORY_ROOT="${LINUXVM_FACTORY_LOCAL_ROOT:-$LINUXVM_REPO_DIR/.factory.local}" \
        "$LIBVIRT_FACTORY" "$@"
}

role_allows_operation() {
    local operation="$1"
    case "$operation" in
        inspect|status|host-doctor) return 0 ;;
        connect|up|reboot|shutdown|force-stop|input|factory-detach-media)
            [[ "$LINUXVM_TARGET_ROLE" == candidate ||
                "$LINUXVM_TARGET_ROLE" == disposable ]]
            ;;
        *) return 1 ;;
    esac
}

assert_target() {
    local operation="${1:-inspect}"
    if [[ "$LINUXVM_REQUIRE_MUTATION_GUARD" != true ]]; then
        printf 'The libvirt provider requires the exact mutation guard\n' >&2
        return 1
    fi
    case "$LINUXVM_TARGET_ROLE" in
        candidate|disposable) ;;
        *)
            printf 'Target role is not candidate/disposable\n' >&2
            return 1
            ;;
    esac
    if [[ -z "$LINUXVM_EXPECTED_UUID" ]]; then
        printf 'Target identity is unpinned in private inventory\n' >&2
        return 1
    fi
    if ! role_allows_operation "$operation"; then
        printf 'Target role does not authorize this operation\n' >&2
        return 1
    fi
    core inspect >/dev/null
}

guard_status() {
    local verified=false
    if assert_target inspect >/dev/null 2>&1; then verified=true; fi
    jq -n \
        --argjson outerUIForbidden \
        "$([[ "$LINUXVM_FORBID_OUTER_UI" == true ]] && printf true || printf false)" \
        --argjson mutationTargetVerified "$verified" \
        --arg targetRole "$LINUXVM_TARGET_ROLE" \
        '{outerUIForbidden:$outerUIForbidden,
          mutationGuardRequired:true,
          mutationTargetVerified:$mutationTargetVerified,
          targetRole:$targetRole}'
}

host_state() {
    local host ready
    host="$(core host-doctor 2>/dev/null || true)"
    ready="$(jq -r '.ready // false' <<<"$host" 2>/dev/null || printf false)"
    jq -n --argjson ready "$ready" \
        --argjson outerUIForbidden \
        "$([[ "$LINUXVM_FORBID_OUTER_UI" == true ]] && printf true || printf false)" \
        '{provider:"libvirt-linux",hardwareAcceleration:"kvm",
          hostReady:$ready,outerUIForbidden:$outerUIForbidden}'
}

ensure_running() {
    assert_target up
    core start
}

vm_up() {
    ensure_running
    if core agent-ready; then
        core ip
    else
        printf 'started (guest agent unavailable)\n'
    fi
}

require_outer_ui_allowed() {
    if [[ "$LINUXVM_FORBID_OUTER_UI" == true ]]; then
        printf 'Refusing host-side libvirt capture/input: outer UI is forbidden\n' >&2
        return 1
    fi
}

unsupported_outer() {
    require_outer_ui_allowed
    printf 'This libvirt recovery operation is not implemented yet\n' >&2
    return 1
}

command="${1:-}"
if [[ -n "$command" ]]; then shift; fi

case "$command" in
    host-doctor) core host-doctor ;;
    target-id) core resolve-uuid ;;
    status) core status ;;
    guard-status) guard_status ;;
    host-state) host_state ;;
    up) vm_up ;;
    ip) assert_target inspect; core ip ;;
    exec)
        assert_target connect
        if [[ "${1:-}" == -- ]]; then shift; fi
        core exec -- "$@"
        ;;
    push)
        assert_target connect
        (( $# == 2 )) || { printf 'Usage: linuxvm push LOCAL REMOTE\n' >&2; exit 2; }
        core push "$1" "$2"
        ;;
    pull)
        assert_target connect
        (( $# >= 1 && $# <= 2 )) || { printf 'Usage: linuxvm pull REMOTE [LOCAL]\n' >&2; exit 2; }
        core pull "$@"
        ;;
    reboot) assert_target reboot; core reboot-linux ;;
    shutdown) assert_target shutdown; core shutdown ;;
    force-stop) assert_target force-stop; core force-stop ;;
    factory-create)
        if (( $# != 3 )); then
            printf 'Usage: linuxvm factory-create NAME CLOUD_IMAGE SEED_ISO\n' >&2
            exit 2
        fi
        factory create-linux "$@"
        ;;
    factory-detach-media)
        assert_target factory-detach-media
        factory detach-media
        ;;
    screenshot|click|drag|type|key|scan)
        unsupported_outer
        ;;
    permissions)
        printf '{"capture":"provider","input":"provider","status":"unavailable"}\n'
        ;;
    window-info)
        unsupported_outer
        ;;
    suspend|shell|disposable|clone)
        printf 'The libvirt provider operation is not implemented yet\n' >&2
        exit 1
        ;;
    *) usage >&2; exit 2 ;;
esac
