#!/usr/bin/env python3
"""Held-out Finder fixture; controller setup and independent filesystem oracle."""
import argparse
import hashlib
import json
from pathlib import Path


def setup(root, seed):
    root.mkdir(parents=True, exist_ok=False)
    for name in ('incoming', 'decoy', 'archive'):
        (root/name).mkdir()
    payload = hashlib.sha256(seed.encode()).hexdigest() + '\n'
    (root/'incoming/draft.txt').write_text(payload)
    (root/'decoy/draft.txt').write_text('Leave this same-named file untouched.\n')
    (root/'expected.json').write_text(json.dumps({'payload': payload,
        'decoy': (root/'decoy/draft.txt').read_text()}))


def oracle(root):
    expected = json.loads((root/'expected.json').read_text())
    actual = {str(p.relative_to(root)): p.read_bytes() for name in ('incoming', 'archive', 'decoy')
              for p in (root/name).rglob('*') if p.is_file()}
    passed = actual == {'archive/reviewed.txt': expected['payload'].encode(),
                        'decoy/draft.txt': expected['decoy'].encode()}
    return {'passed': passed, 'detail': 'Exact moved bytes and untouched decoy; no extra files'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('setup', 'oracle'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--seed', default='fixture')
    args = parser.parse_args()
    if args.operation == 'setup':
        setup(args.root, args.seed)
    else:
        print(json.dumps(oracle(args.root)))
