from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware.auth import APIKeyMiddleware
from app.routers import (
    assessments,
    auth,
    documents,
    health,
    invitations,
    organizations,
    reports,
    scores,
    signals,
    users,
)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

log = structlog.get_logger()

if settings.SENTRY_DSN:
    import sentry_sdk  # type: ignore[import-untyped]

    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)
    log.info("sentry.initialized")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    log.info("app.startup", environment=settings.ENVIRONMENT)
    yield
    log.info("app.shutdown")


app = FastAPI(
    title="Camille API",
    description="AI Liability Risk Assessment Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(APIKeyMiddleware)

PREFIX = "/api/v1"

app.include_router(health.router)
app.include_router(auth.router, prefix=PREFIX)
app.include_router(invitations.router, prefix=PREFIX)
app.include_router(users.router, prefix=PREFIX)
app.include_router(organizations.router, prefix=PREFIX)
app.include_router(assessments.router, prefix=PREFIX)
app.include_router(documents.router, prefix=PREFIX)
app.include_router(scores.router, prefix=PREFIX)
app.include_router(reports.router, prefix=PREFIX)
app.include_router(signals.router, prefix=PREFIX)
