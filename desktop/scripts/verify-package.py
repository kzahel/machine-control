"""Verify updater bytes, signatures, signed version, and nested native code."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import tarfile
import tempfile

p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--revision');p.add_argument('--team-id',required=True);p.add_argument('--test-tampering',action='store_true');args=p.parse_args()
manifest=json.loads((args.directory/'build.json').read_text())
if manifest['schema']!='machine-control-desktop-build/v0':raise SystemExit('Unknown build schema')
if args.revision and manifest['sourceRevision']!=args.revision:raise SystemExit('Source revision mismatch')
config=json.loads((Path(__file__).resolve().parents[1]/'src-tauri/tauri.conf.json').read_text())
with tempfile.TemporaryDirectory(prefix='mc-verify-') as tmp:
    root=Path(tmp);pub=root/'updater.pub';pub.write_bytes(base64.b64decode(config['plugins']['updater']['pubkey'],validate=True))
    archives=[]
    for item in manifest['artifacts']:
        name=item['name']
        if Path(name).name != name:raise SystemExit('Unsafe artifact name')
        file=args.directory/name
        if file.stat().st_size!=item['size'] or hashlib.file_digest(file.open('rb'),'sha256').hexdigest()!=item['sha256']:raise SystemExit('Artifact digest mismatch')
        if name.endswith('.app.tar.gz'):archives.append(file)
    if len(archives)!=1:raise SystemExit('Exactly one updater archive is required')
    archive=archives[0];signature=root/'archive.sig';signature.write_bytes(base64.b64decode(Path(str(archive)+'.sig').read_text(),validate=True))
    def verify(file):
        return subprocess.run(['minisign','-V','-p',str(pub),'-m',str(file),'-x',str(signature)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if verify(archive).returncode:raise SystemExit('Updater archive signature failed')
    comments=[line for line in signature.read_text().splitlines() if line.startswith('trusted comment: ')]
    versions=[field.removeprefix('version:') for line in comments for field in line.split('\t') if field.startswith('version:')]
    if len(comments)!=1 or versions!=[manifest['version']]:raise SystemExit('Signed version mismatch')
    if args.test_tampering:
        bad=root/'tampered';shutil.copyfile(archive,bad)
        with bad.open('ab') as stream:stream.write(b'tampered')
        if verify(bad).returncode==0:raise SystemExit('Modified package signature was accepted')
    with tarfile.open(archive) as tar:
        members=tar.getmembers()
        # The generated app legitimately includes framework links. Enforce the
        # standard data filter, which refuses links escaping the staging tree.
        tar.extractall(root/'extracted',filter='data')
    app=root/'extracted/Machine Control.app'
    info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
    if info['CFBundleIdentifier']!='org.machine-control.app' or info['CFBundleShortVersionString']!=manifest['version'] or info.get('MCSourceRevision')!=manifest['sourceRevision']:raise SystemExit('Installed app identity mismatch')
    for relative in ['Contents/Resources/org.machine-control.resident.plist.in',
                     'Contents/Resources/chrome-extension/manifest.json',
                     'Contents/Resources/chrome-extension/service_worker.js',
                     'Contents/Resources/mc-session-probe',
                     'Contents/Frameworks/MCResident.framework/MCResident']:
        if not (app/relative).is_file():raise SystemExit('Required installed resource missing: '+relative)
    if tuple(map(int, manifest['version'].split('.'))) >= (0, 4, 10):
        if not (app/'Contents/Resources/chrome-extension/indicators.js').is_file():raise SystemExit('Required tab indicator module missing')
    for path in [app,app/'Contents/Frameworks/MCResident.framework',app/'Contents/Resources/mc-session-probe']:
        subprocess.run(['codesign','--verify','--strict','-R',f'=anchor apple generic and certificate leaf[subject.OU] = "{args.team_id}"',str(path)],check=True)
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    subprocess.run(['spctl','--assess','--type','execute',str(app)],check=True)
    subprocess.run(['xcrun','stapler','validate',str(app)],check=True,stdout=subprocess.DEVNULL)
    dmgs=[args.directory/item['name'] for item in manifest['artifacts'] if item['name'].endswith('.dmg')]
    if len(dmgs)!=1:raise SystemExit('Exactly one DMG is required')
    subprocess.run(['codesign','--verify','--strict','-R',f'=anchor apple generic and certificate leaf[subject.OU] = "{args.team_id}"',str(dmgs[0])],check=True)
    subprocess.run(['xcrun','stapler','validate',str(dmgs[0])],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['spctl','--assess','--type','open','--context','context:primary-signature',str(dmgs[0])],check=True)
print('Archive, updater signature, signed version, native signatures, Gatekeeper, and stapling verified')
