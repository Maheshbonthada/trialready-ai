# syntax=docker/dockerfile:1
#
# Build context is the REPO ROOT, not this directory (the image needs both
# apps/api/src and the top-level data/ checklist):
#   docker build -f apps/api/Dockerfile -t trialready-api .
#
# Multi-stage: compile deps in a full image, run in a slim one — small image,
# fast cold start on Container Apps' consumption plan, no build toolchain shipped
# to production.

FROM python:3.11-slim AS builder
WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/pyproject.toml ./
COPY apps/api/src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.11-slim AS runtime

# Non-root user — the container never needs root, and the platform default of
# running as root is exactly the kind of thing a security review flags.
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

COPY --from=builder /install /usr/local
COPY --chown=app:app data /app/data
COPY --chown=app:app apps/api/src /app/src
COPY --chown=app:app apps/api/alembic.ini /app/alembic.ini

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    TRIALREADY_CHECKLIST_PATH=/app/data/essential_documents.yaml

WORKDIR /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

# Single worker per container: Container Apps scales horizontally by replica count
# (see infra/bicep/modules/container-app-api.bicep scaleRule), which gives cleaner
# per-replica metrics and avoids uvicorn's multi-worker + async-event-loop
# interaction pitfalls. Scale out, not up, inside one container.
CMD ["uvicorn", "trialready_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
