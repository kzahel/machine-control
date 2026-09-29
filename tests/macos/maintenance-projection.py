#!/usr/bin/env python3
"""Check consent/readiness separation using the actual audit projection."""
from pathlib import Path
import json
import subprocess

root = Path(__file__).resolve().parents[2]
source = (root / 'platforms/macos/guests/macos/bootstrap/post-update.sh').read_text()
start = source.index('        if [[ "$(json_value "$resident_result" schema')
end = source.index('\n    fi\n\n    unlock_required', start)
projection = source[start:end]
for data, consent, ready in [
    ({'semanticState':'ready','captureState':'ready'}, True, True),
    ({'semanticState':'unavailable','captureState':'ready',
      'semanticAuthorizationState':'ready','captureAuthorizationState':'ready'}, True, False),
    ({'semanticState':'unavailable','captureState':'unavailable',
      'semanticAuthorizationState':'unavailable','captureAuthorizationState':'unavailable'}, False, False),
    ({'semanticState':'ready','captureState':'unavailable',
      'semanticAuthorizationState':'ready','captureAuthorizationState':'ready'}, True, False),
]:
    setup = '''
json_value() { printf '%s' "$1" | /usr/bin/plutil -extract "$2" raw -o - - 2>/dev/null; }
semantic_authorization=false
capture_authorization=false
target_native=false
resident_result="$1"
'''
    script = setup + projection + '\nprintf "%s %s\\n" "$semantic_authorization" "$target_native"\n'
    value = json.dumps({'schema':'machine-control/v0','accepted':True,'data':data})
    result = subprocess.check_output(['bash','-c',script,'fixture',value], text=True).strip()
    assert result == f'{str(consent).lower()} {str(ready).lower()}', result
print('Maintenance consent/readiness projection passed')
