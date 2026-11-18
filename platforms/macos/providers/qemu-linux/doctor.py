"""Project QEMU, SSH and native macOS readiness into the common doctor."""

import json
import os
import sys


def observation(name):
    try:
        value = json.loads(os.environ.get(name, ""))
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


power = os.environ["MACVM_QEMU_PROBE_POWER"]
identity = os.environ["MACVM_QEMU_PROBE_IDENTITY"]
administration = os.environ["MACVM_QEMU_PROBE_ADMINISTRATION"]
provider = os.environ["MACVM_QEMU_PROBE_PROVIDER"]
profile = "macos-intel-libvirt-kvm" if provider == "libvirt-linux-macos" else "macos-intel-qemu-kvm"
response = observation("MACVM_QEMU_PROBE_RESIDENT")
data = response.get("data")
if not isinstance(data, dict):
    data = {}
desktop = data.get("desktopState", "unknown")
if not response:
    desktop = observation("MACVM_QEMU_PROBE_SESSION").get("desktopState", "unknown")
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
        "target": {"platform": "macos", "profile": profile, "kind": "desktop"},
        "ready": all(checks.values()),
        "states": states,
        "checks": [{"id": name, "status": "pass" if ready else "fail"}
                   for name, ready in checks.items()],
        "lifecycleOperations": ["status", "up", "shutdown"],
        "extensions": {"targetIdentity": identity, "transport": "ssh",
                       "provider": provider},
    }))
    raise SystemExit(0 if all(checks.values()) else 1)
