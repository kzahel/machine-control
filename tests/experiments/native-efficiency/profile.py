#!/usr/bin/env python3
"""Scoped API/syscall counts and sampled stacks around a fixed Sky workload.

Requires an authorized dedicated guest and existing profiling privileges.
Does not change signing, permissions, SIP or service configuration.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import time

from mcp_client import MCP
from probe import command, APP

APIS = ('AXUIElementCopyAttributeValue', 'AXUIElementCopyAttributeValues',
        'AXUIElementCopyMultipleAttributeValues', 'AXUIElementPerformAction',
        'AXObserverAddNotification', 'CGEventPostToPid', 'CGEventPost',
        'CGEventCreateMouseEvent', 'CGWindowListCreateImage')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--workload',choices=['unchanged','changed','pointer-and-type'],action='append')
    args=parser.parse_args()
    os.umask(0o077);args.output.mkdir(parents=True,exist_ok=False)
    m=MCP(json.loads(args.config.read_text())['mcpServers']['cua_repl'],args.output)
    records=[]
    try:
        m.js(f'var app = await cua.getApp({json.dumps(APP)});')
        command(args.root,'target','reset');command(args.root,'target','rows',count=100)
        for workload,code in (
            ('unchanged','await app.getAXState();'),
            ('changed','var state = await app.getAXState({disableDiffing:true,emit:false}); '
             'var match = state.match(/^\\s*(\\d+) button Increment$/m); '
             'if (!match) throw new Error("Increment missing"); '
             'await app.click(Number(match[1])); await app.getAXState();'),
            ('pointer-and-type','var state = await app.getAXState({disableDiffing:true,emit:false}); '
             'var pointer = state.match(/^\\s*(\\d+) container Pointer only$/m); '
             'var field = state.match(/^\\s*(\\d+) text field [^\\n]*Probe text\\b/m); '
             'if (!pointer || !field) throw new Error("fixture controls missing"); '
             'await app.click(Number(pointer[1])); await app.click(Number(field[1])); '
             'await app.typeText("x"); await app.getAXState();')):
            if args.workload and workload not in args.workload: continue
            for mode in ('untraced','api','syscalls','sample'):
                trace=None; stdout=None; stderr=None
                if mode!='untraced':
                    stdout=(args.output/f'{workload}-{mode}.txt').open('w')
                    stderr=(args.output/f'{workload}-{mode}.stderr').open('w')
                    if mode=='sample':
                        argv=['sample',str(args.pid),'10','1','-file',str(args.output/f'{workload}-stacks.txt')]
                    else:
                        probes=' '.join('pid$target::'+api+':entry { @calls["'+api+'"] = count(); }' for api in APIS)
                        program=(probes if mode=='api' else
                                 'syscall:::entry /pid == $target/ { @calls[probefunc] = count(); }')
                        argv=['sudo','-n','dtrace','-Z','-q','-p',str(args.pid),'-n',
                              program+' tick-10sec { exit(0); }']
                    trace=subprocess.Popen(argv,stdout=stdout,stderr=stderr)
                    time.sleep(.5)
                samples=[]
                try:
                    for _ in range(10):
                        r=m.js(code);samples.append(r)
                        if r['result'].get('isError'):
                            (args.output/'failed-workload.json').write_text(json.dumps(r,indent=2))
                            raise RuntimeError('workload failed; do not use its timing or trace')
                    coverage = trace.poll() is None if trace else None
                    code_result=trace.wait(timeout=15) if trace else None
                finally:
                    if trace and trace.poll() is None:
                        # All commands are bounded internally. Wait out their finite recording.
                        trace.wait(timeout=15)
                    if stdout:stdout.close()
                    if stderr:stderr.close()
                diagnostics=(args.output/f'{workload}-{mode}.stderr').read_text() if mode!='untraced' else ''
                valid=(code_result==0 and 'dtrace: error' not in diagnostics and 'failed' not in diagnostics.lower()) if trace else None
                records.append({'workload':workload,'mode':mode,'traceExit':code_result,'traceAliveAtWorkEnd':coverage,'traceValid':valid,
                                'samples':samples,'medianSeconds':statistics.median(x['seconds'] for x in samples)})
                (args.output/'records.json').write_text(json.dumps(records,indent=2))
                print(json.dumps({k:v for k,v in records[-1].items() if k!='samples'}),flush=True)
    finally:m.close()


if __name__=='__main__':main()
