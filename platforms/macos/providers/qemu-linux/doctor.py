"""Project QEMU, SSH and native macOS readiness into the common doctor."""

import json
import os
import sys

power = os.environ["MACVM_QEMU_PROBE_POWER"]
identity = os.environ["MACVM_QEMU_PROBE_IDENTITY"]
administration = os.environ["MACVM_QEMU_PROBE_ADMINISTRATION"]
try:
    response = json.loads(os.environ["MACVM_QEMU_PROBE_RESIDENT"])
except ValueError:
    response = {}
if not isinstance(response, dict):
    response = {}
data = response.get("data")
if not isinstance(data, dict):
    data = {}
desktop = data.get("desktopState", "unknown")
states = {
    "power": power,
    "administration": administration,
    "resident": "ready" if response.get("accepted") is True else "unavailable",
    "desktop": desktop if desktop in {"unlocked", "locked", "no_session"} else "unknown",
    "outer": "ready" if power == "running" else "unavailable",
}
if os.environ.get("MACVM_QEMU_FORBID_OUTER_UI") == "true":
    states["outer"] = "prohibited"
for name in ("semantic", "capture", "input"):
    states[name] = "ready" if data.get(name + "State") == "ready" else "unavailable"
checks = {
    "identity": identity == "verified",
    "power": power == "running",
    "administration": administration == "ready",
    "desktop": states["desktop"] == "unlocked",
    **{name: states[name] == "ready" for name in ("resident", "semantic", "capture", "input")},
}
if sys.argv[1] == "bootstrap-stages":
    print(json.dumps({
        "schema": "macvm-bootstrap-stages/v0",
        "stages": [{"name": name, "state": "complete" if checks[check] else "blocked"}
                   for name, check in (
                       ("identity", "identity"), ("power", "power"),
                       ("transport", "administration"), ("resident", "resident"),
                       ("accessibility", "semantic"), ("desktop", "desktop"),
                       ("capture", "capture"))],
    }))
else:
    print(json.dumps({
        "schema": "machine-control-doctor/v0",
        "target": {"platform": "macos", "profile": "macos-intel-qemu-kvm", "kind": "desktop"},
        "ready": all(checks.values()),
        "states": states,
        "checks": [{"id": name, "status": "pass" if ready else "fail"}
                   for name, ready in checks.items()],
        "lifecycleOperations": ["status", "up", "shutdown"],
        "extensions": {"targetIdentity": identity, "transport": "ssh",
                       "provider": "qemu-linux-macos"},
    }))
    raise SystemExit(0 if all(checks.values()) else 1)
