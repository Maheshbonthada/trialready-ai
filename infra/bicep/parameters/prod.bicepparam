using '../main.bicep'

param environmentTag = 'prod'
param namePrefix = 'tr-prod'
param location = 'eastus2'

// Supplied at deploy time via GitHub Actions secret, never committed.
param postgresAdminPassword = ''

param entraTenantId = ''
param entraClientId = ''
param entraIssuer = ''
param entraAudience = ''
