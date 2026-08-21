"""Application Insights wiring via the OpenTelemetry distro.

One call, made once at startup, instruments FastAPI, SQLAlchemy, and outbound
httpx calls (to Azure OpenAI, Document Intelligence, Graph) automatically —
request latency, DB query time, and dependency call time all show up in
Application Insights' end-to-end transaction view without hand-written spans.
Correlates by W3C trace-context, so a single slow gap-check request can be traced
from the API through to the exact Azure OpenAI call that took 4 seconds.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def configure_telemetry(connection_string: str) -> None:
    if not connection_string:
        logger.warning("telemetry.disabled", reason="no connection string configured (expected in local dev)")
        return

    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(connection_string=connection_string)
    logger.info("telemetry.configured")
