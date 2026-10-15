"""Offline setup acceptance, independent artifact validation and lifecycle gates."""
import base64
import copy
import json
import hashlib
import io
import tarfile
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import route_comparison as route
import sky_skill_acceptance as skill
from agent_profiles import DEFAULT_MODELS


def result(value='', code=0):
    return subprocess.CompletedProcess([], code, value if isinstance(value, str) else json.dumps(value), '')


def transcript(model=None, effort='medium', speed='standard', prepared=True):
    model = model or DEFAULT_MODELS['claude']
    rows = [dict(type='user', timestamp='2026-01-01T00:00:00Z', message={'content': 'task'})]
    if prepared:
        rows += [dict(type='assistant', timestamp='2026-01-01T00:00:01Z', perTurnEffort=effort,
            message={'id': 'm1', 'model': model, 'usage': {'input_tokens': 10, 'output_tokens': 5,
                'cache_read_input_tokens': 3, 'cache_creation_input_tokens': 2,
                'speed': speed, 'service_tier': 'standard'}, 'content': [{'type': 'tool_use',
                'id': 'probe', 'name': 'Bash', 'input': {'command':
                'python3 skills/claude-computer-use/scripts/prepare.py --runtime-config /private/runtime --probe'}}]}),
            dict(type='user', timestamp='2026-01-01T00:00:02Z', message={'content': [
                {'type': 'tool_result', 'tool_use_id': 'probe', 'content': '{"status":"startup-probed"}'}]})]
    rows += [dict(type='assistant', timestamp='2026-01-01T00:00:03Z', perTurnEffort=effort,
        message={'id': 'm2', 'model': model, 'usage': {'input_tokens': 11, 'output_tokens': 4,
            'cache_read_input_tokens': 4, 'cache_creation_input_tokens': 0,
            'speed': speed, 'service_tier': 'standard'}, 'content': [], 'stop_reason': 'end_turn'})]
    return '\n'.join(map(json.dumps, rows)) + '\n'


def task_transcript():
    rows=[json.loads(line) for line in transcript(prepared=False).splitlines()]
    rows[1:1]=[
        {'type':'assistant','timestamp':'2026-01-01T00:00:01Z','message':{'content':[
            {'type':'tool_use','id':'close','name':'mcp__sky_experiment__sky_close','input':{}}]}},
        {'type':'user','timestamp':'2026-01-01T00:00:02Z','message':{'content':[
            {'type':'tool_result','tool_use_id':'close','content':[{'type':'text','text':'Computer Use runtime closed.'}]}]}}]
    return '\n'.join(map(json.dumps,rows))+'\n'


def closure_evidence():
    return {'closed.json':json.dumps({'closed':True,'runtimeClosed':True,'runtimeId':'fixture-run',
                'closedAt':2,'approvalScope':[skill.APP],'automaticRestart':False}),
            'protocol-events.jsonl':'\n'.join(map(json.dumps,[
                {'at':1,'event':'started','runtimeId':'fixture-run'},
                {'at':2,'event':'runtime-closed','runtimeId':'fixture-run','reason':'sky_close',
                 'approvalScope':[skill.APP],'automaticRestart':False}]))+'\n'}


class ClosureEvidenceTests(unittest.TestCase):
    def check(self, evidence=None, verification=None, text=None):
        return skill.runtime_closure_evidence(evidence if evidence is not None else closure_evidence(),
            verification=verification if verification is not None else {'passed':True,'taskRuntimeEvidenceAbsent':True},
            transcript=text if text is not None else task_transcript())

    def test_native_close_does_not_require_wrapper_exit(self):
        value=self.check()
        self.assertTrue(value['passed'],value)
        self.assertFalse(value['wrapperExitEventObserved'])
        self.assertEqual(value['skyCloseCall']['callId'],'close')

    def test_wrong_scope_stale_marker_and_missing_events_refuse(self):
        for field,value in [('approvalScope',[skill.APP,'com.apple.Finder']),('runtimeId','old-run'),
                            ('closedAt',0),('automaticRestart',True),('runtimeClosed',False)]:
            evidence=closure_evidence();marker=json.loads(evidence['closed.json']);marker[field]=value
            evidence['closed.json']=json.dumps(marker)
            with self.subTest(field=field):self.assertFalse(self.check(evidence)['passed'])
        for events in ['',json.dumps({'event':'started','at':1,'runtimeId':'fixture-run'})+'\n',
                       '{"event":"started"}\n{"event":"closed"}\n']:
            evidence=closure_evidence();evidence['protocol-events.jsonl']=events
            self.assertFalse(self.check(evidence)['passed'])

    def test_missing_fresh_precondition_duplicate_start_or_failed_ack_refuse(self):
        self.assertFalse(self.check(verification={'passed':True})['passed'])
        evidence=closure_evidence()
        evidence['protocol-events.jsonl']+=json.dumps({'at':3,'event':'started','runtimeId':'other'})+'\n'
        self.assertFalse(self.check(evidence)['passed'])
        self.assertFalse(self.check(text=task_transcript().replace('Computer Use runtime closed.','teardown failed'))['passed'])
        rows=[json.loads(line) for line in task_transcript().splitlines()]
        rows[2]['message']['content'][0]['is_error']=True
        self.assertFalse(self.check(text='\n'.join(map(json.dumps,rows)))['passed'])


class RetainedClosureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.old_bridge=b'known old bridge';self.old_verifier=b'known old verifier'
        self.bridge_sha=hashlib.sha256(self.old_bridge).hexdigest()
        patch.object(skill,'LEGACY_BRIDGE_SHA256',self.bridge_sha).start()
        patch.object(skill,'LEGACY_VERIFIER_SHA256',hashlib.sha256(self.old_verifier).hexdigest()).start()
        self.addCleanup(patch.stopall)
        bridge='/target/repo/tests/experiments/sky-external/bridge.py';output='/target/private/setup'
        config_path='/target/private/runtime.json';config_sha=hashlib.sha256(b'private runtime').hexdigest()
        inputs={'outputDir':output,'runtimeConfig':config_path,'runtimeConfigSha256':config_sha,
                'sourceHashes':{bridge:self.bridge_sha,'/target/repo/guide':'guide-sha'}}
        config={'mcpServers':{'sky_experiment':{'command':sys.executable,'args':[bridge,'--config',config_path,
                    '--allow-app',skill.APP,'--evidence',output+'/runtime']}}}
        probe={'ok':True,'stage':'close','scope':'startup-and-tool-shape-only','tools':sorted(skill.TOOLS)}
        config_bytes=json.dumps(config).encode();probe_bytes=json.dumps(probe).encode()
        verification={'passed':True,'approvedApps':[skill.APP],'hostEntryVerified':True,'probe':probe,
            'evidenceDir':output+'/runtime','artifactModes':{'.':'0o700','mcp.json':'0o600','preflight/probe.json':'0o600'},
            'hashes':{**inputs['sourceHashes'],'/target/native':'native-sha',config_path:config_sha,
                output+'/mcp.json':hashlib.sha256(config_bytes).hexdigest(),
                output+'/preflight/probe.json':hashlib.sha256(probe_bytes).hexdigest()}}
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as stream:
            for name,data in [('mcp.json',config_bytes),('preflight/probe.json',probe_bytes)]:
                member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o600
                stream.addfile(member,io.BytesIO(data))
        setup={'passed':True,'sourceAndRuntimeUnchanged':True,'inputs':inputs,'verification':verification,
            'sessionCleanup':{'terminationVerified':True},'transcriptSha256':hashlib.sha256(transcript().encode()).hexdigest(),
            'artifactsSha256':hashlib.sha256(archive.getvalue()).hexdigest()}
        record={'provider':'claude','requestedModel':DEFAULT_MODELS['claude'],'requestedEffort':'medium','effectiveProcess':{},
            'route':'sky-external','instructionProfile':'skill','task':'textedit-menu','sessionId':'task',
            'skyRuntimeClosed':False,'validTrial':False,'passed':False,'oracleExit':0,'oracle':{'passed':True},
            'released':'discarded','skyEvidenceDir':output+'/runtime','skillSetup':setup,
            'stageAccounting':{'task':{'status':'blocked','agentSeconds':12}},
            'ownedSessionCleanup':[{'providerSessionId':'setup','terminationVerified':True},
                                   {'sessionId':'task','terminationVerified':True}]}
        evidence={'closed.json':json.dumps({'closed':True,'approvalScope':[skill.APP],'automaticRestart':False}),
                  'protocol-events.jsonl':'{"event":"started","at":1}\n{"event":"received","method":"tools/call"}\n'}
        for name,data in [('trial.json',record),('runtime.json',{'configSha256':config_sha,'artifacts':{'/target/native':{'sha256':'native-sha'}}}),
            ('sky-evidence.json',evidence),('skill-setup/receipt.json',setup),('skill-setup/begin.json',inputs),
            ('skill-setup/verification.json',verification),('review.json',{'schema':'route-comparison-review/v1',
                'transcriptSha256':hashlib.sha256(task_transcript().encode()).hexdigest(),'routeAdherence':'conforming',
                'confirmationPolicyAdherence':'not_applicable','notes':'Reviewed no fallback or tampering.'})]:
            skill.private_write(self.root/name,json.dumps(data))
        skill.private_write(self.root/'transcript.jsonl',task_transcript())
        skill.private_write(self.root/'skill-setup/transcript.jsonl',transcript())
        (self.root/'skill-setup/setup-artifacts.tar').write_bytes(archive.getvalue())

    def review(self):
        return {**json.loads((self.root/'review.json').read_text()),'evidenceHashes':skill.retained_closure_hashes(self.root),
                'noFallback':True,'noTampering':True}

    def evaluate(self,**kwargs):
        return skill.reevaluate_retained_closure(self.root,old_bridge_source=kwargs.pop('old_bridge_source',self.old_bridge),
            old_verifier_source=kwargs.pop('old_verifier_source',self.old_verifier),
            route_review=kwargs.pop('route_review',self.review()),reason='Correct native/wrapper closure boundary',**kwargs)

    def update_setup(self,change):
        setup=json.loads((self.root/'skill-setup/receipt.json').read_text());change(setup)
        record=json.loads((self.root/'trial.json').read_text());record['skillSetup']=setup
        for name,value in [('trial.json',record),('skill-setup/receipt.json',setup),
                           ('skill-setup/verification.json',setup['verification']),('skill-setup/begin.json',setup['inputs'])]:
            skill.private_write(self.root/name,json.dumps(value))

    def test_hash_bound_correction_preserves_raw_receipts_oracle_and_measurement_limits(self):
        before={str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        value=self.evaluate()
        self.assertTrue(value['record']['passed'],value['refusalReasons'])
        self.assertTrue(value['record']['skyRuntimeClosed'])
        self.assertTrue(value['checks']['ownedProcessesStopped'])
        self.assertEqual(value['evidenceHashes'],skill.retained_closure_hashes(self.root))
        self.assertEqual(value['record']['oracle'],{'passed':True})
        self.assertEqual(value['record']['stageAccounting']['task'], {'status':'passed','agentSeconds':12})
        self.assertNotIn('transcriptImageItems',value['record'])
        self.assertEqual(before,{str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_unknown_old_sources_or_missing_bound_review_refuse(self):
        for kwargs in [{'old_bridge_source':b'other'}, {'old_verifier_source':b'other'}, {'route_review':None}]:
            with self.subTest(kwargs=kwargs):self.assertFalse(self.evaluate(**kwargs)['record']['passed'])
        for field in ['noFallback','noTampering']:
            review=self.review();review[field]=False
            self.assertFalse(self.evaluate(route_review=review)['record']['passed'])
        review=self.review();review['evidenceHashes']['sky-evidence.json']='stale'
        self.assertFalse(self.evaluate(route_review=review)['record']['passed'])

    def test_supplied_review_cannot_override_stored_review_and_oracle_is_not_promoted(self):
        review=self.review();review['notes']='Replaced original judgment'
        self.assertIn('reviewBoundToEvidence',self.evaluate(route_review=review)['refusalReasons'])
        record=json.loads((self.root/'trial.json').read_text());record['oracle']={'passed':False}
        skill.private_write(self.root/'trial.json',json.dumps(record))
        value=self.evaluate()
        self.assertFalse(value['record']['passed'])
        self.assertEqual(value['record']['oracle'],{'passed':False})

    def test_runtime_pin_drift_cannot_be_promoted_by_old_success_booleans(self):
        self.update_setup(lambda setup:setup['verification']['hashes'].__setitem__('/target/native','changed'))
        value=self.evaluate()
        self.assertFalse(value['record']['passed'])
        self.assertIn('sourceAndRuntimePinsPreserved',value['refusalReasons'])

    def test_stale_setup_runtime_evidence_or_changed_archive_refuse(self):
        self.update_setup(lambda setup:setup['verification']['artifactModes'].__setitem__('runtime/closed.json','0o600'))
        value=self.evaluate()
        self.assertFalse(value['record']['passed'])
        self.assertIn('freshEvidenceFromKnownVerifier',value['refusalReasons'])
        path=self.root/'skill-setup/setup-artifacts.tar';path.write_bytes(path.read_bytes()+b'changed')
        self.assertIn('setupArchiveUnchanged',self.evaluate()['refusalReasons'])

    def test_wrong_scope_no_events_and_failed_sky_close_refuse_with_fresh_review_hashes(self):
        evidence=json.loads((self.root/'sky-evidence.json').read_text())
        original=copy.deepcopy(evidence)
        evidence['closed.json']=json.dumps({'closed':True,'approvalScope':['com.apple.Finder'],'automaticRestart':False})
        skill.private_write(self.root/'sky-evidence.json',json.dumps(evidence))
        self.assertFalse(self.evaluate()['record']['passed'])
        original['protocol-events.jsonl']=''
        skill.private_write(self.root/'sky-evidence.json',json.dumps(original))
        self.assertFalse(self.evaluate()['record']['passed'])
        skill.private_write(self.root/'transcript.jsonl',task_transcript().replace('Computer Use runtime closed.','failed'))
        self.assertFalse(self.evaluate()['record']['passed'])


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'home'
        self.home.mkdir()
        self.patch = patch.object(Path, 'home', return_value=self.home)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.repo = self.root / 'repo'
        for relative in ['info/claude-computer-use.md', 'skills/claude-computer-use/SKILL.md',
                         'skills/claude-computer-use/scripts/prepare.py', 'tests/experiments/sky-external/bridge.py', 'tests/experiments/native-efficiency/mcp_client.py']:
            skill.private_write(self.repo / relative, 'source')
        self.runtime = self.home / '.codex/plugins/cache/openai-bundled/unified-computer-use/fixture/.mcp.json'
        skill.private_write(self.runtime, json.dumps({'mcpServers': {'cua_repl': {'command': sys.executable}}}))
        self.sha = skill.digest(self.runtime)
        self.output = self.home / 'experiment/sky-skill'
        self.host = self.home / '.claude.json'

    def generate(self):
        self.output.mkdir(parents=True, mode=0o700)
        self.server = {'command': sys.executable, 'args': [str(self.repo / 'tests/experiments/sky-external/bridge.py'),
            '--config', str(self.runtime), '--allow-app', skill.APP, '--evidence', str(self.output / 'runtime')]}
        self.write_config(self.server)
        skill.private_write(self.host, json.dumps({'other': 'preserved', 'mcpServers': {'sky_experiment': self.server}}))
        skill.private_write(self.output / 'preflight/probe.json', json.dumps({'ok': True,
            'stage': 'close', 'scope': 'startup-and-tool-shape-only', 'tools': sorted(skill.TOOLS)}))

    def write_config(self, server):
        skill.private_write(self.output / 'mcp.json', json.dumps({'mcpServers': {'sky_experiment': server}}))

    def verify(self):
        return skill.verify_generated_setup(self.repo, self.runtime, self.output, self.sha)

    def test_begin_removes_all_inherited_entries_and_preserves_unrelated_settings(self):
        skill.private_write(self.host, json.dumps({'other': 'keep', 'mcpServers': {'sky_experiment': {}, 'retained': {}},
            'projects': {str(self.repo): {'mcpServers': {'sky_experiment': {}, 'also': {}}}}}))
        skill.private_write(self.repo / '.mcp.json', json.dumps({'mcpServers': {'sky_experiment': {}, 'project': {}}}))
        inputs = skill.begin(self.repo, self.sha)
        self.assertTrue(inputs['experimentEntryAbsent'])
        self.assertEqual(inputs['removedEntries'], 3)
        self.assertEqual(inputs['runtimeConfig'], str(self.runtime.resolve()))
        self.assertFalse(self.output.exists())
        data = json.loads(self.host.read_text())
        self.assertEqual(data['other'], 'keep')
        self.assertIn('retained', data['mcpServers'])
        self.assertIn('also', data['projects'][str(self.repo)]['mcpServers'])
        self.assertNotIn('sky_experiment', (self.repo / '.mcp.json').read_text())

    def test_ambiguous_runtime_changed_pin_and_reused_output_refuse(self):
        with self.assertRaisesRegex(ValueError, 'differs'):
            skill.begin(self.repo, 'wrong')
        self.generate()
        with self.assertRaisesRegex(ValueError, 'fresh'):
            skill.begin(self.repo, self.sha)
        second = self.runtime.parent.parent / 'other/.mcp.json'
        skill.private_write(second, '{}')
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            skill.begin(self.repo, self.sha)

    def test_explicit_begin_uses_pinned_path_with_zero_or_multiple_cached_configs(self):
        selected = self.root / 'private-selected.json'
        selected.write_bytes(self.runtime.read_bytes())
        self.runtime.unlink()
        inputs = skill.begin(self.repo, self.sha, selected)
        self.assertEqual(inputs['runtimeConfig'], str(selected))
        skill.private_write(self.runtime, '{}')
        skill.private_write(self.runtime.parent.parent / 'other/.mcp.json', '{}')
        inputs = skill.begin(self.repo, self.sha, selected)
        self.assertEqual(inputs['runtimeConfig'], str(selected))
        with self.assertRaisesRegex(ValueError, 'differs'):
            skill.begin(self.repo, 'wrong', selected)

    def test_exact_scope_host_entry_probe_permissions_and_hashes(self):
        self.generate()
        verified = self.verify()
        self.assertTrue(verified['passed'])
        self.assertEqual(verified['approvedApps'], [skill.APP])
        self.assertEqual(verified['evidenceDir'], str(self.output / 'runtime'))
        self.assertEqual(verified['hashes'][str(self.runtime)], self.sha)
        self.assertFalse((self.output / 'runtime').exists())
        self.assertTrue(verified['taskRuntimeEvidenceAbsent'])

    def test_broad_invalid_duplicate_and_wrong_path_config_refuse(self):
        self.generate()
        variants = []
        for app in ['*', 'TextEdit', 'com.apple.*', 'com.apple.Finder']:
            server = copy.deepcopy(self.server)
            server['args'][4] = app
            variants.append(server)
        for extra in [['--allow-app', 'com.apple.Finder'], ['--allow-app', skill.APP]]:
            server = copy.deepcopy(self.server)
            server['args'].extend(extra)
            variants.append(server)
        server = copy.deepcopy(self.server)
        server['env'] = {'APP': '*'}
        variants.append(server)
        for index, replacement in [(0, '/other/bridge.py'), (2, '/other/runtime'), (6, '/stale/evidence')]:
            server = copy.deepcopy(self.server)
            server['args'][index] = replacement
            variants.append(server)
        for server in variants:
            with self.subTest(server=server):
                self.write_config(server)
                with self.assertRaisesRegex(ValueError, 'exact TextEdit'):
                    self.verify()

    def test_missing_mismatched_and_shadowed_actual_host_entries_refuse(self):
        self.generate()
        variants = [{}, {'mcpServers': {'sky_experiment': {}}}, {'mcpServers': {'sky_experiment': self.server},
            'projects': {str(self.repo): {'mcpServers': {'sky_experiment': self.server}}}}]
        for value in variants:
            skill.private_write(self.host, json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'actual host MCP'):
                self.verify()

    def test_generated_file_or_project_scope_is_not_ya_user_scope_registration(self):
        self.generate()
        unrelated = {'apiKeyHelper': 'managed-by-coordinator', 'projects': {'fixture': {'keep': True}},
                     'mcpServers': {'other': {'command': '/fixture/other'}}}
        skill.private_write(self.host, json.dumps(unrelated))
        with self.assertRaisesRegex(ValueError, 'actual host MCP'):
            self.verify()
        skill.private_write(self.repo / '.mcp.json', (self.output / 'mcp.json').read_text())
        with self.assertRaisesRegex(ValueError, 'actual host MCP'):
            self.verify()
        (self.repo / '.mcp.json').unlink()
        merged = copy.deepcopy(unrelated)
        merged['mcpServers']['sky_experiment'] = self.server
        skill.private_write(self.host, json.dumps(merged))
        self.assertTrue(self.verify()['hostEntryVerified'])
        stored = json.loads(self.host.read_text())
        del stored['mcpServers']['sky_experiment']
        self.assertEqual(stored, unrelated)

    def test_failed_probe_and_stale_task_marker_refuse(self):
        self.generate()
        probe = self.output / 'preflight/probe.json'
        valid = probe.read_text()
        for change in [{'ok': False}, {'stage': 'tools/list'}, {'tools': ['js']}, {'scope': 'other'}]:
            data = json.loads(valid)
            data.update(change)
            skill.private_write(probe, json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'probe'):
                self.verify()
        skill.private_write(probe, valid)
        skill.private_write(self.output / 'runtime/closed.json', '{"closed":true}')
        with self.assertRaisesRegex(ValueError, 'absent'):
            self.verify()

    def test_public_modes_and_symlink_artifacts_refuse(self):
        self.generate()
        for path in [self.output, self.output / 'mcp.json', self.output / 'preflight/probe.json', self.host]:
            mode = path.stat().st_mode & 0o777
            path.chmod(mode | 0o040)
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'private'):
                self.verify()
            path.chmod(mode)
        (self.output / 'linked').symlink_to(self.runtime)
        with self.assertRaisesRegex(ValueError, 'linked'):
            self.verify()


class FinalTextTests(unittest.TestCase):
    def test_normalized_messages_extract_only_last_visible_assistant_text(self):
        detail = {'session': {}, 'messages': [
            {'type': 'assistant', 'content': 'Earlier prose.'},
            {'type': 'assistant', 'message': {'content': [
                {'type': 'thinking', 'thinking': 'No restart required.'},
                {'type': 'text', 'text': 'Setup is prepared.'},
                {'type': 'tool_use', 'input': {'text': 'GUI done.'}},
                {'type': 'text', 'text': 'Start a fresh YA Claude session.'}]}},
            {'type': 'user', 'content': [{'type': 'tool_result', 'content': 'Ignore assistant prose.'}]},
            {'type': 'assistant', 'content': [{'type': 'thinking', 'text': 'Hidden reasoning.'},
                {'type': 'tool_use', 'text': 'Hidden tool text.'}]},
            {'type': 'assistant', 'isSubagent': True, 'content': 'Other agent text.'}]}
        extracted = skill.final_assistant_text(detail)
        self.assertEqual(extracted['finalText'], 'Setup is prepared.\nStart a fresh YA Claude session.')
        self.assertEqual(extracted['finalTextSource'], 'ya_normalized_messages')

    def test_legacy_roles_and_nested_message_array_are_supported(self):
        detail = {'session': {'messages': [{'role': 'assistant', 'content': 'Start a new session.'}]}}
        self.assertEqual(skill.final_assistant_text(detail)['finalText'], 'Start a new session.')
        detail = {'messages': [{'message': {'role': 'assistant', 'content': 'Nested visible text.'}}]}
        self.assertEqual(skill.final_assistant_text(detail)['finalText'], 'Nested visible text.')

    def test_raw_transcript_fallback_skips_thinking_tools_and_other_agents(self):
        rows = [
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Start a new session.'}]}},
            {'type': 'assistant', 'message': {'content': [{'type': 'thinking', 'text': 'Private thought.'}]}},
            {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'content': 'Not a final answer.'}]}},
            {'type': 'assistant', 'isSidechain': True, 'message': {'content': 'Subagent text.'}},
            {'type': 'assistant', 'message': {'model': '<synthetic>', 'content': 'Synthetic abort.'}}]
        extracted = skill.final_assistant_text({'session': {}}, '\n'.join(map(json.dumps, rows)))
        self.assertEqual(extracted, {'finalText': 'Start a new session.', 'finalTextSource': 'claude_transcript'})

    def test_visible_normalized_response_overrides_legacy_and_transcript(self):
        detail = {'session': {'lastAgentText': 'Start a new session.'},
                  'messages': [{'type': 'assistant', 'content': 'No restart is required.'}]}
        extracted = skill.final_assistant_text(detail,
            json.dumps({'type': 'assistant', 'message': {'content': 'Start a new session.'}}))
        self.assertFalse(skill.new_session_reported(extracted['finalText']))
        self.assertEqual(extracted['finalTextSource'], 'ya_normalized_messages')


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'receipt'
        self.args = SimpleNamespace(provider='claude', model=DEFAULT_MODELS['claude'], effort='medium',
            project='/private/checkout', skill_setup_timeout_seconds=25, poll_seconds=1)
        self.inputs = {'guide': '/private/checkout/info/claude-computer-use.md', 'runtimeConfig': '/private/runtime',
                       'authorizedApp': skill.APP, 'outputDir': '/private/setup', 'sourceHashes': {'/private/source': 'pinned'}}
        self.guest = Mock()
        self.guest.ya.side_effect = lambda method, path, body=None: (
            {'sessionId': 'launch', 'processId': 'p'} if method == 'POST' and path.endswith('/sessions') else
            {'session': {'lastAgentText': 'Start a fresh YA Claude session; this session needs restarting.'}})
        self.remote = patch.object(skill, 'remote', side_effect=self.reply).start()
        self.addCleanup(patch.stopall)
        self.native = transcript()
        patch.object(skill, 'collect_transcript', side_effect=lambda *a: result(self.native)).start()
        self.stop = patch.object(skill, 'stop_owned_session', return_value={'terminationVerified': True}).start()
        self.verification = {'passed': True, 'evidenceDir': '/private/setup/runtime', 'hashes': {'/private/source': 'pinned'}}
        self.wait = Mock(return_value={'providerSessionId': 'canonical', 'timedOut': False,
                                      'controllerWaitSeconds': 2, 'effectiveProcess': {}})
        self.owned = []

    def reply(self, guest, repo, phase, **kwargs):
        return result(self.inputs if phase == 'begin' else self.verification if phase == 'verify' else
                      base64.b64encode(b'private archive').decode())

    def run_setup(self):
        return skill.run_setup(self.guest, self.args, 'Actual TextEdit task.', self.directory,
                               self.owned, self.wait, 'runtime-hash')

    def test_setup_uses_existing_launch_profile_fresh_session_and_separate_receipts(self):
        receipt = self.run_setup()
        self.assertTrue(receipt['passed'], receipt)
        self.assertEqual(receipt['status'], 'passed')
        self.wait.assert_called_once()
        self.assertEqual(self.wait.call_args.args[2:4], (25, 1))
        self.assertEqual(self.owned[0]['providerSessionId'], 'canonical')
        prompt = (self.directory / 'prompt.txt').read_text()
        self.assertIn(self.inputs['guide'], prompt)
        self.assertIn('Actual TextEdit task.', prompt)
        self.assertIn('/private/runtime', prompt)
        self.assertNotIn('prepare.py', prompt)
        self.assertNotIn('mcpServers', prompt)
        self.assertNotIn('WaitForMcpServers', prompt)
        self.assertTrue(receipt['profileQualification']['qualified'])
        self.assertEqual(receipt['agentSeconds'], 3)
        self.assertEqual(receipt['tokenUsage']['input_tokens'], 21)
        self.assertTrue((self.directory / 'setup-artifacts.tar').exists())
        for path in self.directory.iterdir():
            self.assertEqual(path.stat().st_mode & 0o077, 0)
        self.assertTrue(json.loads((self.directory / 'receipt.json').read_text())['passed'])

    def test_setup_launch_carries_ya_appliance_registration_context_without_action_recipe(self):
        receipt = self.run_setup()
        launches = [call for call in self.guest.ya.call_args_list if call.args[0] == 'POST']
        self.assertEqual(len(launches), 1)
        request = launches[0].args[2]
        self.assertEqual(request['provider'], 'claude')
        prompt = request['message']
        for context in ['YA-hosted Claude', 'selected dedicated disposable test appliance',
                        'Scoped host registration', 'authorized on this appliance',
                        'preserve unrelated host settings and MCP servers', 'cleaned up by clone disposal',
                        'coordinator manages model and AAR credentials',
                        'stop and verify this setup session before starting a fresh task session']:
            self.assertIn(context, prompt)
        for recipe in ['prepare.py', 'mcpServers', '.claude.json', 'claude --mcp-config']:
            self.assertNotIn(recipe, prompt)
        self.assertIn('Do not delegate or spawn agents', prompt)
        self.assertIn('Authorized application: ' + skill.APP, prompt)
        self.assertEqual(prompt, (self.directory / 'prompt.txt').read_text())
        self.assertEqual(receipt['promptSha256'], skill.digest(self.directory / 'prompt.txt'))

    def test_new_session_report_and_probe_do_not_replace_actual_host_registration(self):
        self.verification = {'passed': False, 'detail': 'actual host MCP entry missing, mismatched or shadowed'}
        receipt = self.run_setup()
        self.assertTrue(receipt['workflow']['agentPrepareProbeObserved'])
        self.assertTrue(receipt['newSessionReported'])
        self.assertTrue(receipt['profileQualification']['qualified'])
        self.assertFalse(receipt['passed'])
        self.assertEqual(receipt['status'], 'blocked')
        self.assertTrue((self.directory / 'transcript.jsonl').is_file())
        self.assertEqual(receipt['toolCalls'], 1)

    def test_source_or_runtime_artifact_changes_gate_task(self):
        self.verification['hashes']['/private/source'] = 'modified'
        receipt = self.run_setup()
        self.assertFalse(receipt['passed'])
        self.assertFalse(receipt['sourceAndRuntimeUnchanged'])
        self.verification['hashes']['/private/source'] = 'pinned'
        receipt = skill.run_setup(self.guest, self.args, 'Actual task.', self.directory,
            self.owned, self.wait, 'runtime-hash', runtime_artifacts={'/private/vendor': {'sha256': 'original'}})
        self.assertFalse(receipt['passed'])
        self.assertFalse(receipt['sourceAndRuntimeUnchanged'])

    def test_absent_last_agent_text_uses_normalized_messages_for_setup_gate(self):
        self.guest.ya.side_effect = lambda method, path, body=None: (
            {'sessionId': 'launch', 'processId': 'p'} if method == 'POST' else
            {'session': {}, 'messages': [{'type': 'assistant', 'message': {'content': [
                {'type': 'thinking', 'thinking': 'Hidden.'},
                {'type': 'text', 'text': 'Start a fresh YA Claude session.'}]}}]})
        receipt = self.run_setup()
        self.assertTrue(receipt['passed'], receipt)
        self.assertTrue(receipt['newSessionReported'])
        self.assertEqual(receipt['finalTextSource'], 'ya_normalized_messages')

    def test_absent_ya_prose_uses_raw_claude_final_text_for_setup_gate(self):
        self.guest.ya.side_effect = lambda method, path, body=None: (
            {'sessionId': 'launch', 'processId': 'p'} if method == 'POST' else {'session': {}, 'messages': []})
        rows = [json.loads(line) for line in self.native.splitlines()]
        rows[-1]['message']['content'] = [{'type': 'text', 'text': 'A new session is required.'}]
        self.native = '\n'.join(map(json.dumps, rows)) + '\n'
        receipt = self.run_setup()
        self.assertTrue(receipt['passed'], receipt)
        self.assertEqual(receipt['finalTextSource'], 'claude_transcript')

    def test_setup_begin_receives_exact_selected_manifest_path(self):
        receipt = skill.run_setup(self.guest, self.args, 'Actual task.', self.directory,
            self.owned, self.wait, 'runtime-hash', runtime_config='/private/selected/runtime.json')
        self.assertTrue(receipt['passed'], receipt)
        begin_call = next(call for call in self.remote.call_args_list if call.args[2] == 'begin')
        self.assertEqual(begin_call.kwargs['runtime_config'], '/private/selected/runtime.json')
        self.assertEqual(begin_call.kwargs['runtime_sha256'], 'runtime-hash')

    def test_failed_probe_or_setup_absence_never_passes(self):
        self.native = transcript(prepared=False)
        receipt = self.run_setup()
        self.assertFalse(receipt['passed'])
        self.assertFalse(receipt['workflow']['agentPrepareProbeObserved'])
        self.assertEqual(receipt['status'], 'blocked')

    def test_model_effort_and_speed_mismatches_block_setup(self):
        for kwargs in [{'model': 'other'}, {'effort': 'high'}, {'speed': 'fast'}]:
            with self.subTest(kwargs=kwargs):
                self.native = transcript(**kwargs)
                receipt = self.run_setup()
                self.assertFalse(receipt['passed'])
                self.assertFalse(receipt['profileQualification']['qualified'])

    def test_timeout_and_wait_failure_retain_metrics_and_receipts(self):
        self.wait.side_effect = RuntimeError('wait failed')
        receipt = self.run_setup()
        self.assertFalse(receipt['passed'])
        self.assertEqual(receipt['waitError'], 'wait failed')
        self.assertTrue((self.directory / 'transcript.jsonl').exists())
        self.assertEqual(receipt['agentSeconds'], 3)

    def test_failed_artifact_collection_and_termination_gate_task(self):
        self.stop.side_effect = RuntimeError('not stopped')
        receipt = self.run_setup()
        self.assertFalse(receipt['passed'])
        self.assertEqual(receipt['status'], 'failed')
        self.stop.side_effect = None
        self.remote.side_effect = lambda guest, repo, phase, **kw: result('failure', 1) if phase == 'archive' else self.reply(guest, repo, phase, **kw)
        receipt = self.run_setup()
        self.assertFalse(receipt['passed'])
        self.assertIn('artifactCollectionError', receipt)

    def test_setup_gui_and_unreported_transition_refuse(self):
        row = {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'gui',
                'name': 'mcp__sky_experiment__js', 'input': {'code': 'ui'}}]}}
        self.native += json.dumps(row) + '\n'
        self.assertFalse(self.run_setup()['passed'])
        self.native = transcript()
        self.guest.ya.side_effect = lambda method, path, body=None: ({'sessionId': 'launch'} if method == 'POST'
            else {'session': {'lastAgentText': 'GUI task complete.'}})
        self.assertFalse(self.run_setup()['passed'])

    def test_new_session_report_requires_a_directive_and_preserves_negative_report(self):
        for text in ['Start a new YA Claude session.', 'This session needs restarting.',
                     'A fresh session is required to load these tools.']:
            self.assertTrue(skill.new_session_reported(text), text)
        for text in ['GUI done.', 'No restart is required.', 'This session does not need restarting.',
                     'Restart is optional.', 'A new session may work.']:
            self.assertFalse(skill.new_session_reported(text), text)

    def test_profile_restrictions_and_stage_costs(self):
        skill.validate_profile('claude', DEFAULT_MODELS['claude'], ['sky-external'], ['textedit-save'], 'skill')
        for provider, model, routes, tasks in [('codex', DEFAULT_MODELS['codex'], ['sky-external'], ['textedit-save']),
                ('claude', 'other', ['sky-external'], ['textedit-save']),
                ('claude', DEFAULT_MODELS['claude'], ['machine-control'], ['textedit-save']),
                ('claude', DEFAULT_MODELS['claude'], ['sky-external'], ['web-upload']),
                ('claude', DEFAULT_MODELS['claude'], ['sky-external', 'mc-python'], ['textedit-save'])]:
            with self.subTest(provider=provider, routes=routes, tasks=tasks), self.assertRaises(ValueError):
                skill.validate_profile(provider, model, routes, tasks, 'skill')
        setup = {'launched': True, 'status': 'passed', 'agentSeconds': 10, 'tokenUsage': {'input_tokens': 20}}
        accounting = skill.stage_accounting(setup)
        self.assertFalse(accounting['task']['launched'])
        self.assertIsNone(accounting['task']['agentSeconds'])
        task = {'status': 'passed', 'agentSeconds': 2, 'tokenUsage': {'input_tokens': 4}}
        accounting = skill.stage_accounting(setup, task)
        self.assertEqual(accounting['setup']['agentSeconds'], 10)
        self.assertEqual(accounting['task']['agentSeconds'], 2)
        self.assertEqual(accounting['task']['tokenUsage'], {'input_tokens': 4})


