# 2. Languages: .NET, Python, and TypeScript with React

Date: 2026-11-23

## Status

Accepted

## Context

Baseline is written in three languages. This ADR records which part is written in which, and why the UI uses TypeScript and React.

### Split between .NET and Python

The system has two different kinds of work:

- **The application core:** API, data model, sign-in, review, trends, the agent with tools and the pre-visit summary. Long-lived business logic that benefits from strong typing, a mature ORM and Azure integration. .NET offers ASP.NET Core, EF Core, Microsoft Agent Framework, Microsoft.Extensions.AI and .NET Aspire.
- **The document pipeline and quality:** the server-side check of masked pages (OCR), extraction with Document Intelligence and an LLM, schema validation, and evals. Python has the richest ecosystem: Tesseract bindings, image processing, pydantic and LLM evaluation tools.

Masking itself runs in the browser ([ADR-0003](0003-masking-in-the-browser-and-a-second-check.md)), in TypeScript (see below).

#### Considered options

1. **Everything in .NET.** One stack, but OCR, image processing and evals rely on weaker libraries.
2. **Everything in Python.** A rich AI ecosystem, but the core loses typing, EF Core and Agent Framework.
3. **Split by responsibility:** the core in .NET, the pipeline and evals in Python.

### UI in TypeScript and React

The UI does real work, not only display: it renders PDFs, runs OCR, masks pages and checks them before anything is sent ([ADR-0003](0003-masking-in-the-browser-and-a-second-check.md)). The [browser sanitiser spike](../../spikes/browser-sanitiser/README.md) does this in JavaScript with PDF.js and Tesseract.js, including the masking rules and their tests.

The UI also shows trends as charts, the review screen with highlighted values, and a chat. It is served by the API from the same domain ([ADR-0010](0010-identity-users-and-consent.md)).

#### Considered options

1. **TypeScript and React.** PDF.js and Tesseract.js are JavaScript libraries, so the spike's code moves over directly. Large ecosystem for charts and drag and drop.
2. **Blazor WebAssembly.** One language with the API, but PDF.js and Tesseract.js would be called through JavaScript interop, the masking rules would be rewritten or wrapped, and the download is larger.
3. **Server-rendered pages (Razor) with a little JavaScript.** Little client code, but masking must run in the browser anyway, so the heavy JavaScript stays.

| Criterion (weight) | 1: TypeScript, React | 2: Blazor | 3: Razor + JS |
|---|---|---|---|
| K1 simple, self-healing (40) | 5 | 3 | 3 |
| K2 cost (20) | 5 | 5 | 5 |
| K4 engineering practice (15) | 3 | 4 | 3 |
| K5 testable in CI (10) | 4 | 4 | 3 |
| K6 time to deliver (10) | 5 | 4 | 4 |
| K7 performance (5) | 4 | 3 | 3 |
| **Result** | **91** | **75** | **66** |

## Decision

### Split between .NET and Python

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
- **Only the API writes to the database.** The Python services report through Service Bus ([ADR-0005](0005-asynchronous-import-pipeline.md)) and never hold database credentials.
- **Evals test the system from the outside**, through the API and the pipeline's inputs and outputs.

### UI in TypeScript and React

We choose option 1.

1. **TypeScript, React, built with Vite.** The build output is served by the API as static files.
2. **Masking runs in a Web Worker** with PDF.js and Tesseract.js, so the page stays responsive. The masking rules are a separate TypeScript module with their own tests, shared in spirit with the Python checker: both are tested against the same synthetic documents.
3. **No tokens in the browser.** The UI calls the API with the session cookie only.
4. **The UI speaks Polish.** All texts the user sees, including every version of the consent text, are in locale files in the UI project. They are the only Polish text in the repository; code, comments and documents stay in English.
5. **The masking libraries and the OCR language data are served from our own domain**, not from a CDN, so masking works offline once loaded and no third party sees the page.

## Consequences

### Split between .NET and Python

- Each part uses the best ecosystem for its job.
- Python services cannot change data directly, so every status change goes through one place, with one set of rules ([ADR-0006](0006-document-lifecycle-and-review.md)).
- Large outputs of the Python services (page text, results) cannot pass through a message alone. They are stored in Blob Storage and referenced ([ADR-0005](0005-asynchronous-import-pipeline.md)).
- There are three toolchains. CI runs one job per language in parallel.
- The message contracts between the services are written down and versioned.

### UI in TypeScript and React

- The spike's rules and tests move over with little change.
- There are two implementations of the masking rules: TypeScript in the browser and Python in the checker. Synthetic documents in CI keep them in step.
- The UI waits for the API's cold start, because the API serves it ([ADR-0004](0004-serverless-hosting-and-operations.md)).
