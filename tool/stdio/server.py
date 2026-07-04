#!/usr/bin/env python3
"""
MCP stdio server — disk operations.

Speaks JSON-RPC 2.0 over stdin/stdout (one JSON object per line).
Run directly: python -m tool.stdio.server
Spawned automatically by tool/stdio/client.py.

Supported MCP methods:
  initialize    — handshake, returns server info
  tools/list    — returns all tool schemas in MCP format
  tools/call    — executes a tool and returns the result
"""

import json
import os
import sys


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _read_file(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except OSError as e:
        return f"error: {e}"


def _write_file(path: str, content: str) -> str:
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"wrote {len(content)} bytes to {path}"
    except OSError as e:
        return f"error: {e}"


def _list_dir(path: str = ".") -> str:
    try:
        entries = sorted(os.listdir(path))
        if not entries:
            return f"{path}/ is empty"
        lines = []
        for name in entries:
            full = os.path.join(path, name)
            suffix = "/" if os.path.isdir(full) else ""
            lines.append(f"  {name}{suffix}")
        return f"{path}/\n" + "\n".join(lines)
    except OSError as e:
        return f"error: {e}"


# ---------------------------------------------------------------------------
# MCP tool registry (MCP uses inputSchema, not parameters)
# ---------------------------------------------------------------------------

_TOOLS = {
    "read_file": {
        "name": "read_file",
        "description": "Read the contents of a file by path.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "handler": _read_file,
    },
    "write_file": {
        "name": "write_file",
        "description": (
            "Write text content to a file. Creates parent directories if needed. "
            "Overwrites if the file already exists."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        "handler": _write_file,
    },
    "list_dir": {
        "name": "list_dir",
        "description": "List files and subdirectories in a directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Defaults to current directory."},
            },
            "required": [],
        },
        "handler": _list_dir,
    },
}


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

def _ok(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Method handlers
# ---------------------------------------------------------------------------

def _handle_initialize(req: dict) -> dict:
    return _ok(req.get("id"), {
        "protocolVersion": "2024-11-05",
        "serverInfo": {"name": "harness-stdio", "version": "0.1.0"},
        "capabilities": {"tools": {}},
    })


def _handle_tools_list(req: dict) -> dict:
    tools = [
        {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
        for t in _TOOLS.values()
    ]
    return _ok(req.get("id"), {"tools": tools})


def _handle_tools_call(req: dict) -> dict:
    params = req.get("params", {})
    name = params.get("name")
    arguments = params.get("arguments", {})

    if name not in _TOOLS:
        return _err(req.get("id"), -32601, f"unknown tool: {name}")

    try:
        result = _TOOLS[name]["handler"](**arguments)
        return _ok(req.get("id"), {"content": [{"type": "text", "text": result}]})
    except Exception as e:
        return _err(req.get("id"), -32603, str(e))


_DISPATCH = {
    "initialize": _handle_initialize,
    "tools/list": _handle_tools_list,
    "tools/call": _handle_tools_call,
}


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _send(_err(None, -32700, f"parse error: {e}"))
            continue

        method = req.get("method", "")

        # initialized notification — no response needed
        if method == "notifications/initialized":
            continue

        handler = _DISPATCH.get(method)
        if handler is None:
            _send(_err(req.get("id"), -32601, f"method not found: {method}"))
            continue

        _send(handler(req))


if __name__ == "__main__":
    main()
