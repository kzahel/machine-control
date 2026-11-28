"""Closed progress markers and controller-private acceptance diagnostics."""
import json
import os
import subprocess
import sys
import tempfile


MARKER = b'MC_ACCEPTANCE_CHECK '
GUEST_CHECKS = {
    'guest_setup': {'verify_observer', 'backup_original', 'start_observer', 'install_candidate', 'verify_candidate'},
    'guest_campaign': {'browser_file_dialogs', 'remote_arming', 'crash_postflight', 'candidate_integrity'},
    'covered_control': {'capture_display', 'verify_cover_baseline', 'verify_concealment', 'finite_owner_expiry', 'renew_owner',
                        'observe_same_owner', 'observe_guardian', 'verify_browser_effects', 'owner_disconnect'},
}


def announce(phase, check):
    assert check in GUEST_CHECKS[phase]
    print(f'{MARKER.decode("ascii")}{phase} {check}', flush=True)


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
        if not line.startswith(MARKER) or len(line) > 128:
            return False
        try:
            phase, check = line[len(MARKER):].decode('ascii').split()
        except (UnicodeError, ValueError):
            return False
        if check not in GUEST_CHECKS.get(phase, ()):
            return False
        self.step(phase, check)
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
