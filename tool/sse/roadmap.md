# SSE tool roadmap

MCP SSE tools: connects to remote tool servers over HTTP + Server-Sent Events.
The client sends requests via HTTP POST; the server pushes responses via an SSE stream.

Use SSE for tools that live outside the harness process — third-party APIs, cloud
services, databases, or shared tool servers used across multiple agents.

**Current status: placeholder.** `SSEClient` returns an empty tool list. See
implementation steps below before adding any tools.

---

## How to add an SSE tool

SSE tools live on a remote (or local) MCP-compliant HTTP server, not inside the
harness. Adding one is a two-part process.

### Part A — implement the tool on the server

Stand up or extend an MCP SSE server. The server must handle:

- `GET /sse` — SSE event stream (keep-alive)
- `POST /messages` — receives JSON-RPC requests, sends responses via the SSE stream

Register your tool in the server's `tools/list` response:

```json
{
  "name": "my_remote_tool",
  "description": "One sentence description shown to the model.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "arg1": {"type": "string", "description": "What this arg does."}
    },
    "required": ["arg1"]
  }
}
```

And handle `tools/call` for it:

```json
// request
{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
 "params": {"name": "my_remote_tool", "arguments": {"arg1": "value"}}}

// response (via SSE stream)
{"jsonrpc": "2.0", "id": 1,
 "result": {"content": [{"type": "text", "text": "result string"}]}}
```

### Part B — implement SSEClient in the harness

`tool/sse/client.py` is currently a stub. Before any SSE tool works, implement:

1. `__init__`: open `GET /sse` SSE stream; POST `initialize` and read the handshake response.
2. `list_tools()`: POST `tools/list`; read response from SSE stream; convert MCP schemas to OpenAI format.
3. `call(name, arguments)`: POST `tools/call`; match response by `id`; return text content.

Recommended dependencies: `httpx` (async-capable HTTP) + `httpx-sse` (SSE stream parsing).

After `SSEClient` is functional, the registry picks up new tools automatically via
`list_tools()` at startup — no further changes needed in `registry.py`.

See [architecture.md](architecture.md) for the full protocol and message format.

---

## Implementation steps (for SSEClient itself)

1. Stand up an MCP-compliant HTTP server (FastAPI + `sse-starlette`).
2. Implement `GET /sse` for the event stream and `POST /messages` for requests.
3. Implement `initialize` / `tools/list` / `tools/call` handlers.
4. Update `SSEClient` in `client.py` to connect, handshake, and route calls.
5. Add server URL to `config/settings.py` (env var: `HARNESS_SSE_URL`).

---

## Planned servers

| Server | Tools | Notes |
|---|---|---|
| Notion connector | `search_notion`, `get_page`, `create_page` | Notion API key required |
| Linear connector | `list_issues`, `create_issue`, `update_issue` | Linear API key required |
| GitHub connector | `list_prs`, `get_issue`, `create_pr_comment` | GitHub token required |
| Confluence connector | `search_confluence`, `get_page` | Atlassian token required |
| Slack connector | `post_message`, `search_messages` | Slack bot token required |
