#!/usr/bin/env python3
"""Summarize a private comparison batch without transcripts or identifiers."""
import argparse
import collections
import json
from pathlib import Path
import statistics


def distribution(values):
    if not values:
        return None
    return {"n": len(values), "median": statistics.median(values),
            "min": min(values), "max": max(values)}


def summarize(manifest, records):
    expected = {(x['task'], x['route'], x['repetition']) for x in manifest['plan']}
    observed = collections.Counter((x.get('task'), x.get('route'), x.get('repetition')) for x in records)
    duplicates = sum(n-1 for n in observed.values() if n>1)
    groups = collections.defaultdict(list)
    for row in records:
        groups[(row.get('task'),row.get('route'))].append(row)
    result = {"schema":"route-comparison-report/v1", "plannedTrials":len(expected),
              "recordedTrials":len(records), "missingTrials":len(expected-observed.keys()),
              "unexpectedTrials":len(observed.keys()-expected), "duplicateTrials":duplicates,
              "complete":observed.keys()==expected and not duplicates, "groups":[]}
    for (task,route), rows in sorted(groups.items()):
        valid = [r for r in rows if r.get('validTrial') is True and not r.get('error')]
        passed = [r for r in valid if r.get('passed') is True]
        result['groups'].append({
            "task":task,"route":route,"recorded":len(rows),"valid":len(valid),"passed":len(passed),
            "timedOut":sum(r.get('timedOut') is True for r in rows),
            "infrastructureFailures":sum(bool(r.get('error')) for r in rows),
            "cleanupFailures":sum(bool(r.get('releaseError')) or not r.get('released') for r in rows),
            "successfulAgentSeconds":distribution([r['agentSeconds'] for r in passed if r.get('agentSeconds') is not None]),
            "successfulToolCalls":distribution([r['toolCalls'] for r in passed if r.get('toolCalls') is not None]),
            "successfulOutputBytes":distribution([r['toolOutputBytes'] for r in passed if r.get('toolOutputBytes') is not None]),
            "successfulInputTokens":distribution([r['tokenUsage']['input_tokens'] for r in passed
                                                   if r.get('tokenUsage') and 'input_tokens' in r['tokenUsage']]),
            "models":sorted({c['model'] for r in rows for c in r.get('modelContexts',[]) if 'model' in c}),
        })
    result['limits'] = ["Pilot distributions, not population success-rate estimates.",
                        "Latency summaries include only valid successful trials; failures are separate.",
                        "Tool use restrictions are prompt-based; route adherence needs transcript review.",
                        "The JS prototype omits claims/controller audit; its timing is not enforcement parity.",
                        "Input tokens include cached input; this is not a price calculation."]
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    args=parser.parse_args()
    manifest=json.loads((args.run/'manifest.json').read_text())
    records=[json.loads(p.read_text()) for p in sorted(args.run.glob('*/*/trial.json'))]
    print(json.dumps(summarize(manifest,records),indent=2))
