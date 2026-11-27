# Infrastructure

Everything Baseline runs on Azure, as Bicep at resource-group scope ([ADR-0004](../docs/adr/0004-serverless-hosting-and-operations.md), [ADR-0019](../docs/adr/0019-deployment-with-bicep-and-a-smoke-test.md)). The workflow [deploy.yml](../.github/workflows/deploy.yml) deploys it on `main` and on demand, then runs the [smoke test](../tools/smoke/extractor_smoke.py). The requirements are in the living spec [deployment](../openspec/specs/deployment/spec.md), the design in the archived change [add-extractor-deployment](../openspec/changes/archive/2026-11-27-add-extractor-deployment/design.md).

| Resource | Why |
|---|---|
| Storage, containers `incoming`, `clean`, `text` | one container per stage (ADR-0005); shared keys off |
| Service Bus Basic, queues `check`, `extract`, `status` | the pipeline (ADR-0005); local auth off |
| Document Intelligence, Azure OpenAI with the pinned model | extraction (ADR-0007, ADR-0017); local auth off |
| Log Analytics, Application Insights | logs and telemetry without content (ADR-0015); local auth off |
| Container Apps environment and `ca-baseline-extractor` | the extractor, scaled on the `extract` queue, to zero when idle |
| Identities `id-baseline-extractor`, `-evals`, `-smoke` | one per caller, each with roles on what it uses only |

**The smoke test's user** is `019ac000-0000-7000-8000-000000000001`, a fictional UUIDv7 that no real user gets (ours carry the time of sign-up, and its time part is 2025-11-26, before any real user). Its blobs hold only synthetic documents.

The deploying identity, the resource group (in Sweden Central; the Bicep allows no other region) and the GitHub `production` environment are made once by the owner; they are not in the Bicep, because the Bicep runs as that identity.

Compile and lint without Azure: `az bicep build --file infra/main.bicep`.
