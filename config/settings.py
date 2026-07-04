import os

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("HARNESS_MODEL", "qwen3:8b")
MAX_TURNS = int(os.environ.get("HARNESS_MAX_TURNS", "10"))
AGENTS_MD_PATH = os.environ.get("AGENTS_MD_PATH", "agents.md")
PROJECTS_DIR   = os.environ.get("HARNESS_PROJECTS_DIR", "projects")
