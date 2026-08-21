# TrialReady

A regulatory binder gap-checker for independent and academic clinical trial
sites — the site coordinators sponsor-side agentic tools don't build for. Upload
your site regulatory binder; get told exactly what's missing, expired, expiring
soon, or stuck pending review, before a monitor visit finds it for you.

Full product/market rationale: see the "Site, Not Sponsor" idea in the earlier
research memo. This repo is the production build of that MVP wedge.

## Status

**Pre-launch codebase.** Built to deploy to Azure the moment there's budget —
see `docs/runbook.md` for the first-deploy sequence. Runs entirely on synthetic
data until `docs/compliance-checklist.md` is fully checked off.

## Repository layout

```
apps/api/          FastAPI service — the product's backend
  src/trialready_api/
    agents/         The one genuinely agentic step: document OCR + classification
    services/       Orchestration + the deterministic compliance rules engine
    api/routers/    Thin HTTP layer
    db/             SQLAlchemy models + Alembic migrations
  tests/
apps/web/           React + TypeScript SPA (Vite) — sites, protocols, binder upload, gap report
data/               Canonical Site Regulatory Binder checklist (config-as-code)
infra/bicep/        All Azure infrastructure, as code
docs/               Architecture, cost model, compliance checklist, runbook
.github/workflows/  CI (every PR) and CD (manual/tag-triggered deploy, API + web)
```

## Quick start (local)

Backend (needs Postgres — Docker, or your own local instance):
```
cp apps/api/.env.example apps/api/.env   # fill in OPENAI_API_KEY to run real classification, or leave blank for fakes
docker compose up -d postgres            # exposes host port 5433, not 5432 — see docker-compose.yml
cd apps/api && pip install -e ".[dev]"
alembic upgrade head
uvicorn trialready_api.main:app --reload --app-dir src
```
API docs at `http://localhost:8000/docs`. With `AZURE_OPENAI_ENDPOINT` /
`DOC_INTELLIGENCE_ENDPOINT` unset, OCR runs against an in-repo fake (empty
text) and classification runs against a fake unless `AI_PROVIDER=openai` +
`OPENAI_API_KEY` are set, in which case it's a real `gpt-4o-mini` call — see
`apps/api/src/trialready_api/deps.py`.

Frontend:
```
cp apps/web/.env.example apps/web/.env.local
cd apps/web && npm install && npm run dev
```
Open `http://localhost:5173`. It talks straight to the API above — no build
step needed to see backend changes reflected.

## Running tests

```
make install
make test
```

The rules-engine tests (`apps/api/tests/unit/test_rules_engine.py`) are the ones
that matter most — they're the actual product logic, and they run with zero
external dependencies.

## Deploying to Azure

See `docs/runbook.md` for the full sequence. Short version: get an Azure
subscription, set three GitHub secrets for OIDC login, generate a Postgres
password, run the `CD` workflow. Nothing in this repo talks to Azure until you
do that.

## Read next

- [`docs/architecture.md`](docs/architecture.md) — why the compliance decision is
  deterministic and not agentic, request flow, latency budget, scaling plan.
- [`docs/cost-model.md`](docs/cost-model.md) — line-item Azure cost estimate for
  a 500-user pilot (~$130-260/mo in prod).
- [`docs/compliance-checklist.md`](docs/compliance-checklist.md) — what has to be
  true before this system ever touches real patient data.
- [`docs/runbook.md`](docs/runbook.md) — first deploy, ongoing deploys, rollback,
  on-call basics.
