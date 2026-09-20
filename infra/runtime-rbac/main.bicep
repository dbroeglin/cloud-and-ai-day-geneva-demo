targetScope = 'subscription'

param resourceGroupName string
param foundryAccountName string
param applicationInsightsName string
@description('Actual acting agent principal IDs. Entra blueprint principals are not Azure RBAC eligible.')
param agentPrincipalIds string = ''

module runtimeAccess '../modules/identity-access.bicep' = if (!empty(agentPrincipalIds)) {
  name: 'agent-runtime-access'
  scope: resourceGroup(resourceGroupName)
  params: {
    foundryAccountName: foundryAccountName
    applicationInsightsName: applicationInsightsName
    foundryPrincipalIds: split(agentPrincipalIds, ',')
    inferencePrincipalIds: split(agentPrincipalIds, ',')
    telemetryPrincipalIds: split(agentPrincipalIds, ',')
  }
}
