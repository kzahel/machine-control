#!/usr/bin/env bash
# Audit, repair, and prove ChromeOS testbed state after an OS update.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$SCRIPT_DIR/common.sh"

OUTPUT_FORMAT="${CHROMEOS_OUTPUT:-text}"
MODE=audit
MODE_SELECTED=false
AUTO_YES=false
REMOTE_SSH_DIR=/mnt/stateful_partition/etc/ssh
STAGED_BOOTSTRAP="$REMOTE_SSH_DIR/post-update-bootstrap.sh"
REPAIR_MARKER="$REMOTE_SSH_DIR/post-update-repair.pending"

usage() {
    cat <<'EOF'
Usage: chromeos post-update [--repair | --verify-reboot] [-y]

Without options, performs a read-only focused post-update audit.

  --repair         Repair the active ChromeOS image. If rootfs verification is
                   enabled, stages the current bootstrap, disables verification,
                   and reboots. Recover SSH from VT2, then run --repair again.
  --verify-reboot  Reboot and prove SSH returned automatically on the new boot.
  -y, --yes        Confirm the reboot required by --repair or --verify-reboot.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repair)
            if [[ "$MODE_SELECTED" == true && "$MODE" != repair ]]; then
                echo "Choose only one of --repair and --verify-reboot." >&2
                exit 1
            fi
            MODE=repair
            MODE_SELECTED=true
            ;;
        --verify-reboot)
            if [[ "$MODE_SELECTED" == true && "$MODE" != verify-reboot ]]; then
                echo "Choose only one of --repair and --verify-reboot." >&2
                exit 1
            fi
            MODE=verify-reboot
            MODE_SELECTED=true
            ;;
        -y|--yes) AUTO_YES=true ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
    esac
    shift
done

if [[ "$OUTPUT_FORMAT" == json && "$MODE" != audit ]]; then
    echo "Structured output is available for the read-only post-update audit only." >&2
    exit 1
fi

RELEASE=unknown
BOOT_ID=unknown
UPDATE_OPERATION=unknown
ROOTFS_WRITABLE=no
AUTOSTART=missing
FALLBACK=no
PREPARED_RELEASE=missing
BOOT_EVIDENCE=none
DEVTOOLS_CONFIGURED=no
DEVTOOLS_LISTENING=no
REPAIR_STAGED=no
STATUS=unknown
FAIL_COUNT=0
WARN_COUNT=0
CHECKS=()

text_mode() {
    [[ "$OUTPUT_FORMAT" != json ]]
}

require_ssh() {
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_HOST" "echo ok" &>/dev/null; then
        return 0
    fi

    if text_mode; then
        echo "[FAIL] Cannot connect to $SSH_HOST via SSH."
        echo
        print_vt2_ssh_instructions
        echo
        echo "Then run: chromeos post-update --repair"
    else
        python3 - "$SSH_HOST" <<'PY'
import json
import sys
print(json.dumps({
    "ok": False,
    "host": sys.argv[1],
    "status": "ssh_unreachable",
    "checks": [{
        "status": "fail",
        "name": "SSH is unreachable",
        "fix": "Recover SSH from VT2, then run: chromeos post-update --repair",
    }],
}))
PY
    fi
    return 1
}

