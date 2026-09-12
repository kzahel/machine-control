import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import base64
import hashlib
import uuid
import io
import json
from contextlib import redirect_stdout
from unittest.mock import Mock, patch
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('unlock_controller', Path(__file__).resolve().parents[2] / 'release/unlock-controller.py')
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


class UnlockChallengeTests(unittest.TestCase):
    def setUp(self):
        public = b'public-key-fixture'
        self.grant = dict(revision=uuid.uuid4().hex, targetUserSid='account-sid',
                          controllerPublicKey=base64.b64encode(public).decode())
        self.challenge = dict(protocol=controller.PROTOCOL, instance='example',
            grantRevision=self.grant['revision'], targetUserSid='account-sid', credentialKind='password',
            controllerFingerprint=hashlib.sha256(public).hexdigest(), nonce='12' * 32,
            serviceGeneration=uuid.uuid4().hex,
            deadline=(datetime.now(timezone.utc) + timedelta(seconds=40)).isoformat())

    def validate(self, value):
        controller.validate_challenge(value, self.grant, 'example', 'password')

    def test_accepts_exact_approval(self):
        self.validate(self.challenge)

    def test_rejects_changed_authority(self):
        for key in ('protocol', 'instance', 'grantRevision', 'targetUserSid', 'credentialKind', 'controllerFingerprint'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate({**self.challenge, key: 'different'})

    def test_rejects_expired_and_unbounded_challenges(self):
        for seconds in (-1, 120):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                self.validate({**self.challenge, 'deadline': (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()})

    def test_rejects_invalid_generation(self):
        with self.assertRaises(ValueError):
            self.validate({**self.challenge, 'serviceGeneration': 'label'})
        with self.assertRaises(ValueError):
            self.validate({**self.challenge, 'nonce': '00'})

    def test_invalid_expiry_cannot_become_an_indefinite_grant(self):
        for hours in (0, -1, float('nan'), float('inf')):
            with self.subTest(hours=hours), self.assertRaises(ValueError):
                controller.proposal(SimpleNamespace(hours=hours))

    def run_failure(self, challenge, replies):
        source = Mock()
        source.open.return_value = io.BytesIO(b'fixture-credential')
        process = Mock(stdin=io.BytesIO(), stdout=io.BytesIO())
        frames = Mock()
        frames.next.side_effect = [dict(stage='challenge', challenge=json.dumps(challenge)), *replies]
        args = SimpleNamespace(grant=Mock(read_text=lambda: json.dumps(self.grant)), key=Path('fixture-key'),
            carrier=['fixture-carrier'], instance='example', kind='password', secret_file=source)
        output = io.StringIO()
        with patch.object(controller.subprocess, 'Popen', return_value=process), \
                patch.object(controller, 'Frames', return_value=frames), \
                patch.object(controller, 'openssl', return_value=b'public-key-fixture'), redirect_stdout(output):
            self.assertEqual(controller.run(args), 1)
        return json.loads(output.getvalue()), source

    def test_rejected_challenge_never_opens_credential(self):
        result, source = self.run_failure({**self.challenge,
            'deadline': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()}, [])
        source.open.assert_not_called()
        self.assertEqual(result['phase'], 'challenge_validation')
        self.assertFalse(result['credentialRead'])
        self.assertEqual(result['delivery'], 'not_sent')

    def test_disconnect_after_submission_reports_unknown_delivery(self):
        result, source = self.run_failure(self.challenge, [dict(stage='ready',
            credentialTransport='uint16le-length+utf8', maximumBytes=256), ValueError('Disconnected')])
        source.open.assert_called_once_with('rb')
        self.assertEqual(result['phase'], 'result')
        self.assertTrue(result['credentialRead'])
        self.assertEqual(result['delivery'], 'unknown')
        self.assertEqual(result['retrySafety'], 'never_automatically')
