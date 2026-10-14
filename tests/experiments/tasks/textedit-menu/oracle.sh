/opt/homebrew/bin/python3 - <<'PY'
import json
from pathlib import Path
root=Path.home()/'experiment'
p=root/'out/menu-note.txt'
expected_source=br'{\rtf1\ansi\b Menu conversion fixture\b0}'
content=p.read_bytes() if p.exists() else b''
passed=content.strip()==b'Menu conversion complete' and (root/'menu-source.rtf').read_bytes()==expected_source
print(json.dumps({'passed':passed,'detail':'plain-text destination and intact source' if passed else 'wrong format/content/destination or changed source'}))
PY
