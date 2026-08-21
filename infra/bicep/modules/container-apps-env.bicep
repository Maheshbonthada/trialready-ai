@description('Container Apps Environment on the Consumption plan — scale-to-zero when idle, pay per vCPU-second/GiB-second under load. Right choice for a pre-revenue pilot: zero fixed compute cost while nobody is using it, still autoscales cleanly to 500 concurrent users on the same environment.')
param location string
param namePrefix string
param environmentTag string
param logAnalyticsWorkspaceId string
param logAnalyticsCustomerId string
@secure()
param logAnalyticsSharedKey string

resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${namePrefix}-cae'
  location: location
  tags: { environment: environmentTag, app: 'trialready' }
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
    // Consumption-only workload profile: no dedicated/reserved capacity, which is
    // exactly the "no fixed cost while unused" property this pilot needs.
    workloadProfiles: [
      { name: 'Consumption', workloadProfileType: 'Consumption' }
    ]
  }
}

output environmentId string = containerAppsEnv.id