load_snapshot() {
    local snapshot key value
    snapshot=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; bash -s" <<'REMOTE'
release=$(awk -F= '$1 == "CHROMEOS_RELEASE_VERSION" { print $2; exit }' /etc/lsb-release)
boot_id=$(cat /proc/sys/kernel/random/boot_id)
update_operation=$(update_engine_client --status 2>/dev/null |
  awk -F= '$1 == "CURRENT_OP" { print $2; exit }')

rootfs_writable=no
if touch /etc/.chromeos-testbed-post-update-probe 2>/dev/null; then
  rm -f /etc/.chromeos-testbed-post-update-probe
  rootfs_writable=yes
fi

if [ -f /etc/init/openssh-server.conf ] &&
   grep -qx 'author "chromeos-testbed"' /etc/init/openssh-server.conf &&
   grep -qx 'start on shill-connected' /etc/init/openssh-server.conf; then
  if status openssh-server 2>/dev/null | grep -q 'start/running'; then
    autostart=running
  else
    autostart=stopped
  fi
elif [ -f /etc/init/chromeos-testbed-sshd.conf ] &&
     grep -qx 'author "chromeos-testbed"' /etc/init/chromeos-testbed-sshd.conf; then
  autostart=incompatible
else
  autostart=missing
fi

fallback=no
# The stateful partition is mounted noexec on this ChromeOS release. The
# fallback is intentionally invoked through bash, so readability is the real
# requirement even when its Unix execute bits are set.
[ -r /mnt/stateful_partition/etc/ssh/start_sshd.sh ] && fallback=yes

prepared_release=missing
[ -r /mnt/stateful_partition/etc/ssh/prepared-release ] &&
  prepared_release=$(cat /mnt/stateful_partition/etc/ssh/prepared-release)

boot_evidence=none
if grep -q "boot_id=$boot_id .*events=shill-connected" \
    /mnt/stateful_partition/etc/ssh/startup.log 2>/dev/null; then
  boot_evidence=automatic
elif grep -q "boot_id=$boot_id " \
    /mnt/stateful_partition/etc/ssh/startup.log 2>/dev/null; then
  boot_evidence=manual
fi

devtools_configured=no
grep -q -- '--remote-debugging-port=9222' /etc/chrome_dev.conf 2>/dev/null &&
  devtools_configured=yes

devtools_listening=no
awk '{print $2}' /proc/net/tcp 2>/dev/null | grep -qi ':2406' &&
  devtools_listening=yes

repair_staged=no
[ -r /mnt/stateful_partition/etc/ssh/post-update-repair.pending ] &&
  repair_staged=yes

printf 'release\t%s\n' "${release:-unknown}"
printf 'boot_id\t%s\n' "${boot_id:-unknown}"
printf 'update_operation\t%s\n' "${update_operation:-unknown}"
printf 'rootfs_writable\t%s\n' "$rootfs_writable"
printf 'autostart\t%s\n' "$autostart"
printf 'fallback\t%s\n' "$fallback"
printf 'prepared_release\t%s\n' "$prepared_release"
printf 'boot_evidence\t%s\n' "$boot_evidence"
printf 'devtools_configured\t%s\n' "$devtools_configured"
printf 'devtools_listening\t%s\n' "$devtools_listening"
printf 'repair_staged\t%s\n' "$repair_staged"
REMOTE
) || return 1

    while IFS=$'\t' read -r key value; do
        case "$key" in
            release) RELEASE="$value" ;;
            boot_id) BOOT_ID="$value" ;;
            update_operation) UPDATE_OPERATION="$value" ;;
            rootfs_writable) ROOTFS_WRITABLE="$value" ;;
            autostart) AUTOSTART="$value" ;;
            fallback) FALLBACK="$value" ;;
            prepared_release) PREPARED_RELEASE="$value" ;;
            boot_evidence) BOOT_EVIDENCE="$value" ;;
            devtools_configured) DEVTOOLS_CONFIGURED="$value" ;;
            devtools_listening) DEVTOOLS_LISTENING="$value" ;;
            repair_staged) REPAIR_STAGED="$value" ;;
        esac
    done <<< "$snapshot"
}

add_check() {
    local check_status="$1" name="$2" detail="${3:-}" fix="${4:-}"
    CHECKS+=("$check_status" "$name" "$detail" "$fix")
    case "$check_status" in
        fail) FAIL_COUNT=$((FAIL_COUNT + 1)) ;;
        warn) WARN_COUNT=$((WARN_COUNT + 1)) ;;
    esac
}

