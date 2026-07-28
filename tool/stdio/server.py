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

from memory.store import load_project_history


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

_MAX_MSG_CHARS = 2000


def _read_sessions(project: str, max_chars: int = 20000) -> str:
    """Return every past conversation for a project, oldest first.

    Only user and assistant turns are included — the system prompt is
    boilerplate and tool results are mostly noise for knowledge extraction.
    """
    try:
        history = load_project_history(project)
    except Exception as e:
        return f"error reading sessions: {e}"

    if not history:
        return f"No recorded conversations for project '{project}'."

    rendered = [r for r in (_render_session(s) for s in history) if r]
    if not rendered:
        return f"No conversation content recorded for project '{project}'."

    # Fill the budget newest-first so recent decisions survive truncation,
    # then flip back to chronological order for the model to read.
    kept, total = [], 0
    for block in reversed(rendered):
        if kept and total + len(block) > max_chars:
            break
        kept.append(block[:max_chars])
        total += len(block)
    kept.reverse()

    header = f"# Conversation history for '{project}' ({len(kept)} sessions, oldest first)"
    dropped = len(rendered) - len(kept)
    if dropped:
        header += f"\n\n[{dropped} earlier session(s) omitted — {max_chars} char limit]"
    return header + "\n\n" + "\n\n---\n\n".join(kept)


def _render_session(session: dict) -> str:
    """Format one session as text. Returns '' if it has no usable turns."""
    lines = []
    for m in session["messages"]:
        if m["role"] not in ("user", "assistant"):
            continue
        text = (m.get("content") or "").strip()
        if not text:
            continue
        if len(text) > _MAX_MSG_CHARS:
            text = text[:_MAX_MSG_CHARS] + " [...truncated]"
        lines.append(f"{m['role'].upper()}: {text}")

    if not lines:
        return ""
    return f"## Session {session['date']} ({session['id']})\n\n" + "\n\n".join(lines)


def _llm_ingest(path: str) -> str:
    """ Ingests source document into LLM Wiki 
    Usage:
    python tools/ingest.py <path-to-source>
    python tools/ingest.py raw/articles/my-article.md
    python tools/ingest.py report.pdf                  # auto-converts to .md
    python tools/ingest.py slides.pptx notes.docx       # batch, mixed formats
    python tools/ingest.py raw/mixed/ --no-convert      # skip auto-conversion
    python tools/ingest.py --validate-only              # run validation only

    Supported formats (auto-converted via markitdown):
        .pdf .docx .pptx .xlsx .html .htm .txt .csv .json .xml
        .rst .rtf .epub .ipynb .yaml .yml .tsv .wav .mp3

    The LLM reads the source, extracts knowledge, and updates the wiki:
    - Creates wiki/sources/<slug>.md
    - Updates wiki/index.md
    - Updates wiki/overview.md (if warranted)
    - Creates/updates entity and concept pages
    - Appends to wiki/log.md
    - Flags contradictions
    - Runs post-ingest validation (broken links, index coverage)
    """
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    paths_to_process = []
    

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
    "read_sessions": {
        "name": "read_sessions",
        "description": (
            "Read every past conversation recorded for a project, across all dates, "
            "oldest first. Use this to build or update the project's wiki from what "
            "was actually discussed. Returns user and assistant turns only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name, e.g. 'checkout'. This is the /project name, not a path.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Cap on total returned characters. Defaults to 20000.",
                },
            },
            "required": ["project"],
        },
        "handler": _read_sessions,
    },
    # llm_ingest is unregistered while _llm_ingest is still a stub — it returns
    # None, which breaks the client's result join. Re-add this entry once the
    # handler returns a string. See TODO.md.
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
