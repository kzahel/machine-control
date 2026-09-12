import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import base64
import hashlib
import uuid
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
