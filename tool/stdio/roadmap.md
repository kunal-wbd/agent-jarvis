# Stdio tool roadmap

MCP stdio tools: a local subprocess running `tool/stdio/server.py` that speaks
JSON-RPC 2.0 over stdin/stdout. The client (`tool/stdio/client.py`) spawns it once
at startup and reuses the process for the session lifetime.

Use stdio for tools that need OS-level resource access: filesystem, git, databases,
or any operation that benefits from running in a separate process.

## Shipped

| Tool | Description |
|---|---|
| `read_file` | Read file contents by path |
| `write_file` | Write or overwrite a file (creates parent dirs) |
| `list_dir` | List files and subdirectories |

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

## Architecture note

The stdio server is a single process. Adding a tool means:
1. Add a handler function in `server.py`.
2. Register it in `_TOOLS` with its `inputSchema`.
3. The client picks it up automatically via `tools/list` at next startup.

No changes needed in the registry or session layer.
