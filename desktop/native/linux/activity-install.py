#!/usr/bin/python3
"""Closed operator installation/removal for the read-only activity service."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT=Path('/usr/local/libexec/machine-control-activity')
UNIT=Path('/etc/systemd/system/machine-control-activity.service')
SERVICE='machine-control-activity.service'
FILES=('activityd.py','activity_events.py')
UNIT_BYTES=b'''[Unit]
Description=Machine Control read-only physical activity facts
After=systemd-logind.service
Requires=systemd-logind.service
[Service]
Type=simple
ExecStart=/usr/bin/python3 -I -B /usr/local/libexec/machine-control-activity/activityd.py
RuntimeDirectory=machine-control-activity
RuntimeDirectoryMode=0755
UMask=0077
User=root
NoNewPrivileges=true
CapabilityBoundingSet=
PrivateNetwork=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_UNIX
RestrictNamespaces=true
LockPersonality=true
MemoryDenyWriteExecute=true
DevicePolicy=closed
DeviceAllow=char-input r
TimeoutStopSec=5
Restart=no
[Install]
WantedBy=multi-user.target
'''


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def owned(path,mode=None):
    st=path.lstat()
    if st.st_uid!=0 or st.st_mode&0o022 or stat.S_ISLNK(st.st_mode):raise ValueError('unowned_activity_installation')
    if mode=='file' and not stat.S_ISREG(st.st_mode):raise ValueError('unowned_activity_installation')
    if mode=='directory' and not stat.S_ISDIR(st.st_mode):raise ValueError('unowned_activity_installation')


def systemctl(*args,check=True):
    return subprocess.run(['/usr/bin/systemctl',*args],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=check,timeout=20)


def receipt():
    owned(ROOT,'directory');owned(ROOT/'receipt.json','file');owned(UNIT,'file')
    value=json.loads((ROOT/'receipt.json').read_text())
    if value.get('schema')!='machine-control-activity-installation/v1' or set(value.get('files',{}))!=set(FILES):raise ValueError('unowned_activity_installation')
    if digest(UNIT)!=value.get('unitSha256'):raise ValueError('activity_unit_changed')
    for name,sha in value['files'].items():
        owned(ROOT/name,'file')
        if digest(ROOT/name)!=sha:raise ValueError('activity_payload_changed')
    return value


def main():
    if os.geteuid()!=0 or len(sys.argv)!=2 or sys.argv[1] not in ('install','uninstall','status'):
        raise ValueError('typed_root_activity_operation_required')
    operation=sys.argv[1]
    lock=os.open('/run/machine-control-activity-install.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    st=os.fstat(lock)
    if not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_mode&0o077:raise ValueError('invalid_activity_lock')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    exists=ROOT.exists() or UNIT.exists()
    current=receipt() if exists else None
    if operation=='status':
        print(json.dumps({'installed':current is not None,'readOnly':True}));return
    if operation=='uninstall':
        if current is not None:
            systemctl('disable','--now',SERVICE)
            # Every removed path was authenticated by the installation receipt.
            for name in (*FILES,'receipt.json'):(ROOT/name).unlink()
            ROOT.rmdir();UNIT.unlink();systemctl('daemon-reload')
        print(json.dumps({'removed':True}));return
    source=Path(__file__).resolve().parent
    metadata=json.loads((source/'desktop-runtime.json').read_text())
    if metadata.get('schema')!='machine-control-linux-desktop-runtime/v0':raise ValueError('activity_source_unverified')
    entries={row['path']:row['sha256'] for row in metadata['files'] if row.get('path') in FILES}
    if set(entries)!=set(FILES):raise ValueError('activity_source_unverified')
    if any(digest(source/name)!=entries[name] for name in FILES):raise ValueError('activity_source_changed')
    ROOT.parent.mkdir(parents=True,exist_ok=True)
    owned(ROOT.parent,'directory')
    if current is not None:systemctl('stop',SERVICE)
    with tempfile.TemporaryDirectory(prefix='.activity-',dir=ROOT.parent) as temporary:
        stage=Path(temporary)
        for name in FILES:
            shutil.copyfile(source/name,stage/name);(stage/name).chmod(0o644)
            if digest(stage/name)!=entries[name]:raise ValueError('activity_source_changed')
        value=dict(schema='machine-control-activity-installation/v1',files=entries,
                   unitSha256=hashlib.sha256(UNIT_BYTES).hexdigest())
        (stage/'receipt.json').write_text(json.dumps(value)+'\n');(stage/'receipt.json').chmod(0o600)
        ROOT.mkdir(mode=0o755,exist_ok=True);ROOT.chmod(0o755)
        for name in (*FILES,'receipt.json'):os.replace(stage/name,ROOT/name)
    with tempfile.NamedTemporaryFile(dir=UNIT.parent,delete=False) as stream:
        staged_unit=Path(stream.name);os.fchmod(stream.fileno(),0o644);stream.write(UNIT_BYTES);stream.flush();os.fsync(stream.fileno())
    try:os.replace(staged_unit,UNIT)
    finally:staged_unit.unlink(missing_ok=True)
    receipt();systemctl('daemon-reload');systemctl('enable','--now',SERVICE)
    print(json.dumps({'installed':True,'readOnly':True}))


if __name__=='__main__':
    try:main()
    except Exception:
        # No arguments, paths, input or authorization material reach output.
        print(json.dumps({'accepted':False,'errorCode':'activity_installation_refused'}));raise SystemExit(1)
