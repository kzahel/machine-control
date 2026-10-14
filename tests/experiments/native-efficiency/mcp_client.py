"""Bounded stdio MCP host for an installed runtime in a dedicated test guest."""
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time


class MCP:
    def __init__(self, config, output):
        self.output = Path(output)
        self.messages = queue.Queue()
        self.sequence = 0
        self.elicitations = []
        env = {k: v for k, v in os.environ.items() if k in
               ('HOME', 'PATH', 'TMPDIR', 'USER', 'LOGNAME', 'SHELL')}
        env.update(config.get('env', {}))
        env['CUA_REPL_ENABLED_SURFACES'] = 'computer'
        self.stderr = (self.output / 'mcp-stderr.txt').open('w')
        self.process = subprocess.Popen([config['command'], *config.get('args', [])],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
            text=True, bufsize=1, env=env, start_new_session=True)
        def read():
            try:
                for line in self.process.stdout:
                    try: self.messages.put(json.loads(line))
                    except ValueError: self.messages.put({'invalidLine': line[:1000]})
            finally:
                self.messages.put({'closed': True})
        threading.Thread(target=read, daemon=True).start()
        self.request('initialize', {'protocolVersion': '2024-11-05',
            'capabilities': {'elicitation': {}},
            'clientInfo': {'name': 'mc-native-efficiency', 'version': '1'}})
        self.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})

    def send(self, value):
        self.process.stdin.write(json.dumps(value) + '\n'); self.process.stdin.flush()

    def request(self, method, params, timeout=90):
        self.sequence += 1
        ident = self.sequence
        self.send({'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params})
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise TimeoutError(method)
            message = self.messages.get(timeout=remaining)
            if message.get('closed'): raise RuntimeError('MCP runtime exited')
            if message.get('method') == 'elicitation/create':
                self.elicitations.append(message)
                (self.output / 'elicitations.json').write_text(json.dumps(self.elicitations, indent=2))
                meta = message.get('params', {}).get('_meta', {})
                # Only our two owned fixture apps, never arbitrary requested apps.
                apps = {'org.machine-control.efficiency.target', 'org.machine-control.efficiency.sentinel'}
                allowed = (meta.get('connector_id') == 'computer-use' and
                           meta.get('tool_params', {}).get('app') in apps)
                self.send({'jsonrpc': '2.0', 'id': message['id'], 'result':
                    {'action': 'accept' if allowed else 'decline', 'content': {}}})
            elif message.get('id') == ident:
                if 'error' in message: raise RuntimeError(message['error'])
                return message.get('result')
            elif 'method' in message and 'id' in message:
                self.send({'jsonrpc': '2.0', 'id': message['id'],
                           'error': {'code': -32601, 'message': 'Unsupported host request'}})

    def js(self, code):
        start = time.perf_counter()
        result = self.request('tools/call', {'name': 'js', 'arguments': {'code': code, 'title': 'Native fixture probe'}})
        return {'seconds': time.perf_counter() - start, 'result': result}

    def close(self):
        try:
            if self.process.poll() is None:
                try: self.request('tools/call', {'name': 'js_reset', 'arguments': {}}, timeout=10)
                except Exception: pass
                os.killpg(self.process.pid, signal.SIGTERM)
                try: self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL); self.process.wait(timeout=10)
        finally:
            self.stderr.close()
