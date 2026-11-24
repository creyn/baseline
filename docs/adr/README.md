# Architecture Decision Records

Format and rules: [ADR-0001](0001-record-architecture-decisions.md). Every option is checked against the gates and weighted criteria in [docs/decision-criteria.md](../decision-criteria.md), for the workload and costs in [docs/use-cases.md](../use-cases.md).

This set replaces an earlier one (2026-11-17 to 2026-11-20), which is in the Git history. Related decisions were merged on 2026-11-23, while all of them were still proposed, so that each topic is read in one place.

| # | Decision | Status |
|---|---|---|
| 0001 | [Record architecture decisions](0001-record-architecture-decisions.md) | Accepted |
| 0002 | [Languages: .NET, Python, and TypeScript with React](0002-languages-dotnet-python-and-typescript.md) | Accepted |
| 0003 | [Masking in the browser, zone rules, a second check on the server, no archive of originals](0003-masking-in-the-browser-and-a-second-check.md) | Accepted |
| 0004 | [Serverless hosting on Azure, one environment, deployment and operations](0004-serverless-hosting-and-operations.md) | Accepted |
| 0005 | [Asynchronous import: a pipeline of queues, without an outbox](0005-asynchronous-import-pipeline.md) | Accepted |
| 0006 | [Document lifecycle, identifiers, statuses and the mandatory review](0006-document-lifecycle-and-review.md) | Accepted |
| 0007 | [Extraction with Document Intelligence and an LLM](0007-extraction-with-document-intelligence-and-an-llm.md) | Accepted |
| 0008 | [Retrieval without Azure AI Search: SQL queries and vectors in Azure SQL](0008-retrieval-without-ai-search.md) | Accepted |
| 0009 | [One agent with tools and guardrails: questions and pre-visit summaries](0009-agent-questions-and-summaries.md) | Accepted |
| 0010 | [Sign-in, users and consent](0010-identity-users-and-consent.md) | Accepted |
| 0011 | [Lab parameters: dictionary, units and reference ranges](0011-lab-parameters-units-and-ranges.md) | Accepted |
| 0012 | [Deletion of documents and accounts, and retention](0012-deletion-and-retention.md) | Accepted |
| 0013 | [Application security baseline](0013-application-security-baseline.md) | Accepted |
| 0014 | [Development with AI coding agents: specs first, CI as the build, privacy checks everywhere](0014-development-with-ai-agents.md) | Accepted |
| 0015 | [Our own user id, and the identifiers in every log entry](0015-internal-user-id-and-log-identifiers.md) | Accepted |
| 0016 | [The same ZIP sent again matches only a live version](0016-same-zip-after-a-failure.md) | Accepted |

## Order of dependence

Masking (0003) decides what the server may receive. Hosting and operations (0004) rule out always-on services. Together they shape the import pipeline (0005), which defines the lifecycle and the review (0006), refined for uploads sent again (0016). Extraction (0007), retrieval (0008), the agent (0009) and the lab parameters (0011) build on the approved results. Identity and consent (0010, with our own user id in 0015), deletion (0012) and the security baseline (0013) cut across all of them. Languages (0002) and the way of working (0014) apply to every part.