evaluate_snapshot() {
    CHECKS=()
    FAIL_COUNT=0
    WARN_COUNT=0
    STATUS=ready

    add_check ok "SSH is reachable"

    case "$UPDATE_OPERATION" in
        UPDATE_STATUS_UPDATED_NEED_REBOOT)
            add_check warn "ChromeOS update is waiting for reboot" \
                "The new root image may replace SSH autostart and DevTools configuration." \
                "Run: chromeos post-update --repair"
            STATUS=update_pending
            ;;
        UPDATE_STATUS_IDLE)
            add_check ok "No ChromeOS update is waiting for reboot"
            ;;
        *)
            add_check warn "ChromeOS update state is $UPDATE_OPERATION"
            ;;
    esac

    if [[ "$FALLBACK" == yes ]]; then
        add_check ok "Stateful VT2 SSH fallback is available"
    else
        add_check fail "Stateful VT2 SSH fallback is missing" "" \
            "Re-run the bootstrap from VT2 before rebooting"
    fi

    if [[ "$ROOTFS_WRITABLE" == yes ]]; then
        add_check ok "Rootfs is writable"
    else
        add_check fail "Rootfs verification is enabled" "" \
            "Run: chromeos post-update --repair"
    fi

    case "$AUTOSTART" in
        running)
            add_check ok "SSH autostart job is installed and running"
            ;;
        stopped)
            add_check fail "SSH autostart job is installed but stopped" "" \
                "Run: chromeos post-update --repair"
            ;;
        incompatible)
            add_check fail "Incompatible SSH autostart job is installed" "" \
                "Run: chromeos post-update --repair"
            ;;
        *)
            add_check fail "SSH autostart job is missing" "" \
                "Run: chromeos post-update --repair"
            ;;
    esac

    if [[ "$PREPARED_RELEASE" == "$RELEASE" ]]; then
        add_check ok "Current ChromeOS release was prepared by the bootstrap"
    else
        add_check fail "Current ChromeOS release is not marked as prepared" \
            "prepared=${PREPARED_RELEASE}, current=${RELEASE}" \
            "Run: chromeos post-update --repair"
    fi

    case "$BOOT_EVIDENCE" in
        automatic)
            add_check ok "Current boot automatically started SSH after network connection"
            ;;
        manual)
            add_check warn "Current boot started SSH manually" "" \
                "After repair, run: chromeos post-update --verify-reboot"
            [[ "$STATUS" == ready ]] && STATUS=reboot_verification_required
            ;;
        *)
            add_check warn "Current boot has no automatic SSH startup evidence" "" \
                "After repair, run: chromeos post-update --verify-reboot"
            [[ "$STATUS" == ready ]] && STATUS=reboot_verification_required
            ;;
    esac

    if [[ "$DEVTOOLS_CONFIGURED" == yes ]]; then
        add_check ok "Remote debugging is configured"
    else
        add_check fail "Remote debugging configuration is missing" "" \
            "Run: chromeos post-update --repair"
    fi

    if [[ "$DEVTOOLS_LISTENING" == yes ]]; then
        add_check ok "DevTools port 9222 is listening"
    else
        add_check fail "DevTools port 9222 is not listening" "" \
            "Run: chromeos post-update --repair"
    fi

    if [[ "$FAIL_COUNT" -gt 0 ]]; then
        STATUS=repair_required
    fi
}

emit_audit() {
    local i
    if text_mode; then
        echo "ChromeOS post-update audit ($SSH_HOST)"
        echo "Release: $RELEASE"
        echo
        for ((i=0; i<${#CHECKS[@]}; i+=4)); do
            case "${CHECKS[i]}" in
                ok) printf '[OK]   %s\n' "${CHECKS[i+1]}" ;;
                warn) printf '[WARN] %s\n' "${CHECKS[i+1]}" ;;
                fail) printf '[FAIL] %s\n' "${CHECKS[i+1]}" ;;
            esac
            [[ -n "${CHECKS[i+2]}" ]] && printf '       %s\n' "${CHECKS[i+2]}"
            [[ -n "${CHECKS[i+3]}" ]] && printf '       Fix: %s\n' "${CHECKS[i+3]}"
        done
        echo
        echo "Status: $STATUS"
        return
    fi

    python3 - "$SSH_HOST" "$RELEASE" "$BOOT_ID" "$UPDATE_OPERATION" \
        "$STATUS" "$FAIL_COUNT" "$WARN_COUNT" "${CHECKS[@]}" <<'PY'
import json
import sys

host, release, boot_id, update_operation, status = sys.argv[1:6]
failed, warned = map(int, sys.argv[6:8])
fields = sys.argv[8:]
checks = []
for i in range(0, len(fields), 4):
    check_status, name, detail, fix = fields[i:i + 4]
    item = {"status": check_status, "name": name}
    if detail:
        item["detail"] = detail
    if fix:
        item["fix"] = fix
    checks.append(item)
print(json.dumps({
    "ok": status == "ready",
    "host": host,
    "release": release,
    "boot_id": boot_id,
    "update_operation": update_operation,
    "status": status,
    "failed": failed,
    "warned": warned,
    "checks": checks,
}))
PY
}

