#!/usr/bin/env bash
set -euo pipefail

HERE=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MODE=${1:-}
SCREEN_WAKE_HELPER=${STEAMDECK_TESTBED_SCREEN_WAKE_HELPER:-"$HERE/screen-wake.py"}
RUNTIME_DIR=${XDG_RUNTIME_DIR:-"/run/user/$(id -u)"}
WATCHER_UNIT=steamdeck-testbed-screen-wake.service
WATCHER_STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/steamdeck-testbed/screen-wake"
WATCHER_READY="$WATCHER_STATE_DIR/ready"

case "$MODE" in
    off)
        requested=true
        expected=disabled
        label=off
        ;;
    on)
        requested=false
        expected=enabled
        label=on
        ;;
    *)
        echo "usage: $0 off|on" >&2
        exit 2
        ;;
esac

gamescope_display=
if [[ -n ${GAMESCOPE_WAYLAND_DISPLAY:-} ]] &&
    [[ -S "$RUNTIME_DIR/$GAMESCOPE_WAYLAND_DISPLAY" ]]; then
    gamescope_display=$GAMESCOPE_WAYLAND_DISPLAY
else
    for path in "$RUNTIME_DIR"/gamescope-[0-9]*; do
        [[ -S $path ]] || continue
        name=${path##*/}
        [[ $name =~ ^gamescope-[0-9]+$ ]] || continue
        gamescope_display=$name
        break
    done
fi
[[ -n $gamescope_display ]] || {
    echo "steamdeck: active Gaming Mode Gamescope socket not found" >&2
    exit 1
}
command -v gamescopectl >/dev/null 2>&1 || {
    echo "steamdeck: gamescopectl is unavailable" >&2
    exit 1
}

stop_watcher()
{
    systemctl --user stop "$WATCHER_UNIT" >/dev/null 2>&1 || true
    systemctl --user reset-failed "$WATCHER_UNIT" >/dev/null 2>&1 || true
    rm -f -- "$WATCHER_READY"
}

if [[ $requested == true ]]; then
    [[ -x $SCREEN_WAKE_HELPER ]] || {
        echo "steamdeck: screen wake helper is unavailable" >&2
        exit 1
    }
    stop_watcher
    install -d -m 700 "$WATCHER_STATE_DIR"
    systemd-run \
        --user \
        --unit="$WATCHER_UNIT" \
        --collect \
        --quiet \
        /usr/bin/env \
        "XDG_RUNTIME_DIR=$RUNTIME_DIR" \
        "GAMESCOPE_WAYLAND_DISPLAY=$gamescope_display" \
        /usr/bin/python3 \
        "$SCREEN_WAKE_HELPER" \
        "$WATCHER_READY"
    for _attempt in {1..50}; do
        [[ -f $WATCHER_READY ]] && break
        systemctl --user is-active --quiet "$WATCHER_UNIT" || {
            journalctl --user -u "$WATCHER_UNIT" -n 20 --no-pager >&2 || true
            echo "steamdeck: local-input screen wake watcher failed to start" >&2
            exit 1
        }
        sleep 0.1
    done
    [[ -f $WATCHER_READY ]] || {
        stop_watcher
        echo "steamdeck: local-input screen wake watcher did not arm" >&2
        exit 1
    }
else
    stop_watcher
fi

cleanup_failed_sleep()
{
    if [[ $requested == true ]]; then
        XDG_RUNTIME_DIR=$RUNTIME_DIR \
        GAMESCOPE_WAYLAND_DISPLAY=$gamescope_display \
            gamescopectl drm_sleep_internal_screen false >/dev/null 2>&1 || true
        stop_watcher
    fi
}
trap cleanup_failed_sleep ERR

XDG_RUNTIME_DIR=$RUNTIME_DIR \
GAMESCOPE_WAYLAND_DISPLAY=$gamescope_display \
    gamescopectl drm_sleep_internal_screen "$requested"

connector=
for path in /sys/class/drm/card*-eDP-*; do
    [[ -e $path ]] || continue
    connector=$path
    break
done
[[ -n $connector ]] || {
    echo "steamdeck: internal eDP connector not found" >&2
    exit 1
}

state=unknown
for _attempt in {1..20}; do
    state=$(cat "$connector/enabled" 2>/dev/null || echo unknown)
    [[ $state == "$expected" ]] && break
    sleep 0.1
done
[[ $state == "$expected" ]] || {
    echo "steamdeck: internal connector did not become $expected (state=$state)" >&2
    exit 1
}
trap - ERR
printf \
    'Deck internal screen: %s (%s=%s); SSH remains reachable%s\n' \
    "$label" "${connector##*/}" "$state" \
    "$([[ $requested == true ]] && printf '; local Deck-button wake armed' || true)"
