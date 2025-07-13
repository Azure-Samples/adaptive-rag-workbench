targetScope = 'subscription'


@description('Full image reference for the API container.')
param apiImage string = ''

@description('Full image reference for the Web container.')
param webImage string = ''

@description('Login server name of the ACR that holds both images.')
param containerRegistryLoginServer string = ''

@description('Name of the container registry')
param containerRegistryName string = ''

@minLength(1)
@maxLength(64)
@description('Name of the the environment which is used to generate a short unique hash used in all resources.')
param environmentName string = 'arag'

@minLength(1)
@description('Primary location for all resources')
param location string = 'eastus2'

@description('Primary location for all resources')
@allowed(['eastus', 'eastus2', 'westus', 'westus2', 'westus3'])
param openAiLocation string = 'eastus2'

@description('Location for the OpenAI resource group')
@allowed(['eastus', 'eastus2', 'westus', 'westus2', 'westus3'])
param openAiResourceGroupLocation string = location

@description('Name of the API service')
param apiServiceName string = ''

@description('Name of the web service')
param webServiceName string = ''

@description('Name of the OpenAI service')
param openAiServiceName string = ''

@description('Name of the search service')
param searchServiceName string = ''

@description('Name of the document intelligence service')
param documentIntelligenceServiceName string = ''

@description('Name of the storage account')
param storageAccountName string = ''

@description('Name of the key vault')
param keyVaultName string = ''

@description('Name of the log analytics workspace')
param logAnalyticsName string = ''

@description('Name of the application insights')
param applicationInsightsName string = ''

@description('Id of the user or app to assign application roles')
param principalId string = ''



var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }

// Organize resources in a resource group
resource resourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: '${abbrs.resourcesResourceGroups}${environmentName}'
  location: location
  tags: tags
}

resource openAiResourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = if (openAiResourceGroupLocation != location) {
  name: '${abbrs.resourcesResourceGroups}${environmentName}-openai'
  location: openAiResourceGroupLocation
  tags: tags
}

// Create an App Service Plan to group applications under the same payment plan and SKU
module appServicePlan './app/app-service-plan.bicep' = {
  name: 'app-service-plan'
  scope: resourceGroup
  params: {
    name: !empty(apiServiceName) ? apiServiceName : '${abbrs.webServerFarms}api-${resourceToken}'
    location: location
    tags: tags
    sku: {
      name: 'B1'
      capacity: 1
    }
  }
}

// Container Apps Environment
module containerAppsEnvironment './app/container-apps-env.bicep' = {
  name: 'container-apps-env'
  scope: resourceGroup
  params: {
    name: '${abbrs.appManagedEnvironments}${resourceToken}'
    location: location
    tags: tags
    logAnalyticsWorkspaceName: monitoring.outputs.logAnalyticsWorkspaceName
  }
}

// The application backend (depends on secrets being created first)
module api './app/api.bicep' = {
  name: 'api'
  scope: resourceGroup
  dependsOn: [
    kvSecrets
    apiKeyVaultAccess
    apiAcrAccess
  ]
  params: {
    name: !empty(apiServiceName) ? apiServiceName : '${abbrs.appContainerApps}api-${resourceToken}'
    location: location
    tags: tags
    containerAppsEnvironmentName: containerAppsEnvironment.outputs.name
    keyVaultName: keyVault.outputs.name
    openAiEndpoint: openAiResourceGroupLocation == location ? openAi.outputs.endpoint : openAiSeparate.outputs.endpoint
    searchEndpoint: searchService.outputs.endpoint
    searchIndexName: 'adaptive-rag-index'
    documentIntelligenceEndpoint: documentIntelligence.outputs.endpoint
    storageAccountName: storage.outputs.name
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    identityName: apiIdentity.outputs.identityName
    image: !empty(apiImage) ? apiImage : 'nginx:latest'
    registryServer: containerRegistry.outputs.loginServer
  }
}

// The application frontend
module web './app/web.bicep' = {
  name: 'web'
  scope: resourceGroup
  dependsOn: [
    apiAcrAccess
  ]
  params: {
    name: !empty(webServiceName) ? webServiceName : '${abbrs.appContainerApps}web-${resourceToken}'
    location: location
    tags: tags
    containerAppsEnvironmentName: containerAppsEnvironment.outputs.name
    apiBaseUrl: api.outputs.SERVICE_API_URI
    apiServiceName: api.outputs.SERVICE_API_NAME
    image: !empty(webImage) ? webImage : 'nginx:latest'
    registryServer: containerRegistry.outputs.loginServer
    identityName: apiIdentity.outputs.identityName
  }
}

