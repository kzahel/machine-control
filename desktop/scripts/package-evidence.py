"""Bind final signed artifacts to exact source and build identity."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

app, output = map(Path, sys.argv[1:])
info = plistlib.loads((app/'Contents/Info.plist').read_bytes())
files = []
for file in sorted(output.iterdir()):
    if file.suffix in ('.gz', '.dmg', '.sig'):
        files.append({'name': file.name, 'size': file.stat().st_size,
                      'sha256': hashlib.file_digest(file.open('rb'), 'sha256').hexdigest()})
value = {'schema':'machine-control-desktop-build/v0',
         'version':info['CFBundleShortVersionString'],
         'bundleIdentifier':info['CFBundleIdentifier'],
         'sourceRevision':os.environ.get('GITHUB_SHA') or subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
         'sourceState':'ci_checkout' if os.environ.get('GITHUB_ACTIONS') == 'true' else 'local_working_tree',
         'workflowRun':os.environ.get('GITHUB_RUN_ID'), 'workflowAttempt':os.environ.get('GITHUB_RUN_ATTEMPT'),
         'artifacts':files}
(output/'build.json').write_text(json.dumps(value,indent=2)+'\n')
