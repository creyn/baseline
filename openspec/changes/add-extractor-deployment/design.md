# Design

## Context

The extractor's core and service shell are done and tested ([services/extractor](../../../services/extractor/README.md)); its settings come from the environment and it signs in with `DefaultAzureCredential` ([main.py](../../../services/extractor/extractor/main.py)). The live evals use Document Intelligence and Azure OpenAI in `rg-baseline-evals`, made by hand. This change puts the extractor on Azure and moves every resource into one group, as [ADR-0004](../../../docs/adr/0004-serverless-hosting-and-operations.md) asks. How, and why not azd: [ADR-0019](../../../docs/adr/0019-deployment-with-bicep-and-a-smoke-test.md) (proposed).

## Goals and non-goals

- Goal: a message on `extract` with a clean ZIP ends as a `text` blob and an `Extracted` message on `status`, on Azure, with no keys.
- Goal: the evals run against the production AI services; `rg-baseline-evals` is deleted.
- Non-goals: the API, the checker, the UI, SQL, alerts and resource locks (later changes; the locks by hand, ADR-0019).

## Decisions

### Resources ([infra/main.bicep](../../../infra/main.bicep))

- **Names:** `<type>-baseline-<suffix>`, the suffix from the group's id, so a second deployment finds the same resources. Identities and the Container App have fixed names.
- **Storage:** `Standard_LRS`, shared keys and public blob access off, TLS 1.2. Containers `incoming`, `clean`, `text`; a lifecycle rule deletes `incoming` blobs after a day (ADR-0005).
- **Service Bus Basic**, local auth off. Queues `check`, `extract`, `status`: lock 5 minutes (the maximum; the services renew it), at most 10 deliveries (the services give up after 5 and send `Failed`, so the dead-letter queue gets only crashes, ADR-0005 point 6), messages live 14 days.
- **AI services:** Document Intelligence S0 and Azure OpenAI S0, each with a custom subdomain (needed for Entra ID) and local auth off. The model deployment is `DataZoneStandard` (G2) with `versionUpgradeOption: OnceCurrentVersionExpired` (ADR-0017). Capacity 50 thousand tokens a minute to start, because the old evals deployment holds 100 of the subscription's Data Zone quota until it is deleted.
- **Monitoring:** Log Analytics (30 days) and workspace-based Application Insights with local auth off; the extractor sends telemetry with its identity (Monitoring Metrics Publisher). The Container Apps environment sends its logs through a diagnostic setting (category group `allLogs`, to check on the first deployment), so no workspace key is used.
- **Region:** only Sweden Central is allowed by the Bicep (G2).
- **Container Apps:** API version 2025-01-01, the first with `identity` on a scale rule. A workload-profiles environment with the Consumption profile (the consumption-only environment is legacy, checked 2026-11-26). The extractor: 0.5 vCPU and 1 GiB, no ingress, 0 to 1 replica (ADR-0004), scaled by a `azure-servicebus` rule on `extract` with one message per replica, signed in with the extractor's identity. Single revision mode; the previous revision stays for a rollback.
- **Image:** `ghcr.io/<owner>/baseline-extractor:<git sha>`, a public package, so no registry credentials (ADR-0019). Python 3.12 slim, the extractor and the contracts only, run as a non-root user.

### Identities and roles

| Identity | Roles | Scope |
|---|---|---|
| `id-baseline-extractor` | Storage Blob Data Reader | container `clean` |
| | Storage Blob Data Contributor | container `text` |
| | Azure Service Bus Data Owner (receive, and the scaler reads the message count) | queue `extract` |
| | Azure Service Bus Data Sender | queue `status` |
| | Cognitive Services User | Document Intelligence |
| | Cognitive Services OpenAI User | Azure OpenAI |
| | Monitoring Metrics Publisher | Application Insights |
| `id-baseline-evals` (OIDC, environment `evals`) | Cognitive Services User | both AI services |
| `id-baseline-smoke` (OIDC, environment `production`) | Storage Blob Data Contributor, only paths under the test user | container `clean` |
| | Storage Blob Data Reader, only paths under the test user | container `text` |
| | Azure Service Bus Data Sender | queue `extract` |
| deploying identity (made by the owner) | Contributor, Role Based Access Control Administrator | the production group |

