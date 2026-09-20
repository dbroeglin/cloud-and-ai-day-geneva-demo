targetScope = 'resourceGroup'

param location string
param tags object

var suffix = uniqueString(resourceGroup().id)

module workspace 'br/public:avm/res/operational-insights/workspace:0.16.1' = {
  name: 'workspace'
  params: {
    name: 'log-${suffix}'
    location: location
    tags: tags
    skuName: 'PerGB2018'
    dataRetention: 30
    forceCmkForQuery: false
    features: {
      disableLocalAuth: true
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    enableTelemetry: false
  }
}

module insights 'br/public:avm/res/insights/component:0.8.0' = {
  name: 'insights'
  params: {
    name: 'appi-${suffix}'
    location: location
    tags: tags
    workspaceResourceId: workspace.outputs.resourceId
    disableLocalAuth: true
    disableIpMasking: false
    retentionInDays: 30
    enableTelemetry: false
  }
}

output name string = insights.outputs.name
output resourceId string = insights.outputs.resourceId
output connectionString string = insights.outputs.connectionString
output workspaceResourceId string = workspace.outputs.resourceId
