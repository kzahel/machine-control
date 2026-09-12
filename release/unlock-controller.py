#!/usr/bin/env python3
"""Controller-side signing and one-shot credentials for the packaged Windows carrier.

The command after -- must run the installed machine-control-windows.exe unlock
--relay --instance INSTANCE, locally or through an authenticated SSH transport.
Only a signature crosses that transport; the private key stays on this host.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import queue
import uuid
from datetime import datetime, timedelta, timezone

PROTOCOL = 'machine-control-unlock/v0'


def openssl(arguments, data=None):
    return subprocess.run(['openssl', *arguments], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True).stdout


def generate(key, public):
    if key.exists() or public.exists():
        raise ValueError('Refusing to overwrite key material')
    key.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    private = openssl(['genpkey', '-algorithm', 'EC', '-pkeyopt', 'ec_paramgen_curve:P-256'])
    with os.fdopen(os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as output:
        output.write(private)
    der = openssl(['pkey', '-in', str(key), '-pubout', '-outform', 'DER'])
    with public.open('x') as output:
        output.write(base64.b64encode(der).decode() + '\n')
    print(json.dumps({'controllerFingerprint': hashlib.sha256(der).hexdigest()}))


def proposal(args):
    value = dict(schema='machine-control-unlock-grant/v0', revision=uuid.uuid4().hex,
                 targetUserSid=args.target_sid, transportUserSid=args.transport_sid,
                 controllerPublicKey=args.public.read_text().strip())
    if args.hours:
        value['expiresAt'] = (datetime.now(timezone.utc) + timedelta(hours=args.hours)).isoformat()
    with args.output.open('x') as output:
        os.chmod(args.output, 0o600)
        json.dump(value, output, indent=2)
        output.write('\n')


def validate_challenge(value, grant, instance, kind):
    fingerprint = hashlib.sha256(base64.b64decode(grant['controllerPublicKey'], validate=True)).hexdigest()
    expected = dict(protocol=PROTOCOL, instance=instance, grantRevision=grant['revision'],
                    targetUserSid=grant['targetUserSid'], credentialKind=kind,
                    controllerFingerprint=fingerprint)
    if any(value.get(key) != item for key, item in expected.items()):
        raise ValueError('Challenge differs from approved account/controller/instance')
    deadline = datetime.fromisoformat(value['deadline'].replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    if not now < deadline <= now + timedelta(minutes=1):
        raise ValueError('Challenge is expired or has an invalid deadline')
    if len(bytes.fromhex(value['nonce'])) != 32 or uuid.UUID(value['serviceGeneration']).hex != value['serviceGeneration']:
        raise ValueError('Malformed challenge generation or nonce')


class Frames:
    """Bounded output with a timeout, including when the SSH carrier disconnects."""
    def __init__(self, stream):
        self.messages = queue.Queue(maxsize=8)
        def read():
            try:
                while True:
                    data = stream.readline(16385)
                    if not data or len(data) > 16384 or not data.endswith(b'\n'):
                        self.messages.put(ValueError('Carrier closed or exceeded frame bound'))
                        return
                    self.messages.put(json.loads(data))
            except Exception:
                self.messages.put(ValueError('Invalid carrier response'))
        self.thread = threading.Thread(target=read, daemon=True)
        self.thread.start()

    def next(self):
        try:
            message = self.messages.get(timeout=70)
        except queue.Empty:
            raise ValueError('Unlock carrier timed out') from None
        if isinstance(message, Exception):
            raise message
        return message


def run(args):
    grant = json.loads(args.grant.read_text())
    public = openssl(['pkey', '-in', str(args.key), '-pubout', '-outform', 'DER'])
    if base64.b64encode(public).decode() != grant['controllerPublicKey']:
        raise ValueError('Private key differs from approved controller')
    command = args.carrier[1:] if args.carrier[:1] == ['--'] else args.carrier
    if not command:
        raise ValueError('An authenticated carrier command is required after --')
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    frames = Frames(process.stdout)
    def send(value):
        process.stdin.write((json.dumps(value, separators=(',', ':')) + '\n').encode())
        process.stdin.flush()
    try:
        send(dict(operation='unlock', credentialKind=args.kind))
        frame = frames.next()
        if frame.get('stage') != 'challenge':
            print(json.dumps(frame))
            return 1
        challenge_text = frame['challenge']
        validate_challenge(json.loads(challenge_text), grant, args.instance, args.kind)
        signature = openssl(['dgst', '-sha256', '-sign', str(args.key)], challenge_text.encode('utf-8'))
        send(dict(signature=base64.b64encode(signature).decode()))
        frame = frames.next()
        if frame.get('stage') != 'ready':
            print(json.dumps(frame))
            return 1
        if frame.get('credentialTransport') != 'uint16le-length+utf8' or frame.get('maximumBytes') != 256:
            raise ValueError('Unexpected credential transport')
        # Do not even open the credential source until controller authorization
        # and native credential-field discovery have both succeeded.
        if args.secret_file:
            with args.secret_file.open('rb') as source:
                secret = bytearray(source.read(258))
            if secret.endswith(b'\n'):
                del secret[-1:]
                if secret.endswith(b'\r'):
                    del secret[-1:]
        else:
            if sys.stdin.isatty():
                raise ValueError('Use a non-echoing redirected credential source or --secret-file')
            secret = bytearray(sys.stdin.buffer.read(257))
        try:
            if not 1 <= len(secret) <= 256 or any(value in secret for value in (0, 10, 13)):
                raise ValueError('Credential must contain 1-256 UTF-8 bytes without line breaks')
            process.stdin.write(len(secret).to_bytes(2, 'little'))
            process.stdin.write(secret)
            process.stdin.flush()
        finally:
            secret[:] = b'\0' * len(secret)
        frame = frames.next()
        print(json.dumps(frame))
        return 0 if frame.get('result', {}).get('effect') == 'confirmed' else 1
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        process.stdout.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    keygen = commands.add_parser('keygen')
    keygen.add_argument('--key', type=Path, required=True)
    keygen.add_argument('--public', type=Path, required=True)
    grant = commands.add_parser('proposal')
    grant.add_argument('--target-sid', required=True)
    grant.add_argument('--transport-sid', required=True)
    grant.add_argument('--public', type=Path, required=True)
    grant.add_argument('--hours', type=float)
    grant.add_argument('--output', type=Path, required=True)
    unlock = commands.add_parser('unlock')
    unlock.add_argument('--instance', default='default')
    unlock.add_argument('--grant', type=Path, required=True)
    unlock.add_argument('--key', type=Path, required=True)
    unlock.add_argument('--kind', choices=['password', 'pin'], default='password')
    unlock.add_argument('--secret-file', type=Path)
    unlock.add_argument('carrier', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == 'keygen':
        generate(args.key, args.public)
        return 0
    if args.action == 'proposal':
        proposal(args)
        return 0
    return run(args)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        # Never print OpenSSL input, private key bytes or credential contents.
        print(type(error).__name__ + ': unlock setup/transport refused', file=sys.stderr)
        raise SystemExit(1)
