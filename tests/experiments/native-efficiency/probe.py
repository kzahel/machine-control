#!/usr/bin/env python3
"""Deterministic fixture probes. Run only inside a claimed disposable guest."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from mcp_client import MCP

APP = 'org.machine-control.efficiency.target'


def read_state(root, kind):
    return json.loads((root / kind / 'state.json').read_text())


def command(root, kind, operation, **values):
    path = root / kind / 'command.json'
    ident = uuid.uuid4().hex
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(dict(id=ident, operation=operation, **values)))
    tmp.replace(path)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        value = read_state(root, kind)
        if value['lastCommand'] == ident:
            return value
        time.sleep(.01)
    raise RuntimeError('fixture command not acknowledged')


class Provider:
    def __init__(self, args):
        self.args = args
        self.mcp = None
        self.tree = None
        if args.route == 'sky':
            config = json.loads(args.config.read_text())['mcpServers']['cua_repl']
            self.mcp = MCP(config, args.output)
            initial = self.mcp.js(f'var app = await cua.getApp({json.dumps(APP)});')
            (args.output / 'bind.json').write_text(json.dumps(initial, indent=2))
            if initial['result'].get('isError'):
                self.mcp.close(); raise RuntimeError('Sky app binding failed')
        else:
            self.cli = [sys.executable, str(args.checkout/'bin/machine-control'),
                        '--target', 'host', '--claim', args.claim]

    def call(self, request):
        start = time.perf_counter()
        value = subprocess.run([*self.cli, 'desktop', 'call', json.dumps(request)],
                               capture_output=True, text=True, timeout=30)
        return {'seconds': time.perf_counter()-start, 'result': json.loads(value.stdout)}

    def observe(self, full=False):
        if self.mcp:
            result = self.mcp.js('await app.getAXState('+json.dumps({'disableDiffing': full})+');')
            self.tree = '\n'.join(x.get('text', '') for x in result['result'].get('content', []) if x['type']=='text')
        else:
            result = self.call({'operation': 'snapshot', 'target': APP, 'maxDepth': 20,
                                'maxElements': 1500, 'projection': self.args.projection})
            self.tree = result['result'].get('data', {}).get('elements', [])
        return result

    def element(self, label):
        if self.mcp:
            matches = re.findall(r'^\s*(\d+) [^\n]*\b'+re.escape(label)+r'(?:,.*)?$', self.tree, re.M)
            if len(matches) != 1: raise RuntimeError('ambiguous/missing element '+label)
            return int(matches[0])
        found = [e for e in self.tree if e.get('label') == label]
        if len(found) != 1: raise RuntimeError('ambiguous/missing element '+label)
        return found[0]

    def click(self, label, pointer=False):
        element = self.element(label)
        if self.mcp:
            return self.mcp.js(f'await app.click({element});')
        if pointer:
            # Observe capture before coordinate input; bounds come from the current tree.
            capture = self.call({'operation':'capture', 'target':APP, 'scope':'window'})
            if capture['result'].get('accepted') is not True:
                return capture
            b = element['bounds']
            return self.call({'operation':'input.click', 'target':APP,
                             'x':b['x']+b['width']/2, 'y':b['y']+b['height']/2})
        return self.call({'operation':'action','reference':element['reference'],'action':'press'})

    def menu(self):
        if self.mcp:
            section = self.tree.split('menu bar\n', 1)[-1]
            matches = re.findall(r'^\s*(\d+) Efficiency Target$', section, re.M)
            if len(matches) != 1: raise RuntimeError('fixture app menu not found')
            return self.mcp.js(f'await app.click({int(matches[0])});')
        found = [e for e in self.tree if e.get('role')=='AXMenuBarItem' and e.get('label')=='Efficiency Target']
        if len(found)!=1: raise RuntimeError('fixture app menu not found')
        return self.call({'operation':'action','reference':found[0]['reference'],'action':'press'})

    def type_text(self):
        if self.mcp: return self.mcp.js('await app.typeText("probe-text");')
        return self.call({'operation':'input.text','target':APP,'text':'probe-text'})

    def close(self):
        if self.mcp: self.mcp.close()


def run(args):
    args.output.mkdir(parents=True, mode=0o700, exist_ok=False)
    (args.output/'campaign.json').write_text(json.dumps({'route':args.route,
        'projection':args.projection,'repetitions':args.repetitions,
        'sections':args.section or ['background','tree','settle']},indent=2))
    provider = Provider(args)
    records = []
    def measured(name, action, **details):
        before = {k:read_state(args.root,k) for k in ('target','sentinel')}
        record = {'name':name, **details, 'before':before}
        try:
            record.update(action())
        except Exception as error:
            record['error'] = str(error)
        record['atReturn'] = {k:read_state(args.root,k) for k in ('target','sentinel')}
        # Bounded post-action oracle sampling; not part of measured provider latency.
        time.sleep(.12)
        record['after'] = {k:read_state(args.root,k) for k in ('target','sentinel')}
        records.append(record)
        (args.output/'records.json').write_text(json.dumps(records, indent=2))
        print(json.dumps({k:v for k,v in record.items() if k not in ('before','after','atReturn','result','trigger')}),flush=True)
        return record
    def background(name, action, **details):
        command(args.root,'sentinel','foreground'); time.sleep(.1)
        return measured(name, action, **details)
    try:
        for n in range(args.repetitions if not args.section or 'background' in args.section else 0):
            for kind in ('target','sentinel'): command(args.root,kind,'reset')
            command(args.root,'sentinel','foreground');time.sleep(.15)
            background('background-observe',lambda:provider.observe(True),repetition=n)
            background('background-button',lambda:provider.click('Increment'),repetition=n)
            provider.observe(True)
            background('background-pointer',lambda:provider.click('Pointer only',True),repetition=n)
            provider.observe(True)
            # Element click for Sky; explicit MC pointer route for an editable field.
            background('background-field',lambda:provider.click('Probe text',True),repetition=n)
            background('background-type',provider.type_text,repetition=n)
            provider.observe(True)
            background('background-sheet-open',lambda:provider.click('Show sheet'),repetition=n)
            provider.observe(True)
            background('background-sheet-close',lambda:provider.click('Close probe sheet'),repetition=n)
            provider.observe(True)
            background('background-menu-open',provider.menu,repetition=n)
            provider.observe(True)
            measured('background-menu-item',lambda:provider.click('Increment from menu'),repetition=n)
            # Restore controlled foreground before every later case.
            command(args.root,'sentinel','foreground')
        for size in ((20,100,300) if not args.section or 'tree' in args.section else ()):
            command(args.root,'target','rows',count=size)
            measured('tree-first-after-resize',lambda:provider.observe(True),size=size)
            for n in range(args.repetitions):
                measured('tree-unchanged',provider.observe,size=size,repetition=n)
                command(args.root,'target','updates',delay=0.,count=1)
                time.sleep(.05)
                measured('tree-one-change',provider.observe,size=size,repetition=n)
        for name,delay,count,interval in ([('delayed',.35,1,.05),('burst',.02,8,.05),('continuous',.02,100,.03)] if not args.section or 'settle' in args.section else []):
            for n in range(args.repetitions):
                command(args.root,'target','reset'); provider.observe(True)
                command(args.root,'target','updates',delay=delay,count=count,interval=interval)
                measured('settle-'+name,provider.observe,repetition=n,scheduledCount=count)
                # Read again after producer completion to distinguish stale-but-valid observations.
                time.sleep(max(0.,delay+count*interval))
                measured('settle-'+name+'-final',provider.observe,repetition=n)
        for name,label,total in ([('delayed','Delayed update',1),('burst','Burst updates',8),('continuous','Continuous updates',100)] if not args.section or 'settle' in args.section else []):
            for n in range(args.repetitions):
                command(args.root,'target','reset'); provider.observe(True)
                action = provider.click(label)
                measured('settle-action-'+name,provider.observe,repetition=n,
                         scheduledCount=total,trigger=action)
                time.sleep(3.2 if total==100 else .5)
                measured('settle-action-'+name+'-final',provider.observe,repetition=n)
    finally:
        try: command(args.root,'target','reset')
        finally: provider.close()


if __name__=='__main__':
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route',choices=['sky','mc-cli'],required=True)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--config',type=Path)
    parser.add_argument('--checkout',type=Path,default=Path.home()/'code/machine-control')
    parser.add_argument('--claim')
    parser.add_argument('--repetitions',type=int,default=5)
    parser.add_argument('--projection',choices=['full','compact'],default='full')
    parser.add_argument('--section',choices=['background','tree','settle'],action='append')
    args=parser.parse_args()
    if args.route=='sky' and not args.config: parser.error('--config required for sky')
    if args.route=='mc-cli' and not args.claim: parser.error('--claim required for mc-cli')
    run(args)
