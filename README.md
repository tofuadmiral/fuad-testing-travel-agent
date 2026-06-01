# fuad-testing-travel-agent

A small travel-planning agent built on the [Claude Agent SDK](https://docs.claude.com/en/agent-sdk/python), exposed as a public HTTP endpoint and traced into [Arize AX](https://arize.com/docs/ax). Used as a test target for agent endpoint experiments.

## What it does

`POST /invoke` takes a travel goal, runs a Claude orchestrator that sequentially calls four tools:

1. `search_flights`
2. `search_hotels`
3. `get_weather_forecast`
4. `propose_itinerary`

…and returns the final plan plus a trace ID. Tool outputs are mocked (deterministic per-input) so test runs are reproducible.

## Live URL

Once deployed to Render: `https://fuad-testing-travel-agent.onrender.com`

```bash
curl -sS https://fuad-testing-travel-agent.onrender.com/healthz
curl -sS -X POST https://fuad-testing-travel-agent.onrender.com/invoke \
  -H 'Content-Type: application/json' \
  -d '{"goal": "Plan a 3-day trip to Tokyo from SF in October"}' | jq
```

Authentication is **optional**. If `API_KEY` is set on the server, callers can present `Authorization: Bearer <API_KEY>`; requests without it are still accepted (and logged).

## Arize Agent Replay integration

The endpoint reads `x-arize-experiment-id` and `x-arize-experiment-run-id` headers and stamps them as span attributes on the CHAIN span, so traces link back to the experiment run in Arize.

In Arize UI: Space Settings → Agents → New Agent Configuration → endpoint = this URL, auth = bearer with `API_KEY`.

## Local development

```bash
cd ~/projects/fuad-testing-travel-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Install the Claude CLI (required by claude-agent-sdk subprocess model)
npm install -g @anthropic-ai/claude-code

cp .env.example .env
# fill in ANTHROPIC_API_KEY, ARIZE_SPACE_ID, ARIZE_API_KEY

uvicorn src.main:app --reload
```

Then in another terminal:

```bash
curl -sS -X POST http://localhost:8000/invoke \
  -H 'Content-Type: application/json' \
  -d '{"goal": "Weekend in NYC"}' | jq
```

## Deployment (Render)

Connected to GitHub → auto-deploys on push to `main`. Blueprint is in `render.yaml`.

One-time setup:
1. Render dashboard → New → Blueprint → connect this repo.
2. Set secret env vars (marked `sync: false` in `render.yaml`): `ANTHROPIC_API_KEY`, `ARIZE_SPACE_ID`, `ARIZE_API_KEY`, `API_KEY`.
3. Deploy. Render serves from `https://<service>.onrender.com`.

## File layout

```
src/
  main.py             FastAPI app, /invoke + /healthz, auth dep, header capture
  orchestrator.py     Claude Agent SDK setup, CHAIN span, sequential tool flow
  tools.py            4 mocked tools, each emits a TOOL span
  instrumentation.py  arize-otel register() + Anthropic instrumentor
  auth.py             Optional bearer auth (never 401s)
```
