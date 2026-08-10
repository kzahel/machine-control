#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

readonly LINUXVM="$LINUXVM_REPO_DIR/bin/linuxvm"
readonly UI_SOURCE="$LINUXVM_REPO_DIR/guests/ubuntu/ui/linuxui.py"
readonly CONTROL_SOURCE="$LINUXVM_REPO_DIR/guests/ubuntu/ui/linuxcontrol.py"
readonly CLIENT_SOURCE="$LINUXVM_REPO_DIR/guests/ubuntu/ui/machine-control"
readonly UNIT_SOURCE="$LINUXVM_REPO_DIR/guests/ubuntu/ui/linuxvm-control.service"
readonly INPUT_SOURCE="$LINUXVM_REPO_DIR/guests/ubuntu/input/linuxinputd.py"
readonly INPUT_UNIT_SOURCE="$LINUXVM_REPO_DIR/guests/ubuntu/input/linuxvm-input.service"
readonly FIXTURE_SOURCE="$LINUXVM_REPO_DIR/guests/ubuntu/fixtures/control_fixture.py"
readonly FIXTURE_UNIT_SOURCE="$LINUXVM_REPO_DIR/guests/ubuntu/fixtures/linuxvm-fixture.service"
readonly STAGING="/var/tmp/linuxvm-resident.$$"

linuxvm_assert_mutation_target
if ! "$LINUXVM" exec -- /usr/bin/dpkg-query -W \
        gnome-screenshot python3-evdev wl-clipboard >/dev/null 2>&1; then
    "$LINUXVM" exec -- /usr/bin/apt-get update -qq
    "$LINUXVM" exec -- /usr/bin/env DEBIAN_FRONTEND=noninteractive \
        /usr/bin/apt-get install -y gnome-screenshot python3-evdev wl-clipboard
fi
user="$($LINUXVM desktop-user)"
uid="$($LINUXVM exec -- /usr/bin/id -u "$user")"
group="$($LINUXVM exec -- /usr/bin/id -gn "$user")"
home="$($LINUXVM exec -- /usr/bin/getent passwd "$user" \
    | /usr/bin/awk -F: '{print $6}')"
[[ -n "$user" && -n "$uid" && -n "$group" && -n "$home" ]] || {
    printf 'Unable to resolve the active desktop account\n' >&2
    exit 1
}

for source in "$UI_SOURCE" "$CONTROL_SOURCE" "$CLIENT_SOURCE" "$UNIT_SOURCE" \
        "$INPUT_SOURCE" "$INPUT_UNIT_SOURCE" "$FIXTURE_SOURCE" \
        "$FIXTURE_UNIT_SOURCE"; do
    "$LINUXVM" push "$source" "$STAGING.$(/usr/bin/basename "$source")"
done

"$LINUXVM" exec -- /usr/bin/install -d -m 0755 \
    /usr/local/libexec/linuxvm-testbed /usr/local/bin
"$LINUXVM" exec -- /usr/bin/install -m 0755 \
    "$STAGING.linuxui.py" /usr/local/libexec/linuxvm-testbed/linuxui.py
"$LINUXVM" exec -- /usr/bin/install -m 0755 \
    "$STAGING.linuxcontrol.py" /usr/local/libexec/linuxvm-testbed/linuxcontrol.py
"$LINUXVM" exec -- /usr/bin/install -m 0755 \
    "$STAGING.linuxinputd.py" /usr/local/libexec/linuxvm-testbed/linuxinputd.py
"$LINUXVM" exec -- /usr/bin/install -m 0755 \
    "$STAGING.control_fixture.py" \
    /usr/local/libexec/linuxvm-testbed/control_fixture.py
"$LINUXVM" exec -- /usr/bin/install -m 0755 \
    "$STAGING.machine-control" /usr/local/bin/machine-control
"$LINUXVM" exec -- /usr/bin/install -d -m 0755 -o "$user" -g "$group" \
    "$home/.config/systemd/user"
"$LINUXVM" exec -- /usr/bin/install -m 0644 -o "$user" -g "$group" \
    "$STAGING.linuxvm-control.service" \
    "$home/.config/systemd/user/linuxvm-control.service"
"$LINUXVM" exec -- /usr/bin/install -m 0644 -o "$user" -g "$group" \
    "$STAGING.linuxvm-fixture.service" \
    "$home/.config/systemd/user/linuxvm-fixture.service"
"$LINUXVM" exec -- /usr/bin/install -m 0644 \
    "$STAGING.linuxvm-input.service" /etc/systemd/system/linuxvm-input.service
"$LINUXVM" exec -- /bin/rm -f \
    "$STAGING.linuxui.py" "$STAGING.linuxcontrol.py" \
    "$STAGING.machine-control" "$STAGING.linuxvm-control.service"
"$LINUXVM" exec -- /bin/rm -f \
    "$STAGING.linuxinputd.py" "$STAGING.linuxvm-input.service" \
    "$STAGING.control_fixture.py" "$STAGING.linuxvm-fixture.service"

"$LINUXVM" exec -- /usr/bin/systemctl daemon-reload
"$LINUXVM" exec -- /usr/bin/systemctl enable linuxvm-input.service >/dev/null
"$LINUXVM" exec -- /usr/bin/systemctl restart linuxvm-input.service
for _ in {1..30}; do
    if "$LINUXVM" exec -- /usr/bin/test -S /run/linuxvm-testbed/input.sock; then
        break
    fi
    sleep 0.2
done
"$LINUXVM" exec -- /usr/bin/test -S /run/linuxvm-testbed/input.sock

"$LINUXVM" user-exec -- /usr/bin/systemctl --user daemon-reload
"$LINUXVM" user-exec -- /usr/bin/systemctl --user enable \
    linuxvm-control.service >/dev/null
"$LINUXVM" user-exec -- /usr/bin/systemctl --user restart \
    linuxvm-control.service

for _ in {1..30}; do
    if result="$($LINUXVM control-local '{"operation":"status"}' \
            2>/dev/null)" &&
            jq -e '.accepted == true and .data.semanticState == "ready"' \
                >/dev/null <<<"$result"; then
        printf 'LinuxVM resident deployed for the active desktop session.\n'
        exit 0
    fi
    sleep 0.2
done

"$LINUXVM" user-exec -- /usr/bin/systemctl --user status \
    linuxvm-control.service --no-pager >&2 || true
printf 'Resident did not become ready\n' >&2
exit 1
