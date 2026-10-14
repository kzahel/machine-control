"""Offline measurements of retained Codex transcripts; no provider inference."""
from __future__ import annotations

from datetime import datetime
import json


def timestamp(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (AttributeError, TypeError, ValueError):
        return None


def transcript_metrics(text):
    calls, outputs, contexts, starts, ends, usage = {}, {}, [], {}, {}, None
    turn_durations = {}
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
    return {
        "toolCalls": len(calls), "toolCallsByName": by_name,
        "toolOutputBytes": sum(x["bytes"] for x in outputs.values()),
        "toolRoundTripSeconds": durations,
        "toolRoundTripCoverage": {"measured": len(durations), "calls": len(calls)},
        "agentSeconds": sum(turn_durations.get(k, ends[k] - starts[k]) for k in starts) if complete else None,
        "timingSource": "transcript_task_events" if complete else "unavailable",
        "transcriptComplete": complete, "malformedTranscriptLines": malformed,
        "agentTurns": len(starts), "modelContexts": contexts,
        "tokenUsage": usage, "transcriptImageItems": images,
        "nativeOperations": None,
        "measurementLimits": [
            "Tool timestamps include transport and host overhead; intervals may overlap.",
            "Output bytes are serialized transcript payloads, not tokenizer or wire counts.",
            "Image items count only explicit transcript image items, not screenshots.",
            "Native operation counts require provider instrumentation; no string guessing.",
        ],
    }
