@description('Azure AI Document Intelligence — OCR + layout/key-value extraction over uploaded binder PDFs, ahead of the classification agent. Pay-per-page pricing suits a pilot with unpredictable, low document volume far better than any provisioned-throughput alternative.')
param location string
param namePrefix string
param environmentTag string

resource account 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: '${namePrefix}-docint'
  location: location
  tags: { environment: environmentTag, app: 'trialready' }
  kind: 'FormRecognizer'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: '${namePrefix}-docint'
    publicNetworkAccess: 'Enabled' // tighten to private endpoint before real PHI — see compliance-checklist.md
    disableLocalAuth: true
  }
}

output endpoint string = account.properties.endpoint
output accountName string = account.name
