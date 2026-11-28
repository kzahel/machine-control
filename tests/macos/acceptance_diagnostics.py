"""Closed progress markers and controller-private acceptance diagnostics."""
import json
import os
import subprocess
import sys
import tempfile
import time


MARKER = b'MC_ACCEPTANCE_CHECK '
GUEST_CHECKS = {
    'guest_setup': {'verify_observer', 'backup_original', 'start_observer', 'install_candidate', 'verify_candidate'},
    'guest_campaign': {'browser_file_dialogs', 'remote_arming', 'crash_postflight', 'candidate_integrity'},
    'covered_control': {'capture_display', 'verify_cover_baseline', 'verify_concealment', 'finite_owner_expiry', 'renew_owner',
                        'observe_same_owner', 'observe_guardian', 'verify_browser_effects', 'owner_disconnect'},
    'controller_package': {'verify_candidate', 'stage_payload', 'restore_guest'},
    'reliability_reboot': {'stage_candidate', 'verify_credential', 'protected_stop', 'reboot_after_stop',
                           'save_choices', 'reboot_with_consent', 'verify_choices'},
    'smoke_preflight': {'boot_guest', 'capture_display'},
    'smoke_install': {'stage_candidate', 'verify_credential', 'initialize_observer', 'install_candidate'},
    'smoke_browser': {'access_off', 'start_browser', 'browser_round_trip'},
    'smoke_boot': {'reboot', 'access_off'},
    'smoke_protected': {'helper_setup', 'compile_fixture', 'cover', 'native_effect', 'stop_and_relock'},
    'smoke_cleanup': {'stop_guest'},
}


def announce(phase, check):
    assert check in GUEST_CHECKS[phase]
    print(f'{MARKER.decode("ascii")}{phase} {check}', flush=True)


def parse_step(line):
    if not line.startswith(MARKER) or len(line) > 128:
        return None
    try:
        phase, check = line[len(MARKER):].decode('ascii').split()
    except (UnicodeError, ValueError):
        return None
    return (phase, check) if check in GUEST_CHECKS.get(phase, ()) else None


class Timings:
    """Controller wall time, including transport and workspace lifecycle."""
    def __init__(self, clock=time.monotonic, initial_step='workspace/acquire'):
        self.clock = clock
        self.started = self.changed = clock()
        self.current = initial_step
        self.steps = []

    def observe(self, line):
        step = parse_step(line)
        if step:
            self.step('/'.join(step))

    def step(self, name):
        if self.current != name:
            now = self.clock()
            self.steps.append({'step': self.current, 'seconds': round(now - self.changed, 3)})
            self.current, self.changed = name, now

    def finish(self, path, passed):
        self.step('complete')
        path.write_text(json.dumps({'passed': passed, 'elapsedSeconds': round(self.changed - self.started, 3),
                                    'steps': self.steps}, indent=2) + '\n')


class FailureReport:
    def __init__(self, output, workspace_owned):
        self.output = output
        self.step('controller_preflight', 'validate_scope')
        self.failure = None
        self.cleanup = {'appState': 'untouched', 'guestEvidence': 'not_staged', 'stage': 'not_created',
                        'power': 'not_requested',
                        'workspace': 'enclosing_scope' if workspace_owned else 'not_managed'}

    def step(self, phase, check):
        self.phase = phase
        self.check = check

    def observe(self, line):
        step = parse_step(line)
        if not step:
            return False
        self.step(*step)
        return True

    def failed(self, error):
        if self.failure is None:
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                kind = 'interrupted'
            elif isinstance(error, subprocess.TimeoutExpired):
                kind = 'timeout'
            elif isinstance(error, subprocess.CalledProcessError):
                kind = 'command_failed'
            elif isinstance(error, AssertionError):
                kind = 'check_failed'
            else:
                kind = 'error'
            self.failure = {'phase': self.phase, 'check': self.check, 'kind': kind}

    def publish(self, mc=None):
        path = self.output / 'failure.json'
        document = {'schema': 'machine-control-macos-acceptance-failure/v1',
                    **self.failure, 'cleanup': self.cleanup}
        locator = 'unavailable'
        try:
            descriptor, temporary = tempfile.mkstemp(dir=self.output)
            try:
                with os.fdopen(descriptor, 'w') as stream:
                    json.dump(document, stream, indent=2)
                    stream.write('\n')
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            locator = json.dumps(str(path.resolve()))
            if len(locator) > 2048:
                locator = json.dumps(path.name) + ' in the controller output directory'
        except OSError:
            print('Could not save the private acceptance failure report', file=sys.stderr)
        if mc is None:
            return
        note = (f"Packaged acceptance failed during {document['phase']}/{document['check']} "
                f"({document['kind']}). Evidence: {locator}. "
                f"Observed cleanup: {json.dumps(self.cleanup, sort_keys=True)}.\n")
        try:
            subprocess.run(mc + ['usage', 'note', '--kind', 'friction', '--goal', 'Packaged desktop acceptance'],
                           input=note.encode(), stdout=subprocess.DEVNULL, timeout=30, check=True)
        except (OSError, subprocess.SubprocessError):
            print('Could not write the private acceptance usage note', file=sys.stderr)
