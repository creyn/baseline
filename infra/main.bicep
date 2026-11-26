// Baseline on Azure, resource-group scope (ADR-0004, ADR-0019). Deployed by .github/workflows/deploy.yml.
// This first version holds the extractor and what it needs; later changes add the API, the checker and SQL.
// No keys: every service signs in with Microsoft Entra ID, and local auth is off where Azure allows it.
targetScope = 'resourceGroup'

@description('Region. Sweden Central for the EU Data Zone models (ADR-0004).')
param location string = resourceGroup().location

@description('The extractor image, e.g. ghcr.io/creyn/baseline-extractor:<git sha>.')
param extractorImage string

@description('GitHub repository subject prefix for OIDC, in the immutable-id form GitHub sends, e.g. repo:owner@123/baseline@456.')
param githubSubjectPrefix string

@description('Azure OpenAI deployment capacity in thousands of tokens per minute.')
param openAiCapacity int = 50

@description('The model and its pinned version (ADR-0007, ADR-0017).')
param openAiModel string = 'gpt-5.4-mini'
param openAiModelVersion string = '2026-03-17'

@description('The fixed test user of the smoke test (a UUIDv7, fictional).')
param smokeUserId string = '019ac000-0000-7000-8000-000000000001'

var suffix = substring(uniqueString(resourceGroup().id), 0, 6)
var name = 'baseline'

// ------------------------------------------------------------------ identities
resource extractorId 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${name}-extractor'
  location: location
}

resource evalsId 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${name}-evals'
  location: location
}

resource evalsFederation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: evalsId
  name: 'github-evals'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: '${githubSubjectPrefix}:environment:evals'
    audiences: ['api://AzureADTokenExchange']
  }
}

resource smokeId 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${name}-smoke'
  location: location
}

resource smokeFederation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: smokeId
  name: 'github-production'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: '${githubSubjectPrefix}:environment:production'
    audiences: ['api://AzureADTokenExchange']
  }
}

// ------------------------------------------------------------------ monitoring
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${name}-${suffix}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${name}-${suffix}'
  location: location
  kind: 'other'
  properties: {
    Application_Type: 'other'
    WorkspaceResourceId: logs.id
    DisableLocalAuth: true // telemetry is sent with Entra ID (Monitoring Metrics Publisher below)
  }
}

// ------------------------------------------------------------------ storage (ADR-0005: one container per stage)
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'st${name}${suffix}'
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    allowSharedKeyAccess: false
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource incoming 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: 'incoming'
}

resource clean 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: 'clean'
}

resource text 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: 'text'
}

resource lifecycle 'Microsoft.Storage/storageAccounts/managementPolicies@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'incoming-leftovers' // ADR-0005: the checker deletes incoming; leftovers go after a day
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: { blobTypes: ['blockBlob'], prefixMatch: ['incoming/'] }
            actions: { baseBlob: { delete: { daysAfterModificationGreaterThan: 1 } } }
          }
        }
      ]
    }
  }
}

// ------------------------------------------------------------------ Service Bus (ADR-0005: three queues)
resource bus 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: 'sb-${name}-${suffix}'
  location: location
  sku: { name: 'Basic', tier: 'Basic' }
  properties: {
    disableLocalAuth: true
    minimumTlsVersion: '1.2'
  }
}

var queueNames = ['check', 'extract', 'status']

resource queues 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = [for q in queueNames: {
  parent: bus
  name: q
  properties: {
    lockDuration: 'PT5M' // the maximum; receivers renew it while they work (ADR-0005, point 6)
    maxDeliveryCount: 10 // above the 5 tries of the services, so a crash on the last try dead-letters
    deadLetteringOnMessageExpiration: true
    defaultMessageTimeToLive: 'P14D'
  }
}]

// ------------------------------------------------------------------ AI services (ADR-0007, ADR-0017, ADR-0019)
resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'di-${name}-${suffix}'
  location: location
  kind: 'FormRecognizer'
  sku: { name: 'S0' } // F0 reads only the first 2 pages of a document
  properties: {
    customSubDomainName: 'di-${name}-${suffix}' // needed for Entra ID sign-in
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'aoai-${name}-${suffix}'
  location: location
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: 'aoai-${name}-${suffix}'
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource model 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: openAiModel
  sku: { name: 'DataZoneStandard', capacity: openAiCapacity } // EU Data Zone (G2)
  properties: {
    model: { format: 'OpenAI', name: openAiModel, version: openAiModelVersion }
    versionUpgradeOption: 'OnceCurrentVersionExpired' // pinned until retirement (ADR-0017)
  }
}

// ------------------------------------------------------------------ roles
var roles = {
  blobReader: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1' // Storage Blob Data Reader
  blobContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
  busOwner: '090c5cfd-751d-490a-894a-3ce6f1109419' // Azure Service Bus Data Owner (the scaler reads the message count)
  busSender: '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39' // Azure Service Bus Data Sender
  cognitiveUser: 'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services User
  openAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User
  metricsPublisher: '3913510d-42f4-4e42-8a64-420c390055eb' // Monitoring Metrics Publisher
}

// The extractor: reads clean, writes text, receives from extract, sends to status, calls the AI services.
resource extractorClean 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: clean
  name: guid(clean.id, extractorId.id, roles.blobReader)
  properties: { principalId: extractorId.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobReader) }
}

