"""
Football Predictor V9.0 - FastAPI Application
BUG FIX: loguru now writes to SystemLog DB table (logs page populated).
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from app.database import engine, Base
from app.models import all_models  # noqa: F401 — registers all ORM classes
from app.config import settings


# ─────────────────────────────────────────────
# Loguru → DB Sink (fixes empty logs page)
# ─────────────────────────────────────────────
_log_queue: asyncio.Queue = None


def _sync_db_log_sink(message):
    """Synchronous loguru sink — queues messages for async DB writing."""
    if _log_queue is None:
        return
    record = message.record
    level = record["level"].name[:10]
    module = record["name"] or "app"
    msg = record["message"]
    try:
        _log_queue.put_nowait((level, module, msg))
    except Exception:
        pass


async def _db_log_writer():
    """Background task: drains the log queue and writes to SystemLog."""
    global _log_queue
    from app.database import AsyncSessionLocal
    from app.models.logs import SystemLog

    while True:
        try:
            item = await asyncio.wait_for(_log_queue.get(), timeout=5.0)
            level, module, msg = item
            async with AsyncSessionLocal() as session:
                session.add(SystemLog(level=level, module=module[:100], message=msg))
                await session.commit()
        except asyncio.TimeoutError:
            continue
        except Exception:
            await asyncio.sleep(1)


# ─────────────────────────────────────────────
# App Lifespan
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _log_queue

    # Create DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Init log queue and background writer
    _log_queue = asyncio.Queue(maxsize=1000)
    log_writer_task = asyncio.create_task(_db_log_writer())

    # Register loguru DB sink (level INFO+)
    logger.add(
        _sync_db_log_sink,
        level="INFO",
        format="{message}",
        filter=lambda r: r["level"].name in ("INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"),
        enqueue=False,
    )
    logger.add(sys.stderr, level="DEBUG", format="<level>{level: <8}</level> | {name} | {message}")

    # Seed default weights if first run
    from app.services.learning_engine import learning_engine
    await learning_engine.ensure_default_weights()

    # Start scheduler
    from app.services.scheduler import setup_scheduler
    setup_scheduler()

    # Trigger initial data fetch (non-blocking)
    from app.services.data_updater import data_updater
    async def _initial_data_bootstrap():
        await data_updater.fetch_todays_matches()
        await data_updater.generate_daily_predictions()
    asyncio.create_task(_initial_data_bootstrap())

    logger.info("Football Predictor V9.0 started")
    yield

    # Shutdown
    log_writer_task.cancel()
    try:
        await log_writer_task
    except asyncio.CancelledError:
        pass

    from app.services.scheduler import scheduler
    if scheduler.running:
        scheduler.shutdown(wait=False)

    logger.info("Football Predictor V9.0 shutdown complete")


# ─────────────────────────────────────────────
# App Instance
# ─────────────────────────────────────────────
app = FastAPI(
    title="Football Predictor V9.0",
    description="Monte Carlo match prediction engine",
    version="9.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Register routers
from app.routers.main_routes import router as main_router
from app.routers.api_routes import router as api_router

app.include_router(main_router)
app.include_router(api_router, prefix="/api")


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse(
        "base.html",
        {"request": request, "content": "<div class='alert alert-warning'>Página no encontrada (404)</div>"},
        status_code=404,
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    logger.error(f"Internal Server Error: {exc}")
    return templates.TemplateResponse(
        "base.html",
        {"request": request, "content": "<div class='alert alert-danger'>Error interno del servidor (500)</div>"},
        status_code=500,
    )
