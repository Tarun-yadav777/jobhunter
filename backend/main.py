import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import AsyncSessionLocal, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DB tables, sqlite-vec, seed settings, write startup log."""
    vec_ok = await init_db()

    from backend.models.db import StartupLog

    async with AsyncSessionLocal() as session:
        entry = StartupLog(
            started_at=datetime.utcnow(),
            db_ok=True,
            vec_ok=vec_ok,
            api_key_ok=True,
            app_version=settings.app_version,
        )
        session.add(entry)
        await session.commit()

    logger.info("Ollama host: %s  model: %s", settings.ollama_host, settings.ollama_model)

    yield


def create_app() -> FastAPI:
    """Factory that creates and configures the FastAPI application."""
    app = FastAPI(
        title="JobHunter",
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    from backend.routers import health, profile, jobs, generate, tracker

    app.include_router(health.router)
    app.include_router(profile.router)
    app.include_router(jobs.router)
    app.include_router(generate.router)
    app.include_router(tracker.router)

    return app


app = create_app()
