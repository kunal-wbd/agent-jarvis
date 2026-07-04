"""
MCP stdio client — manages a long-lived subprocess running tool/stdio/server.py.

Usage (via registry, not directly):
    client = StdioClient.instance()
    schemas = client.list_tools()      # returns OpenAI-format schemas
    result  = client.call("read_file", {"path": "foo.txt"})
"""

import json
import subprocess
import sys
import threading
from typing import Any


def _mcp_to_openai_schema(tool: dict) -> dict:
    """Convert MCP tool format to OpenAI function-call format."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
        },
    }


class StdioClient:
    """Singleton MCP stdio client. Spawns the server once; reuses for all calls."""

    _instance: "StdioClient | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "tool.stdio.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._req_id = 0
        self._call_lock = threading.Lock()
        self._handshake()

    @classmethod
    def instance(cls) -> "StdioClient":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _send(self, method: str, params: dict | None = None) -> Any:
        """Send a JSON-RPC request and read the response. Thread-safe."""
        with self._call_lock:
            req = {"jsonrpc": "2.0", "id": self._next_id(), "method": method}
            if params is not None:
                req["params"] = params
            self._proc.stdin.write(json.dumps(req) + "\n")
            self._proc.stdin.flush()
            raw = self._proc.stdout.readline()
            return json.loads(raw)

    def _handshake(self) -> None:
        resp = self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "harness", "version": "0.1.0"},
            "capabilities": {},
        })
        if "error" in resp:
            raise RuntimeError(f"MCP stdio init failed: {resp['error']}")
        # send initialized notification (no response expected)
        self._proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        self._proc.stdin.flush()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_tools(self) -> list[dict]:
        """Return tool schemas in OpenAI function format."""
        resp = self._send("tools/list")
        if "error" in resp:
            raise RuntimeError(f"tools/list failed: {resp['error']}")
        return [_mcp_to_openai_schema(t) for t in resp["result"]["tools"]]

    def call(self, name: str, arguments: dict) -> str:
        """Call a tool and return its text result."""
        resp = self._send("tools/call", {"name": name, "arguments": arguments})
        if "error" in resp:
            return f"error: {resp['error']['message']}"
        content = resp["result"].get("content", [])
        return "\n".join(c["text"] for c in content if c.get("type") == "text")

    def shutdown(self) -> None:
        try:
            self._proc.stdin.close()
            self._proc.wait(timeout=3)
        except Exception:
            self._proc.kill()
