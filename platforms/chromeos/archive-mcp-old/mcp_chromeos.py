#!/usr/bin/env python3
"""
ChromeOS MCP Server - Simplified
Exposes raw touchscreen and keyboard input to Claude.

Coordinates are raw touchscreen values. Use chromeos_info to get touch_max.
Screenshot returns the image - Claude figures out coordinates from there.
"""

import asyncio
import json
import base64
import os
import signal
import sys
from io import BytesIO

from PIL import Image
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, ImageContent, Tool

# Capture the original parent PID at startup
# We'll monitor both direct parent and ancestor chain
_ORIGINAL_PPID = os.getppid()


SSH_HOST = "chromeos-testbed"
CLIENT_PATH = "/mnt/stateful_partition/c2/client.py"

server = Server("chromeos")


class Connection:
    """SSH connection to Chromebook."""

    def __init__(self):
        self.process = None
        self._lock = asyncio.Lock()

    def cleanup(self):
        """Clean up SSH process."""
        if self.process and self.process.returncode is None:
            try:
                self.process.terminate()
            except Exception:
                pass

    async def _ensure_client(self):
        """Deploy client.py if needed."""
        from pathlib import Path
        local = Path(__file__).parent / "client.py"

        proc = await asyncio.create_subprocess_exec(
            "ssh", SSH_HOST, f"mkdir -p /mnt/stateful_partition/c2",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.wait()

        proc = await asyncio.create_subprocess_exec(
            "scp", str(local), f"{SSH_HOST}:{CLIENT_PATH}",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.wait()

    async def connect(self):
        if self.process and self.process.returncode is None:
            return
        await self._ensure_client()
        self.process = await asyncio.create_subprocess_exec(
            "ssh", SSH_HOST, f"LD_LIBRARY_PATH=/usr/local/lib64 python3 {CLIENT_PATH}",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=50 * 1024 * 1024)

    async def send(self, cmd: dict, timeout: float = 30) -> dict:
        async with self._lock:
            if not self.process or self.process.returncode is not None:
                await self.connect()
            self.process.stdin.write((json.dumps(cmd) + "\n").encode())
            await self.process.stdin.drain()
            try:
                line = await asyncio.wait_for(self.process.stdout.readline(), timeout)
                return json.loads(line.decode()) if line else {"error": "Connection closed"}
            except asyncio.TimeoutError:
                return {"error": "Timeout"}


conn = Connection()


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="screenshot",
            description="""Capture ChromeOS screenshot. Returns the image.

To tap on UI elements, use visual percentage estimation:
1. Take a screenshot and identify the target element
2. Estimate its position as a percentage of the screen (0-100%):
   - X: 0% = left edge, 100% = right edge
   - Y: 0% = top edge, 100% = bottom edge
3. Get touch_max from chromeos_info: [max_x, max_y]
4. Convert: touch_x = percent_x * max_x / 100, touch_y = percent_y * max_y / 100
5. Call tap with the calculated coordinates

Example: Element appears at roughly 75% across and 85% down the screen.
With touch_max [3492, 1968]: tap(x=2619, y=1673)""",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="tap",
            description="""Tap at raw touchscreen coordinates.

Workflow:
1. Take a screenshot to see the UI
2. Visually estimate target position as percentage (0-100% for X and Y)
3. Get touch_max from chromeos_info
4. Convert: x = percent_x * touch_max_x / 100, y = percent_y * touch_max_y / 100

Example: To tap a button at 50% X, 30% Y with touch_max [3492, 1968]:
x = 50 * 3492 / 100 = 1746, y = 30 * 1968 / 100 = 590""",
            inputSchema={
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate (raw touchscreen)"},
                    "y": {"type": "integer", "description": "Y coordinate (raw touchscreen)"},
                },
                "required": ["x", "y"],
            },
        ),
        Tool(
            name="swipe",
            description="""Swipe between raw touchscreen coordinates.

Use the same percentage-based estimation as tap:
1. Estimate start and end positions as percentages
2. Convert to touch coordinates using touch_max from chromeos_info""",
            inputSchema={
                "type": "object",
                "properties": {
                    "x1": {"type": "integer"}, "y1": {"type": "integer"},
                    "x2": {"type": "integer"}, "y2": {"type": "integer"},
                    "duration_ms": {"type": "integer", "description": "Duration (default 300)"},
                },
                "required": ["x1", "y1", "x2", "y2"],
            },
        ),
        Tool(
            name="type_text",
            description="Type text on keyboard.",
            inputSchema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        ),
        Tool(
            name="press_keys",
            description="Press key combination by Linux keycodes. Common: Enter=28, Space=57, Esc=1, Ctrl=29, Alt=56, Shift=42, Search=125, F1-F12=59-70, Arrows: Left=105, Right=106, Up=103, Down=108",
            inputSchema={
                "type": "object",
                "properties": {"keys": {"type": "array", "items": {"type": "integer"}}},
                "required": ["keys"],
            },
        ),
        Tool(
            name="shortcut",
            description="Execute keyboard shortcut with automatic modifier remapping (handles Ctrl↔Search swap). Modifiers: ctrl, alt, shift, search. Keys: a-z, 0-9, f1-f12.",
            inputSchema={
                "type": "object",
                "properties": {
                    "modifiers": {"type": "array", "items": {"type": "string"}, "description": "Modifier keys"},
                    "key": {"type": "string", "description": "Main key (e.g., 't', 'f5')"},
                },
                "required": ["key"],
            },
        ),
        Tool(
            name="chromeos_info",
            description="Get device info: touchscreen range, keyboard layout, modifier remappings.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="reload_keyboard_config",
            description="Reload keyboard config from ChromeOS preferences (call if settings changed).",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:

    if name == "screenshot":
        result = await conn.send({"cmd": "screenshot"}, timeout=15)
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]

        img_data = base64.b64decode(result["image"])
        img = Image.open(BytesIO(img_data))
        orig_w, orig_h = img.width, img.height

        # Resize for display
        if img.width > 1920:
            ratio = 1920 / img.width
            img = img.resize((1920, int(img.height * ratio)), Image.LANCZOS)

        out = BytesIO()
        img.save(out, format="PNG", optimize=True)
        resized = base64.b64encode(out.getvalue()).decode('ascii')

        return [
            ImageContent(type="image", data=resized, mimeType="image/png"),
            TextContent(type="text", text=f"Screenshot: {orig_w}x{orig_h} (displayed at {img.width}x{img.height})"),
        ]

    elif name == "tap":
        result = await conn.send({"cmd": "tap", "x": arguments["x"], "y": arguments["y"]})
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=f"Tapped at ({arguments['x']}, {arguments['y']})")]

    elif name == "swipe":
        result = await conn.send({
            "cmd": "swipe",
            "x1": arguments["x1"], "y1": arguments["y1"],
            "x2": arguments["x2"], "y2": arguments["y2"],
            "duration_ms": arguments.get("duration_ms", 300)
        })
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=f"Swiped ({arguments['x1']},{arguments['y1']}) -> ({arguments['x2']},{arguments['y2']})")]

    elif name == "type_text":
        result = await conn.send({"cmd": "type", "text": arguments["text"]})
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=f"Typed: {arguments['text']}")]

    elif name == "press_keys":
        result = await conn.send({"cmd": "key", "keys": arguments["keys"]})
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        return [TextContent(type="text", text=f"Pressed keys: {arguments['keys']}")]

    elif name == "shortcut":
        result = await conn.send({
            "cmd": "shortcut",
            "modifiers": arguments.get("modifiers", []),
            "key": arguments["key"]
        })
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        mods = "+".join(arguments.get("modifiers", [])) + "+" if arguments.get("modifiers") else ""
        return [TextContent(type="text", text=f"Shortcut: {mods}{arguments['key']} (keycodes: {result.get('keycodes', [])})")]

    elif name == "chromeos_info":
        result = await conn.send({"cmd": "info"})
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        kb = result.get('keyboard', {})
        info = f"""Device: {result['device']}
Touch max: {result['touch_max']}
Keyboard layout: {kb.get('layout', 'qwerty')}
Modifier remappings: {kb.get('modifier_remappings', {})}"""
        return [TextContent(type="text", text=info)]

    elif name == "reload_keyboard_config":
        result = await conn.send({"cmd": "reload_config"})
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        kb = result.get('keyboard', {})
        return [TextContent(type="text", text=f"Reloaded: layout={kb.get('layout')}, remappings={kb.get('modifier_remappings', {})}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


def _get_process_ancestors(pid: int) -> list[int]:
    """Get list of ancestor PIDs by walking up the process tree.

    Returns list from immediate parent to init (PID 1).
    Uses /proc on Linux or ps on macOS.
    """
    ancestors = []
    current = pid
    seen = set()

    while current and current != 1 and current not in seen:
        seen.add(current)
        try:
            # Try /proc first (Linux)
            try:
                with open(f"/proc/{current}/stat") as f:
                    stat = f.read().split()
                    ppid = int(stat[3])
            except FileNotFoundError:
                # Fall back to ps (macOS)
                import subprocess

                result = subprocess.run(
                    ["ps", "-o", "ppid=", "-p", str(current)],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                if result.returncode != 0 or not result.stdout.strip():
                    break
                ppid = int(result.stdout.strip())

            if ppid > 0:
                ancestors.append(ppid)
                current = ppid
            else:
                break
        except (OSError, ValueError, subprocess.TimeoutExpired):
            break

    return ancestors


async def parent_monitor():
    """Monitor for orphaned process and exit.

    Checks multiple conditions:
    1. Direct parent PID changed (process was reparented)
    2. Any ancestor in the original chain is now PID 1 (launchd/init)
    3. Original parent no longer exists

    On macOS, when Claude Code dies:
    - The 'uv run' process becomes orphaned and gets reparented to PID 1
    - This python process's parent (uv) still exists but its parent is now 1
    """
    # Record the original ancestor chain at startup
    original_ancestors = _get_process_ancestors(os.getpid())

    while True:
        await asyncio.sleep(2)

        current_ppid = os.getppid()

        # Check 1: Direct parent changed
        if current_ppid != _ORIGINAL_PPID:
            print(
                f"Parent PID changed from {_ORIGINAL_PPID} to {current_ppid}, exiting...",
                file=sys.stderr,
            )
            conn.cleanup()
            os._exit(0)

        # Check 2: Our parent (uv run) was reparented to init/launchd
        if current_ppid != 1:
            parent_ancestors = _get_process_ancestors(current_ppid)
            if parent_ancestors and parent_ancestors[0] == 1:
                # Our parent's parent is now init - we're orphaned
                print(
                    "Parent process was reparented to init, exiting...",
                    file=sys.stderr,
                )
                conn.cleanup()
                os._exit(0)

        # Check 3: Verify original parent still exists
        try:
            os.kill(_ORIGINAL_PPID, 0)  # Signal 0 just checks if process exists
        except ProcessLookupError:
            print(
                f"Original parent {_ORIGINAL_PPID} no longer exists, exiting...",
                file=sys.stderr,
            )
            conn.cleanup()
            os._exit(0)
        except PermissionError:
            # Process exists but we can't signal it - that's fine
            pass


async def main():
    # Start parent monitor to detect orphaned process
    monitor_task = asyncio.create_task(parent_monitor())

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        # Clean up when stdio_server exits (e.g., when stdin is closed)
        monitor_task.cancel()
        conn.cleanup()


def _sync_signal_handler(signum, frame):
    """Handle termination signals synchronously."""
    conn.cleanup()
    os._exit(0)


if __name__ == "__main__":
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _sync_signal_handler)
    signal.signal(signal.SIGINT, _sync_signal_handler)
    signal.signal(signal.SIGHUP, _sync_signal_handler)

    asyncio.run(main())
