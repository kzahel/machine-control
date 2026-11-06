"""Host doctor projects surface modes and the common status fields."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'doctor_machost', Path(__file__).resolve().parents[2] / 'platforms/macos/host/machost.py')
machost = importlib.util.module_from_spec(spec)
spec.loader.exec_module(machost)


def doctor(data):
    output = io.StringIO()
    with patch.object(machost, 'call', return_value={'accepted': True, 'data': data}), \
            contextlib.redirect_stdout(output):
        machost.doctor()
    return json.loads(output.getvalue())


def surfaces(desktop='off', browser='off', expired=False):
    return {'admission': {'surfaces': {
        'desktop': {'mode': desktop, 'expired': expired}, 'browser': {'mode': browser, 'expired': False}}}}


class SurfaceCheckTests(unittest.TestCase):
    def check(self, value):
        return next(check for check in value['checks'] if check['id'] == 'grant')

    def test_surface_modes_replace_the_per_request_grant_check(self):
        base = {'desktopState': 'unlocked', 'deployment': {'policy': {
            'preset': 'workstation', 'grantMode': 'surface_modes', 'protectedAdministration': False}}}
        off = self.check(doctor({**base, **surfaces()}))
        self.assertEqual(off['status'], 'warn')
        self.assertNotIn('standing', off['summary'])
        enabled = self.check(doctor({**base, **surfaces('automatic', 'ask')}))
        self.assertEqual(enabled['status'], 'pass')
        self.assertEqual(enabled['summary'], 'Surface access: Desktop automatic, Browser ask')
        expired = self.check(doctor({**base, **surfaces('ask', expired=True)}))
        self.assertEqual(expired['status'], 'warn')
        self.assertEqual(self.check(doctor(base))['status'], 'warn')

    def test_locked_desktop_and_common_phase_are_projected(self):
        value = doctor({'desktopState': 'locked', **surfaces('automatic'),
                        'lockedUse': {'supported': True, 'enabled': True, 'phase': 'relocking'}})
        self.assertEqual(value['states']['desktop'], 'locked')
        self.assertEqual(value['extensions']['lockedUse']['phase'], 'relocking')


if __name__ == '__main__':
    unittest.main()
