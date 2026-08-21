@description('The API container app. System-assigned managed identity is granted RBAC on Postgres-adjacent Key Vault secret, Storage, Azure OpenAI, and Document Intelligence in main.bicep — no credential ever lives in an env var as plaintext.')
param location string
param namePrefix string
param environmentTag string
param containerAppsEnvironmentId string
param containerImage string
param containerRegistryLoginServer string
param keyVaultUri string
param databaseUrlSecretName string
param appInsightsConnectionString string
param openAiEndpoint string
param docIntelligenceEndpoint string
param storageBlobEndpoint string
param entraTenantId string
param entraClientId string
param entraIssuer string
param entraAudience string
param corsAllowedOrigins string

// Cold start matters for a pilot's first impression: keep one warm replica in
// prod, allow scale-to-zero in dev/staging where nobody is watching a stopwatch.
// This is the one place this stack spends idle money on purpose — see
// docs/cost-model.md, "Where the $/month actually goes."
var minReplicas = environmentTag == 'prod' ? 1 : 0
var maxReplicas = environmentTag == 'prod' ? 10 : 3

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-api'
  location: location
  tags: { environment: environmentTag, app: 'trialready' }
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: containerAppsEnvironmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http2'
        allowInsecure: false
      }
      registries: [
        { server: containerRegistryLoginServer, identity: 'system' }
      ]
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: '${keyVaultUri}secrets/${databaseUrlSecretName}'
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: containerImage
          resources: {
            // 0.5 vCPU / 1Gi comfortably serves the classification pipeline's I/O-bound
            // workload (mostly awaiting Azure OpenAI/Document Intelligence, not local
            // compute) for a 500-user pilot. Watch p95 CPU in Application Insights and
            // resize before it's a bottleneck, not after.
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'ENVIRONMENT', value: environmentTag }
            { name: 'LOG_LEVEL', value: environmentTag == 'prod' ? 'INFO' : 'DEBUG' }
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'KEY_VAULT_URL', value: keyVaultUri }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
            { name: 'AZURE_OPENAI_ENDPOINT', value: openAiEndpoint }
            { name: 'DOC_INTELLIGENCE_ENDPOINT', value: docIntelligenceEndpoint }
            { name: 'STORAGE_ACCOUNT_URL', value: storageBlobEndpoint }
            { name: 'ENTRA_TENANT_ID', value: entraTenantId }
            { name: 'ENTRA_CLIENT_ID', value: entraClientId }
            { name: 'ENTRA_ISSUER', value: entraIssuer }
            { name: 'ENTRA_AUDIENCE', value: entraAudience }
            { name: 'AUTH_DISABLED_FOR_LOCAL_DEV', value: 'false' }
            { name: 'CORS_ALLOWED_ORIGINS', value: corsAllowedOrigins }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/healthz', port: 8000 }
              initialDelaySeconds: 5
              periodSeconds: 15
            }
            {
              type: 'Readiness'
              httpGet: { path: '/readyz', port: 8000 }
              initialDelaySeconds: 5
              periodSeconds: 10
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-concurrency'
            http: {
              // 50 concurrent in-flight requests/replica before scaling out. At 500
              // users doing occasional binder uploads/gap-checks (not a chat-style
              // constant-connection workload), this comfortably absorbs bursty usage
              // like "everyone checks before Monday's monitor visit."
              metadata: { concurrentRequests: '50' }
            }
          }
        ]
      }
    }
  }
}

output principalId string = containerApp.identity.principalId
output fqdn string = containerApp.properties.configuration.ingress.fqdn
