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
module backend 'br/public:avm/ptn/azd/acr-container-app:0.5.0' = {
  name: 'backend-revision'
  params: {
    name: name
    location: location
    tags: {
      'azd-env-name': environmentName
      'azd-service-name': 'backend'
    }
    containerAppsEnvironmentName: containerAppsEnvironmentName
    containerRegistryName: containerRegistryName
    imageName: imageName
    identityName: last(split(identityResourceId, '/'))
    userAssignedIdentityResourceId: identityResourceId
    principalId: identityPrincipalId
    containerCpuCoreCount: '0.25'
    containerMemory: '0.5Gi'
    containerMinReplicas: 1
    containerMaxReplicas: 2
    targetPort: 8000
    ingressAllowInsecure: false
    allowedOrigins: [frontendOrigin]
    containerProbes: [
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
    enableTelemetry: false
  }
}

output AZURE_CONTAINER_APP_NAME string = backend.outputs.name
output AZURE_CONTAINER_APP_ID string = backend.outputs.resourceId
output BACKEND_ORIGIN string = backend.outputs.uri
output VITE_API_BASE_URL string = backend.outputs.uri