confirm_reboot() {
    local prompt="$1" confirm
    [[ "$AUTO_YES" == true ]] && return 0
    read -r -p "$prompt [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]]
}

stage_bootstrap() {
    scp -q "$REPO_DIR/scripts/bootstrap.sh" "$SSH_HOST:$STAGED_BOOTSTRAP"
    ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; chmod 700 '$STAGED_BOOTSTRAP'; \
printf 'release=%s boot_id=%s staged_at=%s\n' '$RELEASE' '$BOOT_ID' \"\$(date -Is)\" > '$REPAIR_MARKER'"
}

print_repair_resume() {
    echo
    echo "After ChromeOS boots, recover from VT2:"
    echo
    echo "  1. Press Ctrl+Alt+F2 and log in as chronos"
    echo "  2. sudo -i"
    echo "  3. bash $REMOTE_SSH_DIR/start_sshd.sh"
    echo "  4. Press Ctrl+Alt+F1 to return to ChromeOS"
    echo
    echo "Then run from this machine:"
    echo "  chromeos post-update --repair"
}

reboot_for_next_phase() {
    local reason="$1"
    if ! confirm_reboot "$reason Reboot now?"; then
        echo "Aborted before making boot changes."
        return 1
    fi
    stage_bootstrap || return 1
    return 0
}

print_staged_bootstrap_resume() {
    echo
    echo "After ChromeOS boots, finish the root-image repair from VT2:"
    echo
    echo "  1. Press Ctrl+Alt+F2 and log in as chronos"
    echo "  2. sudo -i"
    echo "  3. bash $STAGED_BOOTSTRAP"
    echo "  4. Press Ctrl+Alt+F1 to return to ChromeOS"
    echo
    echo "Then run from this machine:"
    echo "  chromeos post-update --repair"
}

repair_update() {
    require_ssh || return 1
    load_snapshot || return 1
    evaluate_snapshot

    if [[ "$UPDATE_OPERATION" == UPDATE_STATUS_UPDATED_NEED_REBOOT ]]; then
        reboot_for_next_phase \
            "The pending ChromeOS update must boot before its new root image can be repaired." || return 1
        echo "Rebooting into the pending ChromeOS update..."
        ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; reboot" || true
        print_repair_resume
        return 2
    fi

    if [[ "$ROOTFS_WRITABLE" != yes ]]; then
        reboot_for_next_phase \
            "Repair requires disabling rootfs verification on the active ChromeOS image." || return 1

        local kern_part
        kern_part=$(ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; \
ROOTDEV=\$(rootdev -s); PARTNUM=\${ROOTDEV##*p}; echo \$((PARTNUM - 1))" 2>/dev/null)
        case "$kern_part" in
            2|4) ;;
            *)
                echo "[FAIL] Could not safely identify the active kernel partition (got: ${kern_part:-empty})." >&2
                return 1
                ;;
        esac

        echo "Disabling rootfs verification on active kernel partition $kern_part..."
        ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; \
/usr/share/vboot/bin/make_dev_ssd.sh --remove_rootfs_verification --partitions '$kern_part'"
        echo "Rebooting into the writable root image..."
        ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; reboot" || true
        print_staged_bootstrap_resume
        return 2
    fi

    if [[ "$STATUS" == ready ]]; then
        echo "Post-update state is already repaired and reboot-proven."
        emit_audit
        return 0
    fi

    if [[ "$FAIL_COUNT" -eq 0 ]]; then
        echo "Repair is complete but automatic startup has not been proven on this boot."
        emit_audit
        echo
        echo "Run: chromeos post-update --verify-reboot"
        return 1
    fi

    if [[ "$AUTOSTART" != running ||
          "$PREPARED_RELEASE" != "$RELEASE" ||
          "$DEVTOOLS_CONFIGURED" != yes ]]; then
        echo "Installing the current SSH autostart and DevTools configuration..."
        if ! ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; bash -s" < "$REPO_DIR/scripts/bootstrap.sh"; then
            echo "[FAIL] Bootstrap did not complete." >&2
            return 1
        fi
    fi

    # The bootstrap adds the flag but intentionally does not restart Chrome.
    "$SCRIPT_DIR/fix-devtools.sh" -y || true
    ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; rm -f '$STAGED_BOOTSTRAP' '$REPAIR_MARKER'" 2>/dev/null || true

    load_snapshot || return 1
    evaluate_snapshot
    emit_audit
    if [[ "$STATUS" == ready ]]; then
        return 0
    fi
    echo
    echo "Run: chromeos post-update --verify-reboot"
    return 1
}

