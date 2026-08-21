# Microsoft Entra External ID — manual setup

Entra External ID (customer-facing CIAM, the successor to Azure AD B2C) isn't
fully Bicep/ARM-expressible yet — tenant creation and the sign-up/sign-in user
flow are portal- or Microsoft Graph-driven. Do this once per environment, before
the first deploy that sets `AUTH_DISABLED_FOR_LOCAL_DEV=false`:

1. **Create an External ID tenant** (Azure Portal → "Microsoft Entra External ID"
   → Create tenant). One tenant can serve dev+staging+prod with separate app
   registrations, or use one tenant per environment for stricter isolation —
   for a pilot, one tenant with per-environment app registrations is enough.

2. **Register the API** (App registrations → New registration):
   - Name: `trialready-api-{env}`
   - Expose an API → add a scope, e.g. `access_as_user`
   - Note the **Application (client) ID** → `ENTRA_CLIENT_ID` / `ENTRA_AUDIENCE`
   - Note the **Directory (tenant) ID** → `ENTRA_TENANT_ID`
   - Issuer for token validation: `https://{tenant-subdomain}.ciamlogin.com/{tenant-id}/v2.0` → `ENTRA_ISSUER`

3. **Register the frontend** as a separate SPA/public client app registration
   (once a frontend exists), with the API's scope pre-authorized.

4. **Create a sign-up/sign-in user flow** and attach it to the frontend app
   registration. Site coordinators self-register through this flow; there is no
   admin-provisioning step for the pilot.

5. **Per-site authorization** (which coordinator can see which site/protocol) is
   application-level RBAC, not an Entra concept — see `db.models` for where that
   would be added (a `site_memberships` table joining `AuthenticatedUser.subject`
   to `Site.id`; deliberately not built yet since the pilot ships with one
   coordinator per site and doesn't need it).

Populate the four `ENTRA_*` values into each environment's `.bicepparam` file (or
pass them as `--parameters` overrides in CI) once this is done.
