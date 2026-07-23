"""HealMatrix AI — FastAPI application entry point.

Wires the application shell — lifespan management, configuration, structured logging,
CORS, correlation IDs, the domain exception handler and health probes — and mounts the
versioned API router.
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import settings
from app.core.exceptions import HealMatrixError
from app.core.logging_config import configure_logging, correlation_id_ctx, get_logger
from app.database import indexes, mongodb

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Open resources on startup and release them on shutdown."""
    configure_logging()
    logger.info(
        "app.starting",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )

    await mongodb.connect_to_mongo()
    await indexes.create_indexes()

    logger.info("app.ready", llm_configured=settings.llm_available)
    yield

    await mongodb.close_mongo_connection()
    logger.info("app.stopped")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Multi-Agent Sustainable Healthcare Intelligence Platform. "
        "Ten collaborating AI agents optimise hospital operations while reducing "
        "energy, water, waste and carbon impact."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID", "X-Process-Time-Ms"],
)


@app.middleware("http")
async def correlation_and_timing(request: Request, call_next):
    """Attach a correlation ID to every request and record its duration."""
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    token = correlation_id_ctx.set(correlation_id)
    started = time.perf_counter()

    try:
        response = await call_next(request)
    finally:
        correlation_id_ctx.reset(token)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Process-Time-Ms"] = str(elapsed_ms)

    logger.info(
        "http.request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=elapsed_ms,
    )
    return response


@app.exception_handler(HealMatrixError)
async def healmatrix_exception_handler(_request: Request, exc: HealMatrixError) -> JSONResponse:
    """Render every domain error in one consistent envelope."""
    correlation_id = correlation_id_ctx.get()
    if exc.status_code >= 500:
        logger.error("domain.error", code=exc.code, message=exc.message, details=exc.details)
    else:
        logger.warning("domain.error", code=exc.code, message=exc.message)
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict(correlation_id))


def _serialisable_errors(errors: list[dict]) -> list[dict]:
    """Strip non-JSON-serialisable objects out of Pydantic's error entries.

    Pydantic puts the original exception instance in ``ctx`` when a custom field
    validator raises. Passing that straight to JSONResponse turns a 422 into a 500,
    so the context is reduced to its string form here.
    """
    cleaned: list[dict] = []
    for error in errors:
        entry = {
            "type": error.get("type"),
            "loc": [str(part) for part in error.get("loc", ())],
            "msg": error.get("msg"),
        }
        context = error.get("ctx")
        if context:
            entry["ctx"] = {key: str(value) for key, value in context.items()}
        cleaned.append(entry)
    return cleaned


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Normalise FastAPI validation errors into the same envelope."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "The request payload failed validation.",
                "details": {"errors": _serialisable_errors(exc.errors())},
                "correlation_id": correlation_id_ctx.get(),
            }
        },
    )


app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["meta"], summary="Service banner")
async def root() -> dict:
    """Human-friendly service identity, useful for smoke-checking a deployment."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "tagline": "Empowering Sustainable Hospitals Through Collaborative Agentic AI.",
        "environment": settings.environment,
        "docs": "/docs",
    }


@app.get("/health", tags=["meta"], summary="Liveness probe")
async def health() -> dict:
    """Returns 200 whenever the process is running. Used by container health checks."""
    return {"status": "alive", "version": settings.app_version}


@app.get("/health/ready", tags=["meta"], summary="Readiness probe")
async def readiness() -> JSONResponse:
    """Reports dependency health so a load balancer can withhold traffic when degraded."""
    database_ok = await mongodb.ping()
    dependencies = {
        "mongodb": "up" if database_ok else "down",
        "gemini": "configured" if settings.llm_available else "not_configured",
    }
    ready = database_ok
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "degraded", "dependencies": dependencies},
    )
