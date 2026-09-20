targetScope = 'resourceGroup'

param location string
param tags object
param eventNamespace string
param workspaceResourceId string
param applicationInsightsName string
param foundryAccountName string
param foundryAccountPrincipalId string
param foundryProjectPrincipalId string
param foundryProjectName string

var suffix = uniqueString(resourceGroup().id)
var backendName = 'api-private-${suffix}'

module identity 'br/public:avm/res/managed-identity/user-assigned-identity:0.6.0' = {
  name: 'backend-identity'
  params: {
    name: 'id-backend-${suffix}'
    location: location
    tags: tags
    enableTelemetry: false
  }
}

module storage 'br/public:avm/res/storage/storage-account:0.33.1' = {
  name: 'event-storage'
  params: {
    name: 'st${suffix}'
    location: location
    tags: union(tags, { 'event-namespace': eventNamespace })
    skuName: 'Standard_LRS'
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    allowBlobPublicAccess: false
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'None'
    }
    blobServices: {}
    tableServices: {
      tables: [{ name: 'EventCompanion' }]
    }
    roleAssignments: [
      {
        principalId: identity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
      }
    ]
    enableTelemetry: false
  }
}

module privateConnectivity 'private-connectivity.bicep' = {
  name: 'private-connectivity'
  params: {
    location: location
    tags: tags
    storageAccountResourceId: storage.outputs.resourceId
  }
}

module frontend 'br/public:avm/res/web/static-site:0.9.6' = {
  name: 'frontend'
  params: {
    name: 'swa-${suffix}'
    location: location
    tags: union(tags, { 'azd-service-name': 'frontend' })
    sku: 'Free'
    provider: 'None'
    publicNetworkAccess: 'Enabled'
    enableTelemetry: false
  }
}

module containerEnvironment 'br/public:avm/res/app/managed-environment:0.16.0' = {
  name: 'container-environment'
  params: {
    // A new environment preserves the existing backend until migration is verified.
    name: 'cae-private-${suffix}'
    location: location
    tags: tags
    zoneRedundant: false
    publicNetworkAccess: 'Enabled'
    internal: false
    infrastructureSubnetResourceId: privateConnectivity.outputs.acaSubnetResourceId
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    appLogsConfiguration: {
      destination: 'azure-monitor'
    }
    diagnosticSettings: [
      {
        name: 'shared-workspace'
        workspaceResourceId: workspaceResourceId
        logCategoriesAndGroups: [{ categoryGroup: 'allLogs' }]
        metricCategories: []
      }
    ]
    enableTelemetry: false
  }
}

module applicationAccess 'identity-access.bicep' = {
  name: 'application-access'
  params: {
    foundryAccountName: foundryAccountName
    applicationInsightsName: applicationInsightsName
    foundryPrincipalIds: [identity.outputs.principalId, foundryProjectPrincipalId]
    telemetryPrincipalIds: [identity.outputs.principalId, foundryProjectPrincipalId, foundryAccountPrincipalId]
  }
}

// Revision deployment creates the backend later; registering its URL does not discover tools.
var backendOrigin = 'https://${backendName}.${containerEnvironment.outputs.defaultDomain}'
module agendaConnection 'connections.bicep' = {
  name: 'public-agenda-connection'
  params: {
    foundryAccountName: foundryAccountName
    foundryProjectName: foundryProjectName
    connections: [
      {
        name: 'event-agenda'
        category: 'RemoteTool'
        target: '${backendOrigin}/mcp'
        authType: 'None'
      }
    ]
  }
}

output backendName string = backendName
output backendOrigin string = backendOrigin
output frontendOrigin string = 'https://${frontend.outputs.defaultHostname}'
output environmentName string = containerEnvironment.outputs.name
output identityResourceId string = identity.outputs.resourceId
output identityPrincipalId string = identity.outputs.principalId
output identityClientId string = identity.outputs.clientId
output tableEndpoint string = storage.outputs.serviceEndpoints.table
output vnetResourceId string = privateConnectivity.outputs.vnetResourceId
output acaSubnetResourceId string = privateConnectivity.outputs.acaSubnetResourceId
output tablePrivateEndpointResourceId string = privateConnectivity.outputs.tablePrivateEndpointResourceId
output tablePrivateDnsZoneResourceId string = privateConnectivity.outputs.tablePrivateDnsZoneResourceId
