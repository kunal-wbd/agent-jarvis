# SSE tool roadmap

MCP SSE tools: connects to remote tool servers over HTTP + Server-Sent Events.
The client sends requests via HTTP POST; the server pushes responses via an SSE stream.

Use SSE for tools that live outside the harness process — third-party APIs, cloud
services, databases, or shared tool servers used across multiple agents.

## Planned servers

| Server | Tools | Notes |
|---|---|---|
| Notion connector | `search_notion`, `get_page`, `create_page` | Notion API key required |
| Linear connector | `list_issues`, `create_issue`, `update_issue` | Linear API key required |
| GitHub connector | `list_prs`, `get_issue`, `create_pr_comment` | GitHub token required |
| Confluence connector | `search_confluence`, `get_page` | Atlassian token required |
| Slack connector | `post_message`, `search_messages` | Slack bot token required |

## Implementation steps (when ready)

1. Stand up an MCP-compliant HTTP server (FastAPI + `sse-starlette`).
2. Implement `GET /sse` for the event stream and `POST /messages` for requests.
3. Implement `initialize` / `tools/list` / `tools/call` handlers.
4. Update `SSEClient` in `client.py` to connect, handshake, and route calls.
5. Register discovered tools in the unified registry.

## Protocol reference

MCP SSE transport spec: https://spec.modelcontextprotocol.io/specification/basic/transports/
