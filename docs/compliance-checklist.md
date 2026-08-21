# Compliance checklist

## Current state: synthetic/de-identified data only

This codebase is scoped, per an explicit product decision, to run its pilot on
**synthetic or de-identified data** — no real subject-identifiable information
(PHI) is intended to touch it yet. That decision is what makes the rest of this
document a checklist to complete *before* real PHI is in scope, not a list of
things already broken.

Do not point this system at real patient/subject data, or a sponsor's real
regulatory documents containing real PHI, until every item below is checked.

## Go-to-PHI checklist

- [ ] **Executed Business Associate Agreement (BAA) with Microsoft** — required
      before any Azure service in this stack processes PHI. Azure OpenAI,
      Document Intelligence, Storage, and Postgres Flexible Server are all
      HIPAA-eligible services under Microsoft's BAA; the BAA itself is a
      contractual step, not a technical one, and gates everything else here.
- [ ] **Network isolation** — flip `publicNetworkAccess` to `Disabled` on
      Azure OpenAI and Document Intelligence (`infra/bicep/modules/openai.bicep`,
      `document-intelligence.bicep`), add private endpoints, and VNet-integrate
      the Container Apps environment and Postgres Flexible Server
      (`postgres.bicep`'s `AllowAzureServices` firewall rule is a pilot-only
      simplification — replace it with VNet-scoped access).
- [ ] **Postgres authentication** — move from password auth
      (`administratorPassword` in `postgres.bicep`) to Entra-ID-only
      authentication; eliminates a long-lived secret entirely.
- [ ] **Immutable audit storage** — `audit_log_entries` (`db/models.py`) is
      append-only by application convention today. Before real PHI, enforce it
      at the database level (`REVOKE UPDATE, DELETE` for the app's role) or
      mirror entries to Azure Storage in immutable/legal-hold mode.
- [ ] **Log retention and content** — confirm no PHI ever lands in
      `structlog`/Application Insights output. Current logging
      (`core/logging.py`, service-layer `logger.info(...)` calls) logs IDs and
      confidence scores, not document content — keep it that way; add a log-
      scrubbing test if this is ever in doubt. Extend Log Analytics retention
      past the pilot's 30 days (`log-analytics.bicep`) to match your regulatory
      retention requirement.
- [ ] **21 CFR Part 11 controls** — if this system will ever be the system of
      record for an e-signature or a decision that removes a human from a
      compliance determination, it needs Part 11's audit-trail, access-control,
      and validation documentation. Today it is explicitly *not* that: the
      rules engine informs a human, and a low-confidence classification always
      defers to one (see `docs/architecture.md`, "The confidence gate"). Keep
      it that way, or budget for full Part 11 validation before changing it.
- [ ] **Data residency** — confirm the deployment region satisfies each
      sponsor/site's data residency requirements; multi-region deployment is
      not built and would be new infra work, not a config flip.
- [ ] **Incident response plan** — who gets paged, what the rollback path is,
      and how a breach affecting PHI gets reported within HIPAA's 60-day
      window. Not written yet; write it before go-live with real data, not
      after an incident.

## Already built, and why it's there even during the synthetic-data pilot

Audit trails and the confidence-gate pattern cannot be retrofitted — bolting an
audit log onto a system after the fact leaves a gap for every action taken
before the bolt-on, and a regulator or auditor will ask about exactly that gap.
So `services/audit_service.py`, the append-only `audit_log_entries` table, and
the deterministic rules engine's explainability are built in from commit one,
even though today's data is synthetic. This is the cheapest point in the
project's life to build them — never again this cheap.
