# deployment

## Purpose

Baseline's resources on Azure, how they are deployed, and how a deployment is checked.

## Requirements

### Requirement: Infrastructure as code in one group

Every Azure resource of Baseline SHALL be defined in `infra/main.bicep` and deployed at resource-group scope to the production group. Local authentication MUST be off on Storage, Service Bus, the AI services and Application Insights.

#### Scenario: A key is not accepted

- **WHEN** anyone calls Storage, Service Bus, Document Intelligence or Azure OpenAI with a key or a shared access signature
- **THEN** the call is refused, because only Microsoft Entra ID is accepted

#### Scenario: The model version is pinned in code

- **WHEN** the Bicep is deployed
- **THEN** the model deployment has `versionUpgradeOption` `OnceCurrentVersionExpired`

### Requirement: Least privilege per identity

Each caller SHALL have its own managed identity with roles only on the containers, queues and services it uses, as listed in the [design](../../changes/archive/2026-11-27-add-extractor-deployment/design.md). The smoke test's identity MUST NOT read or write blobs outside the test user's path.

#### Scenario: The smoke identity and a real user's data

- **WHEN** the smoke identity reads `text/{another user}/...`
- **THEN** the read is refused

### Requirement: The extractor scales on its queue

The extractor SHALL run as a Container App with no ingress, from 0 to 1 replica, scaled on the length of the `extract` queue with its managed identity.

#### Scenario: Idle

- **WHEN** the `extract` queue stays empty
- **THEN** the extractor scales to zero

### Requirement: Every deployment is smoke tested

After each deployment, a synthetic document SHALL go through the deployed extractor as the test user, and the deployment fails unless a valid `text` blob with at least one result appears within 10 minutes.

#### Scenario: A missing role

- **WHEN** the extractor cannot read `clean` after a deployment
- **THEN** no `text` blob appears and the workflow fails
