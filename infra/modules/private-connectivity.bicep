targetScope = 'resourceGroup'

param location string
param tags object
param storageAccountResourceId string

var suffix = uniqueString(resourceGroup().id)
var vnetName = 'vnet-${suffix}'

// Workload-profile ACA requires a dedicated /27 or larger, delegated to Microsoft.App/environments.
// No peerings, service endpoints, or custom DNS servers: only Table traffic uses Private Link.
module vnet 'br/public:avm/res/network/virtual-network:0.10.2' = {
  name: 'backend-vnet'
  params: {
    name: vnetName
    location: location
    tags: tags
    addressPrefixes: ['10.42.0.0/24']
    subnets: [
      {
        name: 'aca-infrastructure'
        addressPrefix: '10.42.0.0/27'
        delegation: 'Microsoft.App/environments'
      }
      {
        name: 'private-endpoints'
        addressPrefix: '10.42.0.32/28'
        privateEndpointNetworkPolicies: 'Disabled'
      }
    ]
    enableTelemetry: false
  }
}

module tableDns 'br/public:avm/res/network/private-dns-zone:0.8.1' = {
  name: 'table-private-dns'
  params: {
    name: 'privatelink.table.${environment().suffixes.storage}'
    location: 'global'
    tags: tags
    virtualNetworkLinks: [
      {
        name: '${vnetName}-link'
        virtualNetworkResourceId: vnet.outputs.resourceId
        registrationEnabled: false
        resolutionPolicy: 'Default'
      }
    ]
    enableTelemetry: false
  }
}

module tableEndpoint 'br/public:avm/res/network/private-endpoint:0.12.1' = {
  name: 'table-private-endpoint'
  params: {
    name: 'pep-table-${suffix}'
    location: location
    tags: tags
    subnetResourceId: vnet.outputs.subnetResourceIds[1]
    customNetworkInterfaceName: 'nic-pep-table-${suffix}'
    privateLinkServiceConnections: [
      {
        name: 'table'
        properties: {
          privateLinkServiceId: storageAccountResourceId
          groupIds: ['table']
        }
      }
    ]
    privateDnsZoneGroup: {
      name: 'default'
      privateDnsZoneGroupConfigs: [
        {
          name: 'table'
          privateDnsZoneResourceId: tableDns.outputs.resourceId
        }
      ]
    }
    enableTelemetry: false
  }
}

output vnetResourceId string = vnet.outputs.resourceId
output acaSubnetResourceId string = vnet.outputs.subnetResourceIds[0]
output tablePrivateEndpointResourceId string = tableEndpoint.outputs.resourceId
output tablePrivateDnsZoneResourceId string = tableDns.outputs.resourceId
