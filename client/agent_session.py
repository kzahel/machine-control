"""Typed agent-facing desktop handles over an admitted, audited transport.

This module owns presentation, never authority. Provider references are opaque:
matching labels, positions or tree paths cannot establish element identity.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import struct
import time
from typing import Any, Callable, Literal, Protocol

JSON = dict[str, Any]
Delivery = Literal["no", "yes", "unknown"]


class SessionError(Exception):
    def __init__(self, code: str, message: str, *, delivered: Delivery = "no",
                 retryable: bool = False, result: JSON | None = None) -> None:
        super().__init__(message)
        self.code, self.delivered, self.retryable = code, delivered, retryable
        self.result = result


class StaleElement(SessionError):
    pass


class ClaimLost(SessionError):
    pass


class Stopped(SessionError):
    pass


class ApprovalRequired(SessionError):
    pass


class Unsupported(SessionError):
    pass


class SessionTimeout(SessionError):
    pass


def refusal(value: JSON) -> SessionError:
    code = str(value.get("errorCode") or "operation_refused")
    delivered: Delivery = ("no" if value.get("delivery") == "refused" else
                           "yes" if value.get("delivery") == "confirmed" else "unknown")
    kind: type[SessionError] = SessionError
    if code in {"stale_reference", "invalid_reference", "stale_element"}:
        kind = StaleElement
    elif code.startswith("claim_") or code in {"owner_disconnected", "claim_not_held"}:
        kind = ClaimLost
    elif code in {"approval_required", "approval_denied", "approval_timeout"}:
        kind = ApprovalRequired
    elif code in {"control_interrupted", "control_session_closed", "control_generation_changed"}:
        kind = Stopped
    elif code.startswith("unsupported_"):
        kind = Unsupported
    elif "timeout" in code:
        kind = SessionTimeout
        delivered = "unknown"
    message = str(value.get("message") or code)
    return kind(code, message + "; observe before any retry" if delivered != "no" else message,
                delivered=delivered, result=value)


class Transport(Protocol):
    def call(self, request: JSON) -> JSON: ...
    def image(self, result: JSON) -> bytes: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class Result:
    raw: JSON

    def __str__(self) -> str:
        v = self.raw
        return (f"{v.get('operation')}: route {v.get('actualRoute')}; "
                f"delivery {v.get('delivery')}; effect {v.get('effect')}; "
                f"uncertainty {v.get('uncertainty')}; interference {v.get('hostInterference')}")


def text(value: object, limit: int = 180) -> str:
    """Quote UI text so newlines/control characters cannot impersonate structure."""
    value = str(value)
    return json.dumps(value[:limit] + ("…" if len(value) > limit else ""), ensure_ascii=False)


class Session:
    def __init__(self, transport: Transport, *, target: str,
                 emit: Callable[[str], None] = print,
                 emit_image: Callable[[bytes], None] | None = None,
                 auto_observe: bool = True) -> None:
        self.transport, self.target = transport, target
        self.emit, self.emit_image = emit, emit_image
        self.auto_observe = auto_observe
        self.closed = False
        self.action_attempts = 0
        self.handles: list[App] = []

    def call(self, request: JSON) -> JSON:
        if self.closed:
            raise Stopped("session_closed", "Start a new session")
        if request.get("operation") not in {"applications", "windows", "snapshot", "capture", "status"}:
            self.action_attempts += 1
        value = self.transport.call(request)
        if value.get("accepted") is not True:
            raise refusal(value)
        return value

    def apps(self) -> list[JSON]:
        return list(self.call({"operation": "applications"}).get("data", {}).get("applications", []))

    def windows(self) -> list[JSON]:
        return list(self.call({"operation": "windows"}).get("data", {}).get("windows", []))

    def state(self) -> JSON:
        # Preserve failure information: never disguise a failed observation as empty.
        return {"target": self.target, "applications": self.apps(), "windows": self.windows()}

    def app(self, query: str, *, observe: bool = True) -> App:
        wanted = query.casefold()
        matches = [a for a in self.apps() if any(str(a.get(k, "")).casefold() == wanted
                   for k in ("name", "bundleId", "applicationId", "processId"))]
        if len(matches) != 1:
            raise SessionError("ambiguous_application" if matches else "application_not_found",
                               "Use an exact name/ID from mc.apps(), or mc.launch(application_id) if it is not running")
        match = matches[0]
        identity = str(match.get("bundleId") or match.get("applicationId") or match["processId"])
        app = App(self, identity, str(match.get("name") or identity))
        self.handles.append(app)
        if observe:
            self.emit(app.tree(full=True))
        return app

    def launch(self, application: str) -> App:
        self.call({"operation": "application.launch", "applicationId": application, "target": application})
        return self.app(application)

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            for app in self.handles:
                app.invalidate()
            self.transport.close()

    def __enter__(self) -> Session:
        return self

    def __exit__(self, *exception: object) -> None:
        self.close()


class App:
    def __init__(self, session: Session, target: str, name: str) -> None:
        self.session, self.target, self.name = session, target, name
        self.elements: dict[int, JSON] = {}
        self.identities: dict[tuple[str, str, str], int] = {}
        self.next_number = 1
        self.previous: dict[int, str] = {}
        self.coordinate_space = ""
        self.last_observation: JSON | None = None

    def invalidate(self) -> None:
        self.elements.clear()
        self.identities.clear()
        self.previous.clear()

    def _snapshot(self, query: str | None) -> JSON:
        request: JSON = {"operation": "snapshot", "target": self.target,
                         "projection": "full", "maxDepth": 30, "maxElements": 400}
        if query:
            request["query"] = query
        return self.session.call(request)

    @staticmethod
    def _appearance(value: JSON) -> str:
        # For settling only, never for identity or number reuse.
        data = value.get("data", {})
        return json.dumps([{k: v for k, v in e.items() if k not in ("reference", "elementIdentity")}
                           for e in data.get("elements", [])], sort_keys=True)

    def tree(self, query: str | None = None, *, full: bool = False,
             settle: bool = False) -> str:
        try:
            value = self._snapshot(query)
            stable = not settle
            deadline = time.monotonic() + 1.0
            while settle and time.monotonic() < deadline:
                time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
                newer = self._snapshot(query)
                stable = self._appearance(newer) == self._appearance(value)
                value = newer
                if stable:
                    break
        except BaseException:
            self.invalidate()
            raise
        self.last_observation = value
        data = value.get("data", {})
        generation = str(value.get("generation", ""))
        route = str(value.get("actualRoute", ""))
        identity_generation = data.get("elementIdentityGeneration")
        self.coordinate_space = str(value.get("coordinateSpace", ""))
        # A malformed new observation must not leave old numbers actionable.
        self.elements = {}
        lines: dict[int, str] = {}
        elements: dict[int, JSON] = {}
        identities: dict[tuple[str, str, str], int] = {}
        size = 0
        omitted = False
        skip_below: int | None = None
        for element in data.get("elements", []):
            depth = max(0, min(int(element.get("depth", 0)), 30))
            if skip_below is not None and depth > skip_below:
                continue
            skip_below = None
            reference = element.get("reference")
            if not isinstance(reference, str) or not reference:
                continue
            identity = element.get("elementIdentity")
            if isinstance(identity_generation, str) and isinstance(identity, str):
                key = (generation, route, identity_generation + ":" + identity)
            else:
                key = (generation, route, reference)
            if key in identities:
                raise SessionError("ambiguous_element_identity", "Provider returned duplicate element identities; re-observe")
            number = self.identities.get(key)
            if number is None:
                number = self.next_number
                self.next_number += 1
            role = str(element.get("role", "unknown")).removeprefix("AX").lower()
            label = element.get("label", element.get("name", ""))
            if not query and role == "menubar":
                skip_below = depth
                label = "menu bar; use tree(query=...) to inspect menus"
            body = "  " * depth + f"[{number}] {role}"
            if label:
                body += " " + text(label)
            v = element.get("value")
            if v not in (None, "", label):
                body += " = " + text(v)
            flags = [name for name in ("focused", "selected", "checked", "expanded") if element.get(name) is True]
            if element.get("enabled") is False:
                flags.append("disabled")
            if element.get("actions"):
                flags.append("actions=" + text(element["actions"], 100))
            if flags:
                body += " (" + ", ".join(flags) + ")"
            if size + len(body) > 12000:
                omitted = True
                break
            size += len(body) + 1
            lines[number], elements[number], identities[key] = body, element, number
        self.elements, self.identities = elements, identities
        removed = sorted(self.previous.keys() - lines.keys())
        changed = {n: line for n, line in lines.items() if self.previous.get(n) != line}
        if not full and lines == self.previous:
            body = "No change. Existing numbers remain valid."
        elif not full and self.previous and len(changed) + len(removed) < len(lines) / 2:
            body = "\n".join("+ " + line for line in changed.values())
            if removed:
                body += "\nRemoved (stale): " + ", ".join(map(str, removed))
        else:
            body = "\n".join(lines.values()) or "No matching elements."
        self.previous = lines
        notes = []
        if omitted or data.get("truncated"):
            notes.append("Truncated; narrow the query. Only shown numbers are actionable.")
        if settle:
            notes.append("Observed two equal samples; app completion is unverified." if stable else
                         "Observation deadline reached while UI changed; re-observe before acting.")
        return f"{self.name}:\n{body}" + ("\n" + "\n".join(notes) if notes else "")

    def _element(self, number: int) -> JSON:
        if type(number) is not int or number not in self.elements:
            raise StaleElement("stale_element", "Number is not in the latest observation; read tree()")
        return self.elements[number]

    def _act(self, request: JSON, observe: bool | None) -> Result:
        try:
            result = Result(self.session.call(request))
        except SessionError:
            self.invalidate()
            raise
        self.session.emit(str(result))
        if self.session.auto_observe if observe is None else observe:
            self.session.emit(self.tree(settle=True))
        return result

    def action(self, number: int, action: str, *, text: str | None = None,
               observe: bool | None = None) -> Result:
        request: JSON = {"operation": "action", "reference": self._element(number)["reference"], "action": action}
        if text is not None:
            request["text"] = text
        return self._act(request, observe)

    def press(self, number: int, *, observe: bool | None = None) -> Result:
        actions = self._element(number).get("actions", [])
        if any(str(a).casefold() in ("axpress", "press", "invoke") for a in actions):
            return self.action(number, "press", observe=observe)
        return self.click(number, observe=observe)

    def _centre(self, number: int) -> tuple[int, int]:
        element = self._element(number)
        b = element.get("bounds", {})
        if self.coordinate_space not in {"global_display_points_top_left", "screen_physical_pixels"}:
            raise Unsupported("unsupported_coordinate_space", "Use a semantic action for this provider")
        if any(type(b.get(k)) not in (int, float) or not math.isfinite(b[k]) for k in ("x", "y", "width", "height")) \
                or b["width"] <= 0 or b["height"] <= 0:
            raise Unsupported("unsupported_bounds", "Element has no finite clickable bounds")
        return round(b["x"] + b["width"] / 2), round(b["y"] + b["height"] / 2)

    def click(self, number: int, *, observe: bool | None = None) -> Result:
        x, y = self._centre(number)
        return self._act({"operation": "input.click", "target": self.target, "x": x, "y": y}, observe)

    def _scroll_at(self, x: int, y: int, direction: str, pixels: int,
                   observe: bool | None) -> Result:
        if direction not in {"up", "down"} or type(pixels) is not int or not 1 <= pixels <= 3000:
            raise Unsupported("unsupported_scroll", "Use up/down and 1–3000 pixels")
        moved = self._act({"operation": "input.move", "target": self.target, "x": x, "y": y}, False)
        if moved.raw.get("delivery") != "confirmed":
            raise SessionError("pointer_position_unknown", "Pointer delivery is uncertain; observe before scrolling",
                               delivered="unknown", result=moved.raw)
        return self._act({"operation": "input.scroll", "target": self.target,
                          "deltaX": 0, "deltaY": -pixels if direction == "down" else pixels}, observe)

    def scroll(self, number: int, direction: str = "down", *, pixels: int = 400,
               observe: bool | None = None) -> Result:
        x, y = self._centre(number)
        return self._scroll_at(x, y, direction, pixels, observe)

    def set_value(self, number: int, value: str, *, observe: bool | None = None) -> Result:
        return self.action(number, "set_value", text=value, observe=observe)

    def focus(self, number: int, *, observe: bool | None = None) -> Result:
        return self.action(number, "focus", observe=observe)

    def key(self, chord: str, *, observe: bool | None = None) -> Result:
        return self._act({"operation": "input.key", "target": self.target, "key": chord}, observe)

    def type(self, value: str, *, observe: bool | None = None) -> Result:
        return self._act({"operation": "input.text", "target": self.target, "text": value}, observe)

    def choose(self, path: str, *, confirm: bool = True, observe: bool | None = None) -> Result:
        return self._act({"operation": "dialog.choose", "target": self.target,
                          "path": path, "confirm": confirm}, observe)

    def screenshot(self, *, window_id: int | None = None) -> Capture:
        if self.session.emit_image is None:
            raise Unsupported("unsupported_image_sink", "Supply an image receiver to this library session")
        request: JSON = {"operation": "capture", "scope": "window", "target": self.target}
        if window_id is not None:
            request["windowId"] = window_id
        result = self.session.call(request)
        png = self.session.transport.image(result)
        if len(png) < 24 or png[:8] != b"\x89PNG\r\n\x1a\n" or png[12:16] != b"IHDR":
            raise SessionError("invalid_capture", "Capture has no PNG dimensions")
        width, height = struct.unpack(">II", png[16:24])
        if not width or not height:
            raise SessionError("invalid_capture", "Capture dimensions are empty")
        capture = Capture(self, result, width, height)
        self.session.emit_image(png)
        self.session.emit(str(capture))
        return capture


class Capture:
    """Coordinates grounded in one exact-window image and a verified geometry.

    Only the Mac Quartz mapping is implemented. Other image providers
    remain viewable, but their coordinate actions are explicitly unsupported.
    """
    def __init__(self, app: App, result: JSON, width: int, height: int) -> None:
        self.app, self.raw, self.width, self.height = app, result, width, height
        self.action_sequence = app.session.action_attempts

    def __str__(self) -> str:
        return f"{self.app.name}: {self.width}×{self.height} image pixels. Capture.click(x,y) / Capture.scroll(x,y,direction) use this image; new actions invalidate it."

    def _point(self, x: float, y: float) -> tuple[int, int]:
        if self.action_sequence != self.app.session.action_attempts:
            raise StaleElement("stale_capture", "An action occurred after this capture; capture again")
        if self.raw.get("actualRoute") != "guest.user/macos.quartz" or self.raw.get("coordinateSpace") != "window_pixels" \
                or self.raw.get("fidelity") != "exact_window":
            raise Unsupported("unsupported_capture_coordinates", "This provider has no supported image-to-input mapping")
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (x, y)) \
                or not 0 <= x < self.width or not 0 <= y < self.height:
            raise SessionError("invalid_capture_coordinates", "Coordinates must lie inside the captured image")
        window = self.raw.get("data", {}).get("window", {})
        bounds = window.get("bounds", {})
        if any(type(bounds.get(k)) not in (int, float) or not math.isfinite(bounds[k])
               for k in ("x", "y", "width", "height")) or bounds["width"] <= 0 or bounds["height"] <= 0:
            raise Unsupported("unsupported_capture_bounds", "Capture has no finite window geometry")
        if window.get("windowId") is None or window.get("processId") is None:
            raise Unsupported("unsupported_capture_identity", "Capture has no exact window/process identity")
        current = self.app.session.call({"operation": "windows", "target": self.app.target})
        matches = [w for w in current.get("data", {}).get("windows", [])
                   if w.get("windowId") == window["windowId"] and w.get("processId") == window["processId"]]
        if current.get("generation") != self.raw.get("generation") or len(matches) != 1 \
                or matches[0].get("bounds") != bounds or matches[0].get("onScreen") is not True:
            raise StaleElement("stale_capture", "Captured window changed or disappeared; capture again")
        return round(bounds["x"] + x * bounds["width"] / self.width), round(bounds["y"] + y * bounds["height"] / self.height)

    def click(self, x: float, y: float, *, observe: bool | None = None) -> Result:
        px, py = self._point(x, y)
        return self.app._act({"operation": "input.click", "target": self.app.target, "x": px, "y": py}, observe)

    def scroll(self, x: float, y: float, direction: str = "down", *, pixels: int = 400,
               observe: bool | None = None) -> Result:
        px, py = self._point(x, y)
        return self.app._scroll_at(px, py, direction, pixels, observe)
