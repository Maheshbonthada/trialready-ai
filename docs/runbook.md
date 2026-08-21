# Runbook

## First-time environment setup (once you have an Azure subscription)

1. Create a resource group per environment: `az group create -n rg-trialready-dev -l eastus2`
2. Generate a strong Postgres admin password and store it as a GitHub Actions
   secret (`POSTGRES_ADMIN_PASSWORD`) — never in `.bicepparam`.
3. Set up federated OIDC credentials for GitHub Actions → Azure (no client
   secret): `az ad app federated-credential create ...` scoped to this repo and
   the `cd.yml` workflow. Store `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
   `AZURE_SUBSCRIPTION_ID` as repo secrets.
4. First deploy will use the placeholder `mcr.microsoft.com/k8se/quickstart`
   image (`main.bicep`'s `containerImage` default) so the environment stands up
   before CI has published a real image — this is intentional, not a bug in the
   template.
5. Run `.github/workflows/cd.yml` manually (`workflow_dispatch`, `environment: dev`)
   once secrets are in place. This builds the real image, pushes it to ACR, and
   redeploys the container app with it.
6. **Known first-deploy quirk:** the container app's managed identity is granted
   `AcrPull` in the same deployment that tries to pull the image with it. RBAC
   propagation can lag a few minutes behind the role-assignment API call
   returning success. If the first revision fails to start with an image-pull
   error, wait ~5 minutes and restart the revision (`az containerapp revision restart`)
   rather than re-running the whole deployment.
7. Complete the Entra External ID manual setup:
   `infra/bicep/modules/entra-b2c.md`, then set `ENTRA_*` values in the
   environment's `.bicepparam` and redeploy.
8. Run the migration job once: `az containerapp job start --name tr-dev-migrate --resource-group rg-trialready-dev`.

## Ongoing deploys

Tag a release (`git tag v0.2.0 && git push --tags`) or trigger `cd.yml` manually.
The workflow builds, pushes to ACR, redeploys the Bicep template (idempotent —
safe to re-run), and starts the migration job.

## Rollback

Container Apps keeps prior revisions. Fastest rollback:
```
az containerapp revision list --name tr-prod-api --resource-group rg-trialready-prod -o table
az containerapp ingress traffic set --name tr-prod-api --resource-group rg-trialready-prod \
  --revision-weight <previous-revision>=100
```
This does not roll back a database migration — migrations in this codebase
should be written additive/backward-compatible (add-nullable-column, not
drop-column-in-the-same-release) specifically so a code rollback never needs a
matching schema rollback.

## Local development

```
cp apps/api/.env.example apps/api/.env
docker compose up --build
# API at http://localhost:8000, docs at http://localhost:8000/docs
```

With `AUTH_DISABLED_FOR_LOCAL_DEV=true` and no Azure endpoints configured, every
external dependency (auth, OCR, classification, blob storage) runs against the
in-repo fakes in `deps.py` — a full request can be exercised with zero Azure
credentials.

## On-call basics

- `/healthz` — liveness, never touches the DB. A failure here means restart the
  container, not investigate downstream services.
- `/readyz` — readiness, touches Postgres. A failure here with liveness healthy
  means investigate the DB connection, not the app process.
- Application Insights end-to-end transaction view traces a single request from
  the API through to the exact Azure OpenAI/Document Intelligence call that was
  slow — start there for any latency complaint, not local logs.
