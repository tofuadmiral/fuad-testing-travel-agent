import logging
import os

from opentelemetry.trace import get_tracer

log = logging.getLogger(__name__)

_tracer = None


def init() -> None:
    global _tracer
    if _tracer is not None:
        return

    space_id = os.getenv("ARIZE_SPACE_ID")
    api_key = os.getenv("ARIZE_API_KEY")
    project = os.getenv("ARIZE_PROJECT_NAME", "fuad-testing-travel-agent")

    if not space_id or not api_key:
        log.warning(
            "ARIZE_SPACE_ID / ARIZE_API_KEY not set — tracing disabled, app will still serve requests"
        )
        _tracer = get_tracer("fuad-testing-travel-agent", "0.1.0")
        return

    from arize.otel import register
    from openinference.instrumentation.anthropic import AnthropicInstrumentor

    register(
        space_id=space_id,
        api_key=api_key,
        project_name=project,
    )
    AnthropicInstrumentor().instrument()

    _tracer = get_tracer("fuad-testing-travel-agent", "0.1.0")
    log.info("Arize tracing initialized for project=%s", project)


def tracer():
    if _tracer is None:
        init()
    return _tracer
