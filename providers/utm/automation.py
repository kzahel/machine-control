#!/usr/bin/env python3
"""Bounded Apple Events to the running UTM application."""
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

# UTM gives the primary console the VM's name. Resolve the pinned UUID first,
# require a unique name across the VM registry and windows, and close by the
# Cocoa window ID. Never address a window by its position or activate the app.
CLOSE_CONSOLE_SCRIPT = '''on run argv
    set appPath to item 1 of argv
    set expectedId to item 2 of argv
    if not (application appPath is running) then return "not_running"
    with timeout of 5 seconds
        tell application appPath
            set targetVM to missing value
            set registeredVMs to get every «class UTMv»
            repeat with vmRef in registeredVMs
                ignoring case
                    if id of vmRef is expectedId then
                        if targetVM is not missing value then return "ambiguous"
                        set targetVM to contents of vmRef
                    end if
                end ignoring
            end repeat
            if targetVM is missing value then return "unverified"
            if «property StUs» of targetVM is not «constant VmEsStSa» then return "not_stopped"
            set vmName to name of targetVM
            set sameName to 0
            set consoleId to missing value
            set anotherVisibleWindow to false
            considering case, diacriticals, hyphens, punctuation and white space
                if vmName is in {"", "UTM", "UTM Library", "UTM Server"} then return "ambiguous"
                repeat with vmRef in registeredVMs
                    if name of vmRef is vmName then set sameName to sameName + 1
                end repeat
                if sameName is not 1 then return "ambiguous"
                repeat with windowId in (get id of every window)
                    set windowRef to window id (contents of windowId)
                    if name of windowRef is vmName then
                        if consoleId is not missing value then return "ambiguous"
                        set consoleId to contents of windowId
                    else if «property pvis» of windowRef then
                        set anotherVisibleWindow to true
                    end if
                end repeat
                if consoleId is missing value then return "absent"
                if not anotherVisibleWindow and (get «property kRlW») then return "auto_terminate"
                if not («property hclb» of window id consoleId) then return "unverified"
                if name of window id consoleId is not vmName then return "unverified"
                if name of targetVM is not vmName then return "unverified"
            end considering
            set consoleWasVisible to «property pvis» of window id consoleId
            set consoleWasMinimized to «property pmnd» of window id consoleId
            if «property StUs» of targetVM is not «constant VmEsStSa» then return "not_stopped"
            close window id consoleId saving no
            if consoleId is not in (get id of every window) then return "closed"
            -- UTM retains console window objects after they close.
            if «property pvis» of window id consoleId then return "unverified"
            if «property pmnd» of window id consoleId then return "unverified"
            if consoleWasVisible or consoleWasMinimized then return "closed"
            return "not_visible"
        end tell
    end timeout
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


def run_script(executable: str, script: str, *arguments: str) -> subprocess.CompletedProcess | str:
    bundle = application_bundle(executable)
    if bundle is None:
        # Custom test executables and non-macOS fixture hosts retain their
        # existing behavior; do not accidentally address the user's UTM app.
        return "not_applicable"
    try:
        return subprocess.run(
            ["/usr/bin/osascript", "-e", script, str(bundle), *arguments],
            capture_output=True, text=True, timeout=7, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"


def probe(executable: str) -> str:
    result = run_script(executable, SCRIPT)
    if isinstance(result, str):
        return result
    if result.returncode == 0 and result.stdout.strip() in {"ready", "empty", "not_running"}:
        return result.stdout.strip()
    if "UTM is not ready to accept commands" in result.stderr:
        return "library_unready"
    return "unavailable"


def close_console(executable: str, target_id: str) -> str:
    if not target_id:
        return "unverified"
    result = run_script(executable, CLOSE_CONSOLE_SCRIPT, target_id)
    if isinstance(result, str):
        return result
    outcome = result.stdout.strip()
    if result.returncode == 0 and outcome in {
        "closed", "absent", "not_visible", "ambiguous", "unverified", "not_stopped",
        "not_running", "auto_terminate",
    }:
        return outcome
    return "unavailable"


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "close-console":
        outcome = close_console(sys.argv[2], sys.argv[3])
        if outcome not in {"closed", "absent", "not_visible", "not_running", "not_applicable"}:
            print(f"machine-control: UTM console closure unconfirmed ({outcome})", file=sys.stderr)
    elif len(sys.argv) == 2:
        print(probe(sys.argv[1]))
    else:
        raise SystemExit(2)
