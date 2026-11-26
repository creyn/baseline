# 19. Deployment with Bicep through the Azure CLI, all resources in one group, and a smoke test on a test user

Date: 2026-11-26

## Status

Proposed. Changes point 8 of the first decision in [ADR-0004](0004-serverless-hosting-and-operations.md) ("deployed with azd and Bicep") and the deployment of its second decision (point 3). The rest of ADR-0004 stands.

## Context

The extractor is built and tested ([services/extractor](../../services/extractor/README.md)), and live evals call Document Intelligence and Azure OpenAI in a separate resource group, `rg-baseline-evals`, which the owner created by hand on 2026-11-26. The first deployment puts the extractor on Azure as a Container App with its queue and storage, so a document put on the `extract` queue ends as a `text` blob. Three questions came up that ADR-0004 does not answer, or answers with a tool that does not fit.

1. **The tool.** ADR-0004 names azd. azd deploys Bicep at subscription scope, which needs the deploying identity to create resource groups. Deployments at resource-group scope are an alpha feature behind a flag (`alpha.resourceGroupDeployments`, checked 2026-11-26 on Microsoft Learn, "feature versioning"). azd's other strength, building and pushing images, is not used, because the images go to GitHub Container Registry (ADR-0004, point 5).
2. **Where the AI services live.** ADR-0004 asks for one resource group in which the evals call the production AI services. Today the AI services are in `rg-baseline-evals`, made by hand with `az`. That is how the deployment of the model got the wrong upgrade option, `OnceNewDefaultVersionAvailable` (ADR-0017).
3. **How to know a deployment works.** Unit tests and evals do not touch queues, storage or roles. A wrong role or a wrong setting shows only when a real message goes through.

### Considered options

**The tool:**
1. **azd at subscription scope.** As ADR-0004 says. The deploying identity needs rights on the subscription.
2. **azd with the alpha resource-group scope.** Rights on one group only, but an alpha feature in the only environment.
3. **Bicep through `az deployment group create`** from GitHub Actions with OIDC. Generally available, rights on one group only, and the same Bicep. No local `azd up`; the owner runs the workflow on demand.

**The AI services:**
1. **Keep them in `rg-baseline-evals`**, referenced from the Bicep. Two groups, and the hand-made settings stay.
2. **Create them with the rest in Bicep**, in the production group, with the evals identity. The model deployment's upgrade option is in code. The evals move to the new services, and `rg-baseline-evals` is then deleted.

**Checking a deployment:**
1. **None.** The first real document finds the problems.
2. **A smoke test after every deployment:** a synthetic document goes through the deployed extractor, as a test user.

All options pass the gates. Scores from 1 to 5 on the criteria of [decision-criteria.md](../decision-criteria.md); the other criteria barely differ:

| The tool | K1 (40) | K4 (15) | K6 (10) |
|---|---|---|---|
| 1. azd, subscription scope | 3: broad rights for the deploying identity | 4 | 4 |
| 2. azd, alpha group scope | 2: an alpha feature in production | 4 | 4 |
| 3. Bicep through az | 5: rights on one group, generally available | 4 | 4 |

| The AI services | K1 (40) | K4 (15) | K6 (10) |
|---|---|---|---|
| 1. Keep them by hand | 2: two groups, settings outside code | 2 | 5 |
| 2. In Bicep, one group | 5: one group, every setting in code | 5 | 4 |

| Checking a deployment | K1 (40) | K5 (10) | K2 (20) |
|---|---|---|---|
| 1. None | 2 | 2 | 5 |
| 2. Smoke test | 5: a broken role shows at once | 4 | 4: one page of OCR and one LLM call a deployment |

## Decision

Option 3 for the tool, option 2 for the AI services, option 2 for checking.

1. **Infrastructure is one Bicep file set in `infra/`, deployed at resource-group scope** with `az deployment group create` by the workflow `deploy.yml`, signed in with OIDC to a deploying identity. Incremental mode, as ADR-0004 says.
2. **The deploying identity** has two roles on the production group only: Contributor, and Role Based Access Control Administrator, because the Bicep assigns roles to the services' identities. The owner creates it once, with the group. Limiting which roles it may assign (a condition on the assignment) is to check.
3. **Every Azure resource of Baseline is in the production group**, including Document Intelligence, Azure OpenAI with its model deployment (`versionUpgradeOption: OnceCurrentVersionExpired`, set in code) and the evals identity with its federated credential. After the first deployment the evals use the new services, and the owner deletes `rg-baseline-evals`.
4. **Images are public packages on GitHub Container Registry**, so Container Apps pulls them without credentials. The repository is public, so the image shows nothing that the code does not.
5. **The Service Bus scale rule signs in with the extractor's managed identity**, never with a connection string. The scaler reads the queue's message count, which needs the "Manage" right; the identity gets Azure Service Bus Data Owner on the `extract` queue only (to check on the first deployment).
6. **A smoke test runs after every deployment:**
   - it renders one synthetic document, puts its ZIP in `clean` and sends `ExtractRequested`, as a fixed test user (`userId` in [infra/README.md](../../infra/README.md));
   - it waits for the `text` blob and validates it against the contract;
   - its identity may write `clean` and read `text` only under the test user's path (a condition on the role assignment), and may send to `extract`. It cannot read any real user's data (G3). The `Extracted` message it causes stays in `status` until the API exists, which ignores a version it does not know (ADR-0005, point 5).

## Consequences

- The deploying identity can change anything in the production group, including role assignments. It signs in only from the `production` environment of the repository, which only the `main` branch may use, so only code the owner merged is deployed.
- Resource locks of ADR-0004 (point 6) need the right to write locks, which neither role gives. The owner adds them by hand after the first deployment, until a later change finds a narrower way.
- Moving the AI services means new endpoints for the evals and one more step for the owner. The live evals run against the new services before the old group is deleted.
- Each deployment costs one smoke test: one page of Document Intelligence and one LLM call, about 0.02 USD.
- The smoke test's documents stay under the test user's path. They are fictional; the sweeper of ADR-0012 must not count them as orphans (to note in the API change).
