#!/usr/bin/env python3
"""Compile the resident's pure projection; never query or control a desktop."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / "platforms/macos/resident/Sources/macui/Resident.swift").read_text()
projection = source[source.index("func lockScreenProjection("):source.index("final class ResidentService {")]
fixture = r'''
let locked = lockScreenProjection(screen: "locked", displayActive: true,
    captureAuthorized: true, accessibilityAuthorized: true, keyboardAuthorized: true)
assert(locked["captureState"] as? String == "ready")
assert(locked["accessibilityState"] as? String == "unverified")
assert(locked["nativeKeyboardPermission"] as? String == "granted")
assert(locked["ordinaryInputPolicy"] as? String == "blocked_while_locked")
assert(locked["credentialEntry"] as? String == "not_implemented")
assert(locked["observationRequiresUnlockHelper"] as? Bool == false)
let dark = lockScreenProjection(screen: "locked", displayActive: false,
    captureAuthorized: true, accessibilityAuthorized: true, keyboardAuthorized: true)
assert(dark["captureState"] as? String == "unavailable")
assert(dark["nativeKeyboardPermission"] as? String == "granted")
let noConsent = lockScreenProjection(screen: "locked", displayActive: true,
    captureAuthorized: false, accessibilityAuthorized: false, keyboardAuthorized: false)
assert(noConsent["captureState"] as? String == "unavailable")
assert(noConsent["accessibilityState"] as? String == "unavailable")
assert(noConsent["nativeKeyboardPermission"] as? String == "denied")
for screen in ["unknown", "unlocked", "no_session"] {
    let value = lockScreenProjection(screen: screen, displayActive: true,
        captureAuthorized: true, accessibilityAuthorized: true, keyboardAuthorized: true)
    let expected = screen == "unknown" ? "unknown" : "not_applicable"
    assert(value["captureState"] as? String == expected)
    assert(value["accessibilityState"] as? String == expected)
}
print("Lock-screen projection fixtures passed")
'''
with tempfile.TemporaryDirectory(prefix="mc-lock-screen-projection-") as directory:
    path = Path(directory)
    (path / "main.swift").write_text("import Foundation\n" + projection + fixture)
    subprocess.run(["xcrun", "swiftc", str(path / "main.swift"), "-o", str(path / "fixture")], check=True)
    subprocess.run([str(path / "fixture")], check=True)
