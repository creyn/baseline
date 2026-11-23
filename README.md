# Baseline

A private, secure record of personal lab test results for a family. It understands the documents and helps prepare for doctor visits. It organises data. It does not diagnose.

> **Status:** design phase. The architecture decisions are in [docs/adr](docs/adr/README.md). No product code yet.

## The problem

Lab results are scattered across PDFs, emails, different labs' apps and paper. Trends over time are invisible, previous values are forgotten before a visit, and different labs use different names and units for the same parameter.

## What Baseline does

- **Import:** a PDF or photos of a lab result. Personal data is masked in the browser; the original never leaves the device.
- **Extraction:** results become structured data: parameter, value, unit, reference range, dates, lab.
- **Review:** every extracted value is shown next to its place on the masked page and must be approved before it is used.
- **Trends:** a chart for every parameter over time, with out-of-range results flagged by code.
- **Questions with citations:** e.g. "When did I last test vitamin D, and what was the result?", answered by an agent from the approved results, always with a link to the source page.
- **Pre-visit summary:** changes over a chosen period, out-of-range results, questions for the doctor. Generated on demand and not stored.

## Principles

1. **Organises, does not diagnose.** The agent never says "this means X". It says "this result is outside the lab's reference range, worth asking your doctor".
2. **No number comes from a model without verification.** Every extracted value is approved by the user before it is used.
3. **Out-of-range flags are computed by code, not by the model.**
4. **Every answer has a source:** the document and page it came from.
5. **Privacy by design from day one.**

## Privacy and security

- **The original never leaves the device.** The browser renders each page to an image, masks all personal data (the patient's, the doctor's, stamps, signatures, barcodes) and sends masked pages only. The server checks every page again before any AI service sees it. See [ADR-0003](docs/adr/0003-masking-in-the-browser-and-a-second-check.md).
- **Each person sees only their own data**, enforced in the code and again by Row-Level Security in the database. Sign-in with a Google account or an e-mail with a one-time code; no passwords. See [ADR-0010](docs/adr/0010-identity-users-and-consent.md).
- **Consent** is recorded at first sign-in. Withdrawing it deletes the account and all its data.
- **No keys in code.** Services authenticate with Managed Identity.
- **Region:** Sweden Central; Azure OpenAI models in the EU Data Zone.
- **Telemetry:** identifiers, tokens, latency and errors only; never document content, prompts or answers.
- **Deletion:** deleted from the application at once, from database backups after 7 days. Masked data may stay in the managed AI services for up to 30 days (Azure OpenAI abuse monitoring) or 24 hours (Document Intelligence). See [ADR-0012](docs/adr/0012-deletion-and-retention.md).

## Architecture

![Baseline architecture](docs/architecture.svg)

- **User device (red):** the only place where the original document exists.
- **Managed AI services (teal):** see masked pages and masked text only.
- **Import** is a pipeline of Service Bus queues: check, extract, status ([ADR-0005](docs/adr/0005-asynchronous-import-pipeline.md)). The full sequence, with every alternative path and the state after a failure at each step, is in [docs/adr/0005](docs/adr/0005/c-pipeline-without-outbox.svg).
- **Everything scales to zero**: about 3.50 USD a month for 10 people ([ADR-0004](docs/adr/0004-serverless-hosting-and-operations.md), [use-cases.md](docs/use-cases.md)).

All diagrams are generated from code in [tools/diagrams](tools/diagrams/). Edit the scripts, not the SVG files.

## How decisions are made

Every decision is an ADR with its considered options, checked against fixed gates and weighted criteria ([docs/decision-criteria.md](docs/decision-criteria.md)) for a stated workload and cost ([docs/use-cases.md](docs/use-cases.md)).

## Spikes

Proofs of concept that inform decisions live in [spikes/](spikes/), one folder each, and are published on GitHub Pages:
- [browser-sanitiser](spikes/browser-sanitiser/README.md): masking lab results entirely in the browser.

## Working with AI coding agents

The code is written with AI coding agents. The rules they follow, the privacy gates every change must pass and the tooling that enforces them (a privacy scan in a Git hook, a Claude Code hook and CI, and a review subagent) are in [AGENTS.md](AGENTS.md) and [ADR-0014](docs/adr/0014-development-with-ai-agents.md).

## Tech stack

- **.NET:** ASP.NET Core (.NET 10), Microsoft Agent Framework, Microsoft.Extensions.AI, EF Core, .NET Aspire
- **Python:** pydantic, Tesseract, pytest
- **TypeScript:** React, PDF.js, Tesseract.js
- **Azure:** Azure OpenAI, Document Intelligence, Azure SQL (with vectors), Blob Storage, Service Bus, Container Apps, Entra External ID, Key Vault, Application Insights
- **Delivery:** GitHub Actions, azd, Bicep, OpenSpec

## Quality

Evals run in CI on every prompt or model change:
- **Extraction:** numeric values and units must be 100% correct. Normalised parameter names and reference ranges target at least 95%.
- **Answers:** numbers match the stored results and every claim cites the right document.
- **Safety:** questions like "am I sick?" never get a diagnosis.
- **Masking:** no personal data survives masking. Only the results table and labelled date fields remain visible ([ADR-0003](docs/adr/0003-masking-in-the-browser-and-a-second-check.md)).
