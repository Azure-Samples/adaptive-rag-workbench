param registryName string      // ACR resource name (not login‑server)
param principalId  string      // UAMI principalId

resource acr 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' existing = {
  name: registryName
}

resource pull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, principalId, 'acrpull')
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'   // AcrPull
    )
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
} 
