import importlib.util
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET


DIRECTORY = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(DIRECTORY))
PROVIDER = load("libvirt_provider", DIRECTORY / "libvirt_provider.py")
WORKSPACE = load("workspace_domain", DIRECTORY / "workspace_domain.py")


SOURCE_UUID = "11111111-2222-4333-8444-555555555555"
TARGET_UUID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


SOURCE_XML = f"""
<domain type="kvm">
  <name>fixture-source</name>
  <uuid>{SOURCE_UUID}</uuid>
  <metadata><private>discard</private></metadata>
  <os>
    <type arch="x86_64" machine="pc-q35-noble">hvm</type>
    <loader readonly="yes" secure="yes" type="pflash">firmware</loader>
    <nvram>/private/source-vars.fd</nvram>
  </os>
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>
    <disk type="file" device="disk">
      <driver name="qemu" type="qcow2"/>
      <source file="/private/source.qcow2"/>
      <target dev="vda" bus="virtio"/>
      <address type="pci"/>
    </disk>
    <disk type="file" device="cdrom"><source file="/private/media.iso"/></disk>
    <interface type="network">
      <mac address="52:54:00:00:00:01"/>
      <source network="default"/><model type="virtio"/>
      <target dev="vnet0"/><address type="pci"/>
    </interface>
    <channel type="unix">
      <source mode="bind" path="/private/agent.sock"/>
      <target type="virtio" name="org.qemu.guest_agent.0"/>
      <address type="virtio-serial"/>
    </channel>
    <tpm model="tpm-crb"><backend type="emulator" version="2.0"/></tpm>
  </devices>
</domain>
"""


class DerivationTests(unittest.TestCase):
    def derived(self):
        return WORKSPACE.derive_domain_xml(
            SOURCE_XML,
            source_uuid=SOURCE_UUID,
            source_name="fixture-source",
            target_uuid=TARGET_UUID,
            target_name="fixture-derived",
            target_disk="/private/derived.qcow2",
            target_nvram="/private/derived-vars.fd",
            nvram_template="/private/template-vars.fd",
            require_secure_boot=True,
            require_tpm2=True,
        )

    def test_derives_exact_isolated_domain(self):
        root = ET.fromstring(self.derived())
        self.assertEqual(root.get("type"), "kvm")
        self.assertEqual(root.findtext("name"), "fixture-derived")
        self.assertEqual(root.findtext("uuid"), TARGET_UUID)
        self.assertIsNone(root.find("metadata"))
        self.assertEqual(root.findall("./devices/disk[@device='cdrom']"), [])
        self.assertEqual(
            root.find("./devices/disk[@device='disk']/source").get("file"),
            "/private/derived.qcow2",
        )
        self.assertIsNone(root.find("./devices/interface/mac"))
        self.assertIsNone(root.find("./devices/channel/source"))
        self.assertEqual(root.findtext("./os/nvram"), "/private/derived-vars.fd")
        self.assertEqual(
            root.find("./os/nvram").get("template"),
            "/private/template-vars.fd",
        )

    def test_derived_xml_remains_kvm_contract_compatible(self):
        value = PROVIDER.validate_domain_xml(
            self.derived(),
            expected_uuid=TARGET_UUID,
            expected_name="fixture-derived",
            require_secure_boot=True,
            require_tpm2=True,
        )
        self.assertEqual(value["acceleration"], "kvm")
        self.assertEqual(value["primaryDisk"]["path"], "/private/derived.qcow2")

    def test_rejects_unsafe_generated_name(self):
        with self.assertRaisesRegex(PROVIDER.ProviderError, "name is invalid"):
            WORKSPACE.derive_domain_xml(
                SOURCE_XML,
                source_uuid=SOURCE_UUID,
                source_name="fixture-source",
                target_uuid=TARGET_UUID,
                target_name="../escape",
                target_disk="/private/derived.qcow2",
                target_nvram="/private/derived-vars.fd",
                nvram_template="/private/template-vars.fd",
                require_secure_boot=True,
                require_tpm2=True,
            )

    def test_requires_posix_absolute_workspace_paths_on_every_controller(self):
        for field, value in (
            ("target_disk", r"C:\private\derived.qcow2"),
            ("target_nvram", "private/derived-vars.fd"),
            ("nvram_template", "private/template-vars.fd"),
        ):
            arguments = {
                "source_uuid": SOURCE_UUID,
                "source_name": "fixture-source",
                "target_uuid": TARGET_UUID,
                "target_name": "fixture-derived",
                "target_disk": "/private/derived.qcow2",
                "target_nvram": "/private/derived-vars.fd",
                "nvram_template": "/private/template-vars.fd",
                "require_secure_boot": True,
                "require_tpm2": True,
            }
            arguments[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                PROVIDER.ProviderError, "paths must be absolute"
            ):
                WORKSPACE.derive_domain_xml(SOURCE_XML, **arguments)


if __name__ == "__main__":
    unittest.main()
