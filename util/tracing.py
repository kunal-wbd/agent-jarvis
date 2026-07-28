"""One-time OTEL setup. Call init_tracing() once at startup (agent.py),
then use get_tracer() anywhere to create spans.

Spans are exported to Arize Phoenix over OTLP/HTTP. If Phoenix is not
running, tracing is skipped with a one-line notice rather than flooding
the terminal with connection-refused retries on every span batch.
"""

import urllib.error
import urllib.request

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from config.settings import PHOENIX_HOST, PHOENIX_PROJECT, TRACING_ENABLED

TRACES_PATH = "/v1/traces"

_initialised = False


def _phoenix_is_up(timeout: float = 1.0) -> bool:
    try:
        urllib.request.urlopen(PHOENIX_HOST, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True  # responding, just not with 200 — good enough
    except Exception:
        return False


def init_tracing(project_name: str = PHOENIX_PROJECT, quiet: bool = False) -> bool:
    """Wire up span export to Phoenix. Returns True if tracing is active.

    Safe to call more than once — later calls are no-ops.
    """
    global _initialised
    if _initialised:
        return True

    if not TRACING_ENABLED:
        if not quiet:
            print("[tracing] disabled (TRACING_ENABLED=0)")
        return False

    if not _phoenix_is_up():
        if not quiet:
            print(f"[tracing] Phoenix not reachable at {PHOENIX_HOST} — running without traces.")
            print("[tracing] Start it with:  phoenix serve")
        return False

    resource = Resource({
        "service.name": project_name,
        # Phoenix routes spans into projects by this attribute; without it
        # everything lands in the "default" project.
        "openinference.project.name": project_name,
    })
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=PHOENIX_HOST + TRACES_PATH))
    )
    trace.set_tracer_provider(provider)

    _initialised = True
    if not quiet:
        print(f"[tracing] → {PHOENIX_HOST}  (project: {project_name})")
    return True


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)


def flush() -> None:
    """Force-export any buffered spans. Useful before a short-lived process exits."""
    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush()
