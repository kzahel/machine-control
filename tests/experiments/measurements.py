"""Offline measurements of retained Codex transcripts; no provider inference."""
from __future__ import annotations

from datetime import datetime
import json


def token_metrics(usage, provider="codex"):
    """Normalize reported totals without counting cache/reasoning twice.

    Claude callers must supply deduplicated, session-summed API usage first.
    This does not implement Claude transcript collection or infer missing usage.
    Non-cached input includes cache writes; cache writes remain a breakdown.
    """
    if not isinstance(usage, dict):
        return {}

    def count(key):
        value = usage.get(key)
        return value if type(value) is int and value >= 0 else None

    def add(*values):
        return sum(values) if all(v is not None for v in values) else None

    output = count("output_tokens")
    reasoning = count("reasoning_output_tokens")
    if provider == "codex":
        total_input = count("input_tokens")
        cached = count("cached_input_tokens")
        writes = count("cache_write_input_tokens")
        noncached = (total_input - cached if total_input is not None and
                     cached is not None and cached <= total_input else None)
    elif provider == "claude":
        cached = count("cache_read_input_tokens")
        writes = count("cache_creation_input_tokens")
        noncached = add(count("input_tokens"), writes)
        total_input = add(noncached, cached)
    else:
        return {}
    return {"inputTokens": total_input, "cachedInputTokens": cached,
            "nonCachedInputTokens": noncached, "cacheWriteInputTokens": writes,
            "outputTokens": output, "reasoningOutputTokens": reasoning,
            "totalTokens": add(total_input, output)}


