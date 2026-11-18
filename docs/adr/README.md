# Architecture Decision Records

Format and rules are described in [ADR-0001](0001-record-architecture-decisions.md).

| # | Decision | Status |
|---|---|---|
| 0001 | [Record architecture decisions](0001-record-architecture-decisions.md) | Accepted |
| 0002 | [Split between .NET and Python](0002-split-between-dotnet-and-python.md) | Accepted |
| 0003 | [Mask all personal data before any AI service](0003-mask-personal-data-before-ai.md) | Accepted, amended by 0006 |
| 0004 | [Rasterise incoming PDFs to PNG](0004-rasterise-pdf-to-png.md) | Accepted |
| 0005 | [No archive of original documents in the first version](0005-no-archive-of-originals.md) | Accepted |
| 0006 | [Zone-based masking: keep the results table, mask the rest](0006-zone-based-masking.md) | Accepted |
| 0007 | [Unit normalisation: keep the original, derive a normalised value](0007-unit-normalisation.md) | Accepted |
| 0008 | [Reference ranges are stored with each result](0008-reference-ranges.md) | Accepted |
| 0009 | [Block personal identifiers in the user's questions](0009-personal-data-in-questions.md) | Accepted |
| 0010 | [Store only lab results, not visits](0010-store-only-lab-results.md) | Accepted |
| 0011 | [Deletion and retention](0011-deletion-and-retention.md) | Accepted |
| 0012 | [Parameter dictionary: definitions in the repository, lab names in the database](0012-parameter-dictionary.md) | Accepted |

## To be written

Open questions found while drawing the use cases (Q1–Q8) are listed in [docs/sequences](../sequences/README.md#open-questions).

- Azure AI Search vs. pgvector or Cosmos DB as the vector store
- Extraction: Document Intelligence plus an LLM vs. an LLM with vision only
- Asynchronous import via Service Bus vs. a synchronous endpoint. Includes: the sanitiser reports status (Masked, Blocked) to the API, which stays the only owner of the database.
- Human review of results: why approval is mandatory. Includes: results are indexed in AI Search only after approval, so unverified data never reaches search or the agent.
- Agent guardrails: every number in an answer must match a tool result and every claim must be cited. If a check fails, the user gets the raw results table and a suggestion to ask a doctor instead of the generated answer.
- UI hosting: served by the ASP.NET Core API as a backend-for-frontend (one origin, session cookie, tokens on the server) vs. Azure Static Web Apps vs. GitHub Pages
- UI framework: TypeScript (e.g. React) vs. Blazor. Depends on the browser masking proof of concept.
- One agent with tools vs. multiple agents
- Threat model (STRIDE)
