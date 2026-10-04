"""Exercise carrier fencing and provider binding without any real VM."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix", "POSIX controller SSH/SCP carrier scripts")
class DirectTransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.marker = self.root / "carrier-called"
        for name, body in {
            "bin/winvm": 'printf "%s\\n" "$*" >"$TEST_CLAIM_LOG"; exit "${TEST_CLAIM_EXIT:-0}"',
            "providers/utm-macos/provider.sh": '[[ "$1" == ip ]] || exit 2; [[ "${TEST_NO_ADDRESS:-0}" != 1 ]] || exit 0; printf "192.0.2.10\\n"',
            "providers/libvirt-linux/provider.sh": '[[ "$1" == ip ]] || exit 2; printf "192.0.2.11\\n"',
            "carrier": 'printf "%s\\n" "$@" >"$TEST_CARRIER_LOG"',
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("#!/usr/bin/env bash\nset -eu\n" + body + "\n")
            path.chmod(0o700)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(("WINVM_", "MACHINE_CONTROL_"))}
        self.env.update({"WINVM_REPO_DIR": str(self.root), "WINVM_CONFIG_FILE": "/dev/null",
                         "WINVM_TARGET_FILE": str(self.root / "absent"),
                         "WINVM_PROVIDER": "utm-macos", "WINVM_SSH_HOST": "appliance@example-vm",
                         "WINVM_DIRECT_SSH_BIN": str(self.root / "carrier"),
                         "WINVM_DIRECT_SCP_BIN": str(self.root / "carrier"),
                         "TEST_CARRIER_LOG": str(self.marker),
                         "TEST_CLAIM_LOG": str(self.root / "claim-check")})

    def invoke(self, kind):
        return subprocess.run(["bash", str(ROOT / f"scripts/libvirt-direct-{kind}.sh"),
                               "appliance@example-vm", "probe"], env=self.env,
                              capture_output=True, text=True, timeout=15)

    def test_missing_or_rejected_claim_refuses_before_carrier(self):
        for kind in ("ssh", "scp"):
            self.assertNotEqual(self.invoke(kind).returncode, 0)
            self.assertFalse(self.marker.exists())
            self.env.update({"MACHINE_CONTROL_CLAIM_ID": "example-claim", "TEST_CLAIM_EXIT": "1"})
            self.assertNotEqual(self.invoke(kind).returncode, 0)
            self.assertFalse(self.marker.exists())
            self.env.pop("MACHINE_CONTROL_CLAIM_ID")

    def test_both_providers_resolve_claimed_address_and_disable_proxy(self):
        self.env["MACHINE_CONTROL_CLAIM_ID"] = "example-claim"
        for provider, address in (("utm-macos", "192.0.2.10"),
                                  ("libvirt-linux", "192.0.2.11")):
            self.env["WINVM_PROVIDER"] = provider
            for kind in ("ssh", "scp"):
                self.assertEqual(self.invoke(kind).returncode, 0)
                args = self.marker.read_text().splitlines()
                self.assertIn("ProxyCommand=none", args)
                self.assertIn("HostName=" + address, args)
                self.assertIn("HostKeyAlias=example-vm", args)
                self.assertIn("--claim-id example-claim", (self.root / "claim-check").read_text())

    def test_absent_address_refuses_before_carrier(self):
        self.env.update({"MACHINE_CONTROL_CLAIM_ID": "example-claim", "TEST_NO_ADDRESS": "1"})
        for kind in ("ssh", "scp"):
            self.assertNotEqual(self.invoke(kind).returncode, 0)
            self.assertFalse(self.marker.exists())