// Create an Azure OpenAI instance (same location as main resources)
module openAi './app/ai/cognitive-services.bicep' = if (openAiResourceGroupLocation == location) {
  name: 'openai'
  scope: resourceGroup
  params: {
    name: !empty(openAiServiceName) ? openAiServiceName : '${abbrs.cognitiveServicesAccounts}${resourceToken}'
    location: openAiLocation
    tags: tags
    sku: {
      name: 'S0'
    }
    deployments: [
      {
        name: 'chat'
        model: {
          format: 'OpenAI'
          name: 'gpt-4o-mini'
          version: '2024-07-18'
        }
        sku: {
          name: 'Standard'
          capacity: 10
        }
      }
      {
        name: 'embedding'
        model: {
          format: 'OpenAI'
          name: 'text-embedding-3-large'
          version: '1'
        }
        sku: {
          name: 'Standard'
          capacity: 120
        }
      }
    ]
  }
}

// Create an Azure OpenAI instance (different location from main resources)
module openAiSeparate './app/ai/cognitive-services.bicep' = if (openAiResourceGroupLocation != location) {
  name: 'openai-separate'
  scope: openAiResourceGroup
  params: {
    name: !empty(openAiServiceName) ? openAiServiceName : '${abbrs.cognitiveServicesAccounts}${resourceToken}'
    location: openAiLocation
    tags: tags
    sku: {
      name: 'S0'
    }
    deployments: [
      {
        name: 'chat'
        model: {
          format: 'OpenAI'
          name: 'gpt-4o-mini'
          version: '2024-07-18'
        }
        sku: {
          name: 'Standard'
          capacity: 10
        }
      }
      {
        name: 'embedding'
        model: {
          format: 'OpenAI'
          name: 'text-embedding-3-large'
          version: '1'
        }
        sku: {
          name: 'Standard'
          capacity: 120
        }
      }
    ]
  }
}

// Create Azure AI Search
module searchService './app/ai/search.bicep' = {
  name: 'search-service'
  scope: resourceGroup
  params: {
    name: !empty(searchServiceName) ? searchServiceName : '${abbrs.searchSearchServices}${resourceToken}'
    location: location
    tags: tags
    sku: {
      name: 'basic'
    }
    semanticSearch: 'free'
  }
}

// Create Azure Document Intelligence
module documentIntelligence './app/ai/document-intelligence.bicep' = {
  name: 'document-intelligence'
  scope: resourceGroup
  params: {
    name: !empty(documentIntelligenceServiceName) ? documentIntelligenceServiceName : '${abbrs.cognitiveServicesFormRecognizer}${resourceToken}'
    location: location
    tags: tags
    sku: {
      name: 'S0'
    }
  }
}

// Create a storage account
module storage './app/storage-account.bicep' = {
  name: 'storage'
  scope: resourceGroup
  params: {
    name: !empty(storageAccountName) ? storageAccountName : '${abbrs.storageStorageAccounts}${resourceToken}'
    location: location
    tags: tags
    containers: [
      {
        name: 'documents'
        publicAccess: 'None'
      }
      {
        name: 'ingest-drop'
        publicAccess: 'None'
      }
    ]
  }
}

// Create a keyvault to store secrets
module keyVault './app/keyvault.bicep' = {
  name: 'keyvault'
  scope: resourceGroup
  params: {
    name: !empty(keyVaultName) ? keyVaultName : '${abbrs.keyVaultVaults}${resourceToken}'
    location: location
    tags: tags
  }
}

// Monitor application with Azure Monitor
module monitoring './app/monitoring.bicep' = {
  name: 'monitoring'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    logAnalyticsName: !empty(logAnalyticsName) ? logAnalyticsName : '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    applicationInsightsName: !empty(applicationInsightsName) ? applicationInsightsName : '${abbrs.insightsComponents}${resourceToken}'
  }
}

// Create Azure Container Registry
module containerRegistry './app/container-registry.bicep' = {
  name: 'container-registry'
  scope: resourceGroup
  params: {
    name: !empty(containerRegistryName) ? containerRegistryName : '${abbrs.containerRegistryRegistries}${resourceToken}'
    location: location
    tags: tags
  }
}

// User assigned managed identity to be used by the API to access other Azure resources
module apiIdentity './app/identity.bicep' = {
  name: 'api-identity'
  scope: resourceGroup
  params: {
    name: '${abbrs.managedIdentityUserAssignedIdentities}api-${resourceToken}'
    location: location
    tags: tags
  }
}

