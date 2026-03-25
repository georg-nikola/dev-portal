from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from config import settings
from database import engine, Base, AsyncSessionLocal
from models import Service
from routers import auth, health, services
from status_checker import ping_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_checker_task: asyncio.Task | None = None


async def _run_status_checks():
    """Background loop: ping all services with a status_url every N seconds."""
    while True:
        try:
            await asyncio.sleep(settings.status_check_interval)
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Service).where(Service.status_url.isnot(None))
                )
                svcs = result.scalars().all()

            logger.info("Running background status checks for %d services", len(svcs))
            for svc in svcs:
                new_status = await ping_url(svc.status_url)
                async with AsyncSessionLocal() as db:
                    obj = await db.get(Service, svc.id)
                    if obj:
                        obj.status = new_status
                        obj.last_checked_at = datetime.now(timezone.utc)
                        await db.commit()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("Error in background status checker: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured.")

    # Start background checker
    global _checker_task
    _checker_task = asyncio.create_task(_run_status_checks())
    logger.info("Background status checker started (interval=%ds).", settings.status_check_interval)

    yield

    # Shutdown
    if _checker_task:
        _checker_task.cancel()
        try:
            await _checker_task
        except asyncio.CancelledError:
            pass
    await engine.dispose()


app = FastAPI(
    title="Dev Portal API",
    version="1.0.0",
    description="Internal developer portal — service catalog API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(services.router, prefix="/api")
