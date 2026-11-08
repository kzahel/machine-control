#!/usr/bin/env python3
"""Build the on-device ``login`` request for ``chromeos login``.

Reads the PIN from a configured file, standard input, or a hidden terminal
prompt and writes one JSON request line to standard output, which the CLI
pipes directly into the device client over SSH. The PIN never appears in
arguments, the environment, or error messages.
"""

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import stat
import sys

MAX_PIN_DIGITS = 20
PIN_LINE = re.compile(rb"[0-9]{4,%d}(?:\r?\n)?" % MAX_PIN_DIGITS)


class RequestError(Exception):
    pass


def read_pin_file(path):
    """Open the configured PIN file only if it is private to the caller."""
    path = Path(path)
    if not path.is_absolute():
        raise RequestError("The configured ChromeOS PIN file locator must be absolute")
    descriptor = None
    try:
        parent = path.parent.lstat()
        if not stat.S_ISDIR(parent.st_mode) or path.is_symlink():
            raise RequestError("The configured ChromeOS PIN file is unsafe")
        if os.name != "nt" and (
            parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) != 0o700
        ):
            raise RequestError("The ChromeOS PIN directory must be caller-owned and mode 0700")
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0),
        )
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise RequestError("The configured ChromeOS PIN file must be a regular file")
        if os.name != "nt" and (
            info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise RequestError("The ChromeOS PIN file must be caller-owned and mode 0600")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            value = stream.read(MAX_PIN_DIGITS + 3)
    except OSError:
        raise RequestError("The configured ChromeOS PIN file is unavailable or unsafe") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if not PIN_LINE.fullmatch(value):
        raise RequestError(f"The ChromeOS PIN file must contain one 4 to {MAX_PIN_DIGITS} digit PIN")
    return value.rstrip(b"\r\n").decode("ascii")


def read_pin_stream(stream):
    value = stream.read(MAX_PIN_DIGITS + 3)
    if not PIN_LINE.fullmatch(value):
        raise RequestError(f"A ChromeOS PIN must contain 4 to {MAX_PIN_DIGITS} digits")
    return value.rstrip(b"\r\n").decode("ascii")


def read_pin_prompt():
    try:
        value = getpass.getpass("PIN for the ChromeOS account: ").encode("ascii")
    except (EOFError, UnicodeEncodeError):
        raise RequestError("No PIN was entered") from None
    return read_pin_stream(_Bytes(value))


class _Bytes:
    def __init__(self, value):
        self.value = value

    def read(self, _size):
        return self.value


def build_request(account, pin, timeout):
    request = {"cmd": "login", "pin": pin, "timeout": timeout}
    if account:
        request["account"] = account
    return json.dumps(request)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--pin-file", help="private file containing the PIN")
    source.add_argument("--stdin", action="store_true", help="read the PIN from standard input")
    parser.add_argument("--account", default="", help="account email to sign in")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        if args.pin_file:
            if not args.account:
                raise RequestError(
                    "A configured PIN file requires an explicit account "
                    "(--account or CHROMEOS_TESTBED_ACCOUNT)"
                )
            pin = read_pin_file(os.path.expanduser(args.pin_file))
        elif args.stdin:
            pin = read_pin_stream(sys.stdin.buffer)
        elif sys.stdin.isatty():
            pin = read_pin_prompt()
        else:
            raise RequestError(
                "No PIN source: configure CHROMEOS_TESTBED_PIN_FILE, pass --pin-stdin, "
                "or run on a terminal for the hidden prompt"
            )
    except RequestError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    sys.stdout.write(build_request(args.account.strip().lower(), pin, args.timeout) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
