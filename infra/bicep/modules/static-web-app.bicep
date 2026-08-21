@description('Hosts apps/web on Azure Static Web Apps — Free tier: 100GB bandwidth/mo, free managed SSL, 2 custom domains, $0/month. Genuinely free, not a trial — the right tier for a pilot with no ad spend and no traffic guarantees yet. Deployed via GitHub Actions (see .github/workflows/web-cd.yml) using the deployment token below, not the GitHub-integration/repositoryUrl binding — that keeps this resource decoupled from which repo/branch/host GitHub happens to live under.')
param location string
param namePrefix string
param environmentTag string

resource staticSite 'Microsoft.Web/staticSites@2023-12-01' = {
  name: '${namePrefix}-web'
  // Static Web Apps is only available in a handful of regions — West US 2,
  // Central US, East US 2, West Europe, East Asia — independent of where the
  // rest of the stack lives. Pick the nearest supported region at deploy time
  // if `location` isn't one of these.
  location: location
  tags: { environment: environmentTag, app: 'trialready' }
  sku: { name: 'Free', tier: 'Free' }
  properties: {
    // No `buildProperties`/`repositoryUrl` here on purpose — see module docstring.
  }
}

output defaultHostname string = staticSite.properties.defaultHostname
output staticSiteName string = staticSite.name
