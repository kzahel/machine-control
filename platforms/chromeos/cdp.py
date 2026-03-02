"""Chrome DevTools Protocol client for accessibility tree access.

Connects to Chrome's remote debugging port (9222) via a minimal
WebSocket client (no dependencies beyond stdlib). Queries the
accessibility tree and can click elements by name/role.

Deploy alongside client.py on the Chromebook.
"""

import socket
import struct
import os
import base64
import json
import re
import http.client

CDP_PORT = 9222


# === Minimal WebSocket client (RFC 6455) ===

class WebSocket:
    def __init__(self, url):
        # Parse ws://host:port/path
        url = url.replace("ws://", "")
        slash = url.index("/")
        host_port, self.path = url[:slash], url[slash:]
        if ":" in host_port:
            self.host, p = host_port.rsplit(":", 1)
            self.port = int(p)
        else:
            self.host, self.port = host_port, 80
        self.sock = socket.create_connection((self.host, self.port), timeout=60)
        self._handshake()

    def _handshake(self):
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        self.sock.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Connection closed during handshake")
            resp += chunk
        status_line = resp.split(b"\r\n")[0]
        if b"101" not in status_line:
            raise ConnectionError(f"WebSocket handshake failed: {status_line.decode()}")

    def send(self, text):
        payload = text.encode()
        frame = bytearray([0x81])  # FIN + text opcode
        mask_key = os.urandom(4)
        n = len(payload)
        if n < 126:
            frame.append(0x80 | n)
        elif n < 65536:
            frame.append(0x80 | 126)
            frame.extend(struct.pack(">H", n))
        else:
            frame.append(0x80 | 127)
            frame.extend(struct.pack(">Q", n))
        frame.extend(mask_key)
        frame.extend(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(frame)

    def recv(self):
        def read_exact(n):
            buf = b""
            while len(buf) < n:
                chunk = self.sock.recv(min(n - len(buf), 65536))
                if not chunk:
                    raise ConnectionError("WebSocket connection closed")
                buf += chunk
            return buf

        hdr = read_exact(2)
        fin = bool(hdr[0] & 0x80)
        opcode = hdr[0] & 0x0F
        masked = bool(hdr[1] & 0x80)
        length = hdr[1] & 0x7F
        if length == 126:
            length = struct.unpack(">H", read_exact(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", read_exact(8))[0]
        if masked:
            mk = read_exact(4)
            data = bytearray(read_exact(length))
            data = bytearray(b ^ mk[i % 4] for i, b in enumerate(data))
        else:
            data = read_exact(length)
        if opcode == 0x08:
            raise ConnectionError("WebSocket closed by server")
        if opcode == 0x09:  # ping
            # Send pong
            pong = bytearray([0x8A, 0x80]) + os.urandom(4)
            self.sock.sendall(pong)
            return self.recv()
        return data.decode()

    def close(self):
        try:
            self.sock.sendall(bytearray([0x88, 0x80]) + os.urandom(4))
        except Exception:
            pass
        self.sock.close()


# === CDP session ===

class CDP:
    def __init__(self, ws_url):
        self.ws = WebSocket(ws_url)
        self._next_id = 0

    def call(self, method, **params):
        self._next_id += 1
        mid = self._next_id
        msg = {"id": mid, "method": method}
        if params:
            msg["params"] = params
        self.ws.send(json.dumps(msg))
        while True:
            resp = json.loads(self.ws.recv())
            if resp.get("id") == mid:
                if "error" in resp:
                    err = resp["error"]
                    raise RuntimeError(f"CDP {method}: {err.get('message', err)}")
                return resp.get("result", {})
            # else: event notification, skip

    def close(self):
        self.ws.close()


# === Target discovery ===

def list_targets(port=CDP_PORT):
    """List available CDP targets (pages/tabs)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", "/json")
        resp = conn.getresponse()
        return json.loads(resp.read())
    finally:
        conn.close()


def _get_ws_url(target_idx, port=CDP_PORT):
    """Get WebSocket URL for a target by index."""
    targets = list_targets(port)
    pages = [t for t in targets if t.get("type") == "page"]
    if not pages:
        raise RuntimeError("No page targets found. Is a Chrome window open?")
    if target_idx >= len(pages):
        raise IndexError(f"Target {target_idx} not found (have {len(pages)} pages)")
    ws = pages[target_idx].get("webSocketDebuggerUrl")
    if not ws:
        raise RuntimeError(f"Target {target_idx} has no webSocketDebuggerUrl (already attached?)")
    return ws


def connect(target_idx=0, port=CDP_PORT):
    """Connect to a CDP target. Returns CDP instance."""
    return CDP(_get_ws_url(target_idx, port))


# === AX tree ===

def _simplify_node(node):
    """Extract useful fields from a raw AX node."""
    def val(field):
        v = node.get(field, {})
        return v.get("value", "") if isinstance(v, dict) else str(v)

    out = {
        "nodeId": node.get("nodeId", ""),
        "role": val("role"),
        "name": val("name"),
    }
    if node.get("ignored"):
        out["ignored"] = True

    # Extract key properties
    for prop in node.get("properties", []):
        pname = prop.get("name", "")
        pval = prop.get("value", {})
        pval = pval.get("value", "") if isinstance(pval, dict) else pval
        if pval and pname in ("focused", "editable", "checked", "selected",
                              "expanded", "disabled", "required", "value",
                              "description"):
            out.setdefault("properties", {})[pname] = pval

    if node.get("childIds"):
        out["childIds"] = node["childIds"]
    bid = node.get("backendDOMNodeId")
    if bid:
        out["backendDOMNodeId"] = bid
    return out


def get_ax_tree(target_idx=0, port=CDP_PORT):
    """Get the full accessibility tree for a target.

    Returns list of simplified node dicts.
    """
    cdp = connect(target_idx, port)
    try:
        cdp.call("Accessibility.enable")
        result = cdp.call("Accessibility.getFullAXTree")
        nodes = []
        for raw in result.get("nodes", []):
            node = _simplify_node(raw)
            if node.get("ignored") and not node.get("name"):
                continue
            nodes.append(node)
        return nodes
    finally:
        cdp.close()


def render_tree(nodes, max_depth=None, no_text=True):
    """Render AX nodes as an indented text tree.

    Args:
        max_depth: Max nesting depth to display (None = unlimited).
        no_text: If True, hide StaticText/InlineTextBox leaf nodes.
    """
    by_id = {n["nodeId"]: n for n in nodes}
    children_of = {}
    has_parent = set()
    for n in nodes:
        for cid in n.get("childIds", []):
            children_of.setdefault(n["nodeId"], []).append(cid)
            has_parent.add(cid)

    roots = [n["nodeId"] for n in nodes if n["nodeId"] not in has_parent]
    lines = []

    # Roles to skip (pass through to children)
    SKIP_ROLES = {"generic", "none", "GenericContainer", ""}
    # Leaf text roles to hide when no_text is set
    TEXT_ROLES = {"StaticText", "InlineTextBox"}

    def walk(nid, depth):
        node = by_id.get(nid)
        if not node:
            return
        role = node.get("role", "")
        name = node.get("name", "")
        props = node.get("properties", {})

        # Skip unnamed generic containers (promote children)
        if not name and role in SKIP_ROLES:
            for cid in children_of.get(nid, []):
                walk(cid, depth)
            return

        # Hide leaf text nodes (the parent already has the name)
        if no_text and role in TEXT_ROLES:
            return

        parts = []
        if role:
            parts.append(f"[{role}]")
        if name:
            parts.append(f'"{name}"')
        for k, v in props.items():
            if v is True:
                parts.append(f"({k})")
            elif v:
                parts.append(f"({k}={v})")

        if parts:
            lines.append("  " * depth + " ".join(parts))

        if max_depth is not None and depth >= max_depth:
            child_count = len(children_of.get(nid, []))
            if child_count:
                lines.append("  " * (depth + 1) + f"... {child_count} children")
            return

        for cid in children_of.get(nid, []):
            walk(cid, depth + 1)

    for rid in roots:
        walk(rid, 0)

    return "\n".join(lines)


def find_nodes(pattern, role=None, target_idx=0, port=CDP_PORT):
    """Find AX nodes matching name pattern. Returns nodes with bounds."""
    cdp = connect(target_idx, port)
    try:
        cdp.call("Accessibility.enable")
        cdp.call("DOM.enable")
        result = cdp.call("Accessibility.getFullAXTree")

        pat = re.compile(pattern, re.IGNORECASE)
        matches = []

        for raw in result.get("nodes", []):
            node = _simplify_node(raw)
            if node.get("ignored"):
                continue
            if not pat.search(node.get("name", "")):
                continue
            if role and node.get("role", "").lower() != role.lower():
                continue

            # Resolve bounding box
            bid = node.get("backendDOMNodeId")
            if bid:
                try:
                    cdp.call("DOM.scrollIntoViewIfNeeded", backendNodeId=bid)
                    quads = cdp.call("DOM.getContentQuads", backendNodeId=bid)
                    q = quads.get("quads", [[]])[0]
                    if len(q) >= 8:
                        xs = [q[i] for i in range(0, 8, 2)]
                        ys = [q[i] for i in range(1, 8, 2)]
                        node["bounds"] = {
                            "x": min(xs), "y": min(ys),
                            "width": max(xs) - min(xs),
                            "height": max(ys) - min(ys),
                            "center_x": sum(xs) / 4,
                            "center_y": sum(ys) / 4,
                        }
                except Exception:
                    pass

            matches.append(node)

        return matches
    finally:
        cdp.close()


def click(pattern, role=None, target_idx=0, port=CDP_PORT):
    """Find an element by name and click it via CDP mouse events.

    Returns the clicked node info, or raises if not found.
    """
    cdp = connect(target_idx, port)
    try:
        cdp.call("Accessibility.enable")
        cdp.call("DOM.enable")
        result = cdp.call("Accessibility.getFullAXTree")

        pat = re.compile(pattern, re.IGNORECASE)
        target_node = None

        for raw in result.get("nodes", []):
            node = _simplify_node(raw)
            if node.get("ignored"):
                continue
            if not pat.search(node.get("name", "")):
                continue
            if role and node.get("role", "").lower() != role.lower():
                continue
            bid = node.get("backendDOMNodeId")
            if not bid:
                continue

            # Resolve position
            try:
                cdp.call("DOM.scrollIntoViewIfNeeded", backendNodeId=bid)
                quads = cdp.call("DOM.getContentQuads", backendNodeId=bid)
                q = quads.get("quads", [[]])[0]
                if len(q) >= 8:
                    x = sum(q[i] for i in range(0, 8, 2)) / 4
                    y = sum(q[i] for i in range(1, 8, 2)) / 4
                    target_node = node
                    target_node["click_x"] = x
                    target_node["click_y"] = y
                    break
            except Exception:
                continue

        if not target_node:
            raise RuntimeError(f"No clickable element matching '{pattern}' found")

        x, y = target_node["click_x"], target_node["click_y"]

        cdp.call("Input.dispatchMouseEvent",
                 type="mousePressed", x=x, y=y, button="left",
                 clickCount=1)
        cdp.call("Input.dispatchMouseEvent",
                 type="mouseReleased", x=x, y=y, button="left",
                 clickCount=1)

        return {
            "name": target_node.get("name"),
            "role": target_node.get("role"),
            "x": x,
            "y": y,
        }
    finally:
        cdp.close()


# === Desktop automation (chrome.automation via extension) ===

def _find_automation_target(port=CDP_PORT):
    """Find the Desktop Automation extension's service worker target."""
    targets = list_targets(port)
    for t in targets:
        url = t.get("url", "")
        ttype = t.get("type", "")
        title = t.get("title", "")
        if ttype == "service_worker" and "background.js" in url:
            ws = t.get("webSocketDebuggerUrl")
            if ws:
                return ws
    # Fallback: match by title on any target type
    for t in targets:
        if "Desktop Automation" in t.get("title", ""):
            ws = t.get("webSocketDebuggerUrl")
            if ws:
                return ws
    raise RuntimeError(
        "Desktop Automation extension not found in CDP targets. "
        "Is it deployed and loaded? Check chrome://extensions"
    )


def _js_escape(s):
    """Escape a string for safe inclusion in a JS string literal."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


def desktop_tree(max_depth=None, port=CDP_PORT):
    """Get the full desktop accessibility tree via chrome.automation.

    Returns a nested dict with role/name/state/location/children.
    """
    max_depth_js = "null" if max_depth is None else str(int(max_depth))
    js = f"""
new Promise((resolve, reject) => {{
  chrome.automation.getDesktop((root) => {{
    if (!root) {{ reject(new Error('No desktop root')); return; }}
    const maxDepth = {max_depth_js};
    function walk(node, depth) {{
      const r = {{role: node.role || '', name: node.name || ''}};
      const st = node.state;
      if (st) {{
        const states = {{}};
        for (const [k, v] of Object.entries(st)) {{
          if (v) states[k] = true;
        }}
        if (Object.keys(states).length) r.state = states;
      }}
      const loc = node.location;
      if (loc && (loc.width > 0 || loc.height > 0)) {{
        r.location = {{x: loc.left, y: loc.top,
                       width: loc.width, height: loc.height}};
      }}
      if (maxDepth === null || depth < maxDepth) {{
        const kids = node.children;
        if (kids && kids.length > 0) {{
          r.children = [];
          for (const c of kids) {{
            r.children.push(walk(c, depth + 1));
          }}
        }}
      }}
      return r;
    }}
    resolve(JSON.stringify(walk(root, 0)));
  }});
}})
"""
    ws_url = _find_automation_target(port)
    cdp = CDP(ws_url)
    try:
        result = cdp.call("Runtime.evaluate",
                          expression=js,
                          awaitPromise=True,
                          returnByValue=True)
        val = result.get("result", {}).get("value")
        if val is None:
            exc = result.get("exceptionDetails", {})
            msg = exc.get("exception", {}).get("description", "Unknown error")
            raise RuntimeError(f"desktop_tree failed: {msg}")
        return json.loads(val)
    finally:
        cdp.close()


def desktop_find(pattern, role=None, port=CDP_PORT):
    """Search desktop tree for nodes matching name pattern.

    Returns list of matches with role/name/location/bounds.
    """
    role_js = f"'{_js_escape(role)}'" if role else "null"
    js = f"""
new Promise((resolve, reject) => {{
  chrome.automation.getDesktop((root) => {{
    if (!root) {{ reject(new Error('No desktop root')); return; }}
    const re = new RegExp('{_js_escape(pattern)}', 'i');
    const role = {role_js};
    const matches = [];
    function search(node) {{
      const name = node.name || '';
      const nodeRole = node.role || '';
      if (re.test(name) && (!role || nodeRole === role)) {{
        const m = {{role: nodeRole, name: name}};
        const st = node.state;
        if (st) {{
          const states = {{}};
          for (const [k, v] of Object.entries(st)) {{
            if (v) states[k] = true;
          }}
          if (Object.keys(states).length) m.state = states;
        }}
        const loc = node.location;
        if (loc) {{
          m.location = {{x: loc.left, y: loc.top,
                         width: loc.width, height: loc.height,
                         center_x: loc.left + loc.width / 2,
                         center_y: loc.top + loc.height / 2}};
        }}
        matches.push(m);
      }}
      for (const child of (node.children || [])) {{
        search(child);
      }}
    }}
    search(root);
    resolve(JSON.stringify(matches));
  }});
}})
"""
    ws_url = _find_automation_target(port)
    cdp = CDP(ws_url)
    try:
        result = cdp.call("Runtime.evaluate",
                          expression=js,
                          awaitPromise=True,
                          returnByValue=True)
        val = result.get("result", {}).get("value")
        if val is None:
            exc = result.get("exceptionDetails", {})
            msg = exc.get("exception", {}).get("description", "Unknown error")
            raise RuntimeError(f"desktop_find failed: {msg}")
        return json.loads(val)
    finally:
        cdp.close()


def desktop_click(pattern, role=None, port=CDP_PORT):
    """Find a desktop node by name and activate it via doDefault().

    Returns info about the clicked node, or raises if not found.
    """
    role_js = f"'{_js_escape(role)}'" if role else "null"
    js = f"""
new Promise((resolve, reject) => {{
  chrome.automation.getDesktop((root) => {{
    if (!root) {{ reject(new Error('No desktop root')); return; }}
    const re = new RegExp('{_js_escape(pattern)}', 'i');
    const role = {role_js};
    function search(node) {{
      const name = node.name || '';
      const nodeRole = node.role || '';
      if (re.test(name) && (!role || nodeRole === role)) {{
        return node;
      }}
      for (const child of (node.children || [])) {{
        const found = search(child);
        if (found) return found;
      }}
      return null;
    }}
    const target = search(root);
    if (!target) {{ reject(new Error('No match for pattern: {_js_escape(pattern)}')); return; }}
    target.doDefault();
    const loc = target.location;
    resolve(JSON.stringify({{
      name: target.name || '',
      role: target.role || '',
      location: loc ? {{x: loc.left, y: loc.top,
                        width: loc.width, height: loc.height}} : null
    }}));
  }});
}})
"""
    ws_url = _find_automation_target(port)
    cdp = CDP(ws_url)
    try:
        result = cdp.call("Runtime.evaluate",
                          expression=js,
                          awaitPromise=True,
                          returnByValue=True)
        val = result.get("result", {}).get("value")
        if val is None:
            exc = result.get("exceptionDetails", {})
            msg = exc.get("exception", {}).get("description", "Unknown error")
            raise RuntimeError(f"desktop_click failed: {msg}")
        return json.loads(val)
    finally:
        cdp.close()
