#!/usr/bin/env python3
"""Minimize fixture results to counts and timing; retain raw evidence privately."""
import argparse
import collections
import json
from pathlib import Path
import statistics


def counter(state,key):return state.get('counters',{}).get(key,0)


def summarize(records):
    groups=collections.defaultdict(list)
    for record in records:
        groups[(record['name'],record.get('size'))].append(record)
    output=[]
    for (name,size),rows in groups.items():
        durations=[r['seconds'] for r in rows if 'seconds' in r]
        refusals=sum(bool(r.get('error')) or r.get('result',{}).get('isError') is True or
                     r.get('result',{}).get('accepted') is False for r in rows)
        summary={'name':name,'size':size,'samples':len(rows),'refusalsOrErrors':refusals}
        if durations:
            summary.update(medianMs=round(statistics.median(durations)*1000,2),
                           minMs=round(min(durations)*1000,2),maxMs=round(max(durations)*1000,2),
                           medianResultBytes=statistics.median(len(json.dumps(r.get('result'),ensure_ascii=False).encode()) for r in rows))
        if name.startswith('background-'):
            effects=[]; disturbance=[]; sentinel_ready=[]
            for r in rows:
                b,a=r['before']['target'],r['after']['target']
                sb,sa=r['before']['sentinel'],r['after']['sentinel']
                sentinel_ready.append(sb['keyWindow'] and sb['frontPid']==sb['pid'])
                disturbance.append(sb['cursor']!=sa['cursor'] or sb['frontPid']!=sa['frontPid'] or
                                   not sa['keyWindow'] or sb['text']!=sa['text'] or
                                   counter(sa,'cursorMoved')!=counter(sb,'cursorMoved') or
                                   counter(sa,'foregroundChanged')!=counter(sb,'foregroundChanged') or
                                   counter(sa,'event-10')!=counter(sb,'event-10'))
                if name in ('background-button','background-menu-item'):effects.append(a['revision']==b['revision']+1)
                elif name=='background-pointer':effects.append(counter(a,'pointerDown')==counter(b,'pointerDown')+1 and counter(a,'pointerUp')==counter(b,'pointerUp')+1)
                elif name=='background-type':effects.append(a['text']=='probe-text')
                elif name=='background-sheet-open':effects.append(a['sheetVisible'])
                elif name=='background-sheet-close':effects.append(not a['sheetVisible'] and counter(a,'sheetClosed')==counter(b,'sheetClosed')+1)
            summary.update(sentinelReady=sum(sentinel_ready),disturbances=sum(disturbance),
                           effectPasses=sum(effects) if effects else None,
                           effectChecks=len(effects))
        if name.startswith('settle-'):
            revisions=[]
            for r in rows:
                result=r.get('result',{})
                if 'content' in result:
                    import re
                    matches=re.findall(r'Revision (\d+)', '\n'.join(c.get('text','') for c in result['content']))
                    revisions.append(int(matches[-1]) if matches else None)
                else:
                    labels=[e.get('label','') for e in result.get('data',{}).get('elements',[])]
                    values=[int(v.split()[1]) for v in labels if v.startswith('Revision ')]
                    revisions.append(values[0] if values else None)
            summary['returnedRevisions']=revisions
        output.append(summary)
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('records',type=Path)
    args=parser.parse_args();print(json.dumps(summarize(json.loads(args.records.read_text())),indent=2))
