from dataclasses import dataclass
from typing import Any


@dataclass
class Event:
    type: str  # "text" | "tool_call" | "tool_result" | "max_turns"
    data: dict[str, Any]
