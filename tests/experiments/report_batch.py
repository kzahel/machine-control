#!/usr/bin/env python3
"""Summarize a private comparison batch without transcripts or identifiers."""
import argparse
import collections
import json
from pathlib import Path
import statistics
from measurements import token_metrics
from review_trial import load_receipt, reevaluate, digest


def distribution(values):
    if not values:
        return None
    return {"n": len(values), "median": statistics.median(values),
            "min": min(values), "max": max(values)}


def token_distributions(rows):
    metrics = [token_metrics(r.get('tokenUsage'), r.get('provider', 'codex')) for r in rows]
    keys = sorted({key for item in metrics for key in item})
    return {key: distribution([item[key] for item in metrics if item.get(key) is not None])
            for key in keys}


def resource_accounting(rows, complete):
    resources = {'success':[], 'failed':[], 'invalid':[]}
    for row in rows:
        valid = row.get('validTrial') is True and not row.get('error')
        kind = 'success' if valid and row.get('passed') is True else 'failed' if valid else 'invalid'
        resources[kind].append({'tokens':token_metrics(row.get('tokenUsage'),row.get('provider','codex')).get('totalTokens'),
                                'seconds':row.get('agentSeconds'),'toolCalls':row.get('toolCalls')})
    totals = {}
    for kind, entries in resources.items():
        totals[kind] = {'trials':len(entries)}
        for metric in ('tokens','seconds','toolCalls'):
            values = [x[metric] for x in entries if x[metric] is not None]
            totals[kind][metric] = {'sum':sum(values),'measuredTrials':len(values)}
    successes = len(resources['success'])
    per_success = {}
    for metric in ('tokens','seconds','toolCalls'):
        coverage = sum(totals[k][metric]['measuredTrials'] for k in totals)
        total = sum(totals[k][metric]['sum'] for k in totals)
        per_success[metric] = total/successes if complete and successes and coverage==len(rows) else None
    return {'byOutcome':totals,'allAttemptResourcesPerSuccess':per_success,
            'limits':['Per-success values require a complete batch, known usage for every recorded attempt and at least one success.']}


