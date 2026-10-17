#!/usr/bin/env python3
"""Build an isolated source-native workstation fixture for a claimed Mac VM."""
import argparse
from pathlib import Path
import plistlib
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--socket", required=True, help="Unused guest socket; never select the canonical resident endpoint")
    parser.add_argument("--preferences-suite", required=True, help="Disposable fixture-only preference suite")
    parser.add_argument("--arch", choices=["arm64", "x86_64"], default="arm64")
    parser.add_argument("--appliance-identity", action="store_true",
                        help="Reuse the source appliance's ad-hoc identity and existing VM TCC consent")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    app = args.output.resolve() / "Browser Lock Fixture.app"
    assert not app.exists(), "Refuse to replace an existing app"
    assert args.socket.startswith("/tmp/"), "Use an isolated temporary guest socket"
    assert args.preferences_suite.startswith("org.machine-control.browser-lock-fixture"), "Use a fixture-only preference domain"
    assert args.preferences_suite != "org.machine-control.browser-lock-fixture", "The suite must differ from the app identifier"
    binary = app / "Contents/MacOS/macui"
    resources = app / "Contents/Resources"
    binary.parent.mkdir(parents=True)
    resources.mkdir()
    identifier = "org.machine-control.app" if args.appliance_identity else "org.machine-control.browser-lock-fixture"
    (app / "Contents/Info.plist").write_bytes(plistlib.dumps({
        "CFBundleIdentifier": identifier, "CFBundleExecutable": "macui",
        "CFBundleName": "Browser Lock Fixture", "CFBundlePackageType": "APPL",
        "MCFixtureSocket": args.socket, "MCFixturePreferences": args.preferences_suite,
    }))
    sources = sorted(str(path) for path in (root / "platforms/macos/resident/Sources/macui").glob("*.swift")
                     if path.name != "main.swift")
    target = args.arch + "-apple-macos13.0"
    with tempfile.TemporaryDirectory(prefix="mc-browser-lock-compile-") as scratch:
        main_source = Path(scratch) / "main.swift"
        main_source.write_bytes((root / "tests/macos/browser-locked-fixture.swift").read_bytes())
        subprocess.run(["xcrun", "swiftc", "-O", "-target", target, "-o", str(binary),
                        *sources, str(main_source)], check=True)
    subprocess.run(["xcrun", "clang", "-O2", "-target", target, "-fobjc-arc", "-framework", "Foundation",
                    "-framework", "IOKit", "-o", str(resources / "mc-session-probe"),
                    str(root / "platforms/macos/guests/macos/unlock/Probe.m")], check=True)
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", "--identifier", identifier,
                    "--requirements", '=designated => identifier "' + identifier + '"', str(app)], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    print(app)


if __name__ == "__main__":
    main()
