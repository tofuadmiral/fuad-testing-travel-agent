import logging
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from . import instrumentation

instrumentation.init()

from .auth import optional_bearer_auth
from .orchestrator import run_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="fuad-testing-travel-agent", version="0.1.0")


@app.exception_handler(RequestValidationError)
async def log_422(request: Request, exc: RequestValidationError):
    body = await request.body()
    log.warning(
        "422 on %s: errors=%s raw_body=%r headers=%s",
        request.url.path,
        exc.errors(),
        body[:2000],
        dict(request.headers),
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvokeRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    goal: str | None = None
    input: str | dict | None = None
    config: dict | None = None
    arize_metadata: dict | None = None


@app.get("/healthz")
async def healthz():
    return {"ok": True, "service": "fuad-testing-travel-agent"}


@app.get("/")
async def root():
    return {
        "service": "fuad-testing-travel-agent",
        "endpoints": ["/healthz", "/invoke"],
        "docs": "/docs",
    }


@app.post("/invoke")
async def invoke(
    req: InvokeRequest,
    authed: bool = Depends(optional_bearer_auth),
    x_arize_experiment_id: str | None = Header(default=None, alias="x-arize-experiment-id"),
    x_arize_experiment_run_id: str | None = Header(
        default=None, alias="x-arize-experiment-run-id"
    ),
    baggage_header: str | None = Header(default=None, alias="baggage"),
):
    goal: str | None = None
    config: dict | None = req.config
    if isinstance(req.input, dict):
        goal = req.input.get("goal") or req.input.get("input")
        if not config:
            config = req.input.get("config")
    elif isinstance(req.input, str):
        goal = req.input
    goal = req.goal or goal

    if not goal:
        raise HTTPException(status_code=400, detail="provide `goal` or `input`")

    md = req.arize_metadata or {}
    exp_id = x_arize_experiment_id or md.get("experiment_id")
    run_id = x_arize_experiment_run_id or md.get("run_id")

    space_id, project_name = _resolve_routing(md, baggage_header)

    log.info(
        "invoke: goal=%r authed=%s experiment_id=%s run_id=%s",
        goal[:80],
        authed,
        exp_id,
        run_id,
    )
    return await run_agent(
        goal=goal,
        config=config,
        experiment_id=exp_id,
        experiment_run_id=run_id,
        space_id=space_id,
        project_name=project_name,
    )


def _resolve_routing(md: dict, baggage_header: str | None) -> tuple[str | None, str | None]:
    """Pick the Arize space_id + project_name for this request.

    Priority:
      1. arize_metadata.space_id / arize_metadata.project_name (request body)
      2. W3C baggage header: `arize.space_id=...,arize.project_name=...`
      3. None — caller falls back to env defaults
    """
    space_id = md.get("space_id")
    project_name = md.get("project_name")

    if not (space_id and project_name) and baggage_header:
        bag = _parse_baggage(baggage_header)
        space_id = space_id or bag.get("arize.space_id") or bag.get("space_id")
        project_name = (
            project_name or bag.get("arize.project_name") or bag.get("project_name")
        )

    return space_id, project_name


def _parse_baggage(header: str) -> dict[str, str]:
    """Parse W3C baggage header: `key1=value1,key2=value2; metadata`."""
    from urllib.parse import unquote

    out: dict[str, str] = {}
    for entry in header.split(","):
        entry = entry.strip().split(";", 1)[0]
        if "=" not in entry:
            continue
        k, v = entry.split("=", 1)
        out[unquote(k.strip())] = unquote(v.strip())
    return out
