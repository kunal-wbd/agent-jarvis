import json

import ollama
from openinference.semconv.trace import SpanAttributes
from opentelemetry import trace

from config.settings import MODEL, OLLAMA_HOST
from util.tracing import get_tracer

_client = ollama.Client(host=OLLAMA_HOST)
_tracer = get_tracer("provider.ollama")


class ModelResponse:
    def __init__(self, text: str, tool_calls: list[dict]):
        self.text = text
        self.tool_calls = tool_calls  # [{"id": str, "name": str, "input": dict}]


def complete(messages: list[dict], tools: list[dict] | None = None) -> ModelResponse:
    with _tracer.start_as_current_span("llm") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "LLM")
        span.set_attribute(SpanAttributes.LLM_MODEL_NAME, MODEL)
        span.set_attribute(SpanAttributes.INPUT_VALUE, json.dumps(messages))

        result = _client.chat(
            model=MODEL,
            messages=messages,
            tools=tools or [],
        )

        message = result["message"]
        tool_calls = []
        for i, call in enumerate(message.get("tool_calls") or []):
            tool_calls.append(
                {
                    "id": f"call_{i}",
                    "name": call["function"]["name"],
                    "input": call["function"]["arguments"],
                }
            )

        response = ModelResponse(text=message.get("content", ""), tool_calls=tool_calls)

        span.set_attribute(SpanAttributes.OUTPUT_VALUE, response.text)
        span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_PROMPT, result.get("prompt_eval_count", 0))
        span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_COMPLETION, result.get("eval_count", 0))
        if span.is_recording():
            span.set_status(trace.StatusCode.OK)

        return response
