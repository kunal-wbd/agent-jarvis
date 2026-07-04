import re
import urllib.request
from urllib.error import URLError

SCHEMA = {
    "type": "function",
    "function": {
        "name": "scrape_url",
        "description": (
            "Fetch a web page by URL and return its visible text content, "
            "stripped of HTML tags. Use to read articles, documentation, or "
            "any publicly accessible web page."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch."},
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to return. Defaults to 4000.",
                },
            },
            "required": ["url"],
        },
    },
}


def run(url: str, max_chars: int = 4000) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "harness/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            encoding = resp.headers.get_content_charset() or "utf-8"
            html = raw.decode(encoding, errors="replace")
    except URLError as e:
        return f"error fetching {url}: {e}"
    except Exception as e:
        return f"error: {e}"

    # strip script/style blocks entirely
    html = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", html)
    # strip remaining tags
    text = re.sub(r"<[^>]+>", " ", html)
    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > max_chars:
        text = text[:max_chars] + f"\n[truncated — {len(text)} chars total]"
    return text
