"""Sign native product code before sealing Python scripts in the Mac bundle."""

import argparse
import importlib.util
from pathlib import Path
import subprocess


def sign(app, identity):
    resources = app / "Contents/Resources"
    nested = [(app / "Contents/Frameworks/MCResident.framework", None),
              (resources / "mc-session-probe", None),
              (resources / "shared-policy/node", None),
              (resources / "mc-sudo", "org.machine-control.sudo"),
              (resources / "mc-sudo-askpass", "org.machine-control.sudo.askpass")]
    nested.extend((resources / "unlock" / name, None) for name in
                  ("mc-unlock-broker", "mc-unlock-install", "mc-session-probe", "MCUnlock.bundle"))
    for path in sorted((resources / "mc-cli").rglob("*")):
        if not path.is_file():
            continue
        with path.open("rb") as stream:
            magic = stream.read(4)
        if magic in {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}:
            nested.append((path, None))
    for path, identifier in nested:
        command = ["codesign", "--force", "--options", "runtime", "--sign", identity]
        if identity != "-":
            command += ["--timestamp"]
        if path == resources / "shared-policy/node":
            entitlements = Path(__file__).resolve().parents[2] / 'platforms/macos/resident/app/node-entitlements.plist'
            command += ["--entitlements", str(entitlements)]
        if identifier:
            command += ["--identifier", identifier]
        subprocess.run([*command, str(path)], check=True, stdout=subprocess.DEVNULL)
    policy_script = Path(__file__).resolve().parents[2] / 'platforms/macos/resident/scripts/prepare-policy.py'
    spec = importlib.util.spec_from_file_location("prepare_policy", policy_script)
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    policy.seal(resources / 'shared-policy')
    spec = importlib.util.spec_from_file_location("prepare_cli", Path(__file__).with_name("prepare-cli.py"))
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.inventory(resources / "mc-cli")
    command = ["codesign", "--force", "--options", "runtime", "--sign", identity]
    if identity == "-":
        command += ["--identifier", "org.machine-control.app", "--requirements", '=designated => identifier "org.machine-control.app"']
    else:
        command += ["--timestamp"]
    subprocess.run([*command, str(app)], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("app", type=Path)
    parser.add_argument("--identity", required=True)
    args = parser.parse_args()
    sign(args.app, args.identity)
