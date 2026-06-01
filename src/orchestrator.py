import os
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    query,
)

from .instrumentation import tracer
from .tools import ALL_TOOLS, tool_calls_var

SYSTEM_PROMPT = """You are a travel planning agent.

For every user goal, you MUST use the available tools in this order:
  1. search_flights — find round-trip options
  2. search_hotels — find lodging in the destination city
  3. get_weather_forecast — check weather for the dates
  4. propose_itinerary — synthesize a final day-by-day plan

Pick the cheapest reasonable flight, the highest-rated hotel under $600/night
if possible, and call propose_itinerary with 3 highlights tailored to the goal.

After propose_itinerary returns, write a short final summary for the traveler.
"""

_mcp_server = create_sdk_mcp_server(
    name="travel",
    version="1.0.0",
    tools=ALL_TOOLS,
)

_ALLOWED_TOOLS = [
    "mcp__travel__search_flights",
    "mcp__travel__search_hotels",
    "mcp__travel__get_weather_forecast",
    "mcp__travel__propose_itinerary",
]


async def run_agent(
    goal: str,
    config: dict[str, Any] | None = None,
    experiment_id: str | None = None,
    experiment_run_id: str | None = None,
) -> dict[str, Any]:
    tool_calls: list[dict[str, Any]] = []
    tool_calls_var.set(tool_calls)
    cfg = config or {}
    model = cfg.get("model", os.getenv("DEFAULT_MODEL", "claude-sonnet-4-5"))
    max_turns = int(cfg.get("max_turns", 12))

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"travel": _mcp_server},
        allowed_tools=_ALLOWED_TOOLS,
        max_turns=max_turns,
        model=model,
        permission_mode="bypassPermissions",
    )

    final_text_parts: list[str] = []
    result_text: str | None = None
    trace_id: str | None = None

    with tracer().start_as_current_span("run_agent") as chain_span:
        chain_span.set_attribute("openinference.span.kind", "CHAIN")
        chain_span.set_attribute("input.value", goal)
        chain_span.set_attribute("agent.model", model)
        if experiment_id:
            chain_span.set_attribute("arize.experiment.id", experiment_id)
        if experiment_run_id:
            chain_span.set_attribute("arize.experiment.run.id", experiment_run_id)
        trace_id = format(chain_span.get_span_context().trace_id, "032x")

        async for message in query(prompt=goal, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        final_text_parts.append(block.text)
            elif isinstance(message, ResultMessage):
                result_text = getattr(message, "result", None)

        final = result_text or "\n".join(final_text_parts).strip()
        chain_span.set_attribute("output.value", final or "")

    itinerary = next(
        (c["output"] for c in reversed(tool_calls) if c["name"] == "propose_itinerary"),
        None,
    )

    return {
        "final_response": final,
        "itinerary": itinerary,
        "tool_calls": list(tool_calls),
        "trace_id": trace_id,
        "model": model,
    }
