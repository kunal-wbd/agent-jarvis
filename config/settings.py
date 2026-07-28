import os

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("HARNESS_MODEL", "qwen3:8b")
MAX_TURNS = int(os.environ.get("HARNESS_MAX_TURNS", "10"))
AGENTS_MD_PATH = os.environ.get("AGENTS_MD_PATH", "agents.md")
PROJECTS_DIR   = os.environ.get("HARNESS_PROJECTS_DIR", "PRD")

# Tracing — Phoenix collector. TRACING_ENABLED=0 turns tracing off entirely.
PHOENIX_HOST    = os.environ.get("PHOENIX_HOST", "http://localhost:6006")
PHOENIX_PROJECT = os.environ.get("PHOENIX_PROJECT", "harness")
TRACING_ENABLED = os.environ.get("TRACING_ENABLED", "1") != "0"
