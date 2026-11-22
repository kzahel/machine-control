#!/bin/sh
set -eu

if [ "${1:-}" = remove ] &&
   { [ -d /var/lib/machine-control-locked-use ] ||
     [ -f /etc/systemd/system/machine-control-locked-use.service ]; }; then
    /usr/bin/python3 -I -B /usr/lib/machine-control/locked-runtime/locked-credential.py remove
fi
