# Scripts tool backend — architecture

## What it is

The scripts backend is the simplest tool integration path: pure Python modules imported
directly into the harness process. No subprocess, no protocol, no network — just a
function call.

## How it fits into the harness

```
session/session.py
    │
    └── tool/registry.py  ← discovers scripts at import time
            │
            └── tool/scripts/<name>.py  ← your module
                    └── run(**kwargs) → str
```

At startup, `registry.py` uses `pkgutil.iter_modules` to scan this directory. Any
`.py` file that exposes both a `SCHEMA` constant and a `run()` function is
automatically registered. No manual registration required.

## Module contract

Every scripts tool is a self-contained Python module with exactly two public members:

### `SCHEMA`

An OpenAI function-call schema dict describing the tool to the model:

```python
SCHEMA = {
    "type": "function",
    "function": {
        "name": "tool_name",           # must be unique across all backends
        "description": "...",          # shown to the model — be precise
        "parameters": {
            "type": "object",
            "properties": {
                "arg1": {"type": "string", "description": "..."},
            },
            "required": ["arg1"],
        },
    },
}
```

### `run(**kwargs) -> str`

The function the registry calls when the model requests this tool. Arguments come
directly from the model's `tool_calls` output, matched by name to the schema
`properties`. Must return a plain string — the result is appended to `messages[]`
as a `tool` role message.

```python
def run(arg1: str) -> str:
    ...
    return result_as_string
```

## Data flow

```
model emits tool_call: {"name": "tool_name", "input": {"arg1": "value"}}
    │
    ▼
registry.run_tool("tool_name", {"arg1": "value"})
    │
    ▼
_script_tools["tool_name"].run(arg1="value")
    │
    ▼
returns str → appended to messages[] → sent to model on next turn
```

## When to use this backend

| Use scripts when... | Use stdio instead when... |
|---|---|
| Tool is stateless (no persistent resources) | Tool manages open file handles or DB connections |
| No subprocess or OS-level isolation needed | OS-level isolation is desirable |
| Logic is simple enough to run in-process | Tool does heavy I/O that shouldn't block the REPL |
| Stdlib or a small pure-Python dep is enough | Tool requires a complex dependency tree |

## Naming

Tool names are global across all backends. `registry.py` merges scripts, stdio, and
SSE into one flat namespace. Collisions are silently resolved — last writer wins. Use
a descriptive prefix (`scrape_`, `parse_`, `search_`) to avoid clashes.
