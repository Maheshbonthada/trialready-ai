@description('TrialReady — resource-group-scoped deployment. One resource group per environment (dev/staging/prod); this template is applied to each independently via infra/bicep/parameters/<env>.bicepparam. See docs/runbook.md for the deploy sequence.')
targetScope = 'resourceGroup'

@allowed(['dev', 'staging', 'prod'])
param environmentTag string

param location string = resourceGroup().location

@description('Short, globally-unique-safe prefix, e.g. "tr-dev". Keep to <=12 chars — several resource types (Key Vault, Storage, ACR) have tight name-length limits.')
@maxLength(12)
param namePrefix string

@secure()
param postgresAdminPassword string

@description('Full image reference, e.g. <acr-login-server>/trialready-api:<git-sha>. Left as a placeholder mcr image on first deploy so the environment stands up before CI has published anything — see docs/runbook.md.')
param containerImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

param entraTenantId string = ''
param entraClientId string = ''
param entraIssuer string = ''
param entraAudience string = ''

var tenantId = subscription().tenantId

// --- Foundational: observability, secrets, registry, storage ---

module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'log-analytics'
  params: { location: location, namePrefix: namePrefix, environmentTag: environmentTag }
}

module keyVault 'modules/key-vault.bicep' = {
  name: 'key-vault'
  params: { location: location, namePrefix: namePrefix, environmentTag: environmentTag, tenantId: tenantId }
}

module registry 'modules/container-registry.bicep' = {
  name: 'container-registry'
  params: { location: location, namePrefix: namePrefix, environmentTag: environmentTag }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: { location: location, namePrefix: namePrefix, environmentTag: environmentTag }
}

// --- Data plane ---

module postgres 'modules/postgres.bicep' = {
  name: 'postgres'
  params: {
    location: location
    namePrefix: namePrefix
    environmentTag: environmentTag
    administratorPassword: postgresAdminPassword
  }
}

// --- AI services ---

module openAi 'modules/openai.bicep' = {
  name: 'openai'
  params: { location: location, namePrefix: namePrefix, environmentTag: environmentTag }
}

module documentIntelligence 'modules/document-intelligence.bicep' = {
  name: 'document-intelligence'
  params: { location: location, namePrefix: namePrefix, environmentTag: environmentTag }
}

// --- Compute ---

module containerAppsEnv 'modules/container-apps-env.bicep' = {
  name: 'container-apps-env'
  params: {
    location: location
    namePrefix: namePrefix
    environmentTag: environmentTag
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    logAnalyticsCustomerId: reference(logAnalytics.outputs.workspaceId, '2023-09-01').customerId
    logAnalyticsSharedKey: listKeys(logAnalytics.outputs.workspaceId, '2023-09-01').primarySharedKey
  }
}

// The DB DSN is assembled here (never in application code or CI) and stored as a
// single Key Vault secret — the container app reads it via a Key-Vault-backed
// secretRef, so the connection string exists in exactly one place at rest.
resource keyVaultRef 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVault.outputs.keyVaultName
}

resource databaseUrlSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVaultRef
  name: 'database-url'
  properties: {
    value: 'postgresql+asyncpg://${'trialready_admin'}:${postgresAdminPassword}@${postgres.outputs.serverFqdn}:5432/${postgres.outputs.databaseName}?ssl=require'
  }
}

module containerApp 'modules/container-app-api.bicep' = {
  name: 'container-app-api'
  params: {
    location: location
    namePrefix: namePrefix
    environmentTag: environmentTag
    containerAppsEnvironmentId: containerAppsEnv.outputs.environmentId
    containerImage: containerImage
    containerRegistryLoginServer: registry.outputs.loginServer
    keyVaultUri: keyVault.outputs.keyVaultUri
    databaseUrlSecretName: 'database-url'
    appInsightsConnectionString: logAnalytics.outputs.appInsightsConnectionString
    openAiEndpoint: openAi.outputs.endpoint
    docIntelligenceEndpoint: documentIntelligence.outputs.endpoint
    storageBlobEndpoint: storage.outputs.blobEndpoint
    entraTenantId: entraTenantId
    entraClientId: entraClientId
    entraIssuer: entraIssuer
    entraAudience: entraAudience
  }
  dependsOn: [databaseUrlSecret]
}

module migrationJob 'modules/migration-job.bicep' = {
  name: 'migration-job'
  params: {
    location: location
    namePrefix: namePrefix
    environmentTag: environmentTag
    containerAppsEnvironmentId: containerAppsEnv.outputs.environmentId
    containerImage: containerImage
    containerRegistryLoginServer: registry.outputs.loginServer
    keyVaultUri: keyVault.outputs.keyVaultUri
    databaseUrlSecretName: 'database-url'
  }
  dependsOn: [databaseUrlSecret]
}

// --- RBAC: least-privilege grants to the API's own managed identity. No
// connection strings, API keys, or SAS tokens anywhere in this stack. ---

var roleIds = {
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  keyVaultSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  cognitiveServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'
}

resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.outputs.registryId, containerApp.outputs.principalId, roleIds.acrPull)
  scope: resourceGroup()
  properties: {
    principalId: containerApp.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.acrPull)
  }
}

resource kvSecretsAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.outputs.keyVaultId, containerApp.outputs.principalId, roleIds.keyVaultSecretsUser)
  scope: resourceGroup()
  properties: {
    principalId: containerApp.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.keyVaultSecretsUser)
  }
}

resource storageAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.outputs.storageAccountId, containerApp.outputs.principalId, roleIds.storageBlobDataContributor)
  scope: resourceGroup()
  properties: {
    principalId: containerApp.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.storageBlobDataContributor)
  }
}

resource openAiAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAi.outputs.accountName, containerApp.outputs.principalId, roleIds.cognitiveServicesUser)
  scope: resourceGroup()
  properties: {
    principalId: containerApp.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.cognitiveServicesUser)
  }
}

resource docIntelAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(documentIntelligence.outputs.accountName, containerApp.outputs.principalId, roleIds.cognitiveServicesUser)
  scope: resourceGroup()
  properties: {
    principalId: containerApp.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.cognitiveServicesUser)
  }
}

resource migrateAcrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.outputs.registryId, migrationJob.outputs.principalId, roleIds.acrPull)
  scope: resourceGroup()
  properties: {
    principalId: migrationJob.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.acrPull)
  }
}

resource migrateKvSecretsAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.outputs.keyVaultId, migrationJob.outputs.principalId, roleIds.keyVaultSecretsUser)
  scope: resourceGroup()
  properties: {
    principalId: migrationJob.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleIds.keyVaultSecretsUser)
  }
}

output apiUrl string = 'https://${containerApp.outputs.fqdn}'
output containerRegistryLoginServer string = registry.outputs.loginServer
output keyVaultName string = keyVault.outputs.keyVaultName
