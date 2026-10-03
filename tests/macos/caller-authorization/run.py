#!/usr/bin/env python3
"""Exercise OS peer identity on private fixture sockets, never the MC service."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import selectors
import shutil
import subprocess
import sys
import tempfile


def run(argv, timeout=30, cwd=None):
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("DYLD_") and key not in
                   {"NODE_OPTIONS", "BUN_OPTIONS", "BUN_INSPECT", "LD_PRELOAD"}}
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                            cwd=cwd, env=environment)
    if result.returncode:
        # Tool output can contain local paths and signing identity details.
        raise RuntimeError(f"{Path(argv[0]).name} failed (exit {result.returncode})")
    return result.stdout + result.stderr


def metadata(path):
    value = run(["codesign", "-d", "--verbose=4", str(path)])
    return dict(line.split("=", 1) for line in value.splitlines() if "=" in line)


def requirement(path):
    value = run(["codesign", "-d", "-r-", str(path)])
    return next(line.removeprefix("designated => ") for line in value.splitlines()
                if line.startswith("designated => "))


def signature_valid(path):
    result = subprocess.run(["codesign", "--verify", "--strict", str(path)],
                            capture_output=True)
    return result.returncode == 0


def case(root, gate, policy, command, name, expected):
    endpoint = root / "probe.sock"
    policy_file = root / "requirement.txt"
    policy_file.write_text(policy)
    process = subprocess.Popen([str(gate), "gate", str(endpoint), str(policy_file)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout=7):
                raise RuntimeError(f"{name}: gate did not become ready")
        if json.loads(process.stdout.readline()) != {"ready": True}:
            raise RuntimeError(f"{name}: gate startup failed")
        if endpoint.stat().st_mode & 0o777 != 0o600:
            raise RuntimeError(f"{name}: unexpected socket mode")
        run(command + [str(endpoint)], timeout=7, cwd=root)
        stdout, _ = process.communicate(timeout=7)
        if process.returncode:
            raise RuntimeError(f"{name}: gate failed")
        result = json.loads(stdout)
        if result["accepted"] != expected:
            raise RuntimeError(f"{name}: unexpected admission result")
        return {"case": name, **result}
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)
        endpoint.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True,
                        help="Installed YA app, read-only reference; it is not launched")
    parser.add_argument("--sign-with-app-publisher", action="store_true",
                        help="Sign only temporary fixtures using an available matching Developer ID")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("macOS required")
    app = args.app.resolve()
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    if info.get("CFBundleIdentifier") != "com.yepanywhere.desktop":
        parser.error("expected a YepAnywhere Desktop bundle")
    native = app / "Contents/MacOS" / info["CFBundleExecutable"]
    bun = app / "Contents/MacOS/bun"
    if not all(signature_valid(path) for path in [app, native, bun]):
        raise RuntimeError("reference app or executable signature verification failed")
    team = metadata(native).get("TeamIdentifier", "")
    if not re.fullmatch(r"[A-Z0-9]{10}", team):
        raise RuntimeError("reference has no release team identity")
    desktop_policy = requirement(native)
    publisher_policy = f'anchor apple generic and certificate leaf[subject.OU] = "{team}"'
    identity = None
    if args.sign_with_app_publisher:
        available = run(["security", "find-identity", "-v", "-p", "codesigning"])
        matches = re.findall(r'([A-Fa-f0-9]{40}) "Developer ID Application: [^"\n]+ '
                             + re.escape(f"({team})") + r'"', available)
        if len(matches) != 1:
            raise RuntimeError("expected exactly one matching local Developer ID identity")
        identity = matches[0]

    with tempfile.TemporaryDirectory(prefix="mc-auth-", dir="/tmp") as temporary:
        root = Path(temporary)
        os.chmod(root, 0o700)
        gate = root / "gate"
        run(["swiftc", str(Path(__file__).with_name("probe.swift")), "-o", str(gate)], timeout=120)
        native_client = root / "native-client"
        other_client = root / "other-client"
        forged_client = root / "forged-client"
        for path in [native_client, other_client, forged_client]:
            shutil.copy2(gate, path)
        fixture_id = "org.machine-control.test.caller"
        for path, identifier, signer in [
            (native_client, fixture_id, identity or "-"),
            (other_client, fixture_id + ".other", identity or "-"),
            (forged_client, fixture_id, "-"),
        ]:
            run(["codesign", "--force", "--sign", signer, "--identifier", identifier,
                 "--options", "runtime", "--timestamp=none", str(path)])
        if identity:
            fixture_policy = requirement(native_client)
        else:
            # Ad-hoc designated requirements are not a publisher boundary.
            # Pin the exact code hash for the local OS-mechanics experiment.
            fixture_policy = f'cdhash H"{metadata(native_client)["CDHash"]}"'
        copied_client = root / "renamed-client"
        shutil.copy2(native_client, copied_client)

        script = root / "client.js"
        script.write_text('''import net from "node:net";
const client = net.createConnection(process.argv[2]);
client.on("connect", () => client.write(JSON.stringify({
  application: "YepAnywhere", sessionId: "claimed-session", trusted: true
}) + "\\n"));
client.on("data", () => client.end());
client.on("error", () => process.exit(1));
setTimeout(() => process.exit(2), 4000).unref();
''')
        python = root / "client.py"
        python.write_text('''import socket, sys
with socket.socket(socket.AF_UNIX) as s:
    s.settimeout(4)
    s.connect(sys.argv[1])
    s.recv(1)
''')
        results = []
        for name, policy, command, accepted in [
            ("native_fixture", fixture_policy, [str(native_client), "client"], True),
            ("copied_native_fixture", fixture_policy, [str(copied_client), "client"], True),
            ("different_identity", fixture_policy, [str(other_client), "client"], False),
            ("ordinary_python", fixture_policy, [sys.executable, "-I", str(python)], False),
            ("bundled_bun_claiming_session", fixture_policy, [str(bun), str(script)], False),
            ("bundled_bun_against_desktop_identity", desktop_policy, [str(bun), str(script)], False),
            ("bundled_bun_against_publisher_only", publisher_policy, [str(bun), str(script)],
             metadata(bun).get("TeamIdentifier") == team),
        ]:
            results.append(case(root, gate, policy, command, name, accepted))
        if identity:
            results.append(case(root, gate, fixture_policy, [str(forged_client), "client"],
                                "adhoc_same_identifier", False))
        invalid = root / "invalid.txt"
        invalid.write_text("this is not a code requirement")
        result = subprocess.run([str(gate), "gate", str(root / "invalid.sock"), str(invalid)],
                                capture_output=True, text=True, timeout=7)
        if result.returncode != 1 or json.loads(result.stdout) != {"error": "requirement_parse"}:
            raise RuntimeError("invalid policy did not fail closed")
        results.append({"case": "invalid_policy", "accepted": False, "stage": "requirement_parse"})
        print(json.dumps({
            "schema": "mc-caller-authentication-experiment/v1",
            "fixtureSigning": "developer-id" if identity else "adhoc-code-hash",
            "desktopVersion": info.get("CFBundleShortVersionString"),
            "referenceSignaturesValid": True,
            "desktopExecutableSha256": hashlib.sha256(native.read_bytes()).hexdigest(),
            "bunExecutableSha256": hashlib.sha256(bun.read_bytes()).hexdigest(),
            "cases": results,
            "limits": ["no desktop-native connection or session delegation tested",
                       "no product grant, screen operation or fresh installation tested"],
        }, indent=2))


if __name__ == "__main__":
    main()
