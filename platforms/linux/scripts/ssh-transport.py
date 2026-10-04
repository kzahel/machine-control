#!/usr/bin/env python3
"""Explicit key-only Linux administration after provider identity checks."""
from __future__ import annotations

import ipaddress
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile


def connection() -> list[str]:
    # The provider supplies an address only after its exact-target guard.
    address = str(ipaddress.ip_address(os.environ["LINUXVM_SSH_ADDRESS"]))
    identifier = os.environ["LINUXVM_EXPECTED_UUID"].lower()
    user = os.environ["LINUXVM_DESKTOP_USER"]
    if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", identifier):
        raise ValueError("exact identity required")
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,30}", user):
        raise ValueError("SSH account required")
    key = os.environ["LINUXVM_SETUP_SSH_KEY_FILE"]
    hosts = os.environ["LINUXVM_SETUP_SSH_KNOWN_HOSTS_FILE"]
    if not Path(key).is_file() or not Path(hosts).is_file():
        raise ValueError("private SSH configuration required")
    # Pin by exact provider UUID, so DHCP changes cannot change authority.
    return ["ssh", "-F", "/dev/null", "-T", "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=yes",
            "-o", f"HostKeyAlias={identifier}", "-o", f"UserKnownHostsFile={hosts}",
            "-o", "GlobalKnownHostsFile=/dev/null", "-o", "HostKeyAlgorithms=ssh-ed25519",
            "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none",
            "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4",
            "-i", key, "-l", user, "--", address]


def run(arguments: list[str]) -> int:
    operation, *args = arguments
    carrier = connection()
    if operation == "exec" and args:
        return subprocess.call(carrier + [shlex.join(["sudo", "-n", "--", *args])])
    if operation == "shell" and not args:
        return subprocess.call(carrier + ["sudo -n -- /usr/bin/bash -l"])
    if operation == "push" and len(args) == 2:
        source, destination = args
        with open(source, "rb") as file:
            return subprocess.call(carrier + [
                shlex.join(["sudo", "-n", "--", "/usr/bin/tee", "--", destination])
                + " >/dev/null"], stdin=file)
    if operation == "pull" and len(args) in {1, 2}:
        command = carrier + [shlex.join(["sudo", "-n", "--", "/usr/bin/cat", "--", args[0]])]
        if len(args) == 1:
            return subprocess.call(command)
        with open(args[1], "wb") as file:
            result = subprocess.call(command, stdout=file)
        if result == 0:
            print(args[1])
        return result
    raise ValueError("invalid SSH transport operation")


def pin_host() -> int:
    identifier = os.environ["LINUXVM_EXPECTED_UUID"].lower()
    if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", identifier):
        raise ValueError("exact identity required")
    address = str(ipaddress.ip_address(os.environ["LINUXVM_SSH_ADDRESS"]))
    words = sys.stdin.read(4097).split()
    if len(words) not in {2, 3} or words[0] != "ssh-ed25519":
        raise ValueError("ED25519 host key required")
    destination = Path(os.environ["LINUXVM_SETUP_SSH_KNOWN_HOSTS_FILE"])
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=destination.parent,
                                         prefix=".host-key-", delete=False) as file:
            temporary = Path(file.name)
            # NamedTemporaryFile already creates mode 0600 on POSIX.
            file.write(f"{identifier} {words[0]} {words[1]}\n")
            file.write(f"{address} {words[0]} {words[1]}\n")
            file.flush()
            os.fsync(file.fileno())
        subprocess.run(["ssh-keygen", "-l", "-f", str(temporary)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        temporary.replace(destination)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    print("Exact guest-agent SSH host key pinned.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(pin_host() if sys.argv[1:] == ["pin-host"] else run(sys.argv[1:]))
    except (KeyError, ValueError, OSError, subprocess.CalledProcessError):
        print("Explicit Linux SSH administration configuration is invalid.", file=sys.stderr)
        raise SystemExit(2)
