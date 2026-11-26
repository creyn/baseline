# Proposal

## Why

The extractor runs only in tests and evals. Nothing of Baseline runs on Azure yet. The first deployment puts the extractor on Azure with its queues and storage, so that a document put on the `extract` queue ends as a `text` blob, and shows that the identities, roles and scaling of [ADR-0004](../../../docs/adr/0004-serverless-hosting-and-operations.md) and [ADR-0005](../../../docs/adr/0005-asynchronous-import-pipeline.md) work. How it is deployed is [ADR-0019](../../../docs/adr/0019-deployment-with-bicep-and-a-smoke-test.md) (proposed).

## What Changes

- **Infrastructure in `infra/`** (Bicep, resource-group scope): Storage with the containers `incoming`, `clean` and `text`; Service Bus Basic with the queues `check`, `extract` and `status`; Log Analytics and Application Insights; Document Intelligence and Azure OpenAI with the pinned model deployment; the Container Apps environment and the extractor app; the managed identities of the extractor, the evals and the smoke test, with their roles.
- **The extractor's image:** a Dockerfile, built in CI on every pull request and pushed to GitHub Container Registry on `main`.
- **Workflow `deploy.yml`:** on `main` and on demand, it builds and pushes the image, deploys the Bicep, and runs the smoke test.
- **Smoke test** in `tools/smoke/`: one synthetic document through the deployed extractor, as a test user.
- **CI:** the Bicep is compiled and linted, and the image is built, on every pull request.

## Capabilities

### New Capabilities

- `deployment`: the infrastructure, the deployment and the smoke test.

### Modified Capabilities

None.

## Out of scope

- The API, the checker, the UI and the database: later changes add them to the same Bicep.
- Alerts and resource locks of ADR-0004: the alerts come with the API; the locks are added by hand (ADR-0019).

## Impact

- Cost when idle: about 0 USD (the extractor scales to zero; Service Bus Basic, Storage and Log Analytics are paid by use). Each deployment runs one smoke test, about 0.02 USD.
- The owner sets up the production group and the deploying identity once, and moves the evals to the new AI services.
