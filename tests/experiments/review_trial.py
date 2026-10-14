#!/usr/bin/env python3
"""Inspect private tool calls and record explicit route/discovery annotations.

Annotations are reviewer judgments, not an automated correctness oracle. Never
infer UI operations from substring matching or promote these raw calls to Git.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from measurements import claude_transcript_metrics, transcript_metrics, token_metrics


def calls_from(text, provider):
    calls, seen = [], set()
    for line_number, line in enumerate(text.splitlines()):
        row = json.loads(line)
        if provider == 'codex':
            payload = row.get('payload', {})
            blocks = [payload] if row.get('type') == 'response_item' and payload.get('type') in (
                'function_call', 'custom_tool_call') else []
        else:
            blocks = row.get('message', {}).get('content', []) if row.get('type') == 'assistant' else []
            blocks = [b for b in blocks if isinstance(b, dict) and b.get('type') == 'tool_use'] if isinstance(blocks, list) else []
        for block in blocks:
            identifier = block.get('call_id', block.get('id'))
            if not identifier or identifier in seen:
                continue
            seen.add(identifier)
            arguments = block.get('arguments', block.get('input', ''))
            calls.append({'index': len(calls) + 1, 'line': line_number,
                          'at': row.get('timestamp'), 'name': block.get('name'),
                          'arguments': arguments})
    return calls


def annotation(text, provider, *, adherence, first_ui, discovery, notes):
    calls = calls_from(text, provider)
    if adherence not in ('conforming', 'violated', 'uncertain'):
        raise ValueError('Review route adherence explicitly')
    if first_ui is not None and not 1 <= first_ui <= len(calls):
        raise ValueError('First UI call is out of range')
    if len(set(discovery)) != len(discovery) or any(i < 1 or i > len(calls) for i in discovery):
        raise ValueError('Discovery call indices must be distinct and in range')
    if first_ui is not None and any(i >= first_ui for i in discovery):
        raise ValueError('Pre-UI discovery calls must precede the first UI call')
    parser = transcript_metrics if provider == 'codex' else claude_transcript_metrics
    prefix = '\n'.join(text.splitlines()[:calls[first_ui - 1]['line']]) if first_ui else ''
    usage = parser(prefix).get('tokenUsage') if first_ui else None
    return {'schema': 'route-comparison-review/v1',
            'transcriptSha256': hashlib.sha256(text.encode()).hexdigest(),
            'routeAdherence': adherence, 'firstUICall': first_ui,
            'preUIDiscoveryCalls': sorted(discovery), 'notes': notes,
            'usageReportedBeforeFirstUICall': token_metrics(usage, provider),
            'limits': [
                'First UI call means the first target UI observation or action; doctor, help and claims are setup.',
                'One model tool call may mix documentation, observation and actions; indices do not count native operations.',
                'Usage is a reported checkpoint before that call, not exact causal token attribution to discovery.',
                'Route adherence and discovery classification are explicit reviewer judgments; the effect oracle is separate.']}


def load_review(directory):
    path = directory / 'review.json'
    if not path.is_file():
        return None
    review = json.loads(path.read_text())
    digest = hashlib.sha256((directory / 'transcript.jsonl').read_text().encode()).hexdigest()
    if review.get('schema') != 'route-comparison-review/v1' or review.get('transcriptSha256') != digest:
        raise ValueError('Review is not bound to this transcript')
    if review.get('routeAdherence') not in ('conforming', 'violated', 'uncertain'):
        raise ValueError('Review has no valid route judgment')
    return review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trial', type=Path)
    parser.add_argument('--record', action='store_true', help='Write a private review.json after inspecting the trace')
    parser.add_argument('--adherence', choices=('conforming', 'violated', 'uncertain'))
    parser.add_argument('--first-ui-call', type=int)
    parser.add_argument('--discovery-calls', default='', help='Comma-separated pre-UI call numbers')
    parser.add_argument('--notes', default='')
    options = parser.parse_args()
    receipt = json.loads((options.trial / 'trial.json').read_text())
    text = (options.trial / 'transcript.jsonl').read_text()
    if not options.record:
        print(json.dumps(calls_from(text, receipt['provider']), indent=2))
        return
    review = annotation(text, receipt['provider'], adherence=options.adherence,
        first_ui=options.first_ui_call,
        discovery=[int(n) for n in options.discovery_calls.split(',') if n], notes=options.notes)
    path = options.trial / 'review.json'
    # Never silently overwrite a prior judgment; keep an explicit review history.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(json.dumps(review, indent=2) + '\n')
    print(json.dumps({'reviewed': True, 'routeAdherence': review['routeAdherence']}))


if __name__ == '__main__':
    main()
