# Stdio tool roadmap

MCP stdio tools: a local subprocess running `tool/stdio/server.py` that speaks
JSON-RPC 2.0 over stdin/stdout. The client (`tool/stdio/client.py`) spawns it once
at startup and reuses the process for the session lifetime.

Use stdio for tools that need OS-level resource access: filesystem, git, databases,
or any operation that benefits from running in a separate process.

---

## How to add a stdio tool

All changes happen in `tool/stdio/server.py` only. The client and registry pick up
new tools automatically via `tools/list` at startup.

**Step 1 — write the handler function:**

```python
def _my_tool(arg1: str, arg2: int = 0) -> str:
    # do the work
    return result_as_string   # must return str
```

**Step 2 — register it in `_TOOLS`:**

```python
_TOOLS = {
    # ... existing tools ...
    "my_tool": {
        "name": "my_tool",
        "description": "One sentence description shown to the model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "arg1": {"type": "string", "description": "What this arg does."},
                "arg2": {"type": "integer", "description": "Optional. Defaults to 0."},
            },
            "required": ["arg1"],   # list only the required args
        },
        "handler": _my_tool,
    },
}
```

**Step 3 — restart the harness.** `StdioClient` calls `tools/list` at startup; the
new tool appears automatically in `SCHEMAS` and is routable via `run_tool()`.

**Step 4 (if the tool has side effects)** — add its name to `SIDE_EFFECT_TOOLS` in
`permission/permission.py` so the user is prompted before it runs.

See [architecture.md](architecture.md) for the full protocol, message format, and
when to choose this backend over scripts.

---

## Shipped

| Tool | Description |
|---|---|
| `read_file` | Read file contents by path |
| `write_file` | Write or overwrite a file (creates parent dirs) |
| `list_dir` | List files and subdirectories |

---

## Planned

| Tool | Description | Notes |
|---|---|---|
| `move_file` | Rename or move a file | stdlib `shutil` |
| `delete_file` | Delete a file with confirmation | Requires permission gate update |
| `make_dir` | Create a directory tree | `os.makedirs` |
| `git_status` | Run `git status` in a project directory | subprocess → git |
| `git_diff` | Show uncommitted diff | subprocess → git |
| `git_log` | Recent commit log | subprocess → git |
| `grep_files` | Search file contents by pattern | stdlib `re` + `os.walk` |
| `run_shell` | Execute an arbitrary shell command | High-risk — requires explicit permission |
