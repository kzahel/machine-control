"""Reuse appliance semantics, replacing all privileged input/capture routes."""

import os
from pathlib import Path
import subprocess
import time

import linuxcontrol
import linuxui
import artifacts


class Provider(linuxcontrol.Resident):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def call_input(self, _request):
        # Never reach the appliance socket, even through an inherited method.
        raise linuxcontrol.ControlFailure("unsupported_operation", "Appliance input is unavailable")

    def input_ready(self):
        return self.owner.portal.ready and self.owner.portal.devices & 3 == 3

    def protect_node(self, node):
        app = linuxui.safe(node.get_application)
        pid = linuxui.safe(app.get_process_id, 0) if app else 0
        name = linuxui.safe(app.get_name, "") if app else ""
        role = linuxui.safe(node.get_role_name, "")
        ancestor = pid
        owned = False
        for _ in range(32):
            if ancestor in {os.getpid(), self.owner.operator_pid}:
                owned = True
                break
            if ancestor <= 1:
                break
            try:
                ancestor = int(Path(f"/proc/{ancestor}/stat").read_text().rsplit(")", 1)[1].split()[1])
            except (OSError, ValueError, IndexError):
                raise linuxcontrol.ControlFailure("target_unavailable", "Application identity changed")
        if owned or name.startswith("xdg-desktop-portal"):
            raise linuxcontrol.ControlFailure("operator_protected", "The operator and permission dialogs are protected")
        if role == "password text":
            raise linuxcontrol.ControlFailure("protected_surface", "Password fields are unavailable")

    def resolve_reference(self, request):
        node = super().resolve_reference(request)
        self.protect_node(node)
        return node

    def protect_input(self):
        if self.owner.grants.pending or self.owner.portal.state == "pending":
            raise linuxcontrol.ControlFailure("approval_prompt_visible", "Finish approval first")
        # Refuse ambiguous foreground identity instead of typing into a dialog.
        active = []
        for app in linuxui.application_roots(linuxui.desktop()):
            if linuxui.safe(app.get_process_id, 0) == os.getpid():
                continue
            for _, window in linuxui.children(app):
                if "active" in linuxui.state_names(window):
                    active.append(window)
        if len(active) != 1:
            raise linuxcontrol.ControlFailure("foreground_unavailable", "Foreground window is uncertain")
        self.protect_node(active[0])
        for node, info in linuxui.walk(active[0], 8, 400):
            if info["role"] == "password text":
                raise linuxcontrol.ControlFailure("protected_surface", "Authentication dialogs are unavailable")

    def snapshot(self, request):
        if not request.get("target"):
            raise linuxcontrol.ControlFailure("invalid_request", "Select an application")
        self.protect_node(linuxui.choose_application(linuxui.desktop(), request["target"]))
        return super().snapshot(request)

    def windows(self, request):
        if not request.get("target"):
            raise linuxcontrol.ControlFailure("invalid_request", "Select an application")
        self.protect_node(linuxui.choose_application(linuxui.desktop(), request["target"]))
        return super().windows(request)

    def capture(self, request):
        if request.get("scope", "display") != "display":
            raise linuxcontrol.ControlFailure("unsupported_operation", "Only the shared screen is available")
        data = self.owner.portal.capture()
        artifact = artifacts.write(data)
        result = self.envelope(request, "capture")
        result.update(actualRoute="user/linux.portal-pipewire", fidelity="display_pixels",
                      delivery="confirmed", effect="artifact_observed")
        result["data"] = {"artifact": artifact,
                          "coordinateSpace": "portal_shared_screen",
                          "logicalSize": self.owner.portal.properties.get("logical_size",
                                         self.owner.portal.properties.get("size"))}
        return result

    def input(self, request):
        self.protect_input()
        before = self.owner.portal.deliveries
        try:
            return self.dispatch_input(request)
        except Exception:
            if self.owner.portal.deliveries == before:
                raise
            result = self.fail(request, request["operation"], "input_delivery_unknown", "Input route failed after dispatch")
            result.update(actualRoute="user/linux.portal-notify", delivery="unknown", effect="unknown",
                          uncertainty="provider_failed_after_dispatch", retrySafety="unsafe_delivery_unknown")
            return result

    def dispatch_input(self, request):
        portal = self.owner.portal
        operation = request["operation"]
        if operation == "input.move":
            portal.move(float(request["x"]), float(request["y"]))
        elif operation == "input.click":
            portal.click(float(request["x"]), float(request["y"]), request.get("button", "left"), request.get("count", 1))
        elif operation == "input.drag":
            portal.drag(*[float(request[name]) for name in ["x1", "y1", "x2", "y2"]])
        elif operation == "input.key":
            portal.key(request["key"])
        elif operation == "input.text":
            text = request["text"]
            if not isinstance(text, str) or not text or len(text) > 4096:
                raise ValueError("Choose 1-4096 characters")
            # Mutter's keysym route can acknowledge non-keymap Unicode without
            # inserting it. Reuse the accepted clipboard + ownership oracle,
            # replacing the appliance's virtual Ctrl+V with portal Ctrl+V.
            helper = subprocess.Popen(["/usr/bin/wl-copy", "--foreground", "--paste-once",
                                       "--type", linuxcontrol.CLIPBOARD_TYPE],
                                      stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
            try:
                helper.stdin.write(text.encode())
                helper.stdin.close()
                if not linuxcontrol.clipboard_serves(text.encode()):
                    raise linuxcontrol.ControlFailure("text_delivery_failed", "Clipboard ownership was not observed")
                time.sleep(linuxcontrol.CLIPBOARD_FOCUS_SETTLE_SECONDS)
                portal.key("ctrl+v")
                try:
                    helper.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
            finally:
                if helper.poll() is None:
                    helper.terminate()
                helper.wait(timeout=3)
        elif operation == "input.scroll":
            if "x" in request or "y" in request:
                portal.move(float(request["x"]), float(request["y"]))
            portal.scroll(float(request.get("dx", request.get("deltaX", 0))),
                          float(request.get("dy", request.get("deltaY", 0))))
        else:
            raise linuxcontrol.ControlFailure("unsupported_operation", "Input operation is unavailable")
        result = self.envelope(request, operation)
        result.update(actualRoute="user/linux.portal-notify", fidelity="foreground_input",
                      delivery="confirmed", effect="unverifiable", uncertainty="no_independent_state_change")
        result["data"] = {"coordinateSpace": "portal_shared_screen", "privilege": "ordinary_user",
                          "clipboardTextSideEffect": operation == "input.text",
                          "foregroundConsequence": "foreground_window_receives_input",
                          "cursorConsequence": "moves" if operation in {"input.move", "input.click", "input.drag"} or (
                              operation == "input.scroll" and "x" in request) else "unchanged"}
        return result

    def application_activate(self, request):
        root = linuxui.desktop()
        target = linuxui.choose_application(root, str(request.get("target") or ""))
        self.protect_node(target)
        return super().application_activate(request)

    def application_terminate(self, request):
        root = linuxui.desktop()
        target = linuxui.choose_application(root, str(request.get("target") or ""))
        self.protect_node(target)
        return super().application_terminate(request)