resource extractorText 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: text
  name: guid(text.id, extractorId.id, roles.blobContributor)
  properties: { principalId: extractorId.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobContributor) }
}

resource extractorExtract 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: queues[1]
  name: guid(queues[1].id, extractorId.id, roles.busOwner)
  properties: { principalId: extractorId.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.busOwner) }
}

resource extractorStatus 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: queues[2]
  name: guid(queues[2].id, extractorId.id, roles.busSender)
  properties: { principalId: extractorId.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.busSender) }
}

resource extractorDi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: documentIntelligence
  name: guid(documentIntelligence.id, extractorId.id, roles.cognitiveUser)
  properties: { principalId: extractorId.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cognitiveUser) }
}

resource extractorAoai 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: openAi
  name: guid(openAi.id, extractorId.id, roles.openAiUser)
  properties: { principalId: extractorId.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.openAiUser) }
}

resource extractorMetrics 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: insights
  name: guid(insights.id, extractorId.id, roles.metricsPublisher)
  properties: { principalId: extractorId.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.metricsPublisher) }
}

// The evals: the two AI services only, never storage or queues (ADR-0004).
resource evalsDi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: documentIntelligence
  name: guid(documentIntelligence.id, evalsId.id, roles.cognitiveUser)
  properties: { principalId: evalsId.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cognitiveUser) }
}

resource evalsAoai 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: openAi
  name: guid(openAi.id, evalsId.id, roles.cognitiveUser)
  properties: { principalId: evalsId.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cognitiveUser) }
}

// The smoke test: writes clean and reads text under the test user's path only (G3), sends to extract.
var smokePath = '${smokeUserId}/'
var smokeCleanCondition = '((!(ActionMatches{\'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read\'}) AND !(ActionMatches{\'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write\'}) AND !(ActionMatches{\'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/add/action\'}) AND !(ActionMatches{\'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/delete\'})) OR (@Resource[Microsoft.Storage/storageAccounts/blobServices/containers/blobs:path] StringStartsWith \'${smokePath}\'))'
var smokeTextCondition = '((!(ActionMatches{\'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read\'})) OR (@Resource[Microsoft.Storage/storageAccounts/blobServices/containers/blobs:path] StringStartsWith \'${smokePath}\'))'

resource smokeClean 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: clean
  name: guid(clean.id, smokeId.id, roles.blobContributor)
  properties: {
    principalId: smokeId.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobContributor)
    condition: smokeCleanCondition
    conditionVersion: '2.0'
  }
}

resource smokeText 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: text
  name: guid(text.id, smokeId.id, roles.blobReader)
  properties: {
    principalId: smokeId.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobReader)
    condition: smokeTextCondition
    conditionVersion: '2.0'
  }
}

resource smokeExtract 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: queues[1]
  name: guid(queues[1].id, smokeId.id, roles.busSender)
  properties: { principalId: smokeId.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.busSender) }
}

// ------------------------------------------------------------------ Container Apps (ADR-0004: scale to zero)
resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${name}-${suffix}'
  location: location
  properties: {
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }]
    appLogsConfiguration: { destination: 'azure-monitor' } // to Log Analytics through the diagnostic setting below, no shared key
  }
}

resource environmentLogs 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: environment
  name: 'to-log-analytics'
  properties: {
    workspaceId: logs.id
    logs: [{ categoryGroup: 'allLogs', enabled: true }]
  }
}

resource extractor 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${name}-extractor'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${extractorId.id}': {} } }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single' // the previous revision stays for a rollback (ADR-0004, point 5)
    }
    template: {
      containers: [
        {
          name: 'extractor'
          image: extractorImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'AZURE_CLIENT_ID', value: extractorId.properties.clientId } // DefaultAzureCredential picks this identity
            { name: 'SERVICEBUS_NAMESPACE', value: '${bus.name}.servicebus.windows.net' }
            { name: 'STORAGE_ACCOUNT_URL', value: storage.properties.primaryEndpoints.blob }
            { name: 'DOCUMENT_INTELLIGENCE_ENDPOINT', value: documentIntelligence.properties.endpoint }
            { name: 'AZURE_OPENAI_ENDPOINT', value: openAi.properties.endpoint }
            { name: 'AZURE_OPENAI_DEPLOYMENT', value: model.name }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: insights.properties.ConnectionString } // an address, not a key: local auth is off
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1 // ADR-0004: at most one replica
        rules: [
          {
            name: 'extract-queue'
            custom: {
              type: 'azure-servicebus'
              identity: extractorId.id // no connection string
              metadata: { namespace: bus.name, queueName: 'extract', messageCount: '1' }
            }
          }
        ]
      }
    }
  }
  dependsOn: [extractorClean, extractorText, extractorExtract, extractorStatus, extractorDi, extractorAoai, extractorMetrics]
}

output storageAccountUrl string = storage.properties.primaryEndpoints.blob
output serviceBusNamespace string = '${bus.name}.servicebus.windows.net'
output documentIntelligenceEndpoint string = documentIntelligence.properties.endpoint
output openAiEndpoint string = openAi.properties.endpoint
output openAiDeployment string = model.name
output evalsClientId string = evalsId.properties.clientId
output smokeClientId string = smokeId.properties.clientId
output smokeUserId string = smokeUserId
