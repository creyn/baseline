# 2. Split between .NET and Python

Date: 2026-11-17

## Status

Accepted

## Context

The system has two clearly different parts:

- **Application core:** API, data model, UI, an agent with tools, RAG with citations and summaries. This is long-lived business logic that benefits from strong typing, a mature ORM and integration with Azure. .NET offers Microsoft Agent Framework, Microsoft.Extensions.AI, EF Core and .NET Aspire for this.
- **Data pipeline:** PDF rasterisation, in-house OCR, masking of personal data, extraction with Document Intelligence and an LLM, indexing, and quality evaluation (evals). Python has the richest ecosystem here: PDF rendering libraries, Tesseract bindings, image processing, schema validation (pydantic) and LLM evaluation tooling.

The agent and RAG should stay in .NET, because they are the core of the product.

The data pipeline handles raw, unmasked documents, so it should be isolated from the rest of the system ([ADR-0003](0003-mask-personal-data-before-ai.md)).

### Considered options

1. **Everything in .NET.** One stack and one CI pipeline, but PDF and image processing, OCR and evals would rely on weaker libraries or wrappers.
2. **Everything in Python.** Rich AI ecosystem, but the application core loses what .NET offers: typing, EF Core, Agent Framework and Aspire.
3. **The same features in both languages.** Double the work with no architectural justification.
4. **Split by responsibility.** Application core in .NET, data pipeline and evals in Python.

## Decision

We choose option 4.

| Part | Language |
|---|---|
| API, data model (EF Core), UI | .NET |
| Agent with tools (Agent Framework, MEAI) | .NET |
| RAG with citations, pre-visit summary | .NET |
| Orchestration and deployment (Aspire, azd, Bicep) | .NET |
| Sanitiser and masking ([ADR-0004](0004-rasterise-pdf-to-png.md), [ADR-0003](0003-mask-personal-data-before-ai.md)) | Python |
| Extraction worker (FastAPI, pydantic) | Python |
| Indexing into AI Search | Python |
| Evals (pytest) | Python |

Rules:
- Only .NET owns the SQL database. Python writes results through the API.
- Evals test the .NET API from the outside, as a black box.

## Consequences

- Each part uses the best ecosystem for its job.
- The language boundary is also a security boundary: code that touches raw documents is isolated from the application core.
- There are two toolchains and two dependency sets. CI stays a single workflow with separate .NET and Python jobs, filtered by path and running in parallel, plus an evals job that runs the whole system.
- The contract between the worker and the API must be described explicitly (OpenAPI) and versioned.
