import json
import random
from typing import Any

from claude_agent_sdk import tool

from .instrumentation import tracer

TOOL_CALLS: list[dict[str, Any]] = []


def _seeded(args: dict[str, Any]) -> random.Random:
    return random.Random(json.dumps(args, sort_keys=True))


def _record(name: str, args: dict[str, Any], result: dict[str, Any]) -> None:
    TOOL_CALLS.append({"name": name, "input": args, "output": result})


def _wrap(name: str, args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    span = tracer().start_span(name)
    try:
        span.set_attribute("openinference.span.kind", "TOOL")
        span.set_attribute("tool.name", name)
        span.set_attribute("input.value", json.dumps(args))
        span.set_attribute("output.value", json.dumps(result))
    finally:
        span.end()
    _record(name, args, result)
    return {"content": [{"type": "text", "text": json.dumps(result)}]}


@tool(
    "search_flights",
    "Search round-trip flights. Returns 3 options sorted by price.",
    {"origin": str, "destination": str, "depart_date": str, "return_date": str},
)
async def search_flights(args: dict[str, Any]) -> dict[str, Any]:
    rng = _seeded(args)
    airlines = ["United", "Delta", "ANA", "JAL", "Singapore", "American"]
    base = rng.randint(450, 1400)
    flights = [
        {
            "airline": rng.choice(airlines),
            "price_usd": base + i * rng.randint(40, 220),
            "depart": f"{args['depart_date']} {rng.randint(6, 22):02d}:{rng.choice(['00', '15', '30', '45'])}",
            "return": f"{args['return_date']} {rng.randint(6, 22):02d}:{rng.choice(['00', '15', '30', '45'])}",
            "stops": rng.choice([0, 0, 1]),
            "id": f"FL-{rng.randint(1000, 9999)}",
        }
        for i in range(3)
    ]
    return _wrap(
        "search_flights",
        args,
        {"origin": args["origin"], "destination": args["destination"], "flights": flights},
    )


@tool(
    "search_hotels",
    "Search hotels in a city for given check-in/out dates.",
    {"city": str, "checkin": str, "checkout": str},
)
async def search_hotels(args: dict[str, Any]) -> dict[str, Any]:
    rng = _seeded(args)
    names = ["Park Hyatt", "The Peninsula", "Andaz", "Conrad", "Aman", "Hoshinoya", "Ritz-Carlton"]
    hotels = [
        {
            "name": f"{rng.choice(names)} {args['city']}",
            "nightly_usd": rng.randint(220, 880),
            "rating": round(rng.uniform(4.0, 4.9), 1),
            "id": f"HT-{rng.randint(1000, 9999)}",
        }
        for _ in range(3)
    ]
    return _wrap("search_hotels", args, {"city": args["city"], "hotels": hotels})


@tool(
    "get_weather_forecast",
    "Get daily weather forecast for a city across a date range.",
    {"city": str, "start_date": str, "end_date": str},
)
async def get_weather_forecast(args: dict[str, Any]) -> dict[str, Any]:
    rng = _seeded(args)
    conditions = ["sunny", "partly cloudy", "cloudy", "light rain", "clear"]
    days = []
    for i in range(3):
        days.append(
            {
                "date_offset": i,
                "high_f": rng.randint(58, 82),
                "low_f": rng.randint(45, 68),
                "condition": rng.choice(conditions),
            }
        )
    return _wrap("get_weather_forecast", args, {"city": args["city"], "forecast": days})


@tool(
    "propose_itinerary",
    "Synthesize the final day-by-day itinerary from selected flights, hotel, and weather.",
    {
        "destination": str,
        "flight_id": str,
        "hotel_id": str,
        "days": int,
        "highlights": list,
    },
)
async def propose_itinerary(args: dict[str, Any]) -> dict[str, Any]:
    days = []
    for i in range(args["days"]):
        days.append(
            {
                "day": i + 1,
                "morning": args["highlights"][i % len(args["highlights"])]
                if args["highlights"]
                else "explore neighborhood",
                "afternoon": "local lunch + museum or park",
                "evening": "dinner reservation",
            }
        )
    return _wrap(
        "propose_itinerary",
        args,
        {
            "destination": args["destination"],
            "flight_id": args["flight_id"],
            "hotel_id": args["hotel_id"],
            "days": days,
        },
    )


ALL_TOOLS = [search_flights, search_hotels, get_weather_forecast, propose_itinerary]
