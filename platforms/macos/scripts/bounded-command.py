#!/usr/bin/env python3
"""Run one host command with a deadline, including its child processes."""

import argparse
import os
import signal
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if args.seconds < 1 or not command:
        parser.error("a positive deadline and command are required")
    try:
        child = subprocess.Popen(command, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL,
                                 start_new_session=True)
    except OSError:
        return 127
    try:
        output, _ = child.communicate(timeout=args.seconds)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.communicate()
        return 124
    sys.stdout.buffer.write(output)
    return child.returncode


if __name__ == "__main__":
    raise SystemExit(main())