// Give the API access to KeyVault
module apiKeyVaultAccess './app/rbac/keyvault-access.bicep' = {
  name: 'api-keyvault-access'
  scope: resourceGroup
  params: {
    keyVaultName: keyVault.outputs.name
    principalId: apiIdentity.outputs.identityPrincipalId
  }
}

// Give the API access to the Container Registry
module apiAcrAccess './app/rbac/acr-access.bicep' = {
  name: 'api-acr-access'
  scope: resourceGroup
  params: {
    registryName: containerRegistry.outputs.name
    principalId: apiIdentity.outputs.identityPrincipalId
  }
}

// Give the API access to the OpenAI service (same location)
module apiOpenAiAccess './app/rbac/openai-access.bicep' = if (openAiResourceGroupLocation == location) {
  name: 'api-openai-access'
  scope: resourceGroup
  params: {
    openAiName: openAi.outputs.name
    principalId: apiIdentity.outputs.identityPrincipalId
  }
}

// Give the API access to the OpenAI service (different location)
module apiOpenAiAccessSeparate './app/rbac/openai-access.bicep' = if (openAiResourceGroupLocation != location) {
  name: 'api-openai-access-separate'
  scope: openAiResourceGroup
  params: {
    openAiName: openAiSeparate.outputs.name
    principalId: apiIdentity.outputs.identityPrincipalId
  }
}

// Give the API access to the search service
module apiSearchAccess './app/rbac/search-access.bicep' = {
  name: 'api-search-access'
  scope: resourceGroup
  params: {
    searchServiceName: searchService.outputs.name
    principalId: apiIdentity.outputs.identityPrincipalId
  }
}

// Give the API access to the document intelligence service
module apiDocumentIntelligenceAccess './app/rbac/document-intelligence-access.bicep' = {
  name: 'api-document-intelligence-access'
  scope: resourceGroup
  params: {
    documentIntelligenceName: documentIntelligence.outputs.name
    principalId: apiIdentity.outputs.identityPrincipalId
  }
}

// Give the API access to the storage account
module apiStorageAccess './app/rbac/storage-access.bicep' = {
  name: 'api-storage-access'
  scope: resourceGroup
  params: {
    storageAccountName: storage.outputs.name
    principalId: apiIdentity.outputs.identityPrincipalId
  }
}

// Key Vault secrets for service keys
module kvSecrets 'app/keyvault-secrets.bicep' = {
  name: 'keyvault-secrets'
  scope: resourceGroup
  params: {
    keyVaultName: keyVault.outputs.name
    openAiKey: openAiResourceGroupLocation == location ? openAi.outputs.key : openAiSeparate.outputs.key
    searchKey: searchService.outputs.key
    documentIntelligenceKey: documentIntelligence.outputs.key
    storageKey: storage.outputs.key
  }
}

// Data outputs
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = resourceGroup.name

// Application outputs
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.applicationInsightsConnectionString
output AZURE_KEY_VAULT_ENDPOINT string = keyVault.outputs.endpoint
output AZURE_KEY_VAULT_NAME string = keyVault.outputs.name

// OpenAI outputs
output AZURE_OPENAI_ENDPOINT string = openAiResourceGroupLocation == location ? openAi.outputs.endpoint : openAiSeparate.outputs.endpoint
output AZURE_OPENAI_KEY string = openAiResourceGroupLocation == location ? openAi.outputs.key : openAiSeparate.outputs.key
output AZURE_OPENAI_CHAT_DEPLOYMENT string = 'chat'
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = 'embedding'

// Search outputs
output AZURE_SEARCH_ENDPOINT string = searchService.outputs.endpoint
output AZURE_SEARCH_KEY string = searchService.outputs.key
output AZURE_SEARCH_INDEX string = 'adaptive-rag-index'

// Document Intelligence outputs
output AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT string = documentIntelligence.outputs.endpoint
output AZURE_DOCUMENT_INTELLIGENCE_KEY string = documentIntelligence.outputs.key

// Storage outputs
output AZURE_STORAGE_ACCOUNT string = storage.outputs.name
output AZURE_STORAGE_KEY string = storage.outputs.key
output AZURE_STORAGE_CONNECTION_STRING string = storage.outputs.connectionString

// Container Registry outputs
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer

// Service outputs
output SERVICE_API_IDENTITY_PRINCIPAL_ID string = apiIdentity.outputs.identityPrincipalId
output SERVICE_API_NAME string = api.outputs.SERVICE_API_NAME
output SERVICE_API_URI string = api.outputs.SERVICE_API_URI
output SERVICE_WEB_NAME string = web.outputs.SERVICE_WEB_NAME
output SERVICE_WEB_URI string = web.outputs.SERVICE_WEB_URI
