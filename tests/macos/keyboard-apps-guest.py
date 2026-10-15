#!/usr/bin/env python3
"""Guest-only Terminal/readline and Electron editor keyboard effects."""
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time


def main():
    root = Path(sys.argv[1])
    stage = root.parent
    spec = importlib.util.spec_from_file_location('keyboard', stage / 'keyboard-layouts.py')
    keyboard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(keyboard)
    command = keyboard.command
    model = command(['/usr/sbin/sysctl', '-n', 'hw.model']).decode().strip()
    assert model.startswith('VirtualMac'), 'Tart guest required'
    root.mkdir(exist_ok=False)
    environment = stage / 'environment'
    env = lambda *args: json.loads(command([environment, *args]))
    initial = env('status')
    mapping = keyboard.normalized_hid_mapping(initial['modifierMapping'])
    resident = Path.home() / 'Applications/Machine Control.app/Contents/MacOS/macui'
    socket = Path.home() / 'Library/Application Support/MachineControl/control.sock'
    generation = None
    layout = None
    checks = 0

    def control(operation, target=None, **fields):
        nonlocal generation, checks
        request = dict(operation=operation, provider='macos-native', **fields)
        if target is not None:
            request['target'] = str(target)
        result = json.loads(command([resident, 'request', socket, json.dumps(request)]))
        assert result.get('accepted'), result.get('errorCode')
        assert result.get('hostInterference') == 'none'
        if generation is None:
            generation = result['generation']
        assert result['generation'] == generation, 'Resident restarted during app matrix'
        if operation == 'input.key':
            assert result['data']['activeLayoutId'] == layout, 'Application changed its input source'
        checks += 1
        return result

    def key(pid, chord):
        return control('input.key', pid, key=chord)

    def text(pid, value):
        return control('input.text', pid, text=value)

    def wait(predicate, label):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            try:
                value = predicate()
                if value:
                    return value
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            time.sleep(.05)
        raise AssertionError('App effect missing: ' + label)

    def applications():
        return control('applications')['data']['applications']

    def terminal_tabs(pid):
        snapshot = control('snapshot', pid, projection='compact', maxDepth=12, maxElements=300)
        return sum(e.get('role') == 'AXRadioButton' for e in snapshot['data']['elements'])

    def lines():
        path = root / 'terminal-lines'
        return path.read_bytes().split(b'\0')[:-1] if path.exists() else []

    line_count = 0

    def expect_line(value):
        nonlocal line_count
        line_count += 1
        result = wait(lambda: lines() if len(lines()) >= line_count else None, 'Terminal line')
        assert result[line_count - 1] == value.encode(), 'Terminal/readline text differs'

    def editor_state():
        return json.loads((root / 'editor-state.json').read_text())

    runtime = Path.home() / 'Library/Application Support/macvm-testbed/framework-runtimes/Electron.app'
    assert runtime.exists(), 'Install the pinned framework Electron runtime first'
    pin = re.search(r"^MACVM_ELECTRON_VERSION='([^']+)'", (stage / 'framework-versions.env').read_text(), re.M).group(1)
    runtime_version = plistlib.loads((runtime / 'Contents/Info.plist').read_bytes())['CFBundleShortVersionString']
    assert runtime_version == pin, 'Pinned Electron version required'
    terminal_pid = None
    editor = None
    try:
        # A separate Terminal process owns only this test session. Its PTY runs
        # read -e; no typed bytes are ever evaluated as a command.
        existing = {app['processId'] for app in applications()}
        (root / 'terminal.inputrc').write_text('set editing-mode emacs\nset bell-style none\n')
        wrapper = ('#!/bin/bash\nexport INPUTRC=' + shlex.quote(str(root / 'terminal.inputrc')) + '\nexec /bin/bash '
                   + shlex.quote(str(stage / 'terminal-probe.sh')) + ' ' + shlex.quote(str(root)) + '\n')
        script = root / 'keyboard.command'
        script.write_text(wrapper)
        script.chmod(0o700)
        command(['/usr/bin/open', '-n', '-a', '/System/Applications/Utilities/Terminal.app', script])
        def owned_terminal():
            new = [app for app in applications() if app.get('bundleId') == 'com.apple.Terminal' and app['processId'] not in existing]
            assert len(new) <= 1, 'Exactly one owned Terminal process required'
            return new[0]['processId'] if new else None
        terminal_pid = wait(owned_terminal, 'Owned Terminal process')
        wait(lambda: (root / 'terminal-ready').exists(), 'Terminal PTY ready')

        app = root / 'Keyboard Editor.app'
        command(['/usr/bin/ditto', runtime, app])
        resources = app / 'Contents/Resources/app'
        if resources.exists():
            shutil.rmtree(resources)
        shutil.copytree(stage / 'electron-editor', resources)
        info_path = app / 'Contents/Info.plist'
        info = plistlib.loads(info_path.read_bytes())
        info['CFBundleIdentifier'] = 'org.machine-control.keyboard-editor'
        info['CFBundleName'] = 'Machine Control Keyboard Editor'
        info_path.write_bytes(plistlib.dumps(info))
        command(['/usr/bin/codesign', '--force', '--deep', '--sign', '-', '--identifier', info['CFBundleIdentifier'], app])
        editor = subprocess.Popen([str(app / 'Contents/MacOS' / info['CFBundleExecutable']), '--fixture-root=' + str(root)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        wait(lambda: editor_state().get('ready'), 'Electron editor ready')
        assert editor_state()['pid'] == editor.pid

        for layout in keyboard.LAYOUTS:
            for modifiers in ['default', 'swapped']:
                env('remap', modifiers)
                control('application.activate', terminal_pid)
                env('select', layout)
                sample = layout.rsplit('.', 1)[-1] + ' ' + modifiers + ' aAzZ09 !@#[]{}+-_ é日本語'
                text(terminal_pid, sample)
                key(terminal_pid, 'ctrl+a')
                text(terminal_pid, 'BEGIN ')
                key(terminal_pid, 'ctrl+e')
                text(terminal_pid, ' END')
                key(terminal_pid, 'return')
                expect_line('BEGIN ' + sample + ' END')
                text(terminal_pid, 'discard me')
                key(terminal_pid, 'ctrl+u')
                text(terminal_pid, 'kept')
                key(terminal_pid, 'return')
                expect_line('kept')
                text(terminal_pid, 'one two')
                key(terminal_pid, 'option+left')
                text(terminal_pid, 'X')
                key(terminal_pid, 'return')
                expect_line('one Xtwo')
                tabs = terminal_tabs(terminal_pid)
                key(terminal_pid, 'cmd+t')
                assert terminal_tabs(terminal_pid) >= max(2, tabs + 1), 'Terminal new-tab shortcut had no effect'
                key(terminal_pid, 'cmd+w')
                assert terminal_tabs(terminal_pid) == tabs, 'Terminal close-tab shortcut had no effect'
                text(terminal_pid, 'after tab')
                key(terminal_pid, 'return')
                expect_line('after tab')

                control('application.activate', editor.pid)
                env('select', layout)
                key(editor.pid, 'cmd+a')
                text(editor.pid, sample)
                wait(lambda: editor_state().get('text') == sample, 'Electron Unicode text')
                key(editor.pid, 'cmd+a')
                key(editor.pid, 'cmd+c')
                key(editor.pid, 'right')
                key(editor.pid, 'cmd+v')
                wait(lambda: editor_state().get('text') == sample + sample, 'Electron copy/paste')
                key(editor.pid, 'cmd+z')
                wait(lambda: editor_state().get('text') == sample, 'Electron undo')
                saves = editor_state()['saves']
                key(editor.pid, 'cmd+s')
                wait(lambda: editor_state()['saves'] == saves + 1 and editor_state().get('savedText') == sample, 'Electron Save accelerator')
                finds = editor_state()['finds']
                key(editor.pid, 'cmd+f')
                wait(lambda: editor_state()['finds'] == finds + 1, 'Electron Find accelerator')
                text(editor.pid, 'find query')
                wait(lambda: editor_state().get('query') == 'find query', 'Electron find-field focus')
                key(editor.pid, 'escape')
                flags = env('status')
                assert flags['hidFlags'] & keyboard.MODIFIERS == 0 and flags['sessionFlags'] & keyboard.MODIFIERS == 0
                print(json.dumps({'layout': layout, 'mapping': modifiers, 'terminal': True, 'electron': True, 'residentChecks': checks}), flush=True)
        print(json.dumps({'passed': True, 'applications': ['Terminal/readline', 'Electron editor'], 'cells': 6, 'residentChecks': checks, 'electronVersion': runtime_version}), flush=True)
    finally:
        try:
            env('select', initial['inputSourceId'])
            command(['/usr/bin/hidutil', 'property', '--set', json.dumps({'UserKeyMapping': mapping})])
        finally:
            if editor is not None:
                try:
                    os.killpg(editor.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    editor.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(editor.pid, signal.SIGKILL)
                    editor.wait()
            if terminal_pid:
                process = subprocess.run(['/bin/ps', '-p', str(terminal_pid), '-o', 'command='], stdout=subprocess.PIPE, timeout=5)
                if process.returncode == 0 and '/Terminal.app/Contents/MacOS/Terminal' in process.stdout.decode():
                    os.kill(terminal_pid, signal.SIGTERM)
                    def terminal_exited():
                        return subprocess.run(['/bin/ps', '-p', str(terminal_pid)], stdout=subprocess.DEVNULL, timeout=5).returncode != 0
                    wait(terminal_exited, 'Owned Terminal exit')
            shutil.rmtree(root)


if __name__ == '__main__':
    main()
