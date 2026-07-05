# Scripts tool roadmap

Direct Python tool implementations. No subprocess, no protocol — imported and called
inline by the registry. Best for stateless, self-contained operations with no OS
resource management needed.

---

## How to add a scripts tool

1. Create `tool/scripts/<name>.py` with a `SCHEMA` constant and a `run()` function.

   ```python
   # tool/scripts/my_tool.py

   SCHEMA = {
       "type": "function",
       "function": {
           "name": "my_tool",
           "description": "One sentence description shown to the model.",
           "parameters": {
               "type": "object",
               "properties": {
                   "input": {"type": "string", "description": "What this arg does."},
               },
               "required": ["input"],
           },
       },
   }

   def run(input: str) -> str:
       # do the work
       return result
   ```

2. That's it. The registry auto-discovers it on the next harness startup — no edits to
   `registry.py` or any other file.

3. If the tool has side effects (writes files, sends requests that mutate state), add its
   name to `SIDE_EFFECT_TOOLS` in `permission/permission.py` so the user is prompted
   before it runs.

See [architecture.md](architecture.md) for the full module contract and when to choose
this backend over stdio.

---

## Shipped

| Tool | File | Description |
|---|---|---|
| `scrape_url` | `scrape.py` | Fetch a URL and return visible text, HTML stripped |

---

## Planned

| Tool | Description | Notes |
|---|---|---|
| `search_web` | Query a search engine and return result snippets | Needs a search API key (Brave, SerpAPI, etc.) |
| `parse_pdf` | Extract text from a PDF file by path | Add `pypdf` dep |
| `parse_image` | OCR or describe an image at a path | Requires multimodal model or OCR lib |
| `diff_text` | Produce a unified diff between two strings | stdlib `difflib`, no deps |
| `render_markdown` | Convert markdown to plain text for display | stdlib only |
