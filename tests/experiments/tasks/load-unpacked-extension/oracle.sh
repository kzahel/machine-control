/opt/homebrew/bin/python3 - <<'PY'
import json,time,urllib.request
from pathlib import Path
root=Path.home()/'experiment'
expected=(root/'extension-expected.txt').read_text()
prefs=root/'cft-profile/Default/Secure Preferences'
try:
 settings=json.loads(prefs.read_text()).get('extensions',{}).get('settings',{})
 registered=any(v.get('path')==str(root/'probe-ext') and v.get('state') in (None,1)
                and not v.get('disable_reasons') for v in settings.values())
except (OSError,ValueError,AttributeError):registered=False
# Exercise the installed extension on a fresh page; never install/enable it here.
request=urllib.request.Request('http://127.0.0.1:9223/json/new?http://127.0.0.1:9225/',method='PUT')
try:
 with urllib.request.urlopen(request,timeout=5) as response: tab=json.load(response)['id']
 passed=False
 for _ in range(20):
  with urllib.request.urlopen('http://127.0.0.1:9223/json',timeout=5) as response: pages=json.load(response)
  passed=registered and any(p.get('id')==tab and p.get('title')==expected for p in pages)
  if passed:break
  time.sleep(.25)
 print(json.dumps({'passed':passed,'detail':'enabled extension changed the fresh fixture page' if passed else 'extension behavior absent'}))
except (OSError,ValueError,KeyError):
 print(json.dumps({'passed':False,'detail':'extension verifier unavailable'}));raise SystemExit(1)
PY
