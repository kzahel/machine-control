#!/usr/bin/env python3
"""Extract mandatory versioned release notes from a checked-in changelog."""
import argparse
from pathlib import Path
import re


def notes(version, changelog):
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise ValueError('Expected MAJOR.MINOR.PATCH without leading zeroes')
    lines = Path(changelog).read_text(encoding='utf-8').splitlines()
    indices = [i for i, line in enumerate(lines) if line.strip() == f'## [{version}]']
    if len(indices) != 1:
        raise ValueError('Expected exactly one changelog section for the release')
    start = indices[0] + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith('## ')), len(lines))
    body = '\n'.join(lines[start:end]).strip()
    bullets = []
    fenced = False
    for line in body.splitlines():
        if re.match(r'^\s*(```|~~~)', line):
            fenced = not fenced
        if not fenced:
            match = re.match(r'^-\s+(\S.*)', line)
            if match:
                bullets.append(match[1].strip())
    if not bullets or all(re.fullmatch(r'(?i)(todo|tbd|pending|coming soon)[.!]?', b) for b in bullets):
        raise ValueError('Release notes require at least one nonempty change bullet, not a placeholder')
    return body + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('changelog', type=Path)
    parser.add_argument('version')
    args = parser.parse_args()
    print(notes(args.version, args.changelog), end='')
