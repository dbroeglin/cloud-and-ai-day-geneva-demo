targetScope = 'resourceGroup'

param foundryAccountName string
param applicationInsightsName string
param foundryPrincipalIds string[]
param telemetryPrincipalIds string[]
param inferencePrincipalIds string[] = []

var foundryUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'
var inferenceRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
var monitoringPublisherRoleId = '3913510d-42f4-4e42-8a64-420c390055eb'

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}
resource insights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}
resource foundryAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in foundryPrincipalIds: {
    name: guid(account.id, principalId, foundryUserRoleId)
    scope: account
    properties: {
      principalId: principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRoleId)
    }
  }
]
resource inferenceAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in inferencePrincipalIds: {
    name: guid(account.id, principalId, inferenceRoleId)
    scope: account
    properties: {
      principalId: principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', inferenceRoleId)
    }
  }
]
resource telemetryAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in telemetryPrincipalIds: {
    name: guid(insights.id, principalId, monitoringPublisherRoleId)
    scope: insights
    properties: {
      principalId: principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', monitoringPublisherRoleId)
    }
  }
]
