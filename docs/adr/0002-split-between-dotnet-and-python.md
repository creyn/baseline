# 2. Split between .NET and Python

Date: 2026-11-22

## Status

Proposed

## Context

The system has two different kinds of work:

- **The application core:** API, data model, sign-in, review, trends, the agent with tools and the pre-visit summary. Long-lived business logic that benefits from strong typing, a mature ORM and Azure integration. .NET offers ASP.NET Core, EF Core, Microsoft Agent Framework, Microsoft.Extensions.AI and .NET Aspire.
- **The document pipeline and quality:** the server-side check of masked pages (OCR), extraction with Document Intelligence and an LLM, schema validation, and evals. Python has the richest ecosystem: Tesseract bindings, image processing, pydantic and LLM evaluation tools.

Masking itself runs in the browser ([ADR-0003](0003-mask-in-the-browser-check-again-on-the-server.md)), in TypeScript ([ADR-0021](0021-ui-in-typescript-and-react.md)).

### Considered options

1. **Everything in .NET.** One stack, but OCR, image processing and evals rely on weaker libraries.
2. **Everything in Python.** A rich AI ecosystem, but the core loses typing, EF Core and Agent Framework.
3. **Split by responsibility:** the core in .NET, the pipeline and evals in Python.

## Decision

We choose option 3.

| Part | Language |
|---|---|
| API, data model (EF Core), sign-in, serving the UI | .NET |
| Agent with tools (Agent Framework, Microsoft.Extensions.AI) | .NET |
| Status consumer, sweeper, deletion | .NET |
| Checker: second check of masked pages | Python |
| Extractor: Document Intelligence, LLM, pydantic | Python |
| Evals (pytest) | Python |
| UI, masking in the browser | TypeScript |

Rules:
- **Only the API writes to the database.** The Python services report through Service Bus ([ADR-0007](0007-asynchronous-import-pipeline.md)) and never hold database credentials.
- **Evals test the system from the outside**, through the API and the pipeline's inputs and outputs.

## Consequences

- Each part uses the best ecosystem for its job.
- Python services cannot change data directly, so every status change goes through one place, with one set of rules ([ADR-0008](0008-document-lifecycle-and-identifiers.md)).
- Large outputs of the Python services (page text, results) cannot pass through a message alone. They are stored in Blob Storage and referenced ([ADR-0007](0007-asynchronous-import-pipeline.md)).
- There are three toolchains. CI runs one job per language in parallel.
- The message contracts between the services are written down and versioned.
