import importlib.util
from pathlib import Path
import sys
import unittest


PROVIDER_SOURCE = Path(__file__).resolve().parents[1] / "libvirt_provider.py"
PROVIDER_SPEC = importlib.util.spec_from_file_location(
    "libvirt_provider", PROVIDER_SOURCE
)
assert PROVIDER_SPEC is not None and PROVIDER_SPEC.loader is not None
PROVIDER = importlib.util.module_from_spec(PROVIDER_SPEC)
sys.modules[PROVIDER_SPEC.name] = PROVIDER
PROVIDER_SPEC.loader.exec_module(PROVIDER)

SOURCE = Path(__file__).resolve().parents[1] / "domain_factory.py"
SPEC = importlib.util.spec_from_file_location("domain_factory", SOURCE)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def configuration(domain_name="fixture-domain"):
    return PROVIDER.Configuration(
        uri="qemu:///system",
        domain_name=domain_name,
        expected_uuid="",
        network="fixture-network",
        pool="fixture-pool",
        virsh="virsh",
        qemu="qemu-system-x86_64",
        boot_timeout=60,
        shutdown_timeout=60,
        exec_timeout=60,
        minimum_free_bytes=0,
        require_secure_boot=True,
        require_tpm2=True,
    )


class FactoryPolicyTests(unittest.TestCase):
    def test_name_must_match_private_inventory(self):
        self.assertEqual(
            MODULE.require_name(configuration(), "fixture-domain"),
            "fixture-domain",
        )
        with self.assertRaisesRegex(PROVIDER.ProviderError, "private inventory"):
            MODULE.require_name(configuration(), "different-domain")

    def test_common_domain_is_native_host_passthrough_q35(self):
        arguments = MODULE.common_domain_arguments(
            configuration(),
            "fixture.qcow2",
            memory_mib=8192,
            vcpus=6,
            osinfo="win11",
        )
        joined = " ".join(arguments)
        self.assertIn("--cpu host-passthrough", joined)
        self.assertIn("--machine q35", joined)
        self.assertIn("fixture-pool/fixture.qcow2", joined)
        self.assertIn("network=fixture-network,model=virtio", joined)
        self.assertIn("org.qemu.guest_agent.0", joined)

    def test_cdrom_shape_is_exact_and_ordered(self):
        xml = """
        <domain><devices>
          <disk type="file" device="cdrom">
            <source file="/private/seed.iso"/><target dev="sdb" bus="sata"/>
          </disk>
          <disk type="file" device="cdrom">
            <source file="/private/installer.iso"/><target dev="sda" bus="sata"/>
          </disk>
        </devices></domain>
        """
        self.assertEqual(MODULE.cdrom_targets(xml), ["sda", "sdb"])

    def test_cdrom_without_source_is_refused(self):
        xml = """
        <domain><devices><disk type="file" device="cdrom">
          <target dev="sda" bus="sata"/>
        </disk></devices></domain>
        """
        with self.assertRaisesRegex(PROVIDER.ProviderError, "shape"):
            MODULE.cdrom_targets(xml)


if __name__ == "__main__":
    unittest.main()
