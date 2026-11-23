# 4. Serverless hosting on Azure, one environment, deployment and operations

Date: 2026-11-23

## Status

Accepted

## Context

Where Baseline runs, how a change reaches it, and how the owner learns that something needs attention.

### Serverless hosting on Azure, everything scales to zero

Baseline serves a family of up to 10 people. The workload ([use-cases.md](../use-cases.md)) is tiny and bursty: a few imports a month, browsing results a few times a week, and long idle periods. AI usage costs about 3 USD a month for 10 people. The fixed cost of the services is therefore the bill.

Data and AI processing must stay in the EU (G2). Poland Central would be the closest region, but the Azure price list shows Document Intelligence there only as batch layout, without the synchronous analysis the extractor needs. Sweden Central has every service we use, including Azure OpenAI models in the EU Data Zone.

Fixed monthly cost of the main options (list prices, Sweden Central, 2026-11-22):
- Azure AI Search Basic: 73.73 USD.
- The API always on (one replica, 0.5 vCPU, 1 GiB), after the free grant: about 10 USD.
- Azure SQL Database: Basic 4.90 USD, always on; serverless with the free offer 0 USD, with auto-pause.
- Azure Container Registry Basic: 5.07 USD; GitHub Container Registry: 0 USD.

Restricting outbound traffic of a container is not available in a Consumption-only Container Apps environment. It needs a workload profiles environment with a custom virtual network, and Azure Firewall or a NAT gateway, all of which add fixed cost.

#### Considered options

1. **Always on, with AI Search:** the API with one replica, SQL Basic, AI Search Basic, ACR. About 94 USD a month. No cold start.
2. **Always on, without AI Search:** the API with one replica, SQL Basic. About 15 USD a month. No cold start.
3. **Everything scales to zero:** Container Apps on Consumption with zero minimum replicas, SQL serverless with the free offer and auto-pause, no AI Search, images in GHCR. About 0 USD fixed. The first request after idle time waits for the containers and the database to start.

| Criterion (weight) | 1 | 2 | 3 |
|---|---|---|---|
| K1 simple, self-healing (40) | 4 | 4 | 4 |
| K2 cost (20) | 1 | 3 | 5 |
| K4 engineering practice (15) | 4 | 4 | 4 |
| K5 testable in CI (10) | 4 | 4 | 4 |
| K6 time to deliver (10) | 4 | 4 | 4 |
| K7 performance (5) | 5 | 5 | 3 |
| **Result** | **69** | **77** | **83** |

### One environment, deployment and operations

Baseline has one owner, who also operates it, and about 10 users. Tests run in CI against emulators ([ADR-0014](0014-development-with-ai-agents.md)). Evals cannot use emulators: they need the real Document Intelligence and Azure OpenAI. Everything scales to zero and costs about 0 USD when idle (see above).

Questions to settle:
- whether there is a second environment for development and evals;
- how a change reaches production, including database migrations with Row-Level Security;
- how a mistake in a deployment is prevented from deleting data;
- which alerts exist and who receives them.

#### Considered options

1. **Two environments, dev and prod.** Changes are tried in dev first. A second copy of every resource, and a second set of things to keep in step, for one person.
2. **Production only.** CI with emulators before the merge. Evals call the production AI services, which keep no state for us. A bad release is rolled back to the previous revision.

| Criterion (weight) | 1: dev and prod | 2: prod only |
|---|---|---|
| K1 simple, self-healing (40) | 3 | 5 |
| K2 cost (20) | 4 | 5 |
| K4 engineering practice (15) | 5 | 3 |
| K5 testable in CI (10) | 4 | 4 |
| K6 time to deliver (10) | 3 | 5 |
| K7 performance (5) | 4 | 4 |
| **Result** | **73** | **91** |

## Decision

### Serverless hosting on Azure, everything scales to zero

We choose option 3.

1. **Region: Sweden Central**, with Azure OpenAI models deployed in the EU Data Zone.
2. **Compute: Azure Container Apps, Consumption plan**, one environment. The API, the checker and the extractor scale to zero. The checker and the extractor scale on the length of their Service Bus queue. The API scales on HTTP requests and on the length of the `status` queue, so a status event wakes it. A cron scale rule wakes the API once a day for the sweeper ([ADR-0005](0005-asynchronous-import-pipeline.md)). Each app has at most one replica.
   - An app scales to zero about 5 minutes after its last request or message (the default cooldown).
   - Every start after sleep is a new container, so nothing is kept in memory between starts. Keys that must survive, such as the session cookie keys, are kept in Blob Storage ([ADR-0010](0010-identity-users-and-consent.md)).
