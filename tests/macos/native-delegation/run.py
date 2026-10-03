#!/usr/bin/env python3
"""Run signed YA/MC native delegation acceptance in a claimed Mac appliance.

Requires signed candidates, an initialized isolated credentialed YA profile,
its private owner-session cookie fixture and the deployed native AppKit fixture.
The caller owns target readiness, claim lifetime and power cleanup. Never use a
personal workstation: the runner temporarily installs YA at its canonical path
and selects approval policy while retaining a separate appliance resident.
"""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--claim", required=True)
    parser.add_argument("--registry")
    parser.add_argument("--mc-app", type=Path, required=True)
    parser.add_argument("--ya-app", type=Path, required=True)
    parser.add_argument("--auth-data", type=Path, required=True)
    parser.add_argument("--auth-session-file", type=Path, required=True)
    parser.add_argument("--keep-artifacts", action="store_true")
    args = parser.parse_args()
    if args.target == "host":
        parser.error("This runner requires a dedicated Mac appliance")
    if args.auth_session_file.stat().st_mode & 0o077:
        parser.error("The owner cookie fixture must have mode 0600")
    proof = json.loads(args.auth_session_file.read_text())
    if not isinstance(proof.get("cookie"), str) or not proof["cookie"]:
        parser.error("The cookie fixture must contain a nonempty owner-session cookie")
    for app in (args.mc_app, args.ya_app):
        subprocess.run(
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)],
            check=True,
            capture_output=True,
        )
    mc = [str(ROOT / "bin/machine-control")]
    if args.registry:
        mc += ["--registry", args.registry]
    mc += ["--target", args.target, "--claim", args.claim, "testbed", "--", "exec"]
    remote = subprocess.check_output(
        mc + ["/usr/bin/mktemp", "-d", "/tmp/mc-native-delegation.XXXXXX"],
        text=True,
        timeout=60,
    ).strip()
    if (
        not remote.startswith("/tmp/mc-native-delegation.")
        or "/" in remote[len("/tmp/") :]
    ):
        raise RuntimeError("Unexpected private fixture directory")
    safe_to_remove = False
    try:
        with tempfile.TemporaryDirectory(
            prefix="mc-native-delegation-upload-"
        ) as directory:
            stage = Path(directory)
            shutil.copytree(args.auth_data, stage / "data")
            (stage / "auth.private.json").write_text(
                json.dumps({"cookie": proof["cookie"]})
            )
            (stage / "auth.private.json").chmod(0o600)
            shutil.copy2(FIXTURES / "codex-fixture.py", stage / "codex-fixture.py")
            (stage / "codex-fixture.py").chmod(0o700)

            def send(parent, name):
                tar = subprocess.Popen(
                    ["/usr/bin/tar", "-C", str(parent), "-cf", "-", name],
                    stdout=subprocess.PIPE,
                )
                try:
                    transfer = subprocess.run(
                        mc + ["-i", "/usr/bin/tar", "-xf", "-", "-C", remote],
                        stdin=tar.stdout,
                        capture_output=True,
                        timeout=180,
                    )
                finally:
                    tar.stdout.close()
                if tar.wait(timeout=15) or transfer.returncode:
                    raise RuntimeError("Claimed fixture transfer failed")

            for name in ("data", "auth.private.json", "codex-fixture.py"):
                send(stage, name)
            for app, name in (
                (args.mc_app, "Machine Control.app"),
                (args.ya_app, "YepAnywhere.app"),
            ):
                if app.name != name:
                    raise RuntimeError(
                        "Use the signed candidate's original bundle name"
                    )
                send(app.parent, name)
        result = subprocess.run(
            mc + ["-i", "/usr/bin/python3", "-", remote],
            input=(FIXTURES / "guest.py").read_text(),
            text=True,
            timeout=300,
        )
        # Refuse cleanup if recovery material is still needed. The guest checks
        # restored socket/application state independently of its test outcome.
        verification = """import pathlib,sys,json
root=pathlib.Path(sys.argv[1]); standard=pathlib.Path.home()/'Library/Application Support/MachineControl/control.sock'
assert standard.exists() and not pathlib.Path(str(standard)+'.qa-upstream').exists()
assert not (root/'previous-ya.app').exists()
assert json.loads((root/'restoration.json').read_text())['passed'] is True
"""
        subprocess.run(
            mc + ["-i", "/usr/bin/python3", "-", remote],
            input=verification,
            text=True,
            check=True,
            timeout=60,
        )
        safe_to_remove = True
        if result.returncode:
            raise RuntimeError("Signed native delegation acceptance failed")
        print(
            "PASS signed app enrollment, independent AX effects, Pause/Resume, Stop and unrelated-caller refusal"
        )
    finally:
        if safe_to_remove and not args.keep_artifacts:
            subprocess.run(
                mc + ["/bin/rm", "-rf", "--", remote], check=True, timeout=60
            )
        elif args.keep_artifacts:
            print(
                "Private guest artifacts retained for the caller's diagnostic cleanup"
            )


if __name__ == "__main__":
    main()