def summarize(manifest, records):
    expected = {(x['task'], x['route'], x['repetition']) for x in manifest['plan']}
    observed = collections.Counter((x.get('task'), x.get('route'), x.get('repetition')) for x in records)
    duplicates = sum(n-1 for n in observed.values() if n>1)
    qualified=collections.Counter((x.get('task'),x.get('route'),x.get('repetition'))
        for x in records if x.get('validTrial') is True and not x.get('error'))
    duplicate_qualified=sum(n-1 for n in qualified.values() if n>1)
    groups = collections.defaultdict(list)
    for row in records:
        groups[(row.get('task'),row.get('route'))].append(row)
    result = {"schema":"route-comparison-report/v1", "plannedTrials":len(expected),
              "recordedTrials":len(records), "missingTrials":len(expected-observed.keys()),
              "unexpectedTrials":len(observed.keys()-expected), "duplicateTrials":duplicates,
              "duplicateQualifiedTrials":duplicate_qualified,
              "unqualifiedCells":len(expected-qualified.keys()),
              "complete":qualified.keys()==expected and not duplicate_qualified and observed.keys()<=expected,
              "groups":[]}
    for (task,route), rows in sorted(groups.items()):
        valid = [r for r in rows if r.get('validTrial') is True and not r.get('error')]
        passed = [r for r in valid if r.get('passed') is True]
        reviewed_passed=[r for r in passed if (r.get('routeReview') or {}).get('routeAdherence')=='conforming']
        result['groups'].append({
            "task":task,"route":route,"recorded":len(rows),"valid":len(valid),"passed":len(passed),
            "routeReviews":dict(collections.Counter(
                (r.get('routeReview') or {}).get('routeAdherence','unreviewed') for r in rows)),
            "routeVerifiedPasses":len(reviewed_passed),
            "routeVerifiedAgentSeconds":distribution([r['agentSeconds'] for r in reviewed_passed
                                                       if r.get('agentSeconds') is not None]),
            "routeVerifiedToolCalls":distribution([r['toolCalls'] for r in reviewed_passed
                                                    if r.get('toolCalls') is not None]),
            "routeVerifiedTokenUsage":token_distributions(reviewed_passed),
            "preUIDiscoveryCalls":distribution([len(r['routeReview']['preUIDiscoveryCalls']) for r in rows
                if r.get('routeReview')]),
            "tokensReportedBeforeFirstUICall":distribution([
                r['routeReview']['usageReportedBeforeFirstUICall']['totalTokens'] for r in rows
                if (r.get('routeReview') or {}).get('usageReportedBeforeFirstUICall',{}).get('totalTokens') is not None]),
            "timedOut":sum(r.get('timedOut') is True for r in rows),
            "providerErrors":dict(collections.Counter(str(error) for r in rows for error in r.get('providerErrors',[]))),
            "betweenTurnSeconds":distribution([r['betweenTurnSeconds'] for r in rows if r.get('betweenTurnSeconds') is not None]),
            "infrastructureFailures":sum(bool(r.get('error')) for r in rows),
            "cleanupFailures":sum(bool(r.get('releaseError')) or not r.get('released') for r in rows),
            "successfulAgentSeconds":distribution([r['agentSeconds'] for r in passed if r.get('agentSeconds') is not None]),
            "successfulToolCalls":distribution([r['toolCalls'] for r in passed if r.get('toolCalls') is not None]),
            "successfulOutputBytes":distribution([r['toolOutputBytes'] for r in passed if r.get('toolOutputBytes') is not None]),
            "successfulInputTokens":distribution([r['tokenUsage']['input_tokens'] for r in passed
                                                   if r.get('tokenUsage') and 'input_tokens' in r['tokenUsage']]),
            "successfulTokenUsage":token_distributions(passed),
            "allRecordedTokenUsage":token_distributions(rows),
            "trialsWithReportedUsage":sum(bool(r.get('tokenUsage')) for r in rows),
            "resourceAccounting":resource_accounting(rows,result['complete']),
            "models":sorted({c['model'] for r in rows for c in r.get('modelContexts',[]) if 'model' in c}),
        })
    result['limits'] = ["Pilot distributions, not population success-rate estimates.",
                        "Latency summaries include only valid successful trials; failures are separate.",
                        "Tool use restrictions are prompt-based; route adherence needs transcript review.",
                        "Successful metrics mean oracle/profile success; use routeVerified metrics for reviewed route comparisons.",
                        "Route reviews and discovery indices are explicit judgments bound to transcript hashes; pre-UI usage is a reported checkpoint, not causal attribution.",
                        "The JS prototype omits claims/controller audit; its timing is not enforcement parity.",
                        "Input tokens include cache reads/writes; output includes reported reasoning. Do not sum breakdowns again.",
                        "Token distributions include coverage n; absent usage stays unknown. All-recorded usage includes failed/invalid attempts.",
                        "Tokenizers differ across models; token counts are not a price calculation."]
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    parser.add_argument('--reanalyze',action='store_true',help='Recompute from retained transcripts with the current parser; keep original receipts and oracle invalidations')
    args=parser.parse_args()
    manifest=json.loads((args.run/'manifest.json').read_text())
    carried=manifest.get('carriedAttempts',[])
    directories=[Path(x['directory']) for x in carried]+[p.parent for p in sorted(args.run.glob('*/*/trial.json'))]
    records=[x['record'] for x in carried]+[load_receipt(p) for p in directories[len(carried):]]
    reanalysis=[]
    if args.reanalyze:
        for attempt in carried:
            if any(digest(Path(attempt['directory'])/name)!=value for name,value in attempt['hashes'].items()):
                raise ValueError('Carried evidence changed after the manifest was frozen')
        records=[]
        for directory in directories:
            loaded=load_receipt(directory)
            evaluation_path=directory/'evaluation.json'
            invalidated=json.loads(evaluation_path.read_text()).get('oracleInvalidated',False) if evaluation_path.is_file() else False
            value=reevaluate(directory,reason='Explicit report-time parser reanalysis',invalidate_oracle=invalidated)
            records.append({**value['record'],'routeReview':loaded.get('routeReview')})
            reanalysis.append({k:v for k,v in value.items() if k not in ('record','reason')})
    result=summarize(manifest,records)
    result['reanalysis']=reanalysis
    print(json.dumps(result,indent=2))
