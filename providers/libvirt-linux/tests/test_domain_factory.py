import importlib.util
from dataclasses import replace
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


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

    def test_preflight_checks_exact_unused_destination_without_mutation(self):
        class Provider:
            def __init__(self, occupied=False):
                self.calls = []
                self.occupied = occupied

            def command(self, *arguments, **_kwargs):
                self.calls.append(arguments)
                found = self.occupied and arguments[0] == "domuuid"
                return type("Result", (), {"returncode": 0 if found else 1})()

        with mock.patch.object(MODULE, "require_factory_host"), \
             mock.patch.object(MODULE, "require_local_pool_path"):
            provider = Provider()
            report = MODULE.preflight_destination(
                configuration(), provider, "fixture-domain", "windows",
            )
            self.assertTrue(report["ready"])
            self.assertEqual([call[0] for call in provider.calls],
                             ["domuuid", "vol-info", "vol-info", "vol-info"])
            with self.assertRaisesRegex(PROVIDER.ProviderError, "already exists"):
                MODULE.preflight_destination(
                    configuration(), Provider(occupied=True),
                    "fixture-domain", "windows",
                )

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
        self.assertEqual(
            MODULE.cdrom_media(xml),
            [
                ("sda", "/private/installer.iso"),
                ("sdb", "/private/seed.iso"),
            ],
        )

    def test_cdrom_without_source_is_refused(self):
        xml = """
        <domain><devices><disk type="file" device="cdrom">
          <target dev="sda" bus="sata"/>
        </disk></devices></domain>
        """
        with self.assertRaisesRegex(PROVIDER.ProviderError, "shape"):
            MODULE.cdrom_targets(xml)

    def test_media_stage_reports_exact_detach_sequence_without_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("fixture-domain.installer.iso", "fixture-domain.seed.iso"):
                (Path(directory) / name).touch()

            class Provider:
                def __init__(self, names):
                    self.names = names

                def text(self, operation, *arguments):
                    if operation == "domstate":
                        return "shut off"
                    if operation == "dumpxml":
                        disks = "".join(
                            f'<disk device="cdrom"><source file="{directory}/{name}"/>'
                            f'<target dev="sd{chr(97 + index)}"/></disk>'
                            for index, name in enumerate(self.names)
                        )
                        return f"<domain><devices>{disks}</devices></domain>"
                    raise AssertionError(operation)

            config = replace(configuration(), expected_uuid="fixture-uuid")
            with mock.patch.object(MODULE, "inspect_domain"), \
                 mock.patch.object(MODULE, "require_local_pool_path", return_value=Path(directory)):
                cases = (
                    (["fixture-domain.installer.iso", "fixture-domain.seed.iso"], "installer_and_seed"),
                    (["fixture-domain.seed.iso"], "seed_only"),
                    ([], "detached"),
                )
                for names, expected in cases:
                    report = MODULE.media_stage(config, Provider(names))
                    self.assertEqual(report["stage"], expected)
                    self.assertNotIn(directory, str(report))
                with self.assertRaisesRegex(PROVIDER.ProviderError, "shape"):
                    MODULE.media_stage(config, Provider(["fixture-domain.installer.iso"]))
                linux = MODULE.media_stage(
                    config, Provider(["fixture-domain.seed.iso"]), kind="linux",
                )
                self.assertEqual(linux["schema"], "linuxvm-factory-media-status/v0")
                self.assertEqual(linux["stage"], "seed_only")
                with self.assertRaisesRegex(PROVIDER.ProviderError, "shape"):
                    MODULE.media_stage(
                        config, Provider(["fixture-domain.installer.iso"]), kind="linux",
                    )

    def test_local_pool_path_requires_exact_writable_directory(self):
        class Provider:
            def __init__(self, path):
                self.path = path

            def text(self, *arguments):
                self.arguments = arguments
                return f"<pool><target><path>{self.path}</path></target></pool>"

        with tempfile.TemporaryDirectory() as directory:
            provider = Provider(directory)
            with mock.patch.dict(
                os.environ, {"MC_LIBVIRT_POOL_PATH": directory}, clear=False
            ):
                self.assertEqual(
                    MODULE.require_local_pool_path(provider, "fixture-pool"),
                    Path(directory).resolve(strict=True),
                )
            self.assertEqual(provider.arguments, ("pool-dumpxml", "fixture-pool"))

    def test_local_pool_path_refuses_inventory_mismatch(self):
        class Provider:
            def text(self, *arguments):
                return "<pool><target><path>/different</path></target></pool>"

        with tempfile.TemporaryDirectory() as directory, \
             tempfile.TemporaryDirectory() as different:
            provider = Provider()
            provider.text = mock.Mock(
                return_value=(
                    f"<pool><target><path>{different}</path></target></pool>"
                )
            )
            with mock.patch.dict(
                os.environ, {"MC_LIBVIRT_POOL_PATH": directory}, clear=False
            ):
                with self.assertRaisesRegex(
                    PROVIDER.ProviderError, "exact libvirt pool"
                ):
                    MODULE.require_local_pool_path(provider, "fixture-pool")


if __name__ == "__main__":
    unittest.main()
