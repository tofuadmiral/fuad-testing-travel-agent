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
    )
