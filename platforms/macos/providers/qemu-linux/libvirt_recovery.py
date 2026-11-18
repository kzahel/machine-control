#!/usr/bin/env python3
"""Typed recovery bound to a claimed Intel macOS libvirt guest."""

import json
from pathlib import Path
import sys

from recovery import RecoveryConsole, recover

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "providers/libvirt-linux"))
from libvirt_provider import (  # noqa: E402
    Configuration, Libvirt, ProviderError, recovery_screenshot, require_live_kvm,
)


class LibvirtConsole(RecoveryConsole):
    def __init__(self, configuration, provider):
        self.configuration = configuration
        self.provider = provider

    def request(self, operation, **arguments):
        payload = json.dumps({"execute": operation, "arguments": arguments})
        response = json.loads(self.provider.text(
            "qemu-monitor-command", self.configuration.expected_uuid, payload))
        if "return" not in response:
            raise ValueError("QMP rejected the operation")
        return response["return"]

    def screenshot(self, output):
        recovery_screenshot(self.configuration, self.provider, str(output))


if __name__ == "__main__":
    try:
        configuration = Configuration.from_environment()
        provider = Libvirt(configuration)
        require_live_kvm(configuration, provider)
        raise SystemExit(recover(LibvirtConsole(configuration, provider), sys.argv[1:]))
    except (OSError, ValueError, KeyError, TypeError, ProviderError):
        print("Could not verify or operate the pinned libvirt console", file=sys.stderr)
        raise SystemExit(1)
