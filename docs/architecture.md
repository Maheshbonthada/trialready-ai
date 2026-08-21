# Architecture

## What this system does

One workflow, done well: a site coordinator uploads their regulatory binder
documents; the system tells them exactly what's missing, expired, expiring soon,
or stuck pending review, before a monitor visit finds it for them.

## Request flow

```
Coordinator                Container App (FastAPI)              Azure services
    |  upload PDF                  |                                   |
    |------------------------------>|                                   |
    |                               |-- upload blob ------------------->|  Blob Storage
    |                               |-- OCR + layout ------------------->|  Document Intelligence
    |                               |<-- text + key/value pairs ---------|
    |                               |-- classify + extract ------------->|  Azure OpenAI (gpt-4o-mini)
    |                               |<-- type, dates, confidence --------|
    |                               |
    |                               |-- confidence >= 0.85? -----+
    |                               |        yes -> ACCEPTED     |
    |                               |        no  -> PENDING_REVIEW
    |                               |
    |                               |-- write BinderDocument + AuditLogEntry --> Postgres
    |<-- 201 Created ---------------|
    |
    |  request gap check           |
    |------------------------------>|
    |                               |-- read all documents for protocol --> Postgres
    |                               |-- evaluate_binder() [pure, in-process, no I/O]
    |                               |-- write GapCheckRun + AuditLogEntry --> Postgres
    |<-- GapReport JSON ------------|
```

## Why the decision layer is not an agent

`services/rules_engine.py` computes the actual "is this site ready for a monitor
visit" answer, and it is a deterministic pure function — no LLM call inside it.

This is a considered trade-off, not a shortcut:

- **Explainability.** Every gap item traces to one `if` branch. When a compliance
  lead asks "why does the system say our IRB approval is expired," the answer is
  "because `as_of > expiry` evaluated true," not "the model said so."
- **Reproducibility.** The same binder state always produces the same report. An
  LLM asked to freelance the same judgment could drift between calls, between
  model versions, or under adversarial prompt content buried in a PDF.
- **Auditability.** `GapCheckRun.report_json` is stored verbatim per run
  specifically so a report from six weeks ago can be reproduced exactly, which
  matters when a monitor visit references it.

The agentic part of the system is upstream of this: `agents/classification_agent.py`
reasons over unstructured OCR text to figure out *what a document is* and *what
dates it contains* — a task genuinely suited to an LLM, and not one a rules engine
could do. Its output feeds the deterministic layer as structured, typed data.
This is the general pattern for agent systems in regulated domains: **LLM agents
for perception over unstructured input, deterministic code for decisions that
carry legal or compliance weight.**

## The confidence gate

`classification_min_confidence` (default 0.85, `config.py`) is the single most
important knob in the system. Below it, a document is routed to
`PENDING_HUMAN_REVIEW` instead of being auto-accepted — the rules engine treats
that identically to "not yet resolved," never as "compliant." Raising this
threshold trades convenience for safety; lowering it does the opposite. Any
change to this value should go through the same review as a change to the
checklist itself (see `data/essential_documents.yaml`).

## Service boundaries and why they're drawn where they are

| Boundary | Reason |
|---|---|
| `agents/ocr_client.py` (Protocol + Azure impl + Fake) | Classification logic never imports the Azure SDK directly — swappable, and unit-testable without network access. |
| `agents/classification_agent.py` (Protocol + Azure impl + Fake) | Same reasoning; also isolates the one place a prompt-injection-style attack via a malicious PDF could land — see `docs/compliance-checklist.md`. |
| `services/rules_engine.py` (pure function) | See above. Zero dependencies on DB, Azure, or FastAPI — it's tested with 18 fixture-based unit tests and nothing else. |
| `services/document_ingestion.py` / `report_service.py` | Orchestration only: sequence the pure/testable pieces, handle the one transaction, write the one audit entry. |
| `api/routers/*` | Thin — HTTP concerns (status codes, request/response shapes) only. No business logic lives in a router. |

## Frontend

`apps/web` is a small React 19 + TypeScript SPA (Vite build, react-router, zero
state-management library — three routes and four API calls don't need one).
It talks to the API over plain `fetch`, holds no business logic of its own
(notably: `GapReport.is_monitor_visit_ready` is read from the API response,
never recomputed client-side — see `api/types.ts`), and ships as a static
bundle to Azure Static Web Apps' Free tier (`infra/bicep/modules/static-web-app.bicep`).
`CORS_ALLOWED_ORIGINS` on the API is wired to the Static Web App's actual
hostname at deploy time (`main.bicep`), not a guessed custom domain — CORS has
to work from the first deploy, before anyone points a real domain at it.

## Latency budget (target: p95 under 6s for document upload, under 500ms for a gap check)

- **Gap check** never calls an external service — it's a Postgres read plus an
  in-process pure function. Budget: DB round-trip (~20-50ms) + compute (<5ms).
- **Document upload** is dominated by two sequential external calls: Document
  Intelligence OCR (typically 2-5s for a multi-page PDF) and one Azure OpenAI
  chat completion (typically 1-3s at `temperature=0`, `max_tokens=800`). These
  run sequentially today because classification needs OCR'd text as input —
  there is no parallelism to extract here, only per-call latency to manage
  (right-sized `max_tokens`, the fast/cheap model for this call, not the
  reasoning model). If upload latency becomes a complaint at scale, move it to
  an async job (upload returns 202 + poll/webhook) rather than fighting the
  synchronous critical path — noted as the first scaling change to make, not
  made preemptively because it adds real complexity a 500-user pilot doesn't
  need yet.

## Scaling to 500 users

500 users each occasionally uploading a handful of documents and running a gap
check before a monitor visit is a bursty, low-average, low-concurrency workload
— not a chat product with constant open connections. The design point is
therefore "cheap and correct at low volume, with an explicit, cheap lever to pull
if a burst arrives" rather than pre-built high-concurrency infrastructure:

- Container Apps scales 0-10 replicas on concurrent-request count (`container-app-api.bicep`) — the lever *is* the infrastructure, not a rewrite.
- Postgres Flexible Server Burstable B2s tolerates bursty load by design (it's the entire point of the "burstable" family) and is trivial to resize without a migration.
- Azure OpenAI TPM capacity (`openai.bicep`) is provisioned per-deployment and can be raised independently of everything else the moment usage approaches it.

## What's explicitly deferred (and why that's a decision, not an oversight)

- **VNet integration / private endpoints** — real hardening, real monthly cost, and irrelevant while the pilot runs on synthetic data. Flip-a-switch item once real PHI is in scope; see `docs/compliance-checklist.md`.
- **Redis / caching layer** — nothing in this workflow is called often enough per-entity to need it yet; added when a specific slow, repeated read shows up in Application Insights, not before.
- **Multi-tenant RBAC beyond "one coordinator per site"** — see `infra/bicep/modules/entra-b2c.md`.
- **Async upload processing** — see the latency section above.
