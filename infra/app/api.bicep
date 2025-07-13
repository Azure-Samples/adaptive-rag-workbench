param name string
param location string = resourceGroup().location
param tags object = {}

param containerAppsEnvironmentName string
param keyVaultName string
param openAiEndpoint string
param searchEndpoint string
param searchIndexName string
param documentIntelligenceEndpoint string
param storageAccountName string
param applicationInsightsConnectionString string
param identityName string
param image string
param registryServer string

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' existing = {
  name: containerAppsEnvironmentName
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: identityName
}

resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: keyVaultName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2022-05-01' existing = {
  name: storageAccountName
}

resource api 'Microsoft.App/containerApps@2023-05-01' = {
  name: name
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      registries: !empty(registryServer) ? [
        {
          server: registryServer
          identity: identity.id
        }
      ] : []
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
        }
      }
      secrets: [
        {
          name: 'openai-key'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/AZURE-OPENAI-KEY'
          identity: identity.id
        }
        {
          name: 'search-key'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/AZURE-SEARCH-KEY'
          identity: identity.id
        }
        {
          name: 'document-intelligence-key'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/AZURE-DOCUMENT-INTELLIGENCE-KEY'
          identity: identity.id
        }
        {
          name: 'storage-key'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/AZURE-STORAGE-KEY'
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          image: image
          name: 'api'
          env: [
            {
              name: 'AZURE_CLIENT_ID'
              value: identity.properties.clientId
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: openAiEndpoint
            }
            {
              name: 'AZURE_OPENAI_KEY'
              secretRef: 'openai-key'
            }
            {
              name: 'AZURE_OPENAI_CHAT_DEPLOYMENT'
              value: 'chat'
            }
            {
              name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT'
              value: 'embedding'
            }
            {
              name: 'AZURE_SEARCH_ENDPOINT'
              value: searchEndpoint
            }
            {
              name: 'AZURE_SEARCH_KEY'
              secretRef: 'search-key'
            }
            {
              name: 'AZURE_SEARCH_INDEX'
              value: searchIndexName
            }
            {
              name: 'AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT'
              value: documentIntelligenceEndpoint
            }
            {
              name: 'AZURE_DOCUMENT_INTELLIGENCE_KEY'
              secretRef: 'document-intelligence-key'
            }
            {
              name: 'AZURE_STORAGE_ACCOUNT'
              value: storageAccount.name
            }
            {
              name: 'AZURE_STORAGE_KEY'
              secretRef: 'storage-key'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: applicationInsightsConnectionString
            }
          ]
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 10
      }
    }
  }
}

output SERVICE_API_IDENTITY_PRINCIPAL_ID string = identity.properties.principalId
output SERVICE_API_NAME string = api.name
output SERVICE_API_URI string = 'https://${api.properties.configuration.ingress.fqdn}'
