"""Real on-phone provider acceptance using temporary inference-only AAR grants."""
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time


def run():
    inference = json.loads(Path('inference.json').read_text())
    base = inference['endpoint']
    workspace = Path.cwd()
    summaries = []
    for provider in ('codex','claude'):
        home = workspace/provider
        home.mkdir(mode=0o700)
        publication = home/'session-id'
        environment = {**os.environ,'HOME':str(home),'CODEX_HOME':str(home),'CLAUDE_CONFIG_DIR':str(home),
            'AAR_TOKEN':inference['token'],'OPENAI_API_KEY':inference['token'],
            'ANTHROPIC_API_KEY':inference['token'],'ANTHROPIC_BASE_URL':base+'/claude',
            'DISABLE_AUTOUPDATER':'1','CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1',
            'USE_BUILTIN_RIPGREP':'0','PATH':'/opt/codex/bin:/usr/bin:/bin'}
        bridge_args = [str(workspace/'session.py'),'--receipt',str(workspace/'bridge.json'),
                       '--session-id-file',str(publication)]
        mcp = {'mcpServers':{'phone':{'command':'/usr/bin/python3','args':bridge_args}}}
        mcp_path = home/'mcp.json';mcp_path.write_text(json.dumps(mcp));mcp_path.chmod(0o600)
        challenge = provider.upper() + '_' + Path('challenge.txt').read_text().strip()
        prompt = f'''Operate ONLY the owned MC Android Fixture using the phone MCP mc tool.
Use persistent Python: bind app = mc.app("MC Android Fixture") and remembered = 41.
In a SEPARATE mc tool call assert remembered + 1 == 42, read app.tree(), then use
numbers from the actual current tree to set its textfield to {challenge!r}.
Press the fixture Apply button using its observed number and verify the exact
Result text in a fresh tree. Button labels may be uppercase. Then call
app.screenshot() and inspect the returned image. Finish with mc.close().
No shell, ADB, network, personal apps or other tools. The coordinator publishes
your actual session ID; omit session_id from tool arguments. Report failures
honestly; do not claim an action from delivery alone. If a control is stale,
read app.tree() and use its new numbers. If ownership ended, explicitly use
mc_reset, bind the app again, and observe before deciding any further action.'''
        if provider == 'codex':
            config = '''model = "gpt-6.1-sol"
model_reasoning_effort = "low"
model_provider = "aar"
approval_policy = "never"
sandbox_mode = "danger-full-access"
[model_providers.aar]
name = "Temporary inference grant"
base_url = %s
wire_api = "responses"
env_key = "AAR_TOKEN"
[features]
shell_tool = false
[mcp_servers.phone]
command = "/usr/bin/python3"
args = %s
required = true
enabled_tools = ["mc", "mc_reset"]
[mcp_servers.phone.tools.mc]
approval_mode = "approve"
[mcp_servers.phone.tools.mc_reset]
approval_mode = "approve"
''' % (json.dumps(base+'/codex'),json.dumps(bridge_args))
            (home/'config.toml').write_text(config)
            command = ['/opt/codex/bin/codex','exec','--json','--skip-git-repo-check','--ephemeral',prompt]
        else:
            command = ['/opt/claude/claude','--bare','-p',prompt,'--output-format','stream-json','--verbose',
                '--model','sonnet','--strict-mcp-config','--mcp-config',str(mcp_path),
                '--tools','mcp__phone__mc,mcp__phone__mc_reset','--allowedTools','mcp__phone__mc,mcp__phone__mc_reset',
                '--max-turns','12','--max-budget-usd','0.75']
        events = []
        with (home/'stderr.log').open('wb') as errors:
            process = subprocess.Popen(command,env=environment,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=errors)
            selector = selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
            pending = b''; deadline = time.monotonic()+150
            try:
                while selector.get_map():
                    assert time.monotonic() < deadline, provider+' timed out'
                    for key,_ in selector.select(.2):
                        chunk = os.read(key.fd,65536)
                        if not chunk: selector.unregister(key.fileobj);continue
                        pending += chunk
                        assert len(pending) < 8*1024*1024, 'Unbounded provider line'
                        while b'\n' in pending:
                            line,pending = pending.split(b'\n',1)
                            try: event = json.loads(line)
                            except ValueError: continue
                            events.append(event)
                            identity = event.get('thread_id') if event.get('type') == 'thread.started' else event.get('session_id') if event.get('type') == 'system' and event.get('subtype') == 'init' else None
                            if identity:
                                temporary = publication.with_suffix('.next')
                                temporary.write_text(identity);temporary.chmod(0o600);temporary.replace(publication)
                assert process.wait(timeout=5) == 0, provider+' failed'
            finally:
                selector.close()
                if process.poll() is None: process.kill();process.wait()
            (home/'events.json').write_text(json.dumps(events,indent=2)+'\n')
        if provider == 'codex':
            calls = list({e['item']['id']:e['item'] for e in events if e.get('type') == 'item.completed' and e.get('item',{}).get('type') == 'mcp_tool_call'}.values())
            assert any(e.get('type') == 'turn.completed' for e in events), 'No completed Codex turn'
            assert calls and all(c.get('status') == 'completed' for c in calls), 'Codex MCP failure'
            sources = [c.get('arguments',{}) for c in calls]
            image_count = sum(any(b.get('type')=='image' for b in (c.get('result') or {}).get('content',[])) for c in calls)
        else:
            calls = [b for e in events if e.get('type') == 'assistant' for b in e.get('message',{}).get('content',[]) if b.get('type') == 'tool_use']
            assert any(e.get('type') == 'result' and not e.get('is_error') for e in events), 'No successful Claude result'
            sources = [c.get('input',{}) for c in calls]
            results = [b for e in events if e.get('type') == 'user' for b in e.get('message',{}).get('content',[]) if b.get('type') == 'tool_result']
            assert results and not any(r.get('is_error') for r in results), 'Claude MCP failure'
            image_count = sum(isinstance(r.get('content'),list) and any(b.get('type')=='image' for b in r['content']) for r in results)
        source = '\n'.join(json.dumps(s) for s in sources)
        assert len(calls) >= 3 and 'remembered' in source and 'screenshot' in source and 'close' in source, 'Incomplete real tool exercise'
        assert image_count > 0, 'No actual inline image tool result'
        # Signal the controller to independently read the fixture before the
        # next provider overwrites it. No model-reported text is the oracle.
        Path(provider+'-expected.txt').write_text(challenge)
        Path(provider+'-await-oracle').write_text('ready')
        deadline = time.monotonic()+15
        while not Path(provider+'-oracle-verified').exists():
            assert time.monotonic() < deadline, 'Missing independent provider oracle'
            time.sleep(.05)
        summaries.append({'provider':provider,'actualMcpCalls':len(calls),'persistentState':True,
            'semanticEffectIndependentlyVerified':True,'inlineImageReplies':image_count})
        time.sleep(.2)
    Path('provider-witness.json').write_text(json.dumps(summaries,indent=2)+'\n')


if __name__ == '__main__': run()
