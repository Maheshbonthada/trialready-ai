"""FastAPI application factory and entrypoint (`uvicorn trialready_api.main:app`)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from trialready_api.api.routers import documents, gap_checks, health, protocols, sites
from trialready_api.config import get_settings
from trialready_api.core.logging import configure_logging
from trialready_api.core.telemetry import configure_telemetry

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_telemetry(settings.applicationinsights_connection_string)
    logger.info("app.startup", environment=settings.environment)
    yield
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="TrialReady API",
        description="Regulatory binder gap-checker for independent clinical trial sites.",
        version="0.1.0",
        root_path=settings.api_root_path,
        lifespan=lifespan,
    )

    # Locked down deliberately: this API is called by TrialReady's own frontend and
    # nothing else. Widen only for an explicit, reviewed integration partner.
    # Origins come from config (CORS_ALLOWED_ORIGINS), not a hardcoded guess at a
    # custom domain — see Settings.cors_allowed_origins.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        structlog.contextvars.clear_contextvars()
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("request.unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(health.router)
    app.include_router(sites.router)
    app.include_router(protocols.router)
    app.include_router(documents.router)
    app.include_router(gap_checks.router)

    return app


app = create_app()
