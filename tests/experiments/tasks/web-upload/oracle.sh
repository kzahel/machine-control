/opt/homebrew/bin/python3 - <<'PY'
import hashlib,json,urllib.request,time
from pathlib import Path
file=Path.home()/'experiment/upload-me.txt'
expected='uploaded:'+file.name+':'+hashlib.sha256(file.read_bytes()).hexdigest()
try:
 passed=False
 for _ in range(20):
  with urllib.request.urlopen('http://127.0.0.1:9223/json',timeout=5) as response: pages=json.load(response)
  passed=any(p.get('type')=='page' and 'upload.html' in p.get('url','') and p.get('title')==expected for p in pages)
  if passed:break
  time.sleep(.25)
 print(json.dumps({'passed':passed,'detail':'page received the exact file bytes' if passed else 'expected file content not received'}))
except (OSError,ValueError):
 print(json.dumps({'passed':False,'detail':'upload verifier unavailable'}));raise SystemExit(1)
PY
