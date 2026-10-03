#!/usr/bin/env python3
"""Typed bridge for host-interfering VM input; no legacy fallback."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client"))
sys.path.insert(0, str(ROOT / "providers/claims"))
import claims
import machine_control as mc
from outer_session import OuterSession


def text_keys(text):
    keys = []
    plain = "abcdefghijklmnopqrstuvwxyz0123456789=[];'\\,./`"
    shifted = dict(zip('!@#$%^&*()_+{}:"|<>?~', "1234567890-=[];'\\,./`"))
    for char in text:
        if char == '-': keys.append('minus')
        elif char in plain: keys.append(char)
        elif char in '\n\r': keys.append('enter')
        elif char == '\t': keys.append('tab')
        elif char == ' ': keys.append('space')
        elif char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ': keys.append('shift-' + char.lower())
        elif char in shifted: keys.append('shift-' + ('minus' if shifted[char] == '-' else shifted[char]))
        else: raise mc.ClientError('outer_text_unsupported', 'Outer physical typing requires US-keyboard ASCII')
    return keys


def run(args):
    if args.operation == 'type-secret':
        raise mc.ClientError('secret_safe_outer_transport_unavailable',
                             'Credential recovery requires a verified secret-safe route')
    check = claims.parser().parse_args(['--state-dir', args.state_dir, 'check', '--provider', args.provider,
        '--resource-id', args.resource, '--claim-id', os.environ.get('MACHINE_CONTROL_CLAIM_ID', ''),
        '--required-use-class', 'disruptive'])
    verified = claims.command_check(check)['data']
    binding = dict(schema='machine-control-outer-borrow/v1', directory=str(Path(args.state_dir).resolve()),
        provider=args.provider, resource=args.resource, claimId=verified['claimId'],
        generation=verified['generation'], windowName=args.window_name,
        displayWidth=args.width, displayHeight=args.height)
    # This byte adapter reaches the actual local native arbiter. VM coordination
    # remains in the borrowed binding; a second independent host/VM holder is
    # neither created nor inherited from MACHINE_CONTROL_CLAIM_ID.
    host = dict(command=[sys.executable, str(ROOT / 'platforms/macos/host/machost.py')],
        environment={'MACHINE_CONTROL_CLAIM_ID': ''}, claimPolicy='unsupported')
    values = args.values
    if args.operation == 'type':
        if len(values) != 1 or len(values[0]) > 8192: raise mc.ClientError('invalid_outer_input', 'One bounded text argument is required')
        keys = text_keys(values[0])  # validate all keys before reserving/focusing
    elif args.operation == 'key':
        if len(values) != 1: raise mc.ClientError('invalid_outer_input', 'One key chord is required')
        parts = values[0].lower().split('-')
        names = set("abcdefghijklmnopqrstuvwxyz0123456789=[];'\\,./`") | {'minus','enter','return','tab','space','delete','escape','left','right','up','down'}
        if parts[-1] not in names or any(v not in {'cmd','command','shift'} for v in parts[:-1]):
            raise mc.ClientError('outer_key_unsupported', 'Outer keys support Command/Shift and one named physical key')
        keys = [values[0]]
    else:
        count = 2 if args.operation == 'click' else 4
        if len(values) not in ({2, 3} if count == 2 else {4}): raise mc.ClientError('invalid_outer_input', 'Invalid pointer arguments')
        try: coordinates = [int(v) for v in values[:count]]
        except ValueError: raise mc.ClientError('invalid_outer_coordinate', 'Guest coordinates must be integers')
        if any(v < 0 or v >= (args.width if n % 2 == 0 else args.height) for n,v in enumerate(coordinates)):
            raise mc.ClientError('invalid_outer_coordinate', 'Guest coordinates exceed the selected display')
        button = values[2] if count == 2 and len(values) == 3 else 'left'
        if button not in {'left', 'right', 'middle', 'double'}: raise mc.ClientError('invalid_outer_button', 'Invalid pointer button')
    with OuterSession(host, binding, reason='Explicit VM outer input recovery', wait=args.wait, duration=300) as owner:
        owner.prepare(); owner.begin()
        if args.operation in {'type', 'key'}:
            for key in keys: owner.step('key', key=key)
        elif args.operation == 'click':
            owner.step('click', x=coordinates[0], y=coordinates[1], button='left' if button == 'double' else button)
            if button == 'double': owner.step('click', x=coordinates[0], y=coordinates[1], button='left', clickCount=2)
        else:
            x,y,x2,y2 = coordinates
            owner.step('dragStart', x=x, y=y)
            for step in range(1,21):
                owner.step('dragMove', x=round(x+(x2-x)*step/20), y=round(y+(y2-y)*step/20))
                owner.stopped.wait(.025)
            owner.step('dragEnd', x=x2, y=y2)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', required=True)
    parser.add_argument('--provider', choices=['tart-macos','utm-macos'], required=True)
    parser.add_argument('--resource', required=True)
    parser.add_argument('--window-name', required=True)
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--height', type=int, required=True)
    parser.add_argument('--wait', type=int, default=300)
    parser.add_argument('operation', choices=['click','drag','type','key','type-secret'])
    parser.add_argument('values', nargs='*')
    try: return run(parser.parse_args())
    except (mc.ClientError, claims.ClaimError, OSError) as error:
        print(getattr(error, 'code', 'outer_transport_unavailable'), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
