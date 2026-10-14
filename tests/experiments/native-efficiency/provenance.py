"""Private provenance for a dedicated guest; never commit the resulting file."""
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def collect(config):
    value={'configSha256':digest(config),'commands':{},'artifacts':{}}
    for command in (['sw_vers'],['uname','-m'],['csrutil','status'],['xcode-select','-p']):
        p=subprocess.run(command,capture_output=True,text=True)
        value['commands'][' '.join(command)]={'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    cfg=json.loads(Path(config).read_text())['mcpServers']['cua_repl']
    paths=[Path(cfg['command']),Path(cfg['args'][0]),Path(cfg['env']['CUA_REPL_NODE_REPL_PATH'])]
    service=Path(cfg['env']['SKY_CUA_SERVICE_PATH'])
    info=plistlib.loads((service/'Contents/Info.plist').read_bytes())
    value['service']={k:info.get(k) for k in ('CFBundleIdentifier','CFBundleShortVersionString','CFBundleVersion')}
    paths.append(service/'Contents/MacOS'/info['CFBundleExecutable'])
    paths.extend(Path(__file__).parent.glob('*.py'));paths.extend(Path(__file__).parent.glob('*.swift'))
    # Exact resident identity is discovered from running processes, not inferred from checkout HEAD.
    p=subprocess.run(['pgrep','-fl','MachineControl|MacVMUI'],capture_output=True,text=True)
    value['residentProcesses']=p.stdout
    for line in p.stdout.splitlines():
        pid=line.split()[0]
        path=subprocess.check_output(['ps','-p',pid,'-o','comm='],text=True).strip()
        if Path(path).is_file():paths.append(Path(path))
    for path in paths:
        value['artifacts'][str(path)]={'sha256':digest(path),'bytes':path.stat().st_size}
    return value
