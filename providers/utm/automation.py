#!/usr/bin/env python3
"""Read-only UTM automation health; never launch the crashing CLI to probe it."""
from __future__ import annotations

from pathlib import Path
import plistlib
import subprocess
import sys

# Raw four-character terminology avoids compiling against a broken dynamic
# scripting dictionary. The app path is passed as argv, never source text.
SCRIPT = '''on run argv
    set appPath to item 1 of argv
    if not (application appPath is running) then return "not_running"
    with timeout of 5 seconds
        tell application appPath
            set vmCount to count every «class UTMv»
        end tell
    end timeout
    if vmCount is 0 then return "empty"
    return "ready"
end run
'''


def application_bundle(executable: str) -> Path | None:
    if sys.platform != "darwin":
        return None
    path = Path(executable).resolve()
    bundle = path.parent.parent.parent
    if path.name != "utmctl" or bundle.suffix != ".app":
        return None
    try:
        metadata = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
        return bundle if metadata.get("CFBundleIdentifier") == "com.utmapp.UTM" else None
    except (OSError, ValueError, plistlib.InvalidFileException):
        return None


def probe(executable: str) -> str:
    bundle = application_bundle(executable)
    if bundle is None:
        # Custom test executables and non-macOS fixture hosts retain their
        # existing behavior; do not accidentally address the user's UTM app.
        return "not_applicable"
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", SCRIPT, str(bundle)],
            capture_output=True, text=True, timeout=7, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    if result.returncode == 0 and result.stdout.strip() in {"ready", "empty", "not_running"}:
        return result.stdout.strip()
    if "UTM is not ready to accept commands" in result.stderr:
        return "library_unready"
    return "unavailable"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(2)
    print(probe(sys.argv[1]))
