#!/usr/bin/env python3
"""Package the current bootstrap with one controller public key for VT2."""

import argparse
from pathlib import Path
import shlex
import subprocess
from urllib.parse import urlsplit


def prepare(public_key: Path, output: Path, report_url: str | None = None) -> None:
    if report_url:
        parsed = urlsplit(report_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Report URL must be HTTP(S) without embedded credentials")
    key = public_key.read_text().strip()
    if len(key.splitlines()) != 1 or len(key.split()) < 2:
        raise ValueError("Expected one OpenSSH public key")
    # Drop the optional comment; never package private key material or options.
    kind, data = key.split()[:2]
    if not kind.startswith(("ssh-", "ecdsa-", "sk-")):
        raise ValueError("Expected an OpenSSH public key, not a private key")
    subprocess.run(
        ["ssh-keygen", "-l", "-f", str(public_key)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    source = Path(__file__).with_name("bootstrap.sh").read_text()
    bundle = (
        "#!/bin/bash\n"
        "# Generated locally; contains a controller PUBLIC key. Do not commit.\n"
        f"export CHROMEOS_TESTBED_CONTROLLER_PUBKEY={shlex.quote(kind + ' ' + data)}\n"
        + (f"export CHROMEOS_TESTBED_REPORT_URL={shlex.quote(report_url)}\n" if report_url else "")
        + source
    )
    with output.open("x") as handle:
        handle.write(bundle)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("public_key", type=Path)
    parser.add_argument("output", type=Path, help="New file in a temporary serving directory")
    parser.add_argument("--report-url", help="Explicit controller endpoint for private network diagnostics")
    args = parser.parse_args()
    try:
        prepare(args.public_key, args.output, args.report_url)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Cannot prepare bootstrap: {exc}\n")
    print(f"Prepared {args.output}. Serve only its temporary directory on a trusted LAN.")


if __name__ == "__main__":
    main()
