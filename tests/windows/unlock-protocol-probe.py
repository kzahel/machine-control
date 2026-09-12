#!/usr/bin/env python3
"""Negative tests over an installed carrier; never open a Windows credential."""
import argparse
import base64
import importlib.util
from pathlib import Path
import subprocess
import json

spec = importlib.util.spec_from_file_location('controller', Path(__file__).resolve().parents[2] / 'release/unlock-controller.py')
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


def connect(command):
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    frames = controller.Frames(process.stdout)
    send(process, dict(operation='unlock', credentialKind='password'))
    return process, frames


def send(process, value):
    process.stdin.write((json.dumps(value) + '\n').encode())
    process.stdin.flush()


def close(process):
    process.stdin.close()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    process.stdout.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['wrong-key', 'replay', 'refused', 'ready'], required=True)
    parser.add_argument('--key', type=Path)
    parser.add_argument('--error', default='not_armed_or_expired')
    parser.add_argument('carrier', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.carrier[1:] if args.carrier[:1] == ['--'] else args.carrier
    process, frames = connect(command)
    try:
        initial = frames.next()
        if args.mode == 'refused':
            assert initial.get('stage') == 'refused' and initial.get('errorCode') == args.error, initial.get('stage')
            assert initial.get('credentialRead') is False
        else:
            assert initial.get('stage') == 'challenge', initial.get('stage')
            challenge = initial['challenge']
            proof = controller.openssl(['dgst', '-sha256', '-sign', str(args.key)], challenge.encode())
            if args.mode == 'replay':
                close(process)
                process, frames = connect(command)
                another = frames.next()
                assert another.get('stage') == 'challenge' and another['challenge'] != challenge
            send(process, dict(signature=base64.b64encode(proof).decode()))
            refusal = frames.next()
            if args.mode == 'ready':
                assert refusal.get('stage') == 'ready', (refusal.get('stage'), refusal.get('errorCode'), refusal.get('result', {}).get('errorCode'), refusal.get('result', {}).get('message'))
                assert refusal.get('credentialTransport') == 'uint16le-length+utf8'
            else:
                assert refusal.get('stage') == 'refused' and refusal.get('errorCode') == 'controller_signature_denied', refusal.get('stage')
                assert refusal.get('credentialRead') is False
        print(json.dumps(dict(schema='machine-control-unlock-probe/v0', mode=args.mode, passed=True, credentialRead=False)))
    finally:
        close(process)


if __name__ == '__main__':
    main()
