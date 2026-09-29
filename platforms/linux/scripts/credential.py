#!/usr/bin/env python3
"""Private Linux appliance credential verification; no password in argv/JSON."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tempfile
import time


SCHEMA = "linuxvm-credential-handoff/v0"
ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/linuxvm"
MAX_AGE = 24 * 60 * 60

# Only the result leaves the guest. The password arrives once on SSH stdin;
# neither the shadow entry nor its hash is returned through guest-agent JSON.
VERIFY_SCRIPT = """
import ctypes, hmac, spwd, sys, time
try:
    entry = spwd.getspnam(sys.argv[1])
    today = int(time.time() // 86400)
    if entry.sp_expire >= 0 and today >= entry.sp_expire:
        raise ValueError()
    if entry.sp_lstchg == 0 or (entry.sp_max >= 0 and
            today >= entry.sp_lstchg + entry.sp_max):
        raise ValueError()
    stored = entry.sp_pwdp
    if sys.argv[2] == 'password-free':
        valid = stored.startswith(('!', '*'))
    else:
        password = sys.stdin.buffer.read(4097).removesuffix(b'\\n')
        if not password or len(password) > 4096 or any(c in password for c in (b'\\n', b'\\r', b'\\0')):
            raise ValueError()
        lib = ctypes.CDLL('libcrypt.so.1')
        lib.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        lib.crypt.restype = ctypes.c_char_p
        actual = lib.crypt(password, stored.encode())
        valid = bool(actual and not stored.startswith(('!', '*')) and
                     hmac.compare_digest(actual, stored.encode()))
    if not valid:
        raise ValueError()
except Exception:
    sys.exit(1)
print('verified')
"""


class Refusal(Exception):
    pass


def command(*arguments: str, input_bytes: bytes | None = None) -> str:
    try:
        result = subprocess.run(arguments, input=input_bytes, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Refusal("verification_route_unavailable") from None
    if result.returncode:
        raise Refusal("guest_verification_failed")
    return result.stdout.decode("utf-8", errors="strict").strip()


def configuration() -> dict:
    identifier = os.environ.get("LINUXVM_EXPECTED_UUID", "").lower()
    provider = os.environ.get("LINUXVM_PROVIDER", "")
    user = os.environ.get("LINUXVM_DESKTOP_USER", "")
    profile = os.environ.get("LINUXVM_CREDENTIAL_PROFILE", "password")
    if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", identifier):
        raise Refusal("exact_identity_required")
    if provider not in {"utm-macos", "libvirt-linux"}:
        raise Refusal("credential_provider_unsupported")
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,30}", user):
        raise Refusal("credential_account_required")
    if profile not in {"password", "password-free"}:
        raise Refusal("credential_profile_invalid")
    if command(str(CLI), "target-id").lower() != identifier:
        raise Refusal("exact_identity_mismatch")
    secret = os.environ.get("LINUXVM_LOGIN_SECRET_FILE", "")
    if profile == "password" and not secret:
        raise Refusal("credential_locator_missing")
    return {"targetId": identifier, "provider": provider, "account": user,
            "profile": profile, "secretFile": secret if profile == "password" else None}


def open_secret(path: str) -> tuple[int, dict]:
    """Check ownership/type/permissions without consuming any password bytes."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise Refusal("credential_file_unavailable") from None
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.getuid() or not 0 < info.st_size <= 4097):
        os.close(fd)
        raise Refusal("credential_file_invalid")
    return fd, {"device": info.st_dev, "inode": info.st_ino, "size": info.st_size,
                "modifiedNs": info.st_mtime_ns, "changedNs": info.st_ctime_ns}


def receipt_path(config: dict) -> Path:
    root = Path(os.environ.get("LINUXVM_CREDENTIAL_STATE_DIR") or str(
        Path.home() / ".local/state/machine-control/linux-credentials"))
    return root / f"{config['provider']}-{config['targetId']}.json"


