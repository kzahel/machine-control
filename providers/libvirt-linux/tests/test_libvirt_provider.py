import importlib.util
from pathlib import Path
import sys
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "libvirt_provider.py"
SPEC = importlib.util.spec_from_file_location("libvirt_provider", SOURCE)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


DOMAIN_UUID = "11111111-2222-4333-8444-555555555555"


def domain_xml(
    *,
    domain_type="kvm",
    architecture="x86_64",
    machine="pc-q35-noble",
    emulator="/usr/bin/qemu-system-x86_64",
    secure="yes",
    tpm="2.0",
    channel=True,
):
    channel_xml = """
      <channel type="unix">
        <target type="virtio" name="org.qemu.guest_agent.0"/>
      </channel>
    """ if channel else ""
    tpm_xml = f"""
      <tpm model="tpm-crb">
        <backend type="emulator" version="{tpm}"/>
      </tpm>
    """ if tpm else ""
    return f"""
    <domain type="{domain_type}">
      <name>fixture-domain</name>
      <uuid>{DOMAIN_UUID}</uuid>
      <os>
        <type arch="{architecture}" machine="{machine}">hvm</type>
        <loader readonly="yes" secure="{secure}" type="pflash">firmware</loader>
      </os>
      <devices>
        <emulator>{emulator}</emulator>
        <disk type="file" device="disk">
          <driver name="qemu" type="qcow2"/>
          <source file="/private/fixture.qcow2"/>
          <target dev="vda" bus="virtio"/>
        </disk>
        <interface type="network"><model type="virtio"/></interface>
        {channel_xml}
        {tpm_xml}
      </devices>
    </domain>
    """


class DomainValidationTests(unittest.TestCase):
    def validate(self, value, *, secure=True, tpm=True):
        return MODULE.validate_domain_xml(
            value,
            expected_uuid=DOMAIN_UUID,
            expected_name="fixture-domain",
            require_secure_boot=secure,
            require_tpm2=tpm,
        )

    def test_accepts_native_kvm_q35_domain(self):
        value = self.validate(domain_xml())
        self.assertEqual(value["domainType"], "kvm")
        self.assertEqual(value["architecture"], "x86_64")
        self.assertEqual(value["acceleration"], "kvm")
        self.assertTrue(value["secureBoot"])
        self.assertTrue(value["tpm2"])

    def test_rejects_software_emulation(self):
        with self.assertRaisesRegex(MODULE.ProviderError, "domain type must be KVM"):
            self.validate(domain_xml(domain_type="qemu"))

    def test_rejects_cross_architecture_domain(self):
        with self.assertRaisesRegex(MODULE.ProviderError, "must be x86_64"):
            self.validate(domain_xml(architecture="aarch64"))

    def test_rejects_non_q35_domain(self):
        with self.assertRaisesRegex(MODULE.ProviderError, "must be Q35"):
            self.validate(domain_xml(machine="pc-i440fx-noble"))

    def test_rejects_non_x86_emulator(self):
        with self.assertRaisesRegex(MODULE.ProviderError, "x86_64 QEMU"):
            self.validate(domain_xml(emulator="/usr/bin/qemu-system-aarch64"))

    def test_requires_secure_boot_when_selected(self):
        with self.assertRaisesRegex(MODULE.ProviderError, "Secure Boot"):
            self.validate(domain_xml(secure="no"))
        self.validate(domain_xml(secure="no"), secure=False)

    def test_requires_tpm2_when_selected(self):
        with self.assertRaisesRegex(MODULE.ProviderError, "TPM 2.0"):
            self.validate(domain_xml(tpm="1.2"))
        self.validate(domain_xml(tpm=""), tpm=False)

    def test_requires_guest_agent_channel(self):
        with self.assertRaisesRegex(MODULE.ProviderError, "guest-agent channel"):
            self.validate(domain_xml(channel=False))

    def test_rejects_identity_mismatch(self):
        with self.assertRaisesRegex(MODULE.ProviderError, "UUID"):
            MODULE.validate_domain_xml(
                domain_xml(),
                expected_uuid="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
                expected_name="fixture-domain",
                require_secure_boot=True,
                require_tpm2=True,
            )


class RecoveryInputTests(unittest.TestCase):
    def test_text_input_is_bounded_us_ascii_with_explicit_key_up(self):
        events = MODULE.text_input_events("Az !\n")
        self.assertEqual(events[0]["data"]["key"]["data"], "shift")
        self.assertTrue(events[0]["data"]["down"])
        self.assertEqual(events[-2]["data"]["key"]["data"], "ret")
        self.assertFalse(events[-1]["data"]["down"])
        with self.assertRaisesRegex(MODULE.ProviderError, "US-ASCII"):
            MODULE.text_input_events("é")

    def test_named_chord_releases_keys_in_reverse_order(self):
        events = MODULE.named_key_events("ctrl-alt-delete")
        self.assertEqual(
            [event["data"]["key"]["data"] for event in events],
            ["ctrl", "alt", "delete", "delete", "alt", "ctrl"],
        )
        self.assertEqual(
            [event["data"]["down"] for event in events],
            [True, True, True, False, False, False],
        )

    def test_pointer_coordinates_are_scaled_and_bounded(self):
        events = MODULE.pointer_events(1280, 800, 0, 0, "left", 1279, 799)
        self.assertEqual(events[0]["data"]["value"], 0)
        self.assertEqual(events[1]["data"]["value"], 0)
        self.assertEqual(events[3]["data"]["value"], 0x7FFF)
        self.assertEqual(events[4]["data"]["value"], 0x7FFF)
        with self.assertRaisesRegex(MODULE.ProviderError, "out of bounds"):
            MODULE.pointer_events(1280, 800, 1280, 0, "left")


if __name__ == "__main__":
    unittest.main()