def timestamp(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (AttributeError, TypeError, ValueError):
        return None


def transcript_metrics(text):
    calls, outputs, contexts, starts, ends, usage = {}, {}, [], {}, {}, None
    turn_durations = {}
    turn_errors = {}
    malformed = 0
    images = 0
    for line in text.splitlines():
        try:
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("not an object")
        except (ValueError, TypeError):
            malformed += 1
            continue
        payload = item.get("payload") or {}
        if not isinstance(payload, dict):
            malformed += 1
            continue
        kind = payload.get("type")
        if item.get("type") == "turn_context":
            contexts.append({key: payload[key] for key in
                             ("model", "effort", "reasoning_effort") if key in payload})
        if item.get("type") == "event_msg":
            turn = payload.get("turn_id")
            if kind == "task_started" and turn:
                starts[turn] = timestamp(item.get("timestamp"))
            elif kind == "task_complete" and turn:
                ends[turn] = timestamp(item.get("timestamp"))
                error=payload.get('error')
                turn_errors[turn]=(error.get('codex_error_info','unknown_provider_error')
                                   if isinstance(error,dict) else 'unknown_provider_error' if error else None)
                duration = payload.get("duration_ms")
                if isinstance(duration, (int, float)) and duration >= 0:
                    turn_durations[turn] = duration / 1000
            elif kind == "token_count":
                total = (payload.get("info") or {}).get("total_token_usage")
                if isinstance(total, dict):
                    # Cumulative counts: retain the latest, never sum events.
                    usage = {k: v for k, v in total.items()
                             if k.endswith("tokens") and isinstance(v, int)}
        if item.get("type") != "response_item":
            continue
        call_id = payload.get("call_id")
        if kind in ("function_call", "custom_tool_call") and call_id:
            calls[call_id] = {"name": payload.get("name"),
                              "at": timestamp(item.get("timestamp"))}
        elif kind in ("function_call_output", "custom_tool_call_output") and call_id:
            value = payload.get("output", "")
            encoded = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            outputs[call_id] = {"at": timestamp(item.get("timestamp")),
                                "bytes": len(encoded.encode("utf-8"))}
        elif kind == "message":
            images += sum(isinstance(x, dict) and x.get("type") == "input_image"
                          for x in payload.get("content", []) if isinstance(payload.get("content"), list))
    durations = []
    by_name = {}
    for call_id, call in calls.items():
        by_name[call["name"] or "unknown"] = by_name.get(call["name"] or "unknown", 0) + 1
        end = outputs.get(call_id, {}).get("at")
        if call["at"] is not None and end is not None and end >= call["at"]:
            durations.append(end - call["at"])
    complete = bool(starts) and starts.keys() == ends.keys() and all(
        starts[k] is not None and ends[k] is not None and ends[k] >= starts[k] for k in starts)
    ordered=sorted(starts,key=lambda k:starts[k]) if complete else []
    last=max(ends,key=lambda k:ends[k] if ends[k] is not None else float('-inf')) if ends else None
    return {
        "toolCalls": len(calls), "toolCallsByName": by_name,
        "toolOutputBytes": sum(x["bytes"] for x in outputs.values()),
        "toolRoundTripSeconds": durations,
        "toolRoundTripCoverage": {"measured": len(durations), "calls": len(calls)},
        "agentSeconds":max(ends.values())-min(starts.values()) if complete else None,
        "activeTurnSeconds":sum(turn_durations.get(k,ends[k]-starts[k]) for k in starts) if complete else None,
        "betweenTurnSeconds":sum(max(0,starts[b]-ends[a]) for a,b in zip(ordered,ordered[1:])) if complete else None,
        "timingSource": "transcript_first_start_to_last_complete" if complete else "unavailable",
        "providerErrors":[value for value in turn_errors.values() if value is not None],
        "terminalProviderError":turn_errors.get(last) if last else None,
        "transcriptComplete": complete, "malformedTranscriptLines": malformed,
        "agentTurns": len(starts), "modelContexts": contexts,
        "tokenUsage": usage, "transcriptImageItems": images,
        "nativeOperations": None,
        "measurementLimits": [
            "Elapsed agent time includes waits between recovered turns; active turn durations are separate.",
            "Tool timestamps include transport and host overhead; intervals may overlap.",
            "Output bytes are serialized transcript payloads, not tokenizer or wire counts.",
            "Image items count only explicit transcript image items, not screenshots.",
            "Native operation counts require provider instrumentation; no string guessing.",
        ],
    }


def claude_transcript_metrics(text):
    """Measure native Claude JSONL, deduplicating streamed API-message usage."""
    calls, outputs, api_messages, contexts = {}, {}, {}, []
    observed_messages = set()
    unidentified_messages = 0
    starts, terminal_times = [], []
    malformed = 0
    sidechain = False
    for line in text.splitlines():
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError('not an object')
        except (TypeError, ValueError):
            malformed += 1
            continue
        if row.get('isSidechain'):
            sidechain = True
            continue
        at = timestamp(row.get('timestamp'))
        message = row.get('message')
        if not isinstance(message, dict):
            continue
        blocks = message.get('content', [])
        blocks = blocks if isinstance(blocks, list) else []
        if row.get('type') == 'user':
            results = [b for b in blocks if isinstance(b, dict) and b.get('type') == 'tool_result']
            if results:
                for block in results:
                    key = block.get('tool_use_id')
                    content = block.get('content', '')
                    encoded = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
                    if key:
                        outputs[key] = {'at': at, 'bytes': len(encoded.encode('utf-8'))}
            elif at is not None and row.get('isMeta') is not True:
                starts.append(at)
        elif row.get('type') == 'assistant':
            model = message.get('model')
            usage = message.get('usage')
            if model and model != '<synthetic>':
                if message.get('id'):
                    observed_messages.add(message['id'])
                else:
                    unidentified_messages += 1
            if model and model != '<synthetic>':
                context = {'model': model, 'effort': row.get('perTurnEffort', row.get('effort'))}
                if isinstance(usage, dict):
                    context.update({k: usage[k] for k in ('service_tier', 'speed') if k in usage})
                if context not in contexts:
                    contexts.append(context)
            key = message.get('id')
            if key and isinstance(usage, dict):
                previous = api_messages.setdefault(key, {})
                for name in ('input_tokens', 'cache_read_input_tokens',
                             'cache_creation_input_tokens', 'output_tokens'):
                    value = usage.get(name)
                    if type(value) is int and value >= 0:
                        previous[name] = max(value, previous.get(name, 0))
                thinking = (usage.get('output_tokens_details') or {}).get('thinking_tokens')
                if type(thinking) is int and thinking >= 0:
                    previous['reasoning_output_tokens'] = max(thinking, previous.get('reasoning_output_tokens', 0))
            for block in blocks:
                if isinstance(block, dict) and block.get('type') == 'tool_use' and block.get('id'):
                    calls.setdefault(block['id'], {'name': block.get('name', 'unknown'), 'at': at})
            if message.get('stop_reason') == 'end_turn' and at is not None:
                terminal_times.append(at)
    complete = (len(starts) == 1 and bool(terminal_times) and
                terminal_times[-1] >= starts[0] and not sidechain)
    usage = None
    usage_complete = bool(observed_messages) and observed_messages == api_messages.keys() and not unidentified_messages
    if api_messages and usage_complete:
        common = set.intersection(*(set(v) for v in api_messages.values()))
        usage = {k: sum(v[k] for v in api_messages.values()) for k in common}
    by_name, durations = {}, []
    for key, call in calls.items():
        by_name[call['name']] = by_name.get(call['name'], 0) + 1
        end = outputs.get(key, {}).get('at')
        if call['at'] is not None and end is not None and end >= call['at']:
            durations.append(end-call['at'])
    return {'toolCalls':len(calls), 'toolCallsByName':by_name,
            'toolOutputBytes':sum(v['bytes'] for v in outputs.values()),
            'toolRoundTripSeconds':durations,
            'toolRoundTripCoverage':{'measured':len(durations),'calls':len(calls)},
            'agentSeconds':terminal_times[-1]-starts[0] if complete else None,
            'timingSource':'claude_user_to_end_turn' if complete else 'unavailable',
            'transcriptComplete':complete, 'malformedTranscriptLines':malformed,
            'agentTurns':len(starts), 'modelContexts':contexts, 'tokenUsage':usage,
            'apiMessagesWithUsage':len(api_messages), 'apiMessagesObserved':len(observed_messages),
            'unidentifiedAssistantRecords':unidentified_messages, 'tokenUsageComplete':usage_complete,
            'sidechainObserved':sidechain,
            'nativeOperations':None,
            'measurementLimits':['Claude time spans persisted user message to final end_turn; YA overhead is separate.',
                                 'Usage takes per-message maxima across streamed blocks, then sums distinct API messages.',
                                 'Missing usage classes remain unknown; sidechains invalidate this single-agent trial.']}
