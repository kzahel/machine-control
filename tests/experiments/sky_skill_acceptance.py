"""Agent-led Claude/Sky setup gate. All receipts are controller-private.

The setup agent receives the public guide, actual task and resolved private
inputs. This module never prepares MCP on its behalf or starts a runtime.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys
import tarfile
import time

from agent_profiles import DEFAULT_MODELS, launch_request, qualify
from measurements import claude_transcript_metrics, timestamp

APP = 'com.apple.TextEdit'
TASKS = {'textedit-save', 'textedit-menu'}
TOOLS = {'js', 'js_reset', 'sky_close'}


def validate_profile(provider, model, routes, tasks, instructions):
    if instructions == 'skill' and (provider != 'claude' or model != DEFAULT_MODELS['claude'] or
                                    set(routes or []) != {'sky-external'} or not tasks or
                                    not set(tasks) <= TASKS):
        raise ValueError('skill requires the existing Claude Opus profile, only sky-external, '
                         'and explicit TextEdit save/menu tasks')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def private_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    path.write_text(text)
    path.chmod(0o600)


def host_scopes(repo):
    """All Claude Code locations that can shadow the user-scope server."""
    host = Path.home() / '.claude.json'
    value = json.loads(host.read_text()) if host.exists() else {}
    scopes = [(host, value, value)]
    for entry in value.get('projects', {}).values():
        scopes.append((host, value, entry))
    project = repo / '.mcp.json'
    if project.exists():
        data = json.loads(project.read_text())
        scopes.append((project, data, data))
    return scopes


def source_paths(repo):
    return [repo / relative for relative in (
        'info/claude-computer-use.md', 'skills/claude-computer-use/SKILL.md',
        'skills/claude-computer-use/scripts/prepare.py', 'tests/experiments/sky-external/bridge.py',
        'tests/experiments/native-efficiency/mcp_client.py')]


def begin(repo, runtime_sha256, runtime_config=None):
    """Remove inherited experiment entry, never create a replacement."""
    if runtime_config is None:
        configs = list((Path.home() / '.codex/plugins/cache/openai-bundled/unified-computer-use').glob('*/.mcp.json'))
        if not configs:
            raise ValueError('installed runtime config missing; supply the selected runtime path')
        if len(configs) != 1:
            raise ValueError('ambiguous installed runtime selection; supply the selected runtime path')
        selected = configs[0].resolve(strict=True)
    else:
        selected = Path(runtime_config).resolve(strict=True)
    if digest(selected) != runtime_sha256:
        raise ValueError('installed runtime differs from trial fingerprint')
    if not isinstance(json.loads(selected.read_text())['mcpServers']['cua_repl'], dict):
        raise ValueError('invalid installed runtime')
    output = Path.home() / 'experiment/sky-skill'
    if output.exists() or output.is_symlink():
        raise ValueError('skill output must be fresh')
    removed = 0
    for path, document, scope in host_scopes(repo):
        if 'sky_experiment' in scope.get('mcpServers', {}):
            del scope['mcpServers']['sky_experiment']
            private_write(path, json.dumps(document) + '\n')
            removed += 1
    if any('sky_experiment' in scope.get('mcpServers', {}) for _, _, scope in host_scopes(repo)):
        raise ValueError('inherited experiment entry remains')
    return {'guide': str(repo / 'info/claude-computer-use.md'),
            'runtimeConfig': str(selected), 'runtimeConfigSha256': runtime_sha256,
            'authorizedApp': APP, 'outputDir': str(output),
            'experimentEntryAbsent': True, 'removedEntries': removed,
            'sourceHashes': {str(p): digest(p) for p in source_paths(repo)}}


def verify_generated_setup(repo, runtime_config, output, runtime_sha256, artifact_paths=()):
    """Read-only independent validation; no config writes or runtime launch."""
    repo, runtime_config, output = map(Path, (repo, runtime_config, output))
    if not output.is_absolute() or output == repo or repo in output.parents:
        raise ValueError('private output must be outside checkout')
    if not output.is_dir() or output.is_symlink() or stat.S_IMODE(output.stat().st_mode) != 0o700:
        raise ValueError('output directory must be private mode-0700')
    files = [output, *output.rglob('*')]
    for path in files:
        if path.is_symlink() or not (path.is_file() or path.is_dir()) or path.stat().st_mode & 0o077:
            raise ValueError('setup contains non-private or linked artifacts')
    config = output / 'mcp.json'
    if stat.S_IMODE(config.stat().st_mode) != 0o600:
        raise ValueError('generated config must be mode-0600')
    data = json.loads(config.read_text())
    if set(data) != {'mcpServers'} or set(data['mcpServers']) != {'sky_experiment'}:
        raise ValueError('generated config contains unexpected servers or settings')
    server = data['mcpServers']['sky_experiment']
    expected = [str(repo / 'tests/experiments/sky-external/bridge.py'), '--config', str(runtime_config),
                '--allow-app', APP, '--evidence', str(output / 'runtime')]
    if not isinstance(server, dict) or set(server) != {'command', 'args'} or server['args'] != expected:
        raise ValueError('generated server must have exact TextEdit scope, runtime and evidence path')
    if not isinstance(server['command'], str):
        raise ValueError('generated server command must be an executable path')
    command = Path(server['command'])
    if (not command.is_absolute() or not command.is_file() or not os.access(command, os.X_OK) or
            not re.fullmatch(r'python\d+(?:\.\d+)*', command.name)):
        raise ValueError('generated server must use an installed Python interpreter')
    if str(runtime_config.resolve(strict=True)) != str(runtime_config) or digest(runtime_config) != runtime_sha256:
        raise ValueError('runtime config selection changed')
    host = Path.home() / '.claude.json'
    if host.is_symlink() or stat.S_IMODE(host.stat().st_mode) != 0o600:
        raise ValueError('actual host config must be private mode-0600')
    scopes = host_scopes(repo)
    entries = [(path, scope['mcpServers']['sky_experiment']) for path, _, scope in scopes
               if 'sky_experiment' in scope.get('mcpServers', {})]
    if entries != [(host, server)] or scopes[0][2].get('mcpServers', {}).get('sky_experiment') != server:
        raise ValueError('actual host MCP entry missing, mismatched or shadowed')
    probe = json.loads((output / 'preflight/probe.json').read_text())
    if (probe.get('ok') is not True or probe.get('stage') != 'close' or
            probe.get('scope') != 'startup-and-tool-shape-only' or
            set(probe.get('tools', [])) != TOOLS):
        raise ValueError('successful initialize/list/close probe not verified')
    # The task server has not started. A pre-existing close marker cannot count
    # as cleanup of the task session that will be launched next.
    if (output / 'runtime').exists():
        raise ValueError('task runtime evidence must be absent before fresh task session')
    tracked = [config, output / 'preflight/probe.json', runtime_config, host,
               *source_paths(repo), *(Path(p) for p in artifact_paths)]
    return {'passed': True, 'approvedApps': [APP], 'probe': probe,
            'evidenceDir': str(output / 'runtime'), 'hostEntryVerified': True, 'taskRuntimeEvidenceAbsent': True,
            'hashes': {str(p): digest(p) for p in tracked},
            'artifactModes': {str(p.relative_to(output)): oct(stat.S_IMODE(p.stat().st_mode)) for p in files}}


# Narrow compatibility window: reviewed repository sources that emitted native
# close receipts before MCP wrapper exit, but no runtime-closed protocol event.
LEGACY_BRIDGE_SHA256 = '3304a8bc52c008cef2a2d575d51ce67f2ad0f6c7a60b44d176bb9e871b7fddf1'
LEGACY_VERIFIER_SHA256 = '302bf06d1465a78e63b1f4a3c7ea3844a9d1384abccd08f2ca6448a5cee6ce03'


def successful_sky_close(transcript):
    calls = {}
    for line in transcript.splitlines():
        row = json.loads(line)
        if row.get('isSidechain') or row.get('isSubagent'):
            continue
        blocks = (row.get('message') or {}).get('content', [])
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            if row.get('type') == 'assistant' and block.get('type') == 'tool_use' and block.get('name') == 'mcp__sky_experiment__sky_close':
                if isinstance(block.get('id'), str) and block.get('id') and block.get('input') == {}:
                    calls[block['id']] = {'callId': block['id'], 'callAt': timestamp(row.get('timestamp'))}
            elif row.get('type') == 'user' and block.get('type') == 'tool_result' and not block.get('is_error'):
                call = calls.get(block.get('tool_use_id'))
                content = block.get('content')
                if isinstance(content, list):
                    content = '\n'.join(b['text'] for b in content if isinstance(b, dict) and
                                        b.get('type') == 'text' and isinstance(b.get('text'), str))
                result_at = timestamp(row.get('timestamp'))
                if (call and call['callAt'] is not None and result_at is not None and result_at >= call['callAt'] and
                        isinstance(content, str) and content.strip() == 'Computer Use runtime closed.'):
                    return {**call, 'resultAt': result_at}
    return None


def runtime_closure_evidence(evidence, *, verification, transcript, legacy_source_verified=False):
    """Native teardown evidence; wrapper/process termination is a separate result."""
    checks = {}
    try:
        closed = json.loads(evidence.get('closed.json', '{}'))
        events = [json.loads(line) for line in evidence.get('protocol-events.jsonl', '').splitlines()]
        starts = [e for e in events if e.get('event') == 'started']
        teardown = [e for e in events if e.get('event') == 'runtime-closed']
        checks['freshTaskEvidence'] = verification.get('passed') is True and verification.get('taskRuntimeEvidenceAbsent') is True
        checks['scopedNativeCloseMarker'] = (closed.get('closed') is True and closed.get('approvalScope') == [APP]
                                             and closed.get('automaticRestart') is False)
        checks['singleWrapperStart'] = len(starts) == 1
        close_call = successful_sky_close(transcript)
        checks['successfulTranscriptSkyClose'] = close_call is not None
        if legacy_source_verified:
            checks['knownLegacyProtocol'] = not teardown and bool(starts) and isinstance(starts[0].get('at'), (int, float))
        else:
            start = starts[0] if len(starts) == 1 else {}
            stop = teardown[0] if len(teardown) == 1 else {}
            checks['nativeTeardownEvent'] = (len(teardown) == 1 and bool(start.get('runtimeId')) and
                start.get('runtimeId') == stop.get('runtimeId') == closed.get('runtimeId') and
                stop.get('reason') == 'sky_close' and stop.get('approvalScope') == [APP] and
                stop.get('automaticRestart') is False and closed.get('runtimeClosed') is True and
                isinstance(start.get('at'), (int, float)) and isinstance(stop.get('at'), (int, float)) and
                start['at'] <= stop['at'] and closed.get('closedAt') == stop['at'])
        return {'passed': all(checks.values()), 'checks': checks, 'skyCloseCall': close_call,
                'wrapperExitEventObserved': any(e.get('event') == 'wrapper-process-closed' for e in events),
                'basis': 'known_legacy_source_and_transcript' if legacy_source_verified else 'runtime_closed_event'}
    except (ValueError, TypeError, AttributeError, KeyError):
        return {'passed': False, 'checks': {**checks, 'readableClosureEvidence': False}, 'skyCloseCall': None}


def retained_closure_hashes(directory):
    """The review must bind to this exact completed attempt, including setup."""
    directory = Path(directory)
    names = ('trial.json', 'transcript.jsonl', 'sky-evidence.json', 'runtime.json', 'review.json',
             'skill-setup/receipt.json', 'skill-setup/verification.json', 'skill-setup/begin.json',
             'skill-setup/transcript.jsonl', 'skill-setup/setup-artifacts.tar')
    return {name: digest(directory / name) for name in names}


def reevaluate_retained_closure(directory, *, old_bridge_source, old_verifier_source, route_review=None, reason):
    """Return a separate, explained evaluation; never mutate raw receipts.

    A missing review is an explained refusal, not inferred route conformance.
    The caller supplies source bytes from the recorded Git pin and a review
    with evidenceHashes, noFallback/noTampering and explicit policy judgments.
    """
    directory = Path(directory)
    hashes = retained_closure_hashes(directory)
    record = json.loads((directory / 'trial.json').read_text())
    setup = json.loads((directory / 'skill-setup/receipt.json').read_text())
    verification = json.loads((directory / 'skill-setup/verification.json').read_text())
    begin_inputs = json.loads((directory / 'skill-setup/begin.json').read_text())
    runtime = json.loads((directory / 'runtime.json').read_text())
    transcript = (directory / 'transcript.jsonl').read_text()
    original_review = json.loads((directory / 'review.json').read_text())
    review = route_review or {}
    checks = {'knownOldBridgeSource': hashlib.sha256(old_bridge_source).hexdigest() == LEGACY_BRIDGE_SHA256,
              'knownOldVerifierSource': hashlib.sha256(old_verifier_source).hexdigest() == LEGACY_VERIFIER_SHA256,
              'reasonProvided': bool(reason.strip()),
              'boundedProfile': record.get('provider') == 'claude' and record.get('route') == 'sky-external' and
                                record.get('instructionProfile') == 'skill' and record.get('task') in TASKS,
              'setupReceiptConsistent': setup == record.get('skillSetup') and verification == setup.get('verification') and
                                       begin_inputs == setup.get('inputs'),
              'setupAccepted': setup.get('passed') is True and setup.get('sourceAndRuntimeUnchanged') is True and
                               setup.get('sessionCleanup', {}).get('terminationVerified') is True,
              'setupTranscriptUnchanged': hashes['skill-setup/transcript.jsonl'] == setup.get('transcriptSha256'),
              'setupArchiveUnchanged': hashes['skill-setup/setup-artifacts.tar'] == setup.get('artifactsSha256'),
              'reviewBoundToEvidence': review.get('evidenceHashes') == hashes and
                                       review.get('transcriptSha256') == hashes['transcript.jsonl'] and
                                       all(review.get(key) == value for key, value in original_review.items()),
              'reviewConforming': review.get('schema') == 'route-comparison-review/v1' and review.get('routeAdherence') == 'conforming' and review.get('noFallback') is True and
                                  review.get('noTampering') is True and bool(review.get('notes')) and
                                  review.get('confirmationPolicyAdherence') in ('conforming', 'not_applicable'),
              'ownedProcessesStopped': bool(record.get('ownedSessionCleanup')) and all(
                  entry.get('terminationVerified') is True for entry in record.get('ownedSessionCleanup', [])) and any(
                  entry.get('sessionId', entry.get('providerSessionId')) == record.get('sessionId')
                  for entry in record.get('ownedSessionCleanup', [])),
              'workspaceDiscarded': record.get('released') == 'discarded' and not record.get('releaseError') and
                                    not record.get('tunnelCleanupError')}
    expected_hashes = {**begin_inputs.get('sourceHashes', {}),
                       **{path: entry['sha256'] for path, entry in runtime.get('artifacts', {}).items()}}
    observed = verification.get('hashes', {})
    bridges = [path for path in expected_hashes if path.endswith('/tests/experiments/sky-external/bridge.py')]
    checks['sourceAndRuntimePinsPreserved'] = (bool(expected_hashes) and len(bridges) == 1 and
        observed.get(bridges[0]) == LEGACY_BRIDGE_SHA256 and all(observed.get(p) == sha for p, sha in expected_hashes.items()) and
        runtime.get('configSha256') == begin_inputs.get('runtimeConfigSha256') == observed.get(begin_inputs.get('runtimeConfig')))
    try:
        with tarfile.open(directory / 'skill-setup/setup-artifacts.tar') as archive:
            members = archive.getmembers()
            config_member = archive.getmember('mcp.json')
            probe_member = archive.getmember('preflight/probe.json')
            if not config_member.isfile() or not probe_member.isfile():
                raise ValueError('Expected regular setup artifacts')
            config_bytes = archive.extractfile(config_member).read()
            probe_bytes = archive.extractfile(probe_member).read()
            config = json.loads(config_bytes)
            probe = json.loads(probe_bytes)
        output = begin_inputs['outputDir']
        expected_args = [bridges[0], '--config', begin_inputs['runtimeConfig'], '--allow-app', APP,
                         '--evidence', str(Path(output) / 'runtime')]
        server = config['mcpServers']['sky_experiment']
        checks['generatedConfigBoundAndScoped'] = (set(config) == {'mcpServers'} and
            set(config['mcpServers']) == {'sky_experiment'} and set(server) == {'command', 'args'} and
            server['args'] == expected_args and hashlib.sha256(config_bytes).hexdigest() == observed.get(str(Path(output) / 'mcp.json')) and
            verification.get('approvedApps') == [APP] and verification.get('hostEntryVerified') is True and
            record.get('skyEvidenceDir') == verification.get('evidenceDir') == str(Path(output) / 'runtime'))
        checks['freshEvidenceFromKnownVerifier'] = (checks['knownOldVerifierSource'] and verification.get('passed') is True and
            all(not (m.name == 'runtime' or m.name.startswith('runtime/')) for m in members) and
            all(not (p == 'runtime' or p.startswith('runtime/')) for p in verification.get('artifactModes', {})))
        checks['probePreserved'] = (probe == verification.get('probe') and probe.get('ok') is True and
            probe.get('stage') == 'close' and probe.get('scope') == 'startup-and-tool-shape-only' and
            set(probe.get('tools', [])) == TOOLS and hashlib.sha256(probe_bytes).hexdigest() == observed.get(str(Path(output) / 'preflight/probe.json')))
    except (OSError, ValueError, KeyError, TypeError, IndexError, tarfile.TarError):
        checks['setupArtifactsVerified'] = False
    fresh = {**verification, 'taskRuntimeEvidenceAbsent': checks.get('freshEvidenceFromKnownVerifier') is True}
    closure = runtime_closure_evidence(json.loads((directory / 'sky-evidence.json').read_text()), verification=fresh,
        transcript=transcript, legacy_source_verified=checks['knownOldBridgeSource'] and checks['knownOldVerifierSource'])
    checks['nativeRuntimeClosed'] = closure['passed']
    metrics = claude_transcript_metrics(transcript)
    qualification = qualify(record['provider'], record['requestedModel'], record['requestedEffort'], metrics, record.get('effectiveProcess', {}))
    checks['taskQualified'] = (qualification['qualified'] and metrics['transcriptComplete'] and
        metrics['malformedTranscriptLines'] == 0 and not record.get('error') and not record.get('timedOut') and
        not metrics.get('terminalProviderError') and record.get('oracleExit') == 0)
    corrected = {**record, **metrics, 'profileQualification': qualification, 'skyRuntimeClosed': closure['passed'],
                 'skyRuntimeClosure': closure, 'validTrial': all(checks.values())}
    corrected['passed'] = corrected['validTrial'] and record.get('oracle', {}).get('passed') is True
    if isinstance(record.get('stageAccounting', {}).get('task'), dict):
        corrected['stageAccounting'] = {**record['stageAccounting'], 'task': {
            **record['stageAccounting']['task'],
            'status': 'failed' if record.get('error') else 'passed' if corrected['passed'] else 'blocked'}}
    return {'schema': 'sky-skill-closure-evaluation/v1', 'reason': reason, 'evidenceHashes': hashes,
            'routeReviewSha256': hashlib.sha256(json.dumps(route_review, sort_keys=True).encode()).hexdigest(),
            'sourceHashes': {'oldBridge': hashlib.sha256(old_bridge_source).hexdigest(),
                             'oldVerifier': hashlib.sha256(old_verifier_source).hexdigest(),
                             'evaluator': digest(Path(__file__)),
                             'measurements': digest(Path(__file__).parent / 'measurements.py'),
                             'agentProfiles': digest(Path(__file__).parent / 'agent_profiles.py')},
            'checks': checks, 'refusalReasons': [key for key, passed in checks.items() if not passed],
            'record': corrected, 'limits': ['Raw receipts are unchanged; this separate evaluation retains the original oracle.',
                'Known legacy verifier acceptance and its setup archive establish the pre-task evidence absence.',
                'Runtime teardown and owned wrapper/process stop are distinct evidence.',
                'Route/no-fallback/no-tampering annotations are explicit reviewer judgments.',
                'No image/media qualification or new screenshot observation is inferred.']}


def setup_prompt(inputs, task_prompt):
    return (f"Read {inputs['guide']} and follow its skill to use Computer Use for this task. "
            "Prepare scoped setup if it is missing and report whether this session needs restarting.\n\n"
            "Host context: This fresh setup session is YA-hosted Claude running on the selected dedicated "
            "disposable test appliance. Scoped host registration of the generated server for this task is "
            "authorized on this appliance; preserve unrelated host settings and MCP servers. This task-local "
            "appliance configuration is cleaned up by clone disposal. The coordinator manages model and AAR "
            "credentials; do not change them. Complete setup and report the new-session handoff. The coordinator "
            "will stop and verify this setup session before starting a fresh task session.\n\n"
            f"Installed runtime config: {inputs['runtimeConfig']}\n"
            f"Authorized application: {inputs['authorizedApp']}\n"
            f"Private output directory: {inputs['outputDir']}\n\n"
            f"Task: {task_prompt.strip()}\n\n"
            "Nobody is at the computer and nobody will answer questions. Do not delegate or spawn agents. "
            "If blocked, report the blocker.")


def task_prompt(inputs, actual_task, common):
    return '\n\n'.join([f"Read {inputs['guide']} and follow its skill for this task.",
                         actual_task.strip(), common])


def observed_setup_workflow(transcript):
    calls, results = {}, {}
    gui_calls = []
    for line in transcript.splitlines():
        row = json.loads(line)
        for block in (row.get('message') or {}).get('content', []):
            if not isinstance(block, dict):
                continue
            if block.get('type') == 'tool_use':
                name = block.get('name', '')
                if 'sky_experiment' in name and name.endswith(('__js', '__js_reset')):
                    gui_calls.append(name)
                command = (block.get('input') or {}).get('command', '')
                if isinstance(command, str) and 'skills/claude-computer-use/scripts/prepare.py' in command and '--probe' in command:
                    calls[block.get('id')] = command
            elif block.get('type') == 'tool_result':
                results[block.get('tool_use_id')] = block
    probed = any(key in results and not results[key].get('is_error') and
                 'startup-probed' in json.dumps(results[key].get('content')) for key in calls)
    return {'agentPrepareProbeObserved': probed, 'prematureGuiCalls': gui_calls}


def visible_assistant_text(row):
    """Read only visible assistant prose, never reasoning or nested tool text."""
    if not isinstance(row, dict) or any(row.get(key) for key in
            ('isSidechain', 'isSubagent', '_isStreaming', 'isAbortedMidStream')):
        return ''
    message = row.get('message')
    message = message if isinstance(message, dict) else {}
    if row.get('type', row.get('role', message.get('role'))) != 'assistant':
        return ''
    if message.get('model') == '<synthetic>':
        return ''
    content = message.get('content', row.get('content'))
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ''
    return '\n'.join(block['text'] for block in content if isinstance(block, dict) and
                     block.get('type') == 'text' and isinstance(block.get('text'), str)).strip()


def final_assistant_text(detail, transcript=''):
    """YA normalizes messages separately from session metadata on current hosts."""
    detail = detail if isinstance(detail, dict) else {}
    session = detail.get('session')
    session = session if isinstance(session, dict) else {}
    messages = detail.get('messages', session.get('messages', []))
    if isinstance(messages, list):
        for row in reversed(messages):
            text = visible_assistant_text(row)
            if text:
                return {'finalText': text, 'finalTextSource': 'ya_normalized_messages'}
    legacy = session.get('lastAgentText')
    if isinstance(legacy, str) and legacy.strip():
        return {'finalText': legacy.strip(), 'finalTextSource': 'ya_lastAgentText'}
    for line in reversed(transcript.splitlines()):
        try:
            text = visible_assistant_text(json.loads(line))
        except (ValueError, TypeError):
            continue
        if text:
            return {'finalText': text, 'finalTextSource': 'claude_transcript'}
    return {'finalText': '', 'finalTextSource': 'unavailable'}


def new_session_reported(text):
    negative = (r'\b(?:no|not)\s+(?:new\s+session|restart)\s+(?:is\s+)?(?:needed|required|necessary)|'
                r'\b(?:does|do)\s+not\s+(?:need|require)[^.\n]{0,35}\brestart|'
                r'\brestart\s+(?:is\s+)?(?:not\s+(?:needed|required|necessary)|optional)')
    if re.search(negative, text, re.I):
        return False
    transition = re.search(r'\b(?:new|fresh)\s+(?:(?:YA|Claude|Opus|Code|task)\s+){0,3}session\b|'
                           r'\brestart(?:ed|ing)?\b', text, re.I)
    directive = re.search(r'\b(?:needs?|required?|requires?|must|start|launch|open|restart)\b', text, re.I)
    return bool(transition and directive)


def remote(guest, repo, phase, **values):
    command = ['/opt/homebrew/bin/python3', str(Path(repo) / 'tests/experiments/sky_skill_acceptance.py'), phase,
               '--repo', str(repo)]
    for key, value in values.items():
        command.extend(['--' + key.replace('_', '-'), str(value)])
    return guest.run(shlex.join(command))


def collect_transcript(guest, identifier):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', identifier):
        raise ValueError('invalid provider session ID')
    return guest.run('/opt/homebrew/bin/python3 -', stdin=f'identifier={identifier!r}\n'+'''
from pathlib import Path
paths=list((Path.home()/'.claude/projects').rglob('*'+identifier+'.jsonl'))
if len(paths)!=1: raise SystemExit(3)
print(paths[0].read_text(),end='')
''', timeout=120)


def register_owned_session(response):
    owned = {}
    for source, destination in (('sessionId', 'launchSessionId'), ('processId', 'processId'), ('queueId', 'queueId')):
        if response.get(source):
            identifier = response[source]
            if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', identifier):
                raise ValueError('invalid owned session identity')
            owned[destination] = identifier
    if not owned:
        raise ValueError('launch returned no owned session/process/queue identity')
    return owned


def observe_owned_process(session, process):
    if process.get('sessionId'):
        session['providerSessionId'] = process['sessionId']
    if process.get('id'):
        session['processId'] = process['id']


def stop_owned_session(guest, session, *, sleep=time.sleep):
    """Idle agents still own processes/MCP children. Abort and verify before disposal."""
    if session.get('queueId'):
        cancelled = guest.ya('DELETE', f"/api/queue/{session['queueId']}")
        if cancelled.get('cancelled') is not True:
            raise RuntimeError('owned launch queue cancellation unverified; retain workspace')
        session.pop('queueId')
        if not session.get('launchSessionId') and not session.get('processId'):
            session['terminationVerified'] = True
            return {'terminationVerified': True, 'state': 'queue-cancelled'}
    identifier = session.get('providerSessionId') or session.get('launchSessionId')
    def lookup():
        process = guest.ya('GET', f'/api/sessions/{identifier}/process').get('process') if identifier else None
        if not process and session.get('processId'):
            rows = guest.ya('GET', '/api/processes?includeTerminated=true')
            matches = [p for p in rows.get('processes', []) + rows.get('terminatedProcesses', [])
                       if p.get('id') == session['processId']]
            if len(matches) > 1:
                raise RuntimeError('ambiguous owned process identity')
            process = matches[0] if matches else None
        return process
    process = lookup()
    if process:
        observe_owned_process(session, process)
        identifier = session.get('providerSessionId', identifier)
    if process and process.get('state') != 'terminated':
        if not process.get('id'):
            raise RuntimeError('owned session has no abortable process identity')
        guest.ya('POST', f"/api/processes/{process['id']}/abort", {'blockResume': True})
        for _ in range(20):
            process = lookup()
            if not process or process.get('state') == 'terminated':
                break
            sleep(0.25)
        else:
            raise RuntimeError('owned session termination unverified; retain workspace')
    session['terminationVerified'] = True
    return {'sessionId': identifier, 'terminationVerified': True,
            'state': (process or {}).get('state', 'absent')}


def stage_accounting(setup, task=None):
    keys = ('controllerWallSeconds', 'controllerWaitSeconds', 'agentSeconds', 'tokenUsage',
            'toolCalls', 'transcriptImageItems', 'profileQualification')
    def stage(receipt, launched):
        return {'launched': launched, 'status': receipt.get('status', 'pending'),
                **{key: receipt.get(key) for key in keys}}
    return {'setup': stage(setup, setup.get('launched', False)),
            'task': stage(task or {'status': 'not-launched'}, task is not None),
            'newSessionTransitionRequired': True,
            'limits': ['Setup and task costs are separate; missing measurements remain unknown.']}


def run_setup(guest, args, actual_task, directory, owned_sessions, wait_for_agent, runtime_sha256, *, runtime_artifacts=None, runtime_config=None):
    """Return a failed/blocked receipt on every gate failure; caller gates task launch."""
    directory = Path(directory)
    receipt = {'phase': 'skill-setup', 'status': 'failed', 'launched': False, 'passed': False}
    started = time.monotonic()
    try:
        selection = {'runtime_config': runtime_config} if runtime_config is not None else {}
        result = remote(guest, args.project, 'begin', runtime_sha256=runtime_sha256, **selection)
        private_write(directory / 'begin.json', result.stdout)
        if result.returncode:
            raise RuntimeError('fresh setup precondition failed')
        inputs = receipt['inputs'] = json.loads(result.stdout)
        prompt = setup_prompt(inputs, actual_task)
        private_write(directory / 'prompt.txt', prompt)
        receipt['promptSha256'] = hashlib.sha256(prompt.encode()).hexdigest()
        request = launch_request(args.provider, args.model, args.effort, prompt)
        receipt['launchSettings'] = {k: v for k, v in request.items() if k != 'message'}
        project = base64.urlsafe_b64encode(args.project.encode()).decode().rstrip('=')
        session = guest.ya('POST', f'/api/projects/{project}/sessions', request)
        owned = register_owned_session(session)
        owned_sessions.append(owned)
        receipt.update(owned, launched=True)
        if not owned.get('launchSessionId') or owned.get('queueId'):
            raise RuntimeError('setup launch queued or missing session identity')
        try:
            receipt.update(wait_for_agent(guest, session['sessionId'],
                getattr(args, 'skill_setup_timeout_seconds', 600), args.poll_seconds,
                observe_process=lambda process: observe_owned_process(owned, process)))
            owned['providerSessionId'] = receipt['providerSessionId']
        except Exception as error:
            receipt['waitError'] = str(error)
        identifier = owned.get('providerSessionId', owned['launchSessionId'])
        receipt['sessionId'] = identifier
        detail = {}
        try:
            detail = guest.ya('GET', f'/api/projects/{project}/sessions/{identifier}')
            private_write(directory / 'session.json', json.dumps(detail, indent=2) + '\n')
        except Exception as error:
            receipt['sessionCollectionError'] = str(error)
        try:
            receipt['sessionCleanup'] = stop_owned_session(guest, owned)
        except Exception as error:
            receipt['sessionCleanupError'] = str(error)
        transcript = collect_transcript(guest, identifier)
        private_write(directory / 'transcript.jsonl', transcript.stdout)
        receipt.update(final_assistant_text(detail, transcript.stdout))
        receipt['transcriptSha256'] = hashlib.sha256(transcript.stdout.encode()).hexdigest()
        receipt.update(claude_transcript_metrics(transcript.stdout))
        receipt['transcriptCollectionExit'] = transcript.returncode
        receipt['profileQualification'] = qualify(args.provider, args.model, args.effort, receipt,
                                                   receipt.get('effectiveProcess', {}))
        receipt['workflow'] = observed_setup_workflow(transcript.stdout)
        receipt['newSessionReported'] = new_session_reported(receipt['finalText'])
        checked = remote(guest, args.project, 'verify', runtime_config=inputs['runtimeConfig'],
                         output_dir=inputs['outputDir'], runtime_sha256=runtime_sha256,
                         artifact_paths=json.dumps(list(runtime_artifacts or {})))
        private_write(directory / 'verification.json', checked.stdout)
        receipt['verification'] = json.loads(checked.stdout)
        expected_hashes = {**inputs['sourceHashes'],
                           **{p: v['sha256'] for p, v in (runtime_artifacts or {}).items()}}
        actual_hashes = receipt['verification'].get('hashes', {})
        receipt['sourceAndRuntimeUnchanged'] = bool(expected_hashes) and all(
            actual_hashes.get(path) == expected for path, expected in expected_hashes.items())
        receipt['passed'] = (checked.returncode == 0 and receipt['verification'].get('passed') is True and receipt['sourceAndRuntimeUnchanged'] and
            not receipt.get('sessionCleanupError') and receipt.get('sessionCleanup', {}).get('terminationVerified') is True and
            not receipt.get('waitError') and not receipt.get('timedOut') and receipt.get('transcriptComplete') is True and
            receipt.get('malformedTranscriptLines') == 0 and transcript.returncode == 0 and
            receipt['profileQualification']['qualified'] and receipt['newSessionReported'] and
            receipt['workflow']['agentPrepareProbeObserved'] and not receipt['workflow']['prematureGuiCalls'])
        receipt['status'] = 'passed' if receipt['passed'] else 'failed' if receipt.get('sessionCleanupError') else 'blocked'
    except Exception as error:
        receipt['error'] = str(error)
        receipt['passed'] = False
        receipt['status'] = 'failed'
    finally:
        if receipt.get('inputs'):
            try:
                archive = remote(guest, args.project, 'archive', output_dir=receipt['inputs']['outputDir'])
                # Archive is base64 so Guest's text transport remains unchanged.
                if archive.returncode:
                    raise RuntimeError('setup artifact collection failed')
                data = base64.b64decode(archive.stdout, validate=True)
                path = directory / 'setup-artifacts.tar'
                path.write_bytes(data)
                path.chmod(0o600)
                receipt['artifactsSha256'] = hashlib.sha256(data).hexdigest()
            except Exception as error:
                receipt['artifactCollectionError'] = str(error)
                receipt['passed'] = False
                receipt['status'] = 'failed'
        receipt['controllerWallSeconds'] = time.monotonic() - started
        private_write(directory / 'receipt.json', json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['begin', 'verify', 'archive'])
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--runtime-config', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--runtime-sha256')
    parser.add_argument('--artifact-paths', default='[]', help='Private pinned runtime artifact paths for read-only hashing')
    args = parser.parse_args()
    try:
        if args.phase == 'begin':
            result = begin(args.repo, args.runtime_sha256, args.runtime_config)
        elif args.phase == 'verify':
            result = verify_generated_setup(args.repo, args.runtime_config, args.output_dir, args.runtime_sha256,
                                            json.loads(args.artifact_paths))
        else:
            if args.output_dir.is_symlink() or args.output_dir.resolve() != args.output_dir:
                raise ValueError('archive root must be the resolved private output directory')
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode='w') as archive:
                for path in sorted(args.output_dir.rglob('*')):
                    if path.is_file() and not path.is_symlink():
                        archive.add(path, arcname=str(path.relative_to(args.output_dir)), recursive=False)
            sys.stdout.write(base64.b64encode(buffer.getvalue()).decode())
            return 0
        print(json.dumps(result))
        return 0
    except Exception as error:
        # No config contents or runtime environment in diagnostics.
        print(json.dumps({'passed': False, 'error': type(error).__name__, 'detail': str(error)
                          if isinstance(error, ValueError) else 'artifact inspection failed'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
