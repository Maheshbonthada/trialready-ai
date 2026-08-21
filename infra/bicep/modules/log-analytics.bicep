@description('Log Analytics workspace backing both Container Apps and Application Insights.')
param location string
param namePrefix string
param environmentTag string

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${namePrefix}-log'
  location: location
  tags: { environment: environmentTag, app: 'trialready' }
  properties: {
    sku: { name: 'PerGB2018' }
    // 30 days is enough signal for a 500-user pilot without paying for retention
    // no one will query. Raise before real PHI is in play — see
    // docs/compliance-checklist.md, "Log retention."
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-appi'
  location: location
  kind: 'web'
  tags: { environment: environmentTag, app: 'trialready' }
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
    IngestionMode: 'LogAnalytics'
  }
}

output workspaceId string = workspace.id
output appInsightsConnectionString string = appInsights.properties.ConnectionString
