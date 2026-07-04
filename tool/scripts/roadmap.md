# Scripts tool roadmap

Direct Python tool implementations. No subprocess, no protocol — imported and called
inline by the registry. Best for stateless, self-contained operations with no OS
resource management needed.

## Shipped

| Tool | File | Description |
|---|---|---|
| `scrape_url` | `scrape.py` | Fetch a URL and return visible text, HTML stripped |

## Planned

| Tool | Description | Notes |
|---|---|---|
| `search_web` | Query a search engine and return result snippets | Needs a search API key (Brave, SerpAPI, etc.) |
| `parse_pdf` | Extract text from a PDF file by path | Add `pypdf` dep |
| `parse_image` | OCR or describe an image at a path | Requires multimodal model or OCR lib |
| `diff_text` | Produce a unified diff between two strings | stdlib `difflib`, no deps |
| `render_markdown` | Convert markdown to plain text for display | stdlib only |

## Adding a script tool

1. Create `tool/scripts/<name>.py` with `SCHEMA` (OpenAI function format) and `run(**kwargs) -> str`.
2. The registry auto-discovers it — no further changes needed.
