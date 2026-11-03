"""Fast Windows composition check with real native transports and fake browsers.

Run in a dedicated claimed appliance's interactive session, with no installed
desktop app running. The controller owns claims and power restoration. This
checks native admission, inherited policy IPC and authenticated native-host
connections together; browser effects still require browser-profiles-live.py.
It neither installs a native-host registration nor opens a browser.
"""
import argparse
import ctypes
from collections import deque
import json
import os
from pathlib import Path
import queue
import struct
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'client'))
from observed_owner import ObservedOwner
from cdp_socket import CdpSocket

ORIGIN = 'chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', type=Path, required=True)
    parser.add_argument('--stack-tool', type=Path, help='Write private managed stacks on failure')
    parser.add_argument('--sustain-seconds', type=int, default=0, choices=range(601), metavar='0..600')
    args = parser.parse_args()
    exe = args.install / 'runtime/machine-control-windows.exe'
    processes, sockets, owner = [], [], None
    owner_trace = deque(maxlen=256)
    budget = max(60, args.sustain_seconds+120)
    runtime = subprocess.Popen([str(exe), 'desktop'], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    processes.append(runtime)
    replies = queue.Queue()

    def read_operator():
        for line in runtime.stdout:
            replies.put(json.loads(line))
        replies.put(None)

    threading.Thread(target=read_operator, daemon=True).start()

    def operator(method, **fields):
        runtime.stdin.write(json.dumps(dict(method=method, **fields)).encode()+b'\n')
        runtime.stdin.flush()
        result = replies.get(timeout=20)
        assert result and result.get('ok'), result
        return result

    def provider(name, suffix):
        child = subprocess.Popen([str(exe), ORIGIN], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        processes.append(child)

        def send(frame):
            data = json.dumps(frame).encode()
            child.stdin.write(struct.pack('<I', len(data))+data)
            child.stdin.flush()

        def read_exact(count):
            data = b''
            while len(data) < count:
                part = child.stdout.read(count-len(data))
                if not part:
                    raise EOFError('Native fixture disconnected')
                data += part
            return data

        send(dict(type='hello', protocolVersion=1, extensionVersion='fixture', profile=dict(
            protocolVersion=1, installationId='00000000-0000-4000-8000-00000000000'+str(suffix),
            name=name, enabled=True)))

        def serve():
            try:
                while True:
                    size = struct.unpack('<I', read_exact(4))[0]
                    assert 0 < size <= 1024*1024
                    frame = json.loads(read_exact(size))
                    if frame['type'] == 'request':
                        assert frame['operation'] == 'browser.tabs'
                        send(dict(type='response', id=frame['id'], ok=True,
                                  data=dict(tabs=[dict(tabId=suffix, title=name,
                                                      url='https://example.invalid/'+name.lower())])))
                    elif frame['type'] == 'session.open':
                        send(dict(type='session.opened', id=frame['id']))
                    elif frame['type'] == 'session.command':
                        send(dict(type='session.result', id=frame['id'], cmdId=frame['cmdId'],
                                  result=dict(nativeFixture=name),
                                  **({'sessionId': frame['sessionId']} if 'sessionId' in frame else {})))
            except (OSError, EOFError):
                pass

        threading.Thread(target=serve, daemon=True).start()

    try:
        operator('hello', processId=os.getpid())
        provider('Work', 1)
        provider('Personal', 2)
        deadline = time.monotonic()+30
        while True:
            state = operator('state')['state']['browser']
            profiles = [p for p in state['profiles'] if p['connected']]
            if len(profiles) == 2:
                break
            assert state['available'], state
            assert time.monotonic() < deadline, 'Native providers did not attach'
            time.sleep(.1)
        operator('arm', scopes=['browser', 'devtools'], duration=budget,
                 browserProfileIds=[p['profileId'] for p in profiles])
        session = ctypes.c_uint32()
        assert ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session))
        owner = ObservedOwner({'command': [str(exe), 'channel', '--profile', 'user', '--instance', 'desktop',
                                            '--session-id', str(session.value)]},
                               reason='Native browser composition fixture', scopes=['browser', 'devtools'], wait=30, duration=budget, trace=owner_trace)
        owner.wait()
        for profile in profiles:
            result = owner.call(dict(operation='browser.tabs', browserProfileId=profile['profileId']))
            assert result['accepted'], result
            assert result['data']['tabs'][0]['title'] == profile['name'], result
            endpoint = owner.call(dict(operation='browser.endpoint', browserProfileId=profile['profileId']))
            assert endpoint['accepted'], endpoint
            stream = CdpSocket(endpoint['data']['devtoolsEndpoint'].replace('<tabId>', str(result['data']['tabs'][0]['tabId'])))
            sockets.append(stream)
            assert stream.call('Runtime.enable')['result']['nativeFixture'] == profile['name']
        until = time.monotonic()+args.sustain_seconds
        while time.monotonic() < until:
            assert owner.status()['state'] == 'active', 'Native owner heartbeat ended'
            time.sleep(.25)
        owner.close(); owner = None
        operator('stop')
        assert not operator('state')['state']['browser']['approvedProfiles']
        print('Windows native browser composition passed', flush=True)
    except BaseException as error:
        print('Failure code: '+str(getattr(error, 'code', type(error).__name__)), flush=True)
        print(json.dumps(dict(ownerRpcTrace=list(owner_trace)[-80:])), flush=True)
        if args.stack_tool and runtime.poll() is None:
            try:
                subprocess.run([str(args.stack_tool), 'report', '--process-id', str(runtime.pid)], timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                print('Managed stack collection unavailable', flush=True)
        try:
            state = operator('state')['state']
            print(json.dumps({key: state.get(key) for key in ['browser', 'admission', 'physicalAvailability']}), flush=True)
        except Exception:
            pass
        raise
    finally:
        for stream in sockets:
            try: stream.close()
            except OSError: pass
        if owner:
            owner.close()
        if runtime.poll() is None:
            try:
                operator('quit')
                runtime.wait(timeout=10)
            except Exception:
                runtime.kill()
        for process in reversed(processes):
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