verify_reboot() {
    require_ssh || return 1
    load_snapshot || return 1

    if [[ "$UPDATE_OPERATION" == UPDATE_STATUS_UPDATED_NEED_REBOOT ||
          "$ROOTFS_WRITABLE" != yes ||
          "$AUTOSTART" != running ||
          "$FALLBACK" != yes ||
          "$PREPARED_RELEASE" != "$RELEASE" ||
          "$DEVTOOLS_CONFIGURED" != yes ]]; then
        echo "[FAIL] The device is not ready for a proof reboot."
        echo "Run: chromeos post-update --repair"
        return 1
    fi

    if ! confirm_reboot "This will reboot ChromeOS and sign out the active profile. Continue?"; then
        echo "Aborted."
        return 1
    fi

    local old_boot_id="$BOOT_ID" new_boot_id="" deadline
    echo "Rebooting ChromeOS to prove automatic SSH startup..."
    ssh "$SSH_HOST" "$REMOTE_PATH_SETUP; reboot" || true

    deadline=$((SECONDS + 150))
    while [[ "$SECONDS" -lt "$deadline" ]]; do
        new_boot_id=$(ssh -o BatchMode=yes -o ConnectTimeout=3 -o ConnectionAttempts=1 \
            "$SSH_HOST" "cat /proc/sys/kernel/random/boot_id" 2>/dev/null || true)
        if [[ -n "$new_boot_id" && "$new_boot_id" != "$old_boot_id" ]]; then
            break
        fi
        sleep 2
    done

    if [[ -z "$new_boot_id" || "$new_boot_id" == "$old_boot_id" ]]; then
        echo "[FAIL] SSH did not return automatically with a new boot ID within 150 seconds."
        print_vt2_ssh_instructions
        return 1
    fi

    # SSH starts before the Chrome UI and DevTools listener. Poll observed
    # readiness instead of treating the first accepted connection as final.
    deadline=$((SECONDS + 90))
    while [[ "$SECONDS" -lt "$deadline" ]]; do
        load_snapshot || return 1
        evaluate_snapshot
        if [[ "$BOOT_EVIDENCE" == automatic &&
              "$AUTOSTART" == running &&
              "$DEVTOOLS_LISTENING" == yes ]]; then
            break
        fi
        sleep 2
    done
    emit_audit
    if [[ "$BOOT_EVIDENCE" != automatic ]]; then
        echo "[FAIL] SSH returned, but the stateful log does not prove automatic startup." >&2
        return 1
    fi
    [[ "$STATUS" == ready ]]
}

case "$MODE" in
    audit)
        require_ssh || exit 1
        load_snapshot || exit 1
        evaluate_snapshot
        emit_audit
        [[ "$STATUS" == ready ]]
        ;;
    repair)
        repair_update
        ;;
    verify-reboot)
        verify_reboot
        ;;
esac
