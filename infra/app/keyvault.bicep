param name string
param location string = resourceGroup().location
param tags object = {}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }

    // turn on RBAC and allow public access (you can lock this down later)
    enableRbacAuthorization: true
    publicNetworkAccess: 'Enabled'
  }
}

output endpoint string = keyVault.properties.vaultUri
output id string = keyVault.id
output name string = keyVault.name
