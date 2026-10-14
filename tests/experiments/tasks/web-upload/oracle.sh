title="$(curl -s http://127.0.0.1:9223/json | /opt/homebrew/bin/python3 -c 'import json,sys; print(next((p["title"] for p in json.load(sys.stdin) if p.get("type")=="page" and "upload.html" in p.get("url","")), ""))' 2>/dev/null)"
if [ "$title" = "selected:upload-me.txt" ]; then
    printf '{"passed":true,"detail":"page received upload-me.txt"}\n'
else
    printf '{"passed":false,"detail":"page title is %s"}\n' "${title:-unavailable}"
fi
