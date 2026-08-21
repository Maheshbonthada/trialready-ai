# Cost model — 500-user pilot

Estimates, not quotes — validate against actual Azure retail pricing for your
region/subscription type before committing budget. All figures are monthly, USD,
`eastus2`, as designed in `infra/bicep/`.

## Assumption behind these numbers

500 registered site coordinators, each touching the product a handful of times a
month around monitor visits — not 500 concurrent daily-active chat users. This is
the difference between a $200/month pilot and a $5,000/month one; if usage turns
out to be denser than this, the autoscale rules in `container-app-api.bicep`
absorb it automatically and only the AI-services line items below grow.

## Where the $/month actually goes

| Line item | Tier chosen | Why | Est. $/mo |
|---|---|---|---|
| Container Apps (API) | Consumption, 0.5 vCPU/1GiB, min 1 replica in prod | Scale-to-zero everywhere except prod; prod keeps 1 warm replica for latency (see architecture.md) | $15–35 |
| Container Apps (migration job) | Consumption, runs on-demand only | Zero cost when not deploying | ~$0 |
| Postgres Flexible Server | Burstable B2s, 64GB | Right-sized for a metadata + audit-log workload, not analytics | $55–70 |
| Azure OpenAI | S0, gpt-4o-mini (classification) + gpt-4o (narrative, low volume) | Model routing by task is the biggest single lever here — routing everything through gpt-4o instead would roughly double this line | $30–90 (usage-based; scales with documents uploaded, not users registered) |
| Document Intelligence | S0, pay-per-page | ~$1.50/1,000 pages at prebuilt-document pricing; a binder is ~15-20 pages, uploaded a handful of times per site per month | $10–25 |
| Blob Storage | Standard LRS (ZRS in prod) | Documents are small (PDFs), retention is the only real driver | $2–5 |
| Container Registry | Basic | A few image pushes a week | ~$5 |
| Key Vault | Standard, secrets only | Per-operation pricing, negligible at this volume | <$1 |
| Log Analytics + App Insights | PerGB2018, 30-day retention | Bounded by not shipping verbose debug logs to prod (`LOG_LEVEL=INFO`) | $10–25 |
| Static Web Apps (frontend) | Free tier | 100GB bandwidth/mo, free managed SSL, 2 custom domains — genuinely free, not a trial, and plenty for a pilot's traffic | $0 |
| **Total (prod, steady state)** | | | **~$130–260/mo** |
| **Total (dev, scale-to-zero)** | | | **~$20–50/mo** (mostly Postgres + AI services idle minimums) |

## The three biggest levers if this needs to run cheaper

1. **Drop the prod warm replica** (`minReplicas: 0`) — trades the cold-start
   latency hit (several seconds on first request after idle) for near-zero
   compute cost between bursts. Reasonable while pilot usage is small enough
   that "first request of the day is slow" isn't a complaint yet.
2. **Route more traffic through gpt-4o-mini, less through gpt-4o** — the
   reasoning-tier deployment exists only for the (low-volume) narrative
   generation step; if that step is cut or deferred, its entire TPM allocation
   and spend disappears.
3. **Downgrade Postgres retention/backup redundancy in non-prod** — already done
   (`backupRetentionDays: 7`, no geo-redundancy) but worth re-checking if dev
   environments proliferate.

## The three biggest levers if this needs to run faster (spend to buy latency)

1. Raise `minReplicas` in prod beyond 1, or lower the HTTP-concurrency scale
   trigger threshold, to absorb bursts (e.g. everyone checking before Monday)
   without a scale-out lag.
2. Move document upload to async processing (see architecture.md) — doesn't cost
   more per se, but is the right lever before "add more compute" if p95 upload
   latency becomes the complaint.
3. Raise Azure OpenAI deployment TPM capacity — the failure mode of under-
   provisioning here is 429 rate-limit errors under burst, not slow responses,
   so this is a correctness lever as much as a latency one.
