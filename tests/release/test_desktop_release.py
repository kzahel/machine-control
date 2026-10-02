"""Publication gates over final signed candidates; no real tags or releases."""
import base64
import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('desktop_release', Path(__file__).resolve().parents[2] / 'desktop/scripts/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
VERSION = '0.3.3'
REVISION = 'a' * 40


@unittest.skipUnless(shutil.which("minisign"), "minisign required")
class DesktopReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.candidates = self.root / 'candidates'
        self.output = self.root / 'public'
        for target, (arch, _) in release.TARGETS.items():
            folder = self.candidates / ('macos-desktop-' + target)
            folder.mkdir(parents=True)
            archive = f'MachineControl_{VERSION}_{arch}.app.tar.gz'
            files = {archive: b'fixture archive', archive + '.sig': base64.b64encode(f'trusted comment: timestamp:0\tversion:{VERSION}\n'.encode()), f'MachineControl_{VERSION}_{arch}.dmg': b'fixture dmg'}
            manifest = {'schema':'machine-control-desktop-build/v0', 'version':VERSION,
                        'bundleIdentifier':'org.machine-control.app', 'sourceRevision':REVISION,
                        'sourceState':'ci_checkout', 'workflowRun':'123', 'workflowAttempt':'1',
                        'artifacts':[]}
            for name, value in files.items():
                (folder / name).write_bytes(value)
                manifest['artifacts'].append({'name':name, 'size':len(value), 'sha256':hashlib.sha256(value).hexdigest()})
            (folder / 'build.json').write_text(json.dumps(manifest))

        key, public = self.root / 'key', self.root / 'pub'
        subprocess.run(['minisign', '-G', '-W', '-s', str(key), '-p', str(public)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        config = self.root / 'desktop/src-tauri/tauri.conf.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({'plugins': {'updater': {'pubkey': base64.b64encode(public.read_bytes()).decode()}}}))
        for target, arch in release.windows_package.TARGETS.items():
            folder = self.candidates / ('windows-desktop-' + target)
            folder.mkdir()
            installer = folder / f'Machine Control_{VERSION}_{arch}-setup.exe'
            installer.write_bytes(b'fixture installer')
            subprocess.run(['minisign', '-S', '-s', str(key), '-m', str(installer),
                            '-t', 'timestamp:0\tversion:' + VERSION], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            Path(str(installer) + '.sig').write_bytes(base64.b64encode(Path(str(installer) + '.minisig').read_bytes()))
            required = ['machine-control.exe', 'uninstall.exe', 'runtime/desktop-runtime.json',
                        'runtime/machine-control-windows.exe', 'runtime/package.cat',
                        'runtime/providers/cua/cua-driver.exe', 'runtime/PenImc_cor3.dll',
                        'runtime/PresentationNative_cor3.dll', 'runtime/vcruntime140_cor3.dll',
                        'runtime/wpfgfx_cor3.dll', 'runtime/D3DCompiler_47_cor3.dll']
            (folder / 'payload.json').write_text(json.dumps({
                'schema': 'machine-control-desktop-payload/v0', 'sourceRevision': REVISION,
                'target': target, 'version': VERSION,
                'files': [{'name': name, 'size': 1, 'sha256': 'b' * 64} for name in required]}))
            release.windows_package.evidence(folder, target=target, version=VERSION,
                                             revision=REVISION, run='123.1')

    def stage(self):
        with patch.object(release.windows_package, 'ROOT', self.root):
            release.stage(self.candidates, self.output, VERSION, REVISION, '123.1', '- Desktop preview')

    def test_complete_set_and_pinned_update_urls(self):
        self.stage()
        manifest = json.loads((self.output / 'latest.json').read_text())
        self.assertEqual(set(manifest['platforms']), {'darwin-aarch64', 'darwin-x86_64', 'windows-aarch64', 'windows-x86_64'})
        self.assertEqual(len(list(self.output.iterdir())), 17)
        self.assertIn('/desktop-v0.3.3/MachineControl_0.3.3_arm64.app.tar.gz', manifest['platforms']['darwin-aarch64']['url'])
        self.assertIn('Machine%20Control_0.3.3_x64-setup.exe', manifest['platforms']['windows-x86_64']['url'])
        with self.assertRaises(ValueError):
            self.stage()

    def test_windows_missing_architecture_and_mixed_run_refused(self):
        folder = self.candidates / 'windows-desktop-aarch64-pc-windows-msvc'
        path = folder / 'build.json'
        original = path.read_text()
        value = json.loads(original); value['workflowAttempt'] = '2'
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError): self.stage()
        self.assertFalse(self.output.exists())
        path.write_text(original)
        shutil.rmtree(folder)
        with self.assertRaises(FileNotFoundError): self.stage()
        self.assertFalse(self.output.exists())

    def test_missing_architecture_and_modified_payload_refused(self):
        target = next(iter(release.TARGETS))
        folder = self.candidates / ('macos-desktop-' + target)
        archive = next(folder.glob('*.app.tar.gz'))
        archive.write_bytes(b'modified')
        with self.assertRaises(ValueError):
            self.stage()
        self.assertFalse(self.output.exists())

    def test_wrong_identity_and_missing_assets_refused(self):
        path = self.candidates / 'macos-desktop-aarch64-apple-darwin/build.json'
        original = json.loads(path.read_text())
        for key, value in [('sourceRevision', 'b'*40), ('sourceState','local_working_tree'), ('workflowAttempt','2'), ('version','0.3.2'), ('artifacts',original['artifacts'][:-1])]:
            changed = copy.deepcopy(original); changed[key] = value
            path.write_text(json.dumps(changed))
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.stage()
            self.assertFalse(self.output.exists())

    def test_notes_and_exact_annotated_source_required(self):
        changelog = self.root / 'CHANGELOG.md'
        changelog.write_text('## [0.3.3]\n\n- Preview\n\n## [0.3.2]\n- Old\n')
        self.assertEqual(release.notes(VERSION, changelog), '- Preview\n')
        with self.assertRaises(ValueError):
            release.notes('0.3.4', changelog)
        with patch.object(release, 'git', side_effect=['tag',REVISION]):
            release.check_tag('desktop-v0.3.3',VERSION,REVISION)
        with patch.object(release, 'git', side_effect=['tag','b'*40]), self.assertRaises(ValueError):
            release.check_tag('desktop-v0.3.3',VERSION,REVISION)
        with patch.object(release, 'git', return_value='commit'), self.assertRaises(ValueError):
            release.check_tag('desktop-v0.3.3',VERSION,REVISION)

    def test_immutable_and_monotonic_desktop_publication(self):
        release.check_existing([{'tag_name':'workstation-v99.0.0'}], VERSION)
        for value in [{'tag_name':'desktop-v0.3.3','draft':True}, {'tag_name':'desktop-v0.4.0','draft':False,'prerelease':False}]:
            with self.assertRaises(ValueError):
                release.check_existing([value],VERSION)
        for version in ['01.0.0','1.0','../1.0.0','1.0.0-beta']:
            with self.assertRaises(ValueError):
                release.version_tuple(version)

    def test_draft_uploaded_digests_before_publication(self):
        self.stage()
        assets = [{'name':p.name,'state':'uploaded','size':p.stat().st_size,
                   'digest':'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()} for p in self.output.iterdir()]
        draft = {'tag_name':'desktop-v0.3.3','draft':True,'prerelease':False,'assets':assets,'body':release.notes(VERSION)}
        release.check_upload(self.output,draft,VERSION)
        draft['body'] = '- Different notes'
        with self.assertRaises(ValueError):
            release.check_upload(self.output,draft,VERSION)
        draft['body'] = release.notes(VERSION)
        draft['assets'][0]['digest']='sha256:'+'0'*64
        with self.assertRaises(ValueError):
            release.check_upload(self.output,draft,VERSION)

    def test_only_successful_exact_source_unified_candidates_can_be_promoted(self):
        value = {'id': 123, 'run_attempt': 1, 'path': '.github/workflows/desktop-release.yml',
                 'head_sha': REVISION, 'head_branch': 'main', 'event': 'workflow_dispatch',
                 'status': 'completed', 'conclusion': 'success'}
        self.assertEqual(release.check_run(value, REVISION, '123'), '123.1')
        for key, bad in [('head_sha', 'b'*40), ('head_branch', 'other'), ('path', '.github/workflows/windows-desktop.yml'),
                         ('conclusion', 'failure'), ('status', 'in_progress'), ('id', 124), ('run_attempt', True)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                release.check_run(dict(value, **{key: bad}), REVISION, '123')

    def test_created_draft_resolved_by_id_and_exact_source(self):
        draft = {'id':42,'tag_name':'desktop-v0.3.3','draft':True,'prerelease':False,'target_commitish':REVISION}
        self.assertEqual(release.draft_id([{'tag_name':'workstation-v0.3.3'},draft],VERSION,REVISION),42)
        for candidates in [[],[draft,draft]]:
            with self.assertRaises(ValueError):
                release.draft_id(candidates,VERSION,REVISION)
        for key, value in [('id','42'),('id',True),('id',0),('draft',False),('prerelease',True),('target_commitish','b'*40)]:
            changed = dict(draft);changed[key] = value
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                release.draft_id([changed],VERSION,REVISION)


if __name__ == '__main__':
    unittest.main()
