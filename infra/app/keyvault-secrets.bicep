param keyVaultName string
param openAiKey string
param searchKey string
param documentIntelligenceKey string
param storageKey string

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource kvOpenAiKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'AZURE-OPENAI-KEY'
  parent: keyVault
  properties: { value: openAiKey }
}

resource kvSearchKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'AZURE-SEARCH-KEY'
  parent: keyVault
  properties: { value: searchKey }
}

resource kvDocKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'AZURE-DOCUMENT-INTELLIGENCE-KEY'
  parent: keyVault
  properties: { value: documentIntelligenceKey }
}

resource kvStorageKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'AZURE-STORAGE-KEY'
  parent: keyVault
  properties: { value: storageKey }
} 
