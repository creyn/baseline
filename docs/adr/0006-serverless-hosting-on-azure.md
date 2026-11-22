# 6. Serverless hosting on Azure, everything scales to zero

Date: 2026-11-22

## Status

Proposed

## Context

Baseline serves a family of up to 10 people. The workload ([use-cases.md](../use-cases.md)) is tiny and bursty: a few imports a month, browsing results a few times a week, and long idle periods. AI usage costs about 3 USD a month for 10 people. The fixed cost of the services is therefore the bill.

Data and AI processing must stay in the EU (G2). Poland Central would be the closest region, but the Azure price list shows Document Intelligence there only as batch layout, without the synchronous analysis the extractor needs. Sweden Central has every service we use, including Azure OpenAI models in the EU Data Zone.

Fixed monthly cost of the main options (list prices, Sweden Central, 2026-11-22):
- Azure AI Search Basic: 73.73 USD.
- The API always on (one replica, 0.5 vCPU, 1 GiB), after the free grant: about 10 USD.
- Azure SQL Database: Basic 4.90 USD, always on; serverless with the free offer 0 USD, with auto-pause.
- Azure Container Registry Basic: 5.07 USD; GitHub Container Registry: 0 USD.

Restricting outbound traffic of a container is not available in a Consumption-only Container Apps environment. It needs a workload profiles environment with a custom virtual network, and Azure Firewall or a NAT gateway, all of which add fixed cost.

### Considered options

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

## Decision

We choose option 3.

1. **Region: Sweden Central**, with Azure OpenAI models deployed in the EU Data Zone.
2. **Compute: Azure Container Apps, Consumption plan**, one environment. The API, the checker and the extractor scale to zero. The checker and the extractor scale on the length of their Service Bus queue.
3. **Database: Azure SQL Database serverless with the free offer** (100,000 vCore seconds and 32 GB a month). When the free allowance runs out, the database pauses until the next month instead of billing. The free offer must be watched against real use.
4. **No Azure AI Search** ([ADR-0011](0011-retrieval-without-ai-search.md)).
5. **Container images in GitHub Container Registry.**
6. **A long cold start is accepted.** The targets in [use-cases.md](../use-cases.md) apply to a warm system. Cold start is not measured for now. The UI shows progress, and the API retries a paused database with a timeout.
7. **No restriction of outbound traffic.** The boundary is least privilege instead: each service's managed identity has roles only on what it uses ([ADR-0003](0003-mask-in-the-browser-check-again-on-the-server.md)).
8. **Everything is deployed with azd and Bicep**, from GitHub Actions with OIDC, without secrets ([ADR-0020](0020-development-with-ai-agents.md)).

## Consequences

- About 3 USD a month for 10 people, plus about 15 USD once for importing old results.
- The first page after a quiet period is slow, possibly tens of seconds. Accepted by the owner.
- If the free SQL allowance runs out, the database pauses until the next month. A budget alert and a usage alert on vCore seconds are needed.
- No private endpoints: Service Bus Basic has none, and private endpoints for the other services would add cost. Access is by Microsoft Entra ID only; keys are disabled where the service allows it.
- Moving to always-on later is a configuration change (minimum replicas, auto-pause off), not a redesign.
