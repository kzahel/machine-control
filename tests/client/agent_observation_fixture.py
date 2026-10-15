"""Deterministic observation corpus; qualified IDs are fixture oracles only.

No native control, clocks, model calls or tokenizer estimates. The native-like
arm rotates references just as current macOS snapshots do. The qualified arm
models the benefit conditional on a provider proving replacement-safe identity;
it is not evidence that the macOS provider has that property.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "client"))
from agent_session import App, Session


class ObservationFixture:
    def __init__(self, count: int, *, qualified_identity: bool) -> None:
        self.qualified_identity = qualified_identity
        self.sequence = 0
        self.process = 1
        self.window = 1
        self.items = [dict(incarnation=f"object-{i}", value="") for i in range(count)]
        self.requests: list[dict[str, Any]] = []

    def call(self, request: dict[str, Any]) -> dict[str, Any]:
        assert request['operation'] == 'snapshot', 'Benchmark must never dispatch actions'
        self.requests.append(request)
        self.sequence += 1
        elements = []
        for item in self.items:
            element = dict(reference=f"runtime:desktop:s{self.sequence}:{item['incarnation']}",
                           role='AXButton', label='Row', value=item['value'], depth=0)
            if self.qualified_identity:
                element['elementIdentity'] = item['incarnation']
            elements.append(element)
        data: dict[str, Any] = dict(elements=elements, truncated=False)
        if self.qualified_identity:
            data['elementIdentityGeneration'] = f"process-{self.process}/window-{self.window}"
        else:
            data['elementIdentityLifetime'] = 'snapshot_reference'
        return dict(accepted=True, generation='runtime', actualRoute='offline-fixture',
                    coordinateSpace='global_display_points_top_left', data=data)

    def image(self, result: dict[str, Any]) -> bytes:
        raise AssertionError('Benchmark must never capture')

    def close(self) -> None:
        pass


def serialized_bytes(value: object) -> int:
    """UTF-8 JSON bytes, including JSON-string escaping for rendered text."""
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


def measure(count: int, *, qualified_identity: bool, repeats: int = 20) -> dict[str, Any]:
    peer = ObservationFixture(count, qualified_identity=qualified_identity)
    session = Session(peer, target='offline-fixture', emit=lambda _: None)
    app = App(session, 'fixture-app', 'Fixture')
    result: dict[str, Any] = dict(elements=count, repeats=repeats,
        identity='qualified_fixture_only' if qualified_identity else 'snapshot_references', cases={})

    def observe(case: str) -> None:
        rendered = app.tree()
        observation = deepcopy(app.last_observation)
        assert observation is not None
        # Render a full tree from the exact same observation and number map;
        # taking another provider sample would confound the byte comparison.
        full = app._render_tree(observation, query=None, full=True, settle=False, stable=True)
        result['cases'][case] = dict(
            observation_json_bytes=serialized_bytes(observation),
            rendered_json_bytes=serialized_bytes(rendered),
            full_rendered_json_bytes=serialized_bytes(full),
            shown_elements=len(app.elements),
            truncation_reported='Truncated;' in rendered,
            no_change=rendered.startswith('Fixture:\nNo change.'))

    observe('initial')
    samples = []
    for _ in range(repeats):
        observe('unchanged')
        samples.append(result['cases'].pop('unchanged'))
    result['cases']['unchanged'] = dict(
        rendered_json_bytes=sum(s['rendered_json_bytes'] for s in samples),
        full_rendered_json_bytes=sum(s['full_rendered_json_bytes'] for s in samples),
        observation_json_bytes=sum(s['observation_json_bytes'] for s in samples),
        all_no_change=all(s['no_change'] for s in samples),
        shown_elements=min(s['shown_elements'] for s in samples),
        truncation_reported=any(s['truncation_reported'] for s in samples))
    peer.items[count // 2]['value'] = 'changed'
    observe('single_value')
    peer.items.insert(1, dict(incarnation='inserted-object', value=''))
    observe('insertion')
    peer.items.reverse()
    observe('reorder')
    peer.items[count // 2] = dict(incarnation='replacement-object', value='')
    observe('replacement')
    del peer.items[count // 2]
    observe('removal')
    peer.process += 1
    observe('process_recreation')
    peer.window += 1
    observe('window_recreation')
    session.close()
    return result


def benchmark() -> dict[str, Any]:
    return dict(schema='machine-control/offline-observation-bytes/v1',
                unit='UTF-8 bytes of compact JSON; rendered text is a JSON string',
                limits='Synthetic fixture only; no native latency, tokenizer or task-success evidence',
                measurements=[measure(n, qualified_identity=qualified)
                              for n in (10, 100, 400) for qualified in (False, True)])


if __name__ == '__main__':
    print(json.dumps(benchmark(), indent=2, sort_keys=True))