3. **Database: Azure SQL Database serverless with the free offer** (100,000 vCore seconds and 32 GB a month). When the free allowance runs out, the database pauses until the next month instead of billing. The free offer must be watched against real use.
4. **No Azure AI Search** ([ADR-0008](0008-retrieval-without-ai-search.md)).
5. **Container images in GitHub Container Registry.**
6. **A long cold start is accepted.** The targets in [use-cases.md](../use-cases.md) apply to a warm system. Cold start is not measured for now. The UI shows progress, and the API retries a paused database with a timeout.
7. **No restriction of outbound traffic.** The boundary is least privilege instead: each service's managed identity has roles only on what it uses ([ADR-0003](0003-masking-in-the-browser-and-a-second-check.md)).
8. **Everything is deployed with azd and Bicep**, from GitHub Actions with OIDC, without secrets ([ADR-0014](0014-development-with-ai-agents.md)).

### One environment, deployment and operations

We choose option 2.

1. **One environment: production**, in one resource group in Sweden Central.
2. **Evals call the production Document Intelligence and Azure OpenAI** with synthetic documents only.
   - These services are stateless for us. Document Intelligence keeps input for up to 24 hours and Azure OpenAI keeps prompts for abuse monitoring; both receive fictional data only.
   - Evals never touch the production database, storage or queues. The identity CI uses for evals has roles on the two AI services only.
   - A full eval run on about 30 synthetic pages costs about 1 USD. Evals run on pull requests that change extraction, prompts or the agent, and on demand.
3. **Deployment:** a merge to `main` runs GitHub Actions. The workflow builds the images into GitHub Container Registry, applies the database migrations, then deploys with azd and Bicep. It signs in to Azure with OIDC, without secrets.
4. **Database migrations** are an EF Core migration bundle run by the workflow before the new containers start.
   - Row-Level Security policies and the sweeper's role ([ADR-0010](0010-identity-users-and-consent.md)) are part of the migrations.
   - Every migration is compatible with the previous release (expand, then contract in a later release), so the old revision keeps working if the new one is rolled back.
   - CI applies all migrations to an empty SQL Server container on every pull request.
5. **Rollback:** Container Apps keeps the previous revision. Rolling back reactivates it; the database needs no change because of rule 4.
6. **Protection against our own mistakes:** resource locks (`CanNotDelete`) on the storage account, the SQL server and the Key Vault. Bicep deploys in incremental mode. Deleting one of these needs the lock removed by hand first.
7. **Alerts, all in one place, e-mailed to the owner:**

   | Alert | How | Cost |
   |---|---|---|
   | A message in a dead-letter queue | metric alert on Service Bus | free (up to 10 series) |
   | Monthly cost above 10 USD | Cost Management budget | free |
   | SQL free allowance above 80% used | metric alert on the database | free (up to 10 series) |
   | Owner action needed: `AccountDeleted`, `ConsentDeclined`, the sign-in certificate expires within 30 days, a version ends in `Failed` | one log alert on Application Insights, checked every 15 minutes | 0.50 USD a month |

   The daily sweeper run checks the certificate's expiry date and logs a warning, so a quiet system still raises it.

## Consequences

### Serverless hosting on Azure, everything scales to zero

- About 3.50 USD a month for 10 people, plus about 15 USD once for importing old results.
- The models must be available as Data Zone EU deployments in Sweden Central (gpt-5.4 mini, text-embedding-3-small) to keep G2. This is checked in the first deployment.
- The first page after a quiet period is slow, possibly tens of seconds. Accepted by the owner.
- If the free SQL allowance runs out, the database pauses until the next month. A budget alert and a usage alert on vCore seconds are needed.
- No private endpoints: Service Bus Basic has none, and private endpoints for the other services would add cost. Access is by Microsoft Entra ID only; keys are disabled where the service allows it.
- Moving to always-on later is a configuration change (minimum replicas, auto-pause off), not a redesign.

### One environment, deployment and operations

- No second environment to pay for or keep in step.
- A bug that passes CI and evals reaches the family directly. The mitigations are a green CI, evals on AI changes, a quick rollback, and a small number of users who can tell the owner.
- Evals spend real money, about 1 USD a run, so they do not run on every pull request.
- Migrations take two releases for a breaking change. At this scale that is rare.
- Removing a protected resource is deliberately awkward.
- Alerts add about 0.50 USD a month ([use-cases.md](../use-cases.md)).
