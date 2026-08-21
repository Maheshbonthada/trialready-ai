"""Structured logging, configured once at process startup.

JSON output in every environment (including local) so log shape never changes
between dev and prod — the #1 cause of "works on my machine, unparseable in Log
Analytics" surprises. Azure Monitor's OpenTelemetry exporter (core/telemetry.py)
picks these up and correlates them with traces automatically.
"""

from __future__ import annotations

import logging

import structlog


def configure_logging(log_level: str) -> None:
    logging.basicConfig(format="%(message)s", level=log_level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(log_level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
