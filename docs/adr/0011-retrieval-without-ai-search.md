# 11. Retrieval without Azure AI Search: SQL queries and vectors in Azure SQL

Date: 2026-11-22

## Status

Proposed

## Context

The agent answers questions with citations ([ADR-0012](0012-one-agent-with-tools-and-guardrails.md)). Most questions are about values: "When did I last test vitamin D, and what was the result?", "Which results were out of range this year?". Results are structured data in SQL (parameter, value, unit, range, dates, source page), so these questions are answered exactly by queries.

Some questions are about text: a laboratory's comment on a sample, a note under the table, a descriptive result. They need search by meaning (retrieval-augmented generation with vectors), but they are a small share of questions ([use-cases.md](../use-cases.md)).

Azure AI Search Basic costs 73.73 USD a month, used or not. For 10 people that would be about 96% of the whole bill. Azure SQL has a native `vector` type and `VECTOR_DISTANCE`, generally available since 2025. Exact distance (without an approximate index) is enough for a few thousand fragments.

### Considered options

1. **Azure AI Search Basic** for fragments and vectors, hybrid search, as originally planned.
2. **SQL queries for values, and vectors in Azure SQL for text.** One store, no extra service.
3. **Cosmos DB serverless with vector search.** Paid per use, but one more service, one more store to delete from, and data split between two databases.
4. **PostgreSQL with pgvector.** A mature vector extension, but an always-on server with a fixed charge, next to Azure SQL or instead of it.

Answering only with SQL queries, without any vectors, was also considered. It does not cover questions about descriptive text, so it does not meet the requirement.

| Criterion (weight) | 1: AI Search | 2: SQL + vectors | 3: Cosmos DB | 4: pgvector |
|---|---|---|---|---|
| K1 simple, self-healing (40) | 4 | 5 | 3 | 4 |
| K2 cost (20) | 1 | 5 | 5 | 4 |
| K4 engineering practice (15) | 3 | 4 | 3 | 3 |
| K5 testable in CI (10) | 4 | 4 | 3 | 3 |
| K6 time to deliver (10) | 4 | 4 | 4 | 4 |
| K7 performance (5) | 5 | 4 | 4 | 4 |
| **Result** | **66** | **92** | **71** | **75** |

## Decision

We choose option 2.

1. **Values are retrieved with SQL** through the agent's tools: a trend of a parameter, out-of-range results, the last value, a period summary. The same queries serve the charts.
2. **Descriptive text is retrieved by vectors in Azure SQL.** On approval, the API first reads the text fragments of the version (from the `text` blob) and computes their embeddings (text-embedding-3-small, EU Data Zone), outside any transaction. Then one transaction sets `Approved` and inserts the fragments into a table with a `vector` column. A tool searches them with `VECTOR_DISTANCE`.
3. **Every query filters by the signed-in user and by `Approved`.** Row-Level Security enforces the user filter again ([ADR-0013](0013-identity-users-and-consent.md)).
4. **Every fragment and result keeps its document, version and page hash**, so every answer can cite its source.
5. **AI Search is reconsidered only if evals show** that questions about text fail with this approach.

## Consequences

- No fixed charge for search, and no separate index to keep in step with the database.
- Approval stays a single step: fragments are written in the same transaction as the approval, so there is no indexing stage, no `Indexed` status and no index that can outlive a deleted document.
- Deleting a document deletes its fragments with its rows.
- Hybrid search (keywords and vectors together) and semantic ranking are not available. At this scale and with structured data first, this is accepted.
- Approximate vector search in Azure SQL is in preview. Exact search scans all fragments of one user, which is fine for thousands of rows.
- If the embedding call fails, the approval is not written; the version stays `PendingReview` and the user retries. The cost of embeddings is negligible.
