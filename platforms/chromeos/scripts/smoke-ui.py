#!/usr/bin/env python3
"""Find a newly visible Settings button, excluding baseline shelf icons."""
import argparse
import json
from pathlib import Path


def new_button_indices(baseline, current):
    def signature(match):
        return json.dumps(match.get('location'), sort_keys=True)
    known = {signature(match) for match in baseline['matches']}
    return [index for index, match in enumerate(current['matches'], 1)
            if match.get('location') and not match.get('state', {}).get('invisible')
            and not match.get('state', {}).get('offscreen') and signature(match) not in known]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('current', type=Path)
    parser.add_argument('--absent', action='store_true')
    args = parser.parse_args()
    try:
        indices = new_button_indices(json.loads(args.baseline.read_text()), json.loads(args.current.read_text()))
    except (OSError, ValueError, KeyError, TypeError):
        raise SystemExit(1)
    if args.absent:
        raise SystemExit(0 if not indices else 1)
    if len(indices) != 1:
        raise SystemExit(1)
    print(indices[0])