def write_receipt(config: dict, fingerprint: dict | None) -> None:
    path = receipt_path(config)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent,
                                         prefix=".credential-", delete=False) as file:
            temporary = Path(file.name)
            os.fchmod(file.fileno(), 0o600)
            json.dump({"schema": SCHEMA, **config, "fileIdentity": fingerprint,
                       "verifiedAt": time.time()}, file)
            file.write("\n")
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def recorded(config: dict, fingerprint: dict | None) -> bool:
    try:
        path = receipt_path(config)
        if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
            return False
        record = json.loads(path.read_text())
        observed = record.get("verifiedAt")
        return (record.get("schema") == SCHEMA
                and all(record.get(key) == value for key, value in config.items())
                and record.get("fileIdentity") == fingerprint
                and type(observed) in (int, float)
                and 0 <= time.time() - observed <= MAX_AGE)
    except (OSError, ValueError, AttributeError):
        return False


def verification_route(config: dict) -> list[str]:
    user = config["account"]
    account = command(str(CLI), "exec", "--", "/usr/bin/getent", "passwd", user)
    if len(account.splitlines()) != 1 or account.split(":")[0] != user:
        raise Refusal("credential_account_unverified")
    if config["profile"] == "password-free":
        return [str(CLI), "exec", "--", "/usr/bin/python3", "-W", "ignore",
                "-c", VERIFY_SCRIPT, user, "password-free"]
    key = os.environ.get("LINUXVM_SETUP_SSH_KEY_FILE", "")
    known_hosts = os.environ.get("LINUXVM_SETUP_SSH_KNOWN_HOSTS_FILE", "")
    if not key or not known_hosts or not Path(key).is_file() or not Path(known_hosts).is_file():
        raise Refusal("credential_ssh_configuration_required")
    try:
        address = str(ipaddress.ip_address(command(str(CLI), "ip")))
    except ValueError:
        raise Refusal("credential_address_unverified") from None
    public_key = command(str(CLI), "exec", "--", "/usr/bin/cat",
                         "/etc/ssh/ssh_host_ed25519_key.pub").split()
    entries = command("ssh-keygen", "-F", address, "-f", known_hosts).splitlines()
    if (len(public_key) < 2 or public_key[0] != "ssh-ed25519" or not any(
            line.split()[1:3] == public_key[:2] for line in entries
            if line and not line.startswith("#"))):
        raise Refusal("credential_host_key_unverified")
    remote = shlex.join(["sudo", "-n", "/usr/bin/python3", "-W", "ignore",
                         "-c", VERIFY_SCRIPT, user, "password"])
    return ["ssh", "-F", "/dev/null", "-T", "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={known_hosts}",
            "-o", "GlobalKnownHostsFile=/dev/null", "-o", "HostKeyAlgorithms=ssh-ed25519",
            "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none", "-i", key,
            "-l", user, "--", address, remote]


def inspect(operation: str) -> dict:
    config = configuration()
    fd = None
    try:
        fingerprint = None
        if config["profile"] == "password":
            fd, fingerprint = open_secret(config["secretFile"])
        if operation == "verify":
            # Drop previous evidence first: a failed recheck must not retain it.
            receipt_path(config).unlink(missing_ok=True)
            route = verification_route(config)
            password = os.read(fd, 4098) if fd is not None else None
            if command(*route, input_bytes=password) != "verified":
                raise Refusal("guest_verification_failed")
            if fd is not None:
                other, current = open_secret(config["secretFile"])
                os.close(other)
                if current != fingerprint:
                    raise Refusal("credential_file_changed")
            write_receipt(config, fingerprint)
        ready = recorded(config, fingerprint)
        return {"schema": SCHEMA, "ready": ready, "profile": config["profile"],
                "evidence": "guest_password_hash_verified" if ready and fd is not None else
                "explicit_locked_password_profile_verified" if ready else
                "credential_verification_required"}
    finally:
        if fd is not None:
            os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("status", "verify"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = inspect(args.operation)
    except (Refusal, OSError, UnicodeError) as error:
        result = {"schema": SCHEMA, "ready": False, "profile": "unknown",
                  "evidence": str(error) if isinstance(error, Refusal) else
                  "credential_verification_unavailable"}
    print(json.dumps(result) if args.json else result["evidence"])
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
