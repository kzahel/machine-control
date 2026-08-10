#!/usr/bin/env python3
"""Deterministic GTK fixture with an independent JSON effect oracle."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk


STATE_PATH = Path.home() / ".cache/linuxvm-testbed/fixture/state.json"


class Fixture:
    def __init__(self) -> None:
        GLib.set_prgname("machine-control-fixture")
        GLib.set_application_name("Machine Control Fixture")
        self.state: dict[str, Any] = {
            "pid": os.getpid(),
            "sequence": 0,
            "semanticPresses": 0,
            "visualClicks": 0,
            "dragReleases": 0,
            "scrollX": 0,
            "scrollY": 0,
            "text": "",
            "lastKey": "",
            "lastPointer": None,
        }
        self.dragging = False

        self.window = Gtk.Window(title="Machine Control Fixture")
        self.window.set_default_size(720, 540)
        self.window.set_position(Gtk.WindowPosition.CENTER)
        self.window.connect("destroy", Gtk.main_quit)
        self.window.connect("key-press-event", self.on_key)

        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        layout.set_border_width(18)
        self.window.add(layout)

        title = Gtk.Label(label="Machine Control Deterministic Fixture")
        title.get_style_context().add_class("title")
        layout.pack_start(title, False, False, 0)

        self.entry = Gtk.Entry()
        self.entry.set_name("Fixture Text")
        self.entry.set_placeholder_text("Type Unicode fixture text")
        self.entry.get_accessible().set_name("Fixture Text")
        self.entry.connect("changed", self.on_text)
        layout.pack_start(self.entry, False, False, 0)

        button = Gtk.Button(label="Semantic Increment")
        button.connect("clicked", self.on_semantic_press)
        layout.pack_start(button, False, False, 0)

        self.canvas = Gtk.DrawingArea()
        self.canvas.set_size_request(640, 300)
        self.canvas.set_can_focus(True)
        self.canvas.get_accessible().set_name("Visual Canvas")
        self.canvas.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.SCROLL_MASK
        )
        self.canvas.connect("draw", self.on_draw)
        self.canvas.connect("button-press-event", self.on_button_press)
        self.canvas.connect("button-release-event", self.on_button_release)
        self.canvas.connect("motion-notify-event", self.on_motion)
        self.canvas.connect("scroll-event", self.on_scroll)
        layout.pack_start(self.canvas, True, True, 0)

        self.status = Gtk.Label(label="ready")
        self.status.get_accessible().set_name("Fixture Status")
        layout.pack_start(self.status, False, False, 0)

        self.save("ready")
        self.window.show_all()

    def save(self, event: str) -> None:
        self.state["sequence"] += 1
        self.state["lastEvent"] = event
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = STATE_PATH.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.state, separators=(",", ":"), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(STATE_PATH)
        if hasattr(self, "status"):
            self.status.set_text(f"{event} · sequence {self.state['sequence']}")

    def on_semantic_press(self, _button: Gtk.Button) -> None:
        self.state["semanticPresses"] += 1
        self.save("semantic_press")

    def on_text(self, entry: Gtk.Entry) -> None:
        self.state["text"] = entry.get_text()
        self.save("text_changed")

    def on_key(self, _window: Gtk.Window, event: Gdk.EventKey) -> bool:
        self.state["lastKey"] = Gdk.keyval_name(event.keyval) or str(event.keyval)
        self.save("key_press")
        return False

    def pointer(self, event: Gdk.Event) -> dict[str, int]:
        return {"x": round(event.x), "y": round(event.y)}

    def on_button_press(self, _canvas: Gtk.DrawingArea, event: Gdk.EventButton) -> bool:
        self.dragging = True
        self.state["visualClicks"] += 1
        self.state["lastPointer"] = self.pointer(event)
        self.save("pointer_press")
        return True

    def on_button_release(
        self, _canvas: Gtk.DrawingArea, event: Gdk.EventButton
    ) -> bool:
        self.dragging = False
        self.state["dragReleases"] += 1
        self.state["lastPointer"] = self.pointer(event)
        self.save("pointer_release")
        return True

    def on_motion(self, _canvas: Gtk.DrawingArea, event: Gdk.EventMotion) -> bool:
        if self.dragging:
            self.state["lastPointer"] = self.pointer(event)
            self.save("pointer_drag")
        return True

    def on_scroll(self, _canvas: Gtk.DrawingArea, event: Gdk.EventScroll) -> bool:
        if event.direction == Gdk.ScrollDirection.SMOOTH:
            dx, dy = event.get_scroll_deltas()[1:]
        else:
            vectors = {
                Gdk.ScrollDirection.UP: (0, -1),
                Gdk.ScrollDirection.DOWN: (0, 1),
                Gdk.ScrollDirection.LEFT: (-1, 0),
                Gdk.ScrollDirection.RIGHT: (1, 0),
            }
            dx, dy = vectors.get(event.direction, (0, 0))
        self.state["scrollX"] += round(dx)
        self.state["scrollY"] += round(dy)
        self.save("scroll")
        return True

    def on_draw(self, canvas: Gtk.DrawingArea, context: Any) -> bool:
        allocation = canvas.get_allocation()
        context.set_source_rgb(0.08, 0.12, 0.20)
        context.paint()
        context.set_source_rgb(0.20, 0.70, 0.95)
        context.rectangle(24, 24, allocation.width - 48, allocation.height - 48)
        context.set_line_width(4)
        context.stroke()
        context.set_source_rgb(0.92, 0.95, 1.0)
        context.select_font_face("Sans")
        context.set_font_size(24)
        context.move_to(48, 76)
        context.show_text("Visual Canvas: click, drag, and scroll here")
        return False


def main() -> int:
    Fixture()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
