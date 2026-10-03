import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'client'))
sys.path.insert(0, str(ROOT / 'providers/outer'))
import machine_control as mc
from outer_session import OuterSession
import macos as bridge


class OuterSessionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.record = Path(self.temporary.name) / 'events'
        self.host = dict(command=[sys.executable, str(Path(__file__).with_name('admission_fixture.py'))],
            environment={'MC_ADMISSION_RECORD':str(self.record)}, claimPolicy='unsupported')

    def tearDown(self):
        self.temporary.cleanup()

    def owner(self, mode='outer', **options):
        host = dict(self.host, environment={**self.host['environment'], 'MC_ADMISSION_FIXTURE':mode})
        return OuterSession(host, {'schema':'machine-control-outer-borrow/v1'}, reason='Explicit fixture recovery', **options)

    def test_native_profile_negotiation_and_ordered_effects(self):
        with self.owner() as owner:
            self.assertTrue(owner.sequenced)
            owner.prepare(); owner.begin(); owner.step('key', key='a')
        events = self.record.read_text().splitlines()
        self.assertEqual(events.count('outer.step'), 1)
        self.assertIn('control.cancel', events)
        self.assertIn('EOF', events)

    def test_legacy_provider_cannot_silently_run_outer_recovery(self):
        with self.assertRaises(mc.ClientError) as error:
            self.owner('ready')
        self.assertEqual(error.exception.code, 'outer_admission_unsupported')
        self.assertNotIn('effect', self.record.read_text())
        self.assertIn('EOF', self.record.read_text())

    def test_claim_interruption_is_not_replayed(self):
        with self.owner('outer-refused') as owner:
            owner.prepare(); owner.begin()
            with self.assertRaises(mc.ClientError) as error:
                owner.step('click', x=10,y=10)
            self.assertEqual(error.exception.code, 'outer_claim_changed_or_expired')
        self.assertEqual(self.record.read_text().splitlines().count('outer.step'), 1)

    def test_paused_deadline_never_focuses_or_dispatches(self):
        with self.owner('outer-paused',wait=1) as owner:
            with self.assertRaises(mc.ClientError) as error:
                owner.prepare()
            self.assertEqual(error.exception.code, 'wait_deadline_exceeded')
        self.assertNotIn('effect', self.record.read_text())

    def test_ascii_physical_key_mapping_and_unicode_refusal(self):
        self.assertEqual(bridge.text_keys('Aa"|~_-'), ['shift-a','a',"shift-'",'shift-\\','shift-`','shift-minus','minus'])
        with self.assertRaises(mc.ClientError): bridge.text_keys('é')


if __name__ == '__main__':
    unittest.main()
