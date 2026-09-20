targetScope = 'resourceGroup'

param environmentName string
param location string
param name string
param containerAppsEnvironmentName string
param containerRegistryName string
param imageName string
param identityResourceId string
param identityPrincipalId string
param identityClientId string
param tableEndpoint string
param eventNamespace string
param frontendOrigin string
param foundryProjectEndpoint string
param applicationInsightsConnectionString string

// azd applies this revision only after the real image has been cloud-built.
module registryAccess 'modules/acr-pull-role-assignment.bicep' = {
  name: 'backend-registry-access'
  params: {
    registryName: containerRegistryName
    principalId: identityPrincipalId
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    )
  }
}

// The azd pattern exposes only origins; the resource module also configures PUT and trace headers.
module backend 'br/public:avm/res/app/container-app:0.19.0' = {
  name: 'backend-revision'
  params: {
    name: name
    location: location
    tags: {
      'azd-env-name': environmentName
      'azd-service-name': 'backend'
    }
    environmentResourceId: resourceId('Microsoft.App/managedEnvironments', containerAppsEnvironmentName)
    managedIdentities: {
      userAssignedResourceIds: [identityResourceId]
    }
    registries: [
      {
        server: '${containerRegistryName}.azurecr.io'
        identity: identityResourceId
      }
    ]
    ingressExternal: true
    ingressTargetPort: 8000
    ingressAllowInsecure: false
    activeRevisionsMode: 'Single'
    scaleSettings: {
      minReplicas: 1
      maxReplicas: 2
    }
    corsPolicy: {
      allowedOrigins: [frontendOrigin]
      allowedMethods: ['GET', 'POST', 'PUT', 'OPTIONS']
      allowedHeaders: ['Content-Type', 'traceparent', 'tracestate']
      allowCredentials: false
      maxAge: 600
    }
    containers: [
      {
        name: 'main'
        image: imageName
        resources: {
          cpu: json('0.25')
          memory: '0.5Gi'
        }
        probes: [
          {
            type: 'Startup'
            httpGet: { path: '/api/health', port: 8000 }
            initialDelaySeconds: 5
            periodSeconds: 10
            failureThreshold: 10
          }
          {
            type: 'Readiness'
            httpGet: { path: '/api/health', port: 8000 }
            periodSeconds: 10
          }
          {
            type: 'Liveness'
            httpGet: { path: '/api/health', port: 8000 }
            initialDelaySeconds: 30
            periodSeconds: 30
          }
        ]
        env: [
          { name: 'APP_ENV', value: 'azure' }
          { name: 'AZURE_CLIENT_ID', value: identityClientId }
          { name: 'AZURE_STORAGE_TABLE_ENDPOINT', value: tableEndpoint }
          { name: 'EVENT_TABLE_NAME', value: 'EventCompanion' }
          { name: 'EVENT_NAMESPACE', value: eventNamespace }
          { name: 'FRONTEND_ORIGIN', value: frontendOrigin }
          { name: 'FOUNDRY_PROJECT_ENDPOINT', value: foundryProjectEndpoint }
          { name: 'FOUNDRY_AGENT_NAME', value: 'event-guide' }
          { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: applicationInsightsConnectionString }
          { name: 'OTEL_SERVICE_NAME', value: 'event-companion-backend' }
          { name: 'ENABLE_SENSITIVE_DATA', value: 'false' }
        ]
      }
    ]
    enableTelemetry: false
  }
  dependsOn: [registryAccess]
}

output AZURE_CONTAINER_APP_NAME string = backend.outputs.name
output AZURE_CONTAINER_APP_ID string = backend.outputs.resourceId
output BACKEND_ORIGIN string = 'https://${backend.outputs.fqdn}'
output VITE_API_BASE_URL string = 'https://${backend.outputs.fqdn}'
