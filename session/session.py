import json
from collections.abc import Iterator

from openinference.semconv.trace import SpanAttributes
from opentelemetry import trace

from config.settings import MAX_TURNS
from permission.permission import check
from provider.ollama import complete
from session.event import Event
from session.system import load_system_prompt
from tool.registry import SCHEMAS, run_tool
from util.tracing import get_tracer

_tracer = get_tracer("session")


class Session:
    def __init__(self):
        self.system_prompt = load_system_prompt()
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def set_system_prompt(self, text: str) -> None:
        self.system_prompt = text
        self.messages[0] = {"role": "system", "content": text}

    def send(self, user_message: str) -> Iterator[Event]:
        self.messages.append({"role": "user", "content": user_message})

        with _tracer.start_as_current_span("chain") as root:
            root.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
            root.set_attribute(SpanAttributes.INPUT_VALUE, user_message)

            for _ in range(MAX_TURNS):
                response = complete(self.messages, tools=SCHEMAS)
                self.messages.append({"role": "assistant", "content": response.text})

                if not response.tool_calls:
                    root.set_attribute(SpanAttributes.OUTPUT_VALUE, response.text)
                    root.set_status(trace.StatusCode.OK)
                    yield Event("text", {"text": response.text})
                    return

                if response.text:
                    yield Event("text", {"text": response.text})

                for call in response.tool_calls:
                    yield Event("tool_call", {"name": call["name"], "input": call["input"]})

                    with _tracer.start_as_current_span("tool") as tool_span:
                        tool_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "TOOL")
                        tool_span.set_attribute(SpanAttributes.TOOL_NAME, call["name"])
                        tool_span.set_attribute(SpanAttributes.INPUT_VALUE, json.dumps(call["input"]))

                        if not check(call["name"], call["input"]):
                            result = f"denied: {call['name']} requires permission"
                            tool_span.set_status(trace.StatusCode.ERROR, result)
                        else:
                            result = run_tool(call["name"], call["input"])
                            tool_span.set_attribute(SpanAttributes.OUTPUT_VALUE, result)
                            tool_span.set_status(trace.StatusCode.OK)

                    self.messages.append({"role": "tool", "content": result})
                    yield Event("tool_result", {"name": call["name"], "result": result})

            root.set_status(trace.StatusCode.ERROR, "max turns reached")
            yield Event("max_turns", {})
