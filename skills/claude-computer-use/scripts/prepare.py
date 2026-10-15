#!/usr/bin/env python3
"""Write a private, app-scoped Claude MCP config; optionally probe startup."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sys


ROOT = Path(__file__).resolve().parents[3]
BRIDGE = ROOT / 'tests/experiments/sky-external/bridge.py'


def runtime_config(path):
    """Validate shape without disclosing runtime env values in diagnostics."""
    try:
        config = json.loads(path.read_text())['mcpServers']['cua_repl']
    except (ValueError, KeyError, TypeError):
        raise ValueError('Expected an installed MCP config with mcpServers.cua_repl') from None
    if not isinstance(config, dict):
        raise ValueError('cua_repl must be an MCP server object')
    command, args, env = config.get('command'), config.get('args', []), config.get('env', {})
    if not isinstance(command, str) or not command:
        raise ValueError('cua_repl.command must name an executable')
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise ValueError('cua_repl.args must be a list of strings')
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                          for k, v in env.items()):
        raise ValueError('cua_repl.env must contain string keys and values')
    if not shutil.which(command, path=env.get('PATH', os.environ.get('PATH', ''))):
        raise ValueError('Selected runtime executable is missing or not executable')
    if not Path(command).is_absolute() and '/' in command:
        raise ValueError('Relative runtime executable paths are not portable between hosts')
    return config


def probe(config, apps, output):
    spec = importlib.util.spec_from_file_location('mc_sky_bridge', BRIDGE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bridge = module.Bridge(lambda: module.MCP(config, output, approved_apps=apps))
    stage = 'initialize'
    result = {'ok': False, 'scope': 'startup-and-tool-shape-only'}
    try:
        bridge.handle('initialize', {'protocolVersion': '2024-11-05'})
        stage = 'tools/list'
        listed = bridge.handle('tools/list', {})
        stage = 'close'
        bridge.handle('tools/call', {'name': 'sky_close'})
        result.update(ok=True, tools=[tool['name'] for tool in listed['tools']])
    finally:
        try:
            bridge.close()
        finally:
            result['stage'] = stage
            (output / 'probe.json').write_text(json.dumps(result, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-config', required=True, type=Path)
    parser.add_argument('--allow-app', required=True, action='append')
    parser.add_argument('--output-dir', required=True, type=Path,
                        help='New private directory, outside the checkout; never overwritten')
    parser.add_argument('--probe', action='store_true', help='Initialize/list/close, without app access')
    args = parser.parse_args()
    os.umask(0o077)
    # Termination must unwind probe/factory cleanup, not orphan its native child.
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    try:
        selected = args.runtime_config.expanduser().resolve(strict=True)
        config = runtime_config(selected)
        apps = list(dict.fromkeys(args.allow_app))
        if not all(re.fullmatch(r'[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+', app) for app in apps):
            raise ValueError('Use exact application bundle IDs; names and wildcards are unsupported')
        if not BRIDGE.is_file():
            raise ValueError('Complete Machine Control checkout required; adapter not found')
        output = args.output_dir.expanduser().resolve()
        if output == ROOT or ROOT in output.parents:
            raise ValueError('Keep private configuration and runtime evidence outside the checkout')
        output.mkdir(parents=True, mode=0o700, exist_ok=False)
        server = {'command': sys.executable, 'args': [str(BRIDGE), '--config', str(selected)]}
        for app in apps:
            server['args'].extend(['--allow-app', app])
        server['args'].extend(['--evidence', str(output / 'runtime')])
        destination = output / 'mcp.json'
        destination.write_text(json.dumps({'mcpServers': {'sky_experiment': server}}, indent=2) + '\n')
        if args.probe:
            diagnostic = output / 'preflight'
            diagnostic.mkdir(mode=0o700)
            probe(config, apps, diagnostic)
        print(json.dumps({'config': str(destination), 'approvedApps': apps,
                          'status': 'startup-probed' if args.probe else 'configuration-written',
                          'appAccessVerified': False}))
    except Exception as error:
        # Runtime exceptions may embed private protocol payloads. Keep public
        # diagnostics structural; detailed native stderr stays in the output dir.
        if isinstance(error, (ValueError, FileExistsError, FileNotFoundError)):
            print(f'Setup failed: {error}', file=sys.stderr)
        else:
            print(f'Startup probe failed ({type(error).__name__}); inspect private preflight evidence',
                  file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
