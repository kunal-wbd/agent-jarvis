"""
MCP SSE client — placeholder.

Will connect to remote MCP servers that expose tools over HTTP + Server-Sent Events.
The MCP SSE transport works as follows:
  - Client sends requests via HTTP POST to the server endpoint.
  - Server pushes responses (and server-initiated messages) via SSE stream.

Not yet implemented. See tool/sse/roadmap.md for planned servers and timeline.
"""

from __future__ import annotations


class SSEClient:
    """Placeholder MCP SSE client."""

    def list_tools(self) -> list[dict]:
        return []

    def call(self, name: str, arguments: dict) -> str:
        return f"error: SSE client not implemented (tool: {name})"
