#!/usr/bin/env python3
"""Read-only controller routing and authenticated SSH preflight."""
import argparse
import ipaddress
import json
import os
import platform
import shutil
import socket
import subprocess


def run(argv, timeout=12):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, '', str(exc)


def vpn_route(address, route):
    try:
        local = ipaddress.ip_address(address).is_private
    except ValueError:
        return False
    return local and any(word in route.lower() for word in ('utun', 'tun0', 'tailscale', 'wireguard', 'wg0'))


def check(host):
    rc, output, error = run(['ssh', '-G', host])
    if rc:
        return {'ok': False, 'host': host, 'error': error or 'Cannot resolve SSH configuration'}
    fields = dict(line.split(' ', 1) for line in output.splitlines() if ' ' in line)
    endpoint = fields.get('hostname', host)
    proxy = fields.get('proxycommand', 'none') != 'none' or fields.get('proxyjump', 'none') != 'none'
    routes = []
    try:
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(endpoint, None, type=socket.SOCK_STREAM)})
    except OSError:
        addresses = []
    for address in addresses:
        if platform.system() == 'Darwin':
            command = ['route', '-n', 'get', address]
        elif shutil.which('ip'):
            command = ['ip', 'route', 'get', address]
        else:
            command = ['route', 'print', address] if os.name == 'nt' else []
        if command:
            code, route, err = run(command)
            routes.append({'address': address, 'route': route or err,
                           'privateAddressViaVPN': not proxy and vpn_route(address, route)})
    code, out, err = run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                         '-o', 'ConnectionAttempts=1', '-o', 'ControlPath=none',
                         host, 'printf machine-control-ssh-ready'])
    return {'ok': code == 0 and out == 'machine-control-ssh-ready', 'host': host,
            'endpoint': endpoint, 'port': fields.get('port', '22'),
            'proxyConfigured': proxy, 'routes': routes, 'sshError': err}


def explain(result):
    print(f"Controller SSH preflight: {result['host']}")
    for route in result.get('routes', []):
        print(f"Route to {route['address']}:\n{route['route']}")
        if route['privateAddressViaVPN']:
            print('CHECK: private address routes through a VPN. For a local Chromebook,')
            print('enable local LAN access on the VPN/exit node, or disconnect it.')
    if result['ok']:
        print('[OK] Authenticated SSH works from this controller.')
    else:
        print('[FAIL] ' + (result.get('sshError') or result.get('error') or 'SSH failed'))
        print('Check SSH HostName/User/Port/key and accept the host key with an initial ssh connection.')
        print('A successful Chromebook-to-controller download does not prove the reverse SSH route.')
        print('Check controller routing before changing the Chromebook firewall.')
        print('After a setup reboot, start the stateful start_sshd.sh from VT2 if needed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    result = check(os.environ.get('CHROMEBOOK_HOST', 'chromeos-testbed'))
    if args.json:
        print(json.dumps(result))
    else:
        explain(result)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
