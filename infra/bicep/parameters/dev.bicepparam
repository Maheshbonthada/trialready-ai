using '../main.bicep'

param environmentTag = 'dev'
param namePrefix = 'tr-dev'
param location = 'eastus2'

// Supplied at deploy time, never committed:
//   az deployment group create ... --parameters postgresAdminPassword=$POSTGRES_ADMIN_PASSWORD
param postgresAdminPassword = ''

param entraTenantId = ''
param entraClientId = ''
param entraIssuer = ''
param entraAudience = ''