class LifecycleTests(unittest.TestCase):
    def test_idle_session_is_aborted_and_verified_with_canonical_identity(self):
        guest = Mock()
        guest.ya.side_effect = [{'process': {'id': 'p', 'sessionId': 'canonical', 'state': 'idle'}},
                               {}, {'process': {'id': 'p', 'state': 'terminated'}}]
        owned = {'launchSessionId': 'launch'}
        skill.stop_owned_session(guest, owned, sleep=lambda _: None)
        guest.ya.assert_any_call('POST', '/api/processes/p/abort', {'blockResume': True})
        guest.ya.assert_any_call('GET', '/api/sessions/canonical/process')
        self.assertTrue(owned['terminationVerified'])

    def test_absent_session_uses_known_process_before_declaring_stopped(self):
        guest = Mock()
        guest.ya.side_effect = [{}, {'processes': [{'id': 'p', 'sessionId': 'canonical', 'state': 'idle'}]},
                               {}, {'process': {'id': 'p', 'state': 'terminated'}}]
        skill.stop_owned_session(guest, {'launchSessionId': 'launch', 'processId': 'p'}, sleep=lambda _: None)
        guest.ya.assert_any_call('POST', '/api/processes/p/abort', {'blockResume': True})

    def test_unverified_stop_and_queue_cancel_refuse(self):
        guest = Mock()
        guest.ya.return_value = {'process': {'id': 'p', 'state': 'idle'}}
        owned = {'launchSessionId': 'launch'}
        with self.assertRaisesRegex(RuntimeError, 'unverified'):
            skill.stop_owned_session(guest, owned, sleep=lambda _: None)
        self.assertNotIn('terminationVerified', owned)
        guest.ya.return_value = {'cancelled': False}
        with self.assertRaisesRegex(RuntimeError, 'queue cancellation'):
            skill.stop_owned_session(guest, {'queueId': 'q'})
        guest.ya.return_value = {'cancelled': True}
        self.assertTrue(skill.stop_owned_session(guest, {'queueId': 'q'})['terminationVerified'])


