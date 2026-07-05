# SSE tool backend — architecture

## What it is

The SSE backend connects to remote MCP servers over HTTP. The client sends requests
via HTTP POST; the server pushes responses (and server-initiated messages) via a
Server-Sent Events stream. This is the MCP SSE transport.

**Current status: placeholder.** `SSEClient` returns an empty tool list and errors on
any call. See the roadmap for implementation steps.

## Intended process model

```
harness process (agent.py)
    │
    └── tool/sse/client.py  (SSEClient)
            │  HTTP POST (requests) + SSE stream (responses)
            ▼
        Remote MCP server  (separate host or localhost)
            ├── GET  /sse       ← SSE event stream (server → client)
            └── POST /messages  ← tool requests (client → server)
```

Unlike stdio, the SSE server is not spawned by the harness. It runs independently —
on localhost, a container, or a remote host — and the client connects to it at startup.
Multiple harness instances can share one SSE server.

## Intended startup sequence

```
registry.py imported
    │
    └── SSEClient()
            │
            ├── GET /sse  → open SSE stream (keep-alive connection)
            │
            └── POST /messages → initialize
                    ├── → {protocolVersion, clientInfo, capabilities}
                    └── ← {protocolVersion, serverInfo, capabilities}  (via SSE)
```

After the handshake, the client sends `tools/list` and the registry merges the
returned schemas into the unified namespace alongside scripts and stdio tools.

## Message format

MCP SSE uses the same JSON-RPC 2.0 envelope as stdio, but transported differently:

**Request (HTTP POST to `/messages`):**
```
POST /messages HTTP/1.1
Content-Type: application/json

{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_page", "arguments": {"page_id": "abc123"}}}
```

**Response (SSE event on `/sse` stream):**
```
event: message
data: {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "page content"}]}}
```

The SSE stream also carries server-initiated events (e.g., resource change
notifications) that don't correspond to a client request — these have no `id`.

## Tool definition format

Same MCP `inputSchema` format as stdio. The client converts to OpenAI format before
passing to the registry:

```python
# MCP format (returned by tools/list)
{
    "name": "get_page",
    "description": "Fetch a Notion page by ID.",
    "inputSchema": {
        "type": "object",
        "properties": {"page_id": {"type": "string"}},
        "required": ["page_id"],
    },
}
```

## When to use this backend

| Use SSE when... | Use stdio instead when... |
|---|---|
| Tool lives in a remote service (Notion, Linear, Slack) | Tool only needs local OS access |
| Multiple agents or sessions share one tool server | Isolation via subprocess is sufficient |
| Server needs to push notifications to the client | Request/response is all you need |
| Tool server is written in a different language | Python subprocess is fine |

## Protocol reference

MCP SSE transport specification:
https://spec.modelcontextprotocol.io/specification/basic/transports/