Every role is scoped to the one container, queue or service it is for. The smoke identity's conditions limit data actions only; Storage Blob Data Contributor also allows deleting the container (ADR-0019, consequences). The smoke test checks on every run that it cannot read another user's `text`. The role ids in the Bicep are checked on the first deployment; a wrong id fails it.

### Deployment ([deploy.yml](../../../.github/workflows/deploy.yml))

1. Only `main` (the workflow fails on any other ref), on push (paths of the extractor, the contracts, the infrastructure and the smoke test) and on demand. Skipped until the `production` environment has its variables. One deployment at a time, never cancelled half way.
2. Build the image and push it to GitHub Container Registry with the workflow's own token.
3. Sign in as the deploying identity (OIDC, environment `production`, only `main`), and `az deployment group create` in incremental mode. The job summary lists the new endpoints and the evals identity's client id, never a key.
4. Sign in as the smoke identity and run the smoke test.

Pull requests compile and lint the Bicep and build and start the image (CI), without Azure.

### Smoke test ([tools/smoke](../../../tools/smoke/extractor_smoke.py))

Renders page 1 of the synthetic document `a1-vitamin-d`. A refused upload or send is retried for up to 5 minutes, because new role assignments take time. It writes its clean ZIP under the test user with new `docId` and `verId`, sends `ExtractRequested` (validated against the contract), and waits up to 10 minutes for the `text` blob. The blob must pass the schema and the text checks and hold at least one result. It prints identifiers and counts only. A cold start (scale from zero, about 30 seconds of polling plus the start) is part of the wait.

### Failure handling

- **A deployment fails half way:** incremental mode leaves what was created; the next run completes it. Nothing is deleted by a deployment.
- **A role is not applied yet:** new role assignments can take minutes. The smoke test retries a refused upload or send for up to 5 minutes; the extractor's transient errors are retried by Service Bus (ADR-0005). A first deployment that still fails is run again.
- **A bad image:** the new revision does not start and the smoke test fails; the previous revision can be reactivated (ADR-0004, point 5).
- **The scaler cannot read the queue:** the extractor never starts, and the smoke test fails after 10 minutes.
- **Messages the smoke test leaves:** `Extracted` waits on `status` until the API consumes it, which ignores an unknown version (ADR-0005, point 5). `status` does not dead-letter expired messages, so they never raise the dead-letter alert; a real event lost that way is recovered by the sweeper (ADR-0005, point 7). `check` and `extract` keep dead-lettering.
- **The extractor fails the smoke document:** it sends `Failed`, which the smoke test cannot read, so the test fails after its 10 minutes; the extractor's logs say why.
- **The first deployment:** the new image package is private, so the pull fails; the owner makes it public and runs again (ADR-0019).

### Moving the evals

After the first deployment the owner points the repository variables `AZURE_CLIENT_ID`, `DOCUMENT_INTELLIGENCE_ENDPOINT` and `AZURE_OPENAI_ENDPOINT` at the new identity and services (the job summary lists them), runs the live evals, and when they pass deletes `rg-baseline-evals`.

## Risks

- **The deploying identity is powerful** in the group (ADR-0019). Mitigation: OIDC from `main` only; limiting the roles it can assign is to check.
- **Data Zone quota:** two model deployments share it until the old group is deleted. If 50 does not fit, the deployment fails with a quota error and the capacity parameter is lowered.
- **The scale rule's identity** for Service Bus and the Data Owner role it needs are documented for KEDA but not shown in a Container Apps example (checked 2026-11-26): to check on the first deployment.
