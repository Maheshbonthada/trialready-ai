@description('Storage account for uploaded binder documents. Private container, no public blob access, no shared-key access — the API talks to it exclusively via its managed identity.')
param location string
param namePrefix string
param environmentTag string
param binderContainerName string = 'binder-documents'

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  // Storage account names: <=24 chars, lowercase alphanumeric only, globally unique.
  name: replace('${namePrefix}st', '-', '')
  location: location
  tags: { environment: environmentTag, app: 'trialready' }
  sku: { name: environmentTag == 'prod' ? 'Standard_ZRS' : 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false // forces Entra ID (managed identity) auth for every client
    networkAcls: {
      defaultAction: 'Allow' // tighten to 'Deny' + private endpoint before real PHI — see compliance-checklist.md
      bypass: 'AzureServices'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 14 }
    containerDeleteRetentionPolicy: { enabled: true, days: 14 }
  }
}

resource binderContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: binderContainerName
  properties: {
    publicAccess: 'None'
  }
}

output storageAccountId string = storage.id
output storageAccountName string = storage.name
output blobEndpoint string = storage.properties.primaryEndpoints.blob
