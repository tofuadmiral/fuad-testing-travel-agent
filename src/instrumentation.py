import logging
import os
from contextlib import contextmanager

from opentelemetry.trace import get_tracer

log = logging.getLogger(__name__)

_tracer = None
_routing_enabled = False


def init() -> None:
    global _tracer, _routing_enabled
    if _tracer is not None:
        return

    api_key = os.getenv("ARIZE_API_KEY")
    if not api_key:
        log.warning(
            "ARIZE_API_KEY not set — tracing disabled, app will still serve requests"
        )
        _tracer = get_tracer("fuad-testing-travel-agent", "0.1.0")
        return

    from arize.otel import register_with_routing
    from openinference.instrumentation.anthropic import AnthropicInstrumentor

    tracer_provider = register_with_routing(api_key=api_key)
    AnthropicInstrumentor().instrument(tracer_provider=tracer_provider)
    _routing_enabled = True

    _tracer = get_tracer("fuad-testing-travel-agent", "0.1.0")
    log.info("Arize tracing initialized with per-request routing")


def tracer():
    if _tracer is None:
        init()
    return _tracer


@contextmanager
def routing(space_id: str | None, project_name: str | None):
    """Route any spans started inside this block to the given Arize space/project.

    Both must be provided for spans to be exported. If either is missing, falls
    back to env defaults; if those are missing too, spans are dropped (per
    arize-otel routing semantics).
    """
    space_id = space_id or os.getenv("ARIZE_SPACE_ID")
    project_name = project_name or os.getenv("ARIZE_PROJECT_NAME", "fuad-testing-travel-agent")

    if not _routing_enabled or not space_id or not project_name:
        yield
        return

    from arize.otel import set_routing_context

    with set_routing_context(space_id=space_id, project_name=project_name):
        yield
