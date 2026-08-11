#!/bin/bash

set -uo pipefail

readonly SCHEMA=machine-control-macos-post-update/v0
readonly RESIDENT_LABEL=com.kzahel.macvm-testbed.resident
readonly GUEST_DAEMON_LABEL=org.cirruslabs.tart-guest-daemon
readonly GUEST_AGENT_LABEL=org.cirruslabs.tart-guest-agent
readonly GUEST_DAEMON_PLIST=/Library/LaunchDaemons/org.cirruslabs.tart-guest-daemon.plist
readonly GUEST_AGENT_PLIST=/Library/LaunchAgents/org.cirruslabs.tart-guest-agent.plist

usage() {
    printf '%s\n' \
        'Usage: post-update.sh --mode audit|repair --profile development|runtime --nonce VALUE'
}

mode=audit
profile=development
nonce=
while (( $# > 0 )); do
    case "$1" in
        --mode)
            [[ $# -ge 2 ]] || { usage >&2; exit 2; }
            mode="$2"
            shift 2
            ;;
        --profile)
            [[ $# -ge 2 ]] || { usage >&2; exit 2; }
            profile="$2"
            shift 2
            ;;
        --nonce)
            [[ $# -ge 2 ]] || { usage >&2; exit 2; }
            nonce="$2"
            shift 2
            ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done
if [[ "$mode" != audit && "$mode" != repair ]] ||
        [[ "$profile" != development && "$profile" != runtime ]] ||
        [[ ! "$nonce" =~ ^[a-z0-9]{24}$ ]]; then
    usage >&2
    exit 2
fi

readonly uid="$(/usr/bin/id -u)"
readonly domain="gui/$uid"
readonly home_directory="$HOME"
readonly resident_app="$home_directory/Applications/MacVM UI.app"
readonly resident_binary="$resident_app/Contents/MacOS/macui"
readonly resident_socket_path="$home_directory/Library/Application Support/macvm-testbed/control.sock"
readonly resident_plist="$home_directory/Library/LaunchAgents/$RESIDENT_LABEL.plist"
readonly resident_cli="$home_directory/bin/machine-control"

launchd_ready() {
    /bin/launchctl print "$1/$2" 2>/dev/null |
        /usr/bin/grep -q 'state = running'
}

json_value() {
    printf '%s' "$1" | /usr/bin/plutil -extract "$2" raw -o - - \
        2>/dev/null
}

collect_state() {
    guest_daemon=false
    if launchd_ready system "$GUEST_DAEMON_LABEL"; then guest_daemon=true; fi
    guest_agent=false
    if launchd_ready "$domain" "$GUEST_AGENT_LABEL"; then guest_agent=true; fi

    aqua_session=false
    console_user="$(/usr/bin/stat -f %Su /dev/console 2>/dev/null || true)"
    if [[ -n "$console_user" && "$console_user" != root &&
          "$console_user" != loginwindow ]]; then
        aqua_session=true
    fi

    resident_bundle=false
    if [[ -x "$resident_binary" && -x "$resident_cli" &&
          -f "$resident_plist" ]] &&
            /usr/bin/codesign --verify --deep --strict "$resident_app" \
                >/dev/null 2>&1; then
        resident_bundle=true
    fi
    resident_launch_agent=false
    if launchd_ready "$domain" "$RESIDENT_LABEL"; then
        resident_launch_agent=true
    fi
    resident_socket_ready=false
    if [[ -S "$resident_socket_path" ]]; then resident_socket_ready=true; fi

    target_native=false
    semantic_authorization=false
    capture_authorization=false
    resident_result=
    if [[ "$resident_bundle" == true && "$resident_socket_ready" == true ]]; then
        resident_result="$("$resident_binary" request "$resident_socket_path" \
            '{"operation":"status"}' 2>/dev/null || true)"
        if [[ "$(json_value "$resident_result" schema || true)" == \
                machine-control/v0 ]] &&
                [[ "$(json_value "$resident_result" accepted || true)" == true ]]; then
            if [[ "$(json_value "$resident_result" data.semanticState || true)" == \
                    ready ]]; then
                semantic_authorization=true
            fi
            if [[ "$(json_value "$resident_result" data.captureState || true)" == \
                    ready ]]; then
                capture_authorization=true
            fi
            if [[ "$semantic_authorization" == true &&
                  "$capture_authorization" == true ]]; then
                target_native=true
            fi
        fi
    fi

    profile_tools=true
    if [[ "$profile" == development ]]; then
        if [[ ! -x /usr/bin/python3 ]] ||
                ! /usr/bin/xcrun --find git >/dev/null 2>&1 ||
                ! /usr/bin/xcrun --find swiftc >/dev/null 2>&1; then
            profile_tools=false
        fi
    fi
}

daemon_repair=not_requested
agent_repair=not_requested
resident_repair=not_requested
if [[ "$mode" == repair ]]; then
    collect_state
    daemon_repair=not_needed
    if [[ "$guest_daemon" != true ]]; then
        daemon_repair=not_repairable
        if [[ -f "$GUEST_DAEMON_PLIST" ]]; then
            /usr/bin/sudo -n /bin/launchctl bootstrap system \
                "$GUEST_DAEMON_PLIST" >/dev/null 2>&1 || true
            if /usr/bin/sudo -n /bin/launchctl kickstart -k \
                    "system/$GUEST_DAEMON_LABEL" >/dev/null 2>&1; then
                daemon_repair=restarted
            fi
        fi
    fi
    agent_repair=not_needed
    if [[ "$guest_agent" != true ]]; then
        agent_repair=not_repairable
        if [[ -f "$GUEST_AGENT_PLIST" ]]; then
            /bin/launchctl bootstrap "$domain" "$GUEST_AGENT_PLIST" \
                >/dev/null 2>&1 || true
            if /bin/launchctl kickstart -k "$domain/$GUEST_AGENT_LABEL" \
                    >/dev/null 2>&1; then
                agent_repair=restarted
            fi
        fi
    fi
    resident_repair=not_needed
    if [[ "$resident_launch_agent" != true || "$resident_socket_ready" != true ||
          "$target_native" != true ]]; then
        resident_repair=not_repairable
        if [[ "$resident_bundle" == true ]]; then
            /bin/launchctl bootstrap "$domain" "$resident_plist" \
                >/dev/null 2>&1 || true
            if /bin/launchctl kickstart -k "$domain/$RESIDENT_LABEL" \
                    >/dev/null 2>&1; then
                resident_repair=restarted
            fi
        fi
    fi
    for _ in 1 2 3 4 5; do
        collect_state
        if [[ "$resident_launch_agent" == true &&
              "$resident_socket_ready" == true && "$target_native" == true ]]; then
            break
        fi
        /bin/sleep 1
    done
else
    collect_state
fi

healthy=true
for required_state in "$guest_daemon" "$guest_agent" "$aqua_session" \
        "$resident_bundle" "$resident_launch_agent" "$resident_socket_ready" \
        "$semantic_authorization" "$capture_authorization" "$target_native" \
        "$profile_tools"; do
    if [[ "$required_state" != true ]]; then healthy=false; fi
done

check_json() {
    local id="$1" required="$2" ready="$3" pass_state="$4" fail_state="$5"
    local state="$fail_state"
    if [[ "$ready" == true ]]; then state="$pass_state"; fi
    printf '{"id":"%s","required":%s,"healthy":%s,"state":"%s"}' \
        "$id" "$required" "$ready" "$state"
}

checks="$(check_json guest_daemon true "$guest_daemon" active unavailable),"
checks+="$(check_json guest_user_agent true "$guest_agent" active unavailable),"
checks+="$(check_json aqua_session true "$aqua_session" unlocked unavailable),"
checks+="$(check_json resident_bundle true "$resident_bundle" verified unavailable),"
checks+="$(check_json resident_launch_agent true "$resident_launch_agent" active unavailable),"
checks+="$(check_json resident_socket true "$resident_socket_ready" ready unavailable),"
checks+="$(check_json semantic_authorization true "$semantic_authorization" ready unavailable),"
checks+="$(check_json capture_authorization true "$capture_authorization" ready unavailable),"
checks+="$(check_json target_native true "$target_native" ready unavailable),"
checks+="$(check_json profile_tools true "$profile_tools" available missing),"
checks+="$(check_json pending_reboot false false not_required not_observable)"

repairs='[]'
if [[ "$mode" == repair ]]; then
    repairs="[{\"id\":\"guest_daemon\",\"status\":\"$daemon_repair\"},"
    repairs+="{\"id\":\"guest_user_agent\",\"status\":\"$agent_repair\"},"
    repairs+="{\"id\":\"resident_launch_agent\",\"status\":\"$resident_repair\"}]"
fi

printf '%s\n' \
    "{\"schema\":\"$SCHEMA\",\"mode\":\"$mode\",\"profile\":\"$profile\",\"nonce\":\"$nonce\",\"healthy\":$healthy,\"checks\":[$checks],\"repairs\":$repairs}"
[[ "$healthy" == true ]]
