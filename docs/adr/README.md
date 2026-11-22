# Architecture Decision Records

Format and rules: [ADR-0001](0001-record-architecture-decisions.md). Every option is checked against the gates and weighted criteria in [docs/decision-criteria.md](../decision-criteria.md), for the workload and costs in [docs/use-cases.md](../use-cases.md).

This set replaces an earlier one (2026-11-17 to 2026-11-20), which is in the Git history.

| # | Decision | Status |
|---|---|---|
| 0001 | [Record architecture decisions](0001-record-architecture-decisions.md) | Proposed |
| 0002 | [Split between .NET and Python](0002-split-between-dotnet-and-python.md) | Proposed |
| 0003 | [Mask in the browser, check again on the server](0003-mask-in-the-browser-check-again-on-the-server.md) | Proposed |
| 0004 | [Zone-based masking: keep the results table, mask the rest](0004-zone-based-masking.md) | Proposed |
| 0005 | [No archive of original documents](0005-no-archive-of-originals.md) | Proposed |
| 0006 | [Serverless hosting on Azure, everything scales to zero](0006-serverless-hosting-on-azure.md) | Proposed |
| 0007 | [Asynchronous import: a pipeline of queues, without an outbox](0007-asynchronous-import-pipeline.md) | Proposed |
| 0008 | [Document lifecycle, identifiers and status changes](0008-document-lifecycle-and-identifiers.md) | Proposed |
| 0009 | [Every extracted value is reviewed before it is used](0009-mandatory-review-of-extracted-values.md) | Proposed |
| 0010 | [Extraction with Document Intelligence and an LLM](0010-extraction-with-document-intelligence-and-an-llm.md) | Proposed |
| 0011 | [Retrieval without Azure AI Search: SQL queries and vectors in Azure SQL](0011-retrieval-without-ai-search.md) | Proposed |
| 0012 | [One agent with tools and guardrails](0012-one-agent-with-tools-and-guardrails.md) | Proposed |
| 0013 | [Sign-in, users and consent](0013-identity-users-and-consent.md) | Proposed |
| 0014 | [Block personal identifiers in the user's questions](0014-personal-data-in-questions.md) | Proposed |
| 0015 | [Unit normalisation: keep the original, derive a normalised value](0015-unit-normalisation.md) | Proposed |
| 0016 | [Reference ranges are stored with each result](0016-reference-ranges.md) | Proposed |
| 0017 | [Parameter dictionary: definitions in the repository, lab names in the database](0017-parameter-dictionary.md) | Proposed |
| 0018 | [Store only lab results, not visits](0018-store-only-lab-results.md) | Proposed |
| 0019 | [Deletion of documents and accounts, and retention](0019-deletion-and-retention.md) | Proposed |
| 0020 | [Development with AI coding agents](0020-development-with-ai-agents.md) | Proposed |
| 0021 | [UI in TypeScript and React](0021-ui-in-typescript-and-react.md) | Proposed |

## Order of dependence

Masking (0003, 0004, 0005) decides what the server may receive. Hosting and cost (0006) rule out always-on services. Together they shape the import pipeline (0007), which defines the lifecycle (0008) and the review (0009). Extraction (0010), retrieval (0011) and the agent (0012) build on the approved results. Identity (0013) and deletion (0019) cut across all of them.
