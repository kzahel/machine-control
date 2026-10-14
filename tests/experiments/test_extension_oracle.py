import json
from pathlib import Path
import tempfile
import unittest

from extension_oracle import poll, registration


class ExtensionOracleTest(unittest.TestCase):
    def setUp(self):
        self.now=0

    def sleep(self, seconds):
        self.now+=seconds

    def poll(self, registry, behavior):
        return poll(registry,behavior,timeout=1,clock=lambda:self.now,sleep=self.sleep)

    def test_delayed_disk_registration_does_not_hide_live_behavior(self):
        result=self.poll(lambda:{'readable':True,'enabled':self.now>=.5},lambda:True)
        self.assertTrue(result['passed'])
        self.assertFalse(result['registeredAtStart'])
        self.assertEqual(result['verificationSeconds'],.5)

    def test_registered_without_behavior_and_unchanged_both_fail(self):
        for enabled in (True,False):
            result=self.poll(lambda:{'readable':True,'enabled':enabled},lambda:False)
            self.assertFalse(result['passed'])
            self.assertTrue(result['verifierAvailable'])

    def test_unreadable_or_inconsistent_evidence_is_not_a_product_failure(self):
        for readable,observed in ((False,False),(True,True)):
            result=self.poll(lambda:{'readable':readable,'enabled':False},lambda:observed)
            self.assertFalse(result['passed'])
            self.assertFalse(result['verifierAvailable'])

    def test_disabled_and_wrong_path_registration_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            prefs=root/'cft-profile/Default/Secure Preferences'
            prefs.parent.mkdir(parents=True)
            for extra,enabled in (({},True),({'state':0},False),
                                  ({'disable_reasons':[1]},False),({'path':'elsewhere'},False)):
                value={'path':str(root/'probe-ext'),**extra}
                prefs.write_text(json.dumps({'extensions':{'settings':{'id':value}}}))
                self.assertEqual(registration(root),{'readable':True,'enabled':enabled})


if __name__=='__main__':unittest.main()
