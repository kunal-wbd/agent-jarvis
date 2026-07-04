"""
Unified tool registry.

Discovers tools from three sources and presents a single flat namespace to the
session layer. Sources are queried in this order at import time:

  1. scripts/   — direct Python modules; auto-scanned for SCHEMA + run()
  2. stdio/     — MCP stdio server; discovered via tools/list RPC
  3. sse/       — MCP SSE server; placeholder, returns empty list

run_tool() routes each call to the correct backend transparently.
"""

import importlib
import pkgutil

import tool.scripts as _scripts_pkg
from tool.stdio.client import StdioClient
from tool.sse.client import SSEClient

# ---------------------------------------------------------------------------
# Source 1: scripts — auto-scan tool/scripts/ for modules with SCHEMA + run()
# ---------------------------------------------------------------------------

_script_tools: dict[str, object] = {}  # name → module

for _info in pkgutil.iter_modules(_scripts_pkg.__path__):
    _mod = importlib.import_module(f"tool.scripts.{_info.name}")
    if hasattr(_mod, "SCHEMA") and hasattr(_mod, "run"):
        _name = _mod.SCHEMA["function"]["name"]
        _script_tools[_name] = _mod

# ---------------------------------------------------------------------------
# Source 2: stdio — discover via MCP tools/list at startup
# ---------------------------------------------------------------------------

_stdio_client = StdioClient.instance()
_stdio_schemas: list[dict] = _stdio_client.list_tools()
_stdio_tool_names: set[str] = {s["function"]["name"] for s in _stdio_schemas}

# ---------------------------------------------------------------------------
# Source 3: sse — placeholder
# ---------------------------------------------------------------------------

_sse_client = SSEClient()
_sse_schemas: list[dict] = _sse_client.list_tools()
_sse_tool_names: set[str] = {s["function"]["name"] for s in _sse_schemas}

# ---------------------------------------------------------------------------
# Unified schema list (sent to the model on every call)
# ---------------------------------------------------------------------------

SCHEMAS: list[dict] = (
    [m.SCHEMA for m in _script_tools.values()]
    + _stdio_schemas
    + _sse_schemas
)

# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def run_tool(name: str, tool_input: dict) -> str:
    if name in _script_tools:
        return _script_tools[name].run(**tool_input)
    if name in _stdio_tool_names:
        return _stdio_client.call(name, tool_input)
    if name in _sse_tool_names:
        return _sse_client.call(name, tool_input)
    return f"error: unknown tool '{name}'"


def discovered_tools() -> dict[str, str]:
    """Return {tool_name: backend} for all registered tools. Useful for debugging."""
    result = {}
    for name in _script_tools:
        result[name] = "scripts"
    for name in _stdio_tool_names:
        result[name] = "stdio"
    for name in _sse_tool_names:
        result[name] = "sse"
    return result
