#!/usr/bin/env python3
"""Experiment-only MCP adapter for an already-installed genuine CUA runtime.

No vendor code is copied. A controller explicitly names preauthorized
apps; all other approval requests are declined. Not a same-user sandbox.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'native-efficiency'))
from mcp_client import MCP

EXPOSED = frozenset({'js', 'js_reset'})
CLOSE = {'name': 'sky_close', 'description':
    'Finish this Computer Use experiment: release the runtime and app holds. '
    'Call after final verification. This server will not silently restart.',
    'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}}


class UnsupportedMethod(ValueError):
    pass


class Bridge:
    def __init__(self, factory, *, on_runtime_closed=None):
        self.factory = factory
        self.on_runtime_closed = on_runtime_closed
        self.runtime_closed = False
        self.runtime = None
        self.closed = False

    def handle(self, method, params):
        # Claude probes server/discover before standard MCP initialization.
        # Unknown optional methods must not terminate the subsequent handshake.
        if method not in {'initialize', 'tools/list', 'tools/call', 'ping'}:
            raise UnsupportedMethod('Unsupported MCP method')
        if method == 'ping':
            return {}
        if method == 'initialize':
            if self.runtime is not None or self.closed:
                raise ValueError('Already initialized or closed')
            self.runtime = self.factory()
            upstream = self.runtime.initialization
            return {**upstream, 'protocolVersion': params.get('protocolVersion', '2024-11-05'),
                'capabilities': {'tools': {}},
                'serverInfo': {'name': 'mc-sky-external-experiment', 'version': '0.1'},
                'instructions': upstream.get('instructions', '') +
                    '\nUse only the explicitly authorized apps for this session. Preserve native refusals. '
                    'After verification call sky_close. No MC UI or shell mutation fallback.'}
        if self.closed:
            raise ValueError('Experiment runtime closed; start a new explicitly authorized session')
        if self.runtime is None:
            raise ValueError('Initialize first')
        if method == 'tools/list':
            result = self.runtime.request('tools/list', {})
            tools = [t for t in result.get('tools', []) if t.get('name') in EXPOSED]
            if {t['name'] for t in tools} != EXPOSED:
                raise ValueError('Installed runtime does not expose the qualified js/js_reset interface')
            return {'tools': tools + [CLOSE]}
        if method == 'tools/call':
            name = params.get('name')
            if name == 'sky_close':
                self.close(reason='sky_close')
                return {'content': [{'type': 'text', 'text': 'Computer Use runtime closed.'}]}
            if name not in EXPOSED:
                raise ValueError('Tool not exposed by experiment')
            # Preserve images, native refusals and documentation without rewriting.
            return self.runtime.request(method, params, timeout=180)
        raise UnsupportedMethod('Unsupported MCP method')

    def close(self, *, reason='cleanup'):
        self.closed = True
        if self.runtime is not None:
            self.runtime.close()
            self.runtime = None
            self.runtime_closed = True
            if self.on_runtime_closed:
                self.on_runtime_closed(reason)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True,
                        help='Exact installed unified-computer-use .mcp.json, not a newest-cache guess')
    parser.add_argument('--allow-app', action='append', required=True,
                        help='Exact application bundle ID explicitly authorized by the controller')
    parser.add_argument('--evidence', type=Path, required=True,
                        help='Private directory for runtime stderr, approval requests and closure')
    args = parser.parse_args()
    os.umask(0o077)
    args.evidence.mkdir(parents=True, mode=0o700, exist_ok=True)
    config = json.loads(args.config.read_text())['mcpServers']['cua_repl']
    runtime_id = uuid.uuid4().hex
    def event(kind, **values):
        row = {'at': time.time(), 'event': kind, 'runtimeId': runtime_id, **values}
        with (args.evidence/'protocol-events.jsonl').open('a') as stream:
            stream.write(json.dumps(row)+'\n')
        return row
    def runtime_closed(reason):
        row = event('runtime-closed', reason=reason, approvalScope=args.allow_app, automaticRestart=False)
        (args.evidence / 'closed.json').write_text(json.dumps({'closed': True, 'runtimeClosed': True,
            'runtimeId': runtime_id, 'closedAt': row['at'], 'approvalScope': args.allow_app,
            'automaticRestart': False}) + '\n')
    bridge = Bridge(lambda: MCP(config, args.evidence, approved_apps=args.allow_app),
                    on_runtime_closed=runtime_closed)
    event('started')
    def stop(*unused):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        for line in sys.stdin:
            message = json.loads(line)
            event('received', method=message.get('method'))
            if 'id' not in message:
                if message.get('method') == 'notifications/cancelled':
                    bridge.close(reason='cancelled')
                continue
            try:
                result = bridge.handle(message.get('method'), message.get('params', {}))
                reply = {'jsonrpc': '2.0', 'id': message['id'], 'result': result}
            except UnsupportedMethod as error:
                reply = {'jsonrpc': '2.0', 'id': message['id'], 'error':
                         {'code': -32601, 'message': str(error)}}
            except Exception as error:
                event('failed', error=str(error))
                bridge.close(reason='request_failed')
                reply = {'jsonrpc': '2.0', 'id': message['id'], 'error':
                         {'code': -32000, 'message': str(error)}}
            print(json.dumps(reply), flush=True)
    finally:
        try:
            bridge.close(reason='process_exit')
        finally:
            event('wrapper-process-closed', runtimeClosed=bridge.runtime_closed)


if __name__ == '__main__':
    main()
