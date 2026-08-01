#!/usr/bin/env python3
"""Small AT-SPI command-line client for the interactive Wayland session."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Iterable

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402


class UIError(RuntimeError):
    pass


def safe(call, default=None):
    try:
        return call()
    except Exception:
        return default


STATE_TYPES = (
    ("active", Atspi.StateType.ACTIVE),
    ("checked", Atspi.StateType.CHECKED),
    ("editable", Atspi.StateType.EDITABLE),
    ("enabled", Atspi.StateType.ENABLED),
    ("expanded", Atspi.StateType.EXPANDED),
    ("focusable", Atspi.StateType.FOCUSABLE),
    ("focused", Atspi.StateType.FOCUSED),
    ("selected", Atspi.StateType.SELECTED),
    ("showing", Atspi.StateType.SHOWING),
    ("visible", Atspi.StateType.VISIBLE),
)


def state_names(node) -> list[str]:
    states = safe(node.get_state_set)
    if states is None:
        return []
    return [name for name, state in STATE_TYPES if safe(lambda: states.contains(state), False)]


def interfaces(node) -> list[str]:
    values = safe(node.get_interfaces, []) or []
    return sorted(str(value) for value in values)


def actions(node) -> list[dict[str, Any]]:
    if "Action" not in interfaces(node):
        return []
    count = safe(node.get_n_actions, 0) or 0
    result = []
    for index in range(count):
        result.append(
            {
                "index": index,
                "name": safe(lambda: node.get_localized_name(index), "") or "",
                "keyBinding": safe(lambda: node.get_key_binding(index), "") or "",
            }
        )
    return result


def bounds(node) -> dict[str, int] | None:
    if "Component" not in interfaces(node):
        return None
    rect = safe(lambda: node.get_extents(Atspi.CoordType.SCREEN))
    if rect is None:
        return None
    return {
        "x": int(rect.x),
        "y": int(rect.y),
        "width": int(rect.width),
        "height": int(rect.height),
    }


def node_info(node, path: str, depth: int) -> dict[str, Any]:
    info: dict[str, Any] = {
        "path": path,
        "depth": depth,
        "role": safe(node.get_role_name, "unknown") or "unknown",
        "name": safe(node.get_name, "") or "",
        "description": safe(node.get_description, "") or "",
        "states": state_names(node),
        "interfaces": interfaces(node),
        "actions": actions(node),
    }
    rect = bounds(node)
    if rect is not None:
        info["bounds"] = rect
    return info


def children(node) -> Iterable[tuple[int, Any]]:
    count = safe(node.get_child_count, 0) or 0
    for index in range(max(0, count)):
        child = safe(lambda index=index: node.get_child_at_index(index))
        if child is not None:
            yield index, child


def desktop():
    Atspi.init()
    result = Atspi.get_desktop(0)
    if result is None:
        raise UIError("AT-SPI desktop is unavailable")
    return result


def application_roots(root) -> list[Any]:
    return [child for _, child in children(root)]


def choose_application(root, query: str | None):
    if not query:
        return root
    folded = query.casefold()
    apps = application_roots(root)
    exact = [app for app in apps if (safe(app.get_name, "") or "").casefold() == folded]
    partial = [app for app in apps if folded in (safe(app.get_name, "") or "").casefold()]
    matches = exact or partial
    if not matches:
        names = sorted((safe(app.get_name, "") or "?") for app in apps)
        raise UIError(f"No AT-SPI application matches {query!r}; available: {', '.join(names)}")
    return matches[0]


def walk(root, max_depth: int, limit: int, interactive_only: bool = False):
    stack = [(root, "0", 0)]
    emitted = 0
    while stack and emitted < limit:
        node, path, depth = stack.pop()
        info = node_info(node, path, depth)
        interactive = bool(info["actions"]) or any(
            name in info["interfaces"] for name in ("EditableText", "Value")
        ) or "focusable" in info["states"]
        if not interactive_only or interactive:
            emitted += 1
            yield node, info
        if depth < max_depth:
            child_values = list(children(node))
            for index, child in reversed(child_values):
                stack.append((child, f"{path}/{index}", depth + 1))


def find_nodes(root, query: str, max_depth: int, limit: int):
    folded = query.casefold()
    matches = []
    for node, info in walk(root, max_depth=max_depth, limit=5000):
        haystack = " ".join(
            (info["name"], info["role"], info["description"])
        ).casefold()
        if folded in haystack:
            matches.append((node, info))
            if len(matches) >= limit:
                break
    return matches


def resolve_node(root, query: str, max_depth: int):
    matches = find_nodes(root, query, max_depth=max_depth, limit=100)
    if not matches:
        raise UIError(f"No accessible node matches {query!r}")
    exact = [item for item in matches if item[1]["name"].casefold() == query.casefold()]
    return (exact or matches)[0]


def emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def command_health(root) -> None:
    apps = application_roots(root)
    emit(
        {
            "atspiAvailable": True,
            "applicationCount": len(apps),
            "applications": sorted((safe(app.get_name, "") or "?") for app in apps),
            "dbusSessionBus": os.environ.get("DBUS_SESSION_BUS_ADDRESS", ""),
            "sessionType": os.environ.get("XDG_SESSION_TYPE", ""),
            "user": os.environ.get("USER", ""),
        }
    )


def command_apps(root) -> None:
    result = []
    for index, app in enumerate(application_roots(root)):
        result.append(
            {
                "index": index,
                "name": safe(app.get_name, "") or "",
                "processId": safe(app.get_process_id, 0) or 0,
                "toolkit": safe(app.get_toolkit_name, "") or "",
                "version": safe(app.get_toolkit_version, "") or "",
            }
        )
    emit(result)


def command_windows(root, app_query: str | None) -> None:
    target = choose_application(root, app_query)
    result = [node_info(child, f"0/{index}", 1) for index, child in children(target)]
    emit(result)


def command_tree(root, args) -> None:
    target = choose_application(root, args.app)
    emit(
        [
            info
            for _, info in walk(
                target,
                max_depth=args.depth,
                limit=args.limit,
                interactive_only=args.interactive,
            )
        ]
    )


def command_find(root, args) -> None:
    target = choose_application(root, args.app)
    emit([info for _, info in find_nodes(target, args.query, args.depth, args.limit)])


def command_actions(root, args) -> None:
    target = choose_application(root, args.app)
    _, info = resolve_node(target, args.query, args.depth)
    emit({"node": info, "actions": info["actions"]})


def command_press(root, args) -> None:
    target = choose_application(root, args.app)
    node, info = resolve_node(target, args.query, args.depth)
    available = actions(node)
    if not available:
        raise UIError(f"Matched node has no AT-SPI action: {info['path']}")
    selected = available[0]
    if args.action:
        folded = args.action.casefold()
        candidates = [action for action in available if folded in action["name"].casefold()]
        if not candidates:
            raise UIError(f"No action matches {args.action!r}")
        selected = candidates[0]
    if not node.do_action(selected["index"]):
        raise UIError(f"AT-SPI rejected action {selected['name']!r}")
    emit({"invoked": selected, "node": info})


def command_focus(root, args) -> None:
    target = choose_application(root, args.app)
    node, info = resolve_node(target, args.query, args.depth)
    if "Component" not in interfaces(node) or not node.grab_focus():
        raise UIError("Matched node cannot accept focus")
    emit({"focused": True, "node": info})


def command_set_value(root, args) -> None:
    target = choose_application(root, args.app)
    node, info = resolve_node(target, args.query, args.depth)
    node_interfaces = interfaces(node)
    if "EditableText" in node_interfaces:
        if not node.set_text_contents(args.value):
            raise UIError("AT-SPI rejected editable-text value")
        kind = "text"
    elif "Value" in node_interfaces:
        node.set_current_value(float(args.value))
        kind = "number"
    else:
        raise UIError("Matched node exposes neither EditableText nor Value")
    emit({"set": kind, "value": args.value, "node": info})


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="linuxui")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("health")
    commands.add_parser("apps")

    windows = commands.add_parser("windows")
    windows.add_argument("--app")

    tree = commands.add_parser("tree")
    tree.add_argument("--app")
    tree.add_argument("--depth", type=int, default=6)
    tree.add_argument("--limit", type=int, default=500)
    tree.add_argument("--interactive", action="store_true")

    for name in ("find", "actions", "press", "focus", "set-value"):
        command = commands.add_parser(name)
        command.add_argument("query")
        if name == "set-value":
            command.add_argument("value")
        command.add_argument("--app")
        command.add_argument("--depth", type=int, default=12)
        if name == "find":
            command.add_argument("--limit", type=int, default=100)
        if name == "press":
            command.add_argument("--action")
    return result


def main() -> int:
    args = parser().parse_args()
    root = desktop()
    dispatch = {
        "health": lambda: command_health(root),
        "apps": lambda: command_apps(root),
        "windows": lambda: command_windows(root, args.app),
        "tree": lambda: command_tree(root, args),
        "find": lambda: command_find(root, args),
        "actions": lambda: command_actions(root, args),
        "press": lambda: command_press(root, args),
        "focus": lambda: command_focus(root, args),
        "set-value": lambda: command_set_value(root, args),
    }
    dispatch[args.command]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except UIError as error:
        print(f"linuxui: {error}", file=sys.stderr)
        raise SystemExit(1) from error
