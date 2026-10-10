"""
SigEnergy Optimizer — FastAPI application entry point.

Starts three background tasks:
  1. HAWebSocketClient  — subscribes to HA state_changed events, pushes entity
                          IDs into optimizer.trigger_queue
  2. SigEnergyOptimizer — event-driven loop that reads from trigger_queue and
                          runs _tick(); falls back to a 60 s heartbeat if the
                          WebSocket is disconnected
  3. DecisionTraceStore  — passive 15-minute persistence of existing trace rows
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .ha_client import HAClient
from .ha_ws_client import HAWebSocketClient
from .optimizer import SigEnergyOptimizer
from .decision_trace_store import DecisionTraceStore
from .routers.ui import ui
from .routers.api import router as api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def _parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _read_source_commit() -> str:
    p = Path("/app/.source_commit")
    try:
        if p.exists():
            return p.read_text(encoding="utf-8").strip() or "unknown"
    except Exception:
        pass
    return "unknown"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SigEnergy Optimizer")
    logger.info("Container source commit=%s", _read_source_commit())

    ha = HAClient(settings.ha_url, settings.ha_token)
    optimizer = SigEnergyOptimizer(ha, settings)
    logger.info(
        "Runtime signature=%s morning_slow_charge_runtime_disabled=%s",
        getattr(optimizer, "runtime_signature", "unknown"),
        bool(getattr(optimizer, "_morning_slow_charge_runtime_disabled", False)),
    )

    # Wire the WebSocket client so it feeds the optimizer's trigger queue
    ws_client = HAWebSocketClient(
        ha_url=settings.ha_url,
        token=settings.ha_token,
        trigger_queue=optimizer.trigger_queue,
        watch_entities=optimizer.get_watch_entities(),
        on_connect=optimizer.on_ws_connect,
        on_disconnect=optimizer.on_ws_disconnect,
        on_state_observation=optimizer.on_provider_state_observation,
    )

    app.state.ha = ha
    app.state.optimizer = optimizer
    app.state.ws_client = ws_client

    # Start both tasks concurrently
    optimizer_task = asyncio.create_task(optimizer.run_forever(), name="optimizer")
    ws_task = asyncio.create_task(ws_client.run_forever(), name="ha_websocket")

    app.state.optimizer_task = optimizer_task
    app.state.ws_task = ws_task

    trace_store = None
    trace_task = None
    trace_coroutine = None
    app.state.decision_trace_store = None
    app.state.decision_trace_task = None
    try:
        trace_store = DecisionTraceStore()
        trace_coroutine = trace_store.run_forever(optimizer)
        trace_task = asyncio.create_task(trace_coroutine, name="decision_trace")
        app.state.decision_trace_store = trace_store
        app.state.decision_trace_task = trace_task
    except Exception:
        logger.exception("Decision trace setup failed; diagnostics disabled")
        try:
            if trace_coroutine is not None and trace_task is None:
                trace_coroutine.close()
            if trace_store is not None:
                trace_store.stop()
        except Exception:
            logger.exception("Decision trace setup cleanup failed")

    logger.info(
        "Background tasks started — optimizer (event-driven + 60s heartbeat) + WebSocket listener; passive decision trace=%s",
        trace_task is not None,
    )

    try:
        yield
    finally:
        # Passive diagnostics have no final flush and never delay control-task
        # cancellation waiting for a filesystem worker to finish.
        if trace_store is not None:
            trace_store.stop()
        if trace_task is not None:
            trace_task.cancel()
            try:
                await trace_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Decision trace task failed during shutdown")

    # Shutdown: cancel both tasks
    logger.info("Shutting down background tasks")
    for task in (ws_task, optimizer_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await ha.close()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    allowed_origins = _parse_csv_list(settings.cors_allowed_origins)
    app = FastAPI(
        title="SigEnergy Optimizer",
        version="2.3.57-haos68",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["content-type", "x-api-key"],
    )
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.include_router(ui)
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
