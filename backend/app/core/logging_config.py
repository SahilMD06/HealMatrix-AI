"""Structured logging.

Every log line is JSON with a correlation ID so an HTTP request can be traced through
the service layer into an agent run and back out again.
"""

import logging
import sys
from contextvars import ContextVar

import structlog

from app.core.config import settings

correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def _add_correlation_id(_logger, _method_name, event_dict):
    """structlog processor that injects the current correlation ID."""
    cid = correlation_id_ctx.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def configure_logging() -> None:
    """Configure structlog and the stdlib logging bridge. Call once at startup."""
    level = logging.DEBUG if settings.debug else logging.INFO

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_correlation_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if settings.is_production
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Quieten noisy third-party loggers.
    for noisy in ("pymongo", "httpx", "httpcore", "urllib3", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given module."""
    return structlog.get_logger(name)