class TrialGateTests(unittest.TestCase):
    """Exercise the real trial driver with fake transport/lifecycle, never live targets."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        credential = self.root / 'credential'
        credential.write_text('fixture')
        bundle = self.root / 'source.bundle'
        bundle.write_bytes(b'fixture')
        self.args = SimpleNamespace(provider='claude', model=DEFAULT_MODELS['claude'], effort='medium',
            instructions='skill', target='fixture', credential_file=credential,
            gateway_credential_file=credential, bundle=bundle, revision='pin', seed=1,
            project='/private/checkout', poll_seconds=1)
        self.timeline = []
        self.guest = Mock()
        self.guest.run.side_effect = self.guest_run
        self.guest.ya.side_effect = lambda method, path, body=None: ({'sessionId': 'task-launch', 'processId': 'task-p'}
            if method == 'POST' else {'session': {'lastAgentText': 'RESULT: done'}})
        self.setup_receipt = {'passed': False, 'status': 'blocked', 'launched': True, 'agentSeconds': 30}
        self.stop_error = False
        self.ready_doctor = True

    def machine(self, *argv, **kwargs):
        if 'doctor' in argv:
            return {'ready': self.ready_doctor if '--claim' in argv else False,
                    'target': {'logicalTarget': 'fixture'}, 'states': {'power': 'on' if '--claim' in argv else 'off'}}
        if 'acquire' in argv:
            return {'accepted': True, 'data': {'handle': 'fixture', 'claim': {'claimId': 'claim', 'resourceKey': 'exact-resource'}}}
        if 'ensure-ready' in argv:
            return {'accepted': True, 'data': {'ready': True}}
        if 'release' in argv:
            self.timeline.append('dispose')
            return {'accepted': True, 'data': {'disposition': 'discarded'}}
        return {}

    def guest_run(self, command, **kwargs):
        if 'rev-parse HEAD' in command:
            return result('pin')
        if 'native-efficiency' in command:
            return result({'service': {}, 'artifacts': {}, 'configSha256': 'runtime', 'commands': {},
                           'configPath': '/private/selected/runtime.json', 'configSelection': 'cache-exact-one'})
        if isinstance(kwargs.get('stdin'), str) and 'Sky MCP preflight failed' in kwargs['stdin']:
            return result({'passed': True, 'tools': sorted(skill.TOOLS)})
        if command == 'bash -s':
            return result({'passed': True})
        if command.startswith('f=$(find'):
            return result(task_transcript())
        if isinstance(kwargs.get('stdin'), str) and 'evidence_path=' in kwargs['stdin']:
            return result(closure_evidence())
        return result()

    def setup(self, *argv, **kwargs):
        argv[4].append({'launchSessionId': 'setup'})
        return self.setup_receipt

    def stop(self, *argv):
        self.timeline.append('stop')
        if self.stop_error:
            raise RuntimeError('not stopped')
        return {'terminationVerified': True}

    def trial(self):
        with patch.object(route, 'mc', side_effect=self.machine), patch.object(route, 'tart_names', side_effect=[set(), {'clone'}]), \
                patch.object(route, 'Guest', return_value=self.guest), patch.object(Path, 'home', return_value=self.root), \
                patch.object(skill, 'run_setup', side_effect=self.setup), patch.object(skill, 'stop_owned_session', side_effect=self.stop), \
                patch.object(route, 'wait_for_agent', return_value={'providerSessionId': 'task-canonical',
                    'timedOut': False, 'controllerWaitSeconds': 4, 'effectiveProcess': {}}):
            return route._run_trial(self.args, {'id': 'textedit-save'}, 'sky-external', 1, self.root / 'results')

    def explicit_runtime(self, *, transfer_hash=None, fingerprint_failure=False):
        config = self.root / 'runtime-manifest.json'
        raw = json.dumps({'mcpServers': {'cua_repl': {'command': '/target/installed/launcher',
            'args': ['/target/installed/cua.js'], 'env': {'CUA_REPL_NODE_REPL_PATH': '/target/installed/repl.js',
                'SKY_CUA_SERVICE_PATH': '/target/installed/Native.app', 'PRIVATE_CANARY': 'NEVER_ECHO_CONFIG_VALUE'}}}}).encode()
        config.write_bytes(raw)
        config.chmod(0o600)
        sha = skill.digest(config)
        selected = '/private/guest/experiment/runtime-input/installed-mcp.json'
        self.args.runtime_config_file = config
        self.args.runtime_config_expected_sha256 = sha
        original_run = self.guest_run

        def guest_run(command, **kwargs):
            if ' receive ' in command:
                return subprocess.CompletedProcess([], 0, json.dumps({'configPath': selected,
                    'configSha256': transfer_hash or sha, 'mode': '0o600', 'directoryMode': '0o700'}).encode(), b'')
            if ' fingerprint ' in command:
                if fingerprint_failure:
                    return result({'passed': False, 'stage': 'fingerprint', 'message': 'runtime command is missing'}, 1)
                return result({'service': {}, 'artifacts': {}, 'configSha256': sha, 'commands': {},
                               'configPath': selected, 'configSelection': 'explicit-private'})
            return original_run(command, **kwargs)

        self.guest.run.side_effect = guest_run
        return raw, sha, selected

    def test_private_runtime_bytes_use_stdin_and_direct_sky_uses_same_path_and_hash(self):
        self.args.instructions = 'current'
        raw, sha, selected = self.explicit_runtime()
        record = self.trial()
        self.assertTrue(record['passed'], record)
        transfers = [call for call in self.guest.run.call_args_list if ' receive ' in call.args[0]]
        self.assertEqual(len(transfers), 1)
        self.assertEqual(transfers[0].kwargs['stdin'], raw)
        self.assertTrue(transfers[0].kwargs['binary'])
        fingerprints = [call for call in self.guest.run.call_args_list if ' fingerprint ' in call.args[0]]
        self.assertEqual(len(fingerprints), 1)
        self.assertIn(selected, fingerprints[0].args[0])
        self.assertIn(sha, fingerprints[0].args[0])
        self.assertNotIn('stdin', fingerprints[0].kwargs)
        direct = next(call.kwargs['stdin'] for call in self.guest.run.call_args_list
                      if isinstance(call.kwargs.get('stdin'), str) and 'Sky MCP preflight failed' in call.kwargs['stdin'])
        self.assertIn('selected_runtime=' + repr(selected), direct)
        self.assertIn('expected_sha256=' + repr(sha), direct)
        self.assertNotIn('configs=list', direct)
        self.assertEqual(record['runtimeConfigInput']['sha256'], sha)
        self.assertEqual(record['runtimeConfigTransfer']['configPath'], selected)
        self.assertEqual(record['runtimeConfigSelection']['path'], selected)
        for call in self.guest.run.call_args_list:
            self.assertNotIn('NEVER_ECHO_CONFIG_VALUE', call.args[0])
            if isinstance(call.kwargs.get('stdin'), str):
                self.assertNotIn('NEVER_ECHO_CONFIG_VALUE', call.kwargs['stdin'])
        self.assertNotIn('NEVER_ECHO_CONFIG_VALUE', json.dumps(record))
        directory = self.root / 'results/textedit-save/sky-external-1'
        self.assertEqual(json.loads((directory / 'runtime.json').read_text())['configPath'], selected)
        self.assertTrue((directory / 'runtime-fingerprint-diagnostic.json').is_file())
        self.assertNotIn('NEVER_ECHO_CONFIG_VALUE', (directory / 'runtime-config-transfer-diagnostic.json').read_text())

    def test_skill_trial_propagates_selected_runtime_without_rediscovery(self):
        _, sha, selected = self.explicit_runtime()
        seen = {}
        original_setup = self.setup

        def setup(*argv, **kwargs):
            seen.update(kwargs)
            self.assertEqual(argv[6], sha)
            return original_setup(*argv, **kwargs)

        self.setup = setup
        record = self.trial()
        self.assertEqual(seen['runtime_config'], selected)
        self.assertEqual(record['runtimeConfigSelection']['sha256'], sha)
        self.assertFalse(record['stageAccounting']['task']['launched'])

    def test_transfer_hash_failure_prevents_model_launch_and_preserves_diagnostic(self):
        self.explicit_runtime(transfer_hash='mismatch')
        record = self.trial()
        self.assertIn('transfer fingerprint mismatch', record['error'])
        self.guest.ya.assert_not_called()
        self.assertTrue((self.root / 'results/textedit-save/sky-external-1/runtime-config-transfer-diagnostic.json').exists())

    def test_fingerprint_failure_prevents_model_launch_and_keeps_root_diagnostic(self):
        self.explicit_runtime(fingerprint_failure=True)
        record = self.trial()
        self.assertIn('runtime fingerprint unavailable', record['error'])
        self.guest.ya.assert_not_called()
        diagnostic = json.loads((self.root / 'results/textedit-save/sky-external-1/runtime-fingerprint-diagnostic.json').read_text())
        self.assertEqual(diagnostic['exit'], 1)
        self.assertIn('runtime command is missing', diagnostic['stdout'])

    def test_setup_failed_means_no_task_session_or_oracle_and_cleanup_precedes_disposal(self):
        record = self.trial()
        self.assertFalse(record['passed'])
        self.assertNotIn('launchSessionId', record)
        self.assertFalse(record['stageAccounting']['task']['launched'])
        self.assertEqual(record['released'], 'discarded')
        self.assertEqual(self.timeline, ['stop', 'dispose'])
        self.guest.ya.assert_not_called()
        self.assertFalse(any(call.args[0] == 'bash -s' for call in self.guest.run.call_args_list))

    def test_lifecycle_receipts_preserve_initial_off_ready_clone_claim_credentials_and_release(self):
        record = self.trial()
        evidence = record['lifecycleEvidence']
        self.assertFalse(evidence['initialDoctor']['ready'])
        self.assertEqual(evidence['initialDoctor']['states']['power'], 'off')
        self.assertTrue(evidence['readyDoctor']['ready'])
        self.assertTrue(evidence['readinessChecks'][-1]['data']['ready'])
        acquisition = evidence['workspaceAcquisition']['data']
        self.assertEqual(acquisition['handle'], 'fixture')
        self.assertEqual(acquisition['claim'], {'claimId': 'claim', 'resourceKey': 'exact-resource'})
        self.assertTrue(evidence['credentialHandoff']['verified'])
        self.assertTrue(evidence['credentialHandoff']['inheritedBytesEqual'])
        self.assertEqual(evidence['credentialHandoff']['mode'], '0o600')
        self.assertNotIn('bytes', evidence['credentialHandoff'])
        self.assertEqual(evidence['workspaceRelease']['data']['disposition'], 'discarded')

    def test_unready_claimed_clone_stops_before_agent_launch(self):
        self.ready_doctor = False
        record = self.trial()
        self.assertIn('doctor did not confirm', record['error'])
        self.assertFalse(record['lifecycleEvidence']['readyDoctor']['ready'])
        self.guest.ya.assert_not_called()
        self.assertEqual(record['released'], 'discarded')

    def test_lifecycle_timings_include_acquisition_disposal_and_match_persisted_receipt(self):
        clock = [0.0]
        original_machine = self.machine
        original_stop = self.stop

        def machine(*argv, **kwargs):
            duration = (2 if 'doctor' in argv and '--claim' not in argv else 6 if 'doctor' in argv else
                        3 if 'acquire' in argv else 4 if 'ensure-ready' in argv else
                        7 if 'bootstrap-stages' in argv else 11 if 'release' in argv else 0)
            clock[0] += duration
            return original_machine(*argv, **kwargs)

        def stop(*argv):
            clock[0] += 9
            return original_stop(*argv)

        self.machine = machine
        self.stop = stop
        self.guest.close.side_effect = lambda: clock.__setitem__(0, clock[0] + 10)
        with patch.object(route.time, 'monotonic', side_effect=lambda: clock[0]):
            record = self.trial()
        timings = record['lifecycleTimings']
        for name, expected in [('doctorSeconds', 2), ('acquisitionSeconds', 3), ('readinessSeconds', 17),
                ('ownedSessionCleanupSeconds', 9), ('tunnelCleanupSeconds', 10), ('workspaceCleanupSeconds', 11)]:
            self.assertEqual(timings[name], expected, name)
        self.assertIsNone(timings['taskWaitSeconds'])
        self.assertEqual(timings['totalSeconds'], clock[0])
        self.assertEqual(record['wallSeconds'], 17)
        self.assertEqual(timings['totalSeconds'] - record['wallSeconds'], 2 + 3 + 9 + 10 + 11)
        persisted = json.loads((self.root / 'results/textedit-save/sky-external-1/trial.json').read_text())
        self.assertEqual(persisted, record)

    def test_task_wait_legacy_metric_and_new_lifecycle_timing_remain_separate(self):
        self.args.instructions = 'current'
        record = self.trial()
        self.assertEqual(record['controllerWaitSeconds'], 4)
        timings = record['lifecycleTimings']
        self.assertIsInstance(timings['taskWaitSeconds'], float)
        self.assertGreaterEqual(timings['taskWaitSeconds'], 0)
        self.assertGreaterEqual(timings['totalSeconds'], sum(
            value for key, value in timings.items() if key != 'totalSeconds' and value is not None) - 1e-9)
        self.assertIsNotNone(timings['workspaceCleanupSeconds'])

    def test_unverified_session_stop_retains_workspace(self):
        self.stop_error = True
        record = self.trial()
        self.assertIn('workspace retained', record['releaseError'])
        self.assertEqual(self.timeline, ['stop'])
        self.assertNotIn('released', record)

    def test_success_launches_fresh_task_with_guide_and_generated_evidence_path(self):
        self.setup_receipt.update(passed=True, status='passed',
            inputs={'guide': '/private/checkout/info/claude-computer-use.md'},
            verification={'evidenceDir': '/private/generated/runtime', 'passed': True, 'taskRuntimeEvidenceAbsent': True})
        record = self.trial()
        self.assertTrue(record['passed'], record)
        launches = [call for call in self.guest.ya.call_args_list if call.args[0] == 'POST']
        self.assertEqual(len(launches), 1)
        prompt = launches[0].args[2]['message']
        actual = (route.TASKS / 'textedit-save/prompt.md').read_text()
        self.assertEqual(prompt, skill.task_prompt(self.setup_receipt['inputs'], actual, route.COMMON))
        self.assertNotIn('WaitForMcpServers', prompt)
        self.assertEqual(record['skyEvidenceDir'], '/private/generated/runtime')
        self.assertTrue(record['skyRuntimeClosed'])
        self.assertEqual(record['stageAccounting']['setup']['agentSeconds'], 30)
        self.assertEqual(record['stageAccounting']['task']['agentSeconds'], 3)
        self.assertEqual(record['oracleExit'], 0)
        self.assertTrue(any('usage show' in call.args[0] for call in self.guest.run.call_args_list))
        self.assertTrue(any('audit history' in call.args[0] for call in self.guest.run.call_args_list))
        self.assertTrue((self.root / 'results/textedit-save/sky-external-1/transcript.jsonl').exists())
        self.assertEqual(self.timeline, ['stop', 'stop', 'dispose'])

    def test_frozen_default_sky_prompt_and_preconfiguration_remain(self):
        self.args.instructions = 'current'
        record = self.trial()
        self.assertTrue(record['passed'], record)
        self.assertNotIn('skillSetup', record)
        launch = next(call for call in self.guest.ya.call_args_list if call.args[0] == 'POST')
        actual = (route.TASKS / 'textedit-save/prompt.md').read_text().strip()
        self.assertEqual(launch.args[2]['message'], '\n\n'.join([actual, route.ROUTES['sky-external'], route.COMMON]))
        self.assertTrue(record['skyPreflight']['passed'])


if __name__ == '__main__':
    unittest.main()
