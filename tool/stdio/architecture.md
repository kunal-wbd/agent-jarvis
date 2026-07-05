# Stdio tool backend — architecture

## What it is

The stdio backend runs a separate Python process (`tool/stdio/server.py`) that speaks
JSON-RPC 2.0 over stdin/stdout. The harness communicates with it over pipes. This is
the Model Context Protocol (MCP) stdio transport.

## Process model

```
harness process (agent.py)
    │
    └── tool/stdio/client.py  (StdioClient singleton)
            │  JSON-RPC over stdin/stdout pipes
            ▼
        tool/stdio/server.py  (subprocess, one per harness run)
            ├── read_file handler
            ├── write_file handler
            └── list_dir handler
```

`StdioClient` is a singleton — the subprocess is spawned once at registry import time
and kept alive for the full session. All calls in a session reuse the same process.

## Startup sequence

```
registry.py imported
    │
    └── StdioClient.instance()
            │
            ├── subprocess.Popen([python, -m, tool.stdio.server], stdin/stdout pipes)
            │
            └── _handshake()
                    ├── → initialize (JSON-RPC)
                    ├── ← {protocolVersion, serverInfo, capabilities}
                    └── → notifications/initialized (no response)
```

After the handshake, the client calls `tools/list` and the registry merges the
returned schemas into the unified tool namespace.

## Message format

Every message is a newline-delimited JSON object (NDJSON). No framing headers.

**Request:**
```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "read_file", "arguments": {"path": "foo.txt"}}}
```

**Response:**
```json
{"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "file contents here"}]}}
```

**Error response:**
```json
{"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "unknown tool: bad_name"}}
```

## Tool definition format

Tools are registered in `server.py`'s `_TOOLS` dict using MCP's `inputSchema` format
(not OpenAI's `parameters` format). The client converts to OpenAI format when
returning schemas to the registry:

```python
# MCP format (used inside server.py)
{
    "name": "read_file",
    "description": "Read the contents of a file by path.",
    "inputSchema": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
    "handler": _read_file,   # Python callable — not sent over the wire
}
```

`_mcp_to_openai_schema()` in `client.py` converts `inputSchema` → `parameters` before
the registry merges it with the scripts and SSE schemas.

## Data flow for a tool call

```
model emits tool_call: {"name": "read_file", "input": {"path": "foo.txt"}}
    │
    ▼
registry.run_tool("read_file", {"path": "foo.txt"})
    │
    ▼
StdioClient.call("read_file", {"path": "foo.txt"})
    │  JSON-RPC → stdin pipe
    ▼
server.py _handle_tools_call()
    │
    ▼
_read_file(path="foo.txt") → "file contents"
    │  JSON-RPC ← stdout pipe
    ▼
StdioClient returns str → registry returns str → appended to messages[]
```

## Thread safety

`StdioClient` uses a `threading.Lock` (`_call_lock`) around every `_send()` call.
The protocol is strictly request/response with integer IDs, so only one in-flight
request at a time is safe. This is sufficient because the agent loop is single-threaded.

## When to use this backend

| Use stdio when... | Use scripts instead when... |
|---|---|
| Tool needs OS-level isolation | Tool is a simple stateless function |
| Tool manages persistent resources (DB conn, file handles) | No subprocess overhead needed |
| Tool may produce errors that should not crash the harness | Tool uses only stdlib or light deps |
| Following MCP protocol matters (e.g., interop with other MCP clients) | Speed matters more than isolation |
