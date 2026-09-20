targetScope = 'subscription'

param resourceGroupName string
param foundryAccountName string
param applicationInsightsName string
@description('Comma-separated actual instance and blueprint principal IDs queried after agent deployment.')
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
