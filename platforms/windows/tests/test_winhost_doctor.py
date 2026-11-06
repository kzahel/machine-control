"""Host doctor projects the resident's common status (Tactical 159 decision 8)."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('winhost', ROOT / 'platforms/windows/host/winhost.py')
winhost = importlib.util.module_from_spec(spec)
spec.loader.exec_module(winhost)


def status(desktop_state, surfaces, ready):
    return {'accepted': True, 'generation': 'g', 'sessionLocked': desktop_state == 'locked', 'data': {
        'desktopProduct': True, 'ready': ready, 'desktopState': desktop_state,
        'deployment': {'policy': {'preset': 'workstation', 'grantMode': 'surface_modes',
                                  'protectedAdministration': False},
                       'availability': {'paused': False, 'blockingReasons': []},
                       'browserOnlyWhileLocked': False},
        'lockedUse': {'supported': True, 'enabled': True, 'phase': 'ready'},
        'admission': {'surfaces': surfaces}}}


class WindowsHostDoctorTests(unittest.TestCase):
    def doctor(self, reply):
        output = io.StringIO()
        with mock.patch.object(winhost, 'resource_id', return_value='private-identity'), \
                mock.patch.object(winhost, 'call', side_effect=[reply]) as call, \
                contextlib.redirect_stdout(output):
            code = winhost.doctor()
        self.assertEqual(call.call_count, 1, 'status alone carries the deployment projection')
        return code, json.loads(output.getvalue())

    def test_locked_desktop_maps_directly(self):
        code, value = self.doctor(status('locked', {'desktop': {'mode': 'automatic'},
                                                    'browser': {'mode': 'off'}}, False))
        self.assertEqual(code, 1)
        self.assertEqual(value['states']['desktop'], 'locked')
        self.assertEqual(value['checks'][-1], {'id': 'grant', 'status': 'pass',
                                               'summary': 'Surface access: Desktop automatic'})
        self.assertEqual(value['extensions']['lockedUsePhase'], 'ready')

    def test_surfaces_off_warn_instead_of_requesting_a_grant(self):
        code, value = self.doctor(status('unlocked', {'desktop': {'mode': 'off'},
                                                      'browser': {'mode': 'automatic', 'expired': True}}, True))
        self.assertEqual(code, 0)
        self.assertEqual(value['states']['desktop'], 'unlocked')
        self.assertEqual(value['checks'][-1]['status'], 'warn')
        self.assertNotIn('grant', value['checks'][-1]['summary'].split()[0].lower())

    def test_unknown_state_is_not_guessed(self):
        code, value = self.doctor(status('unknown', {'desktop': {'mode': 'ask'}}, False))
        self.assertEqual(value['states']['desktop'], 'unknown')
        self.assertEqual(value['checks'][-1]['summary'], 'Surface access: Desktop ask')


if __name__ == '__main__':
    unittest.main()
