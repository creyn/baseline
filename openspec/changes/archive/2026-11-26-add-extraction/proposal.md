# Proposal

## Why

Extraction is the core of Baseline: it turns a masked lab result into values that the user reviews, and that trends and the agent use. The decisions are made ([ADR-0005](../../../../docs/adr/0005-asynchronous-import-pipeline.md), [ADR-0006](../../../../docs/adr/0006-document-lifecycle-and-review.md), [ADR-0007](../../../../docs/adr/0007-extraction-with-document-intelligence-and-an-llm.md), [ADR-0011](../../../../docs/adr/0011-lab-parameters-units-and-ranges.md)), but nobody can build the extractor from them without guessing: the messages, the `text` blob and the tables are not written down.

ADR-0007 also sets the quality bar: values and units 100% correct. Without evals, nobody knows whether we meet it.

This is a first version. It covers the path from a clean ZIP to results in `text`, and the evals that measure it. Everything else comes in later changes that add to these specs.

## What Changes

- **Contracts** in `contracts/`, as JSON Schema with examples and tests:
  - the messages `ExtractRequested`, `Extracted` and `Failed`, with one envelope and a versioning rule;
  - the `text` blob: words with positions, descriptive fragments, results and how the extraction was made.
- **Data model** in [docs/data-model.md](../../../../docs/data-model.md): the tables for documents, versions and results, for the API to build. No .NET code in this change.
- **Extractor** in `services/extractor/` (Python): reads the clean ZIP, calls Document Intelligence and the LLM in batches of pages, validates the answer, writes `text` and reports. Idempotent and retried as ADR-0005 says.
- **Evals** in `evals/extraction/`: run the extractor on the synthetic documents and compare with their truth. An offline run with fake AI services on every pull request; a live run against the real services when the extractor or its prompt changes.
- **CI:** a job for the contracts and the extractor's tests, and a workflow for the live evals.

## Capabilities

### New Capabilities

- `extraction-contracts`: messages between the services and the `text` blob.
- `extraction`: the extractor and its evals.

### Modified Capabilities

None.

## Not in this change

Each of these is a later change that adds to the specs above:

- `CheckRequested`, `Blocked` and the ZIP manifest (the checker).
- The API: OpenAPI, the status consumer, the sweeper, the review, EF Core migrations.
- Users, consent, deletion and export tables.
- Normalised values, computed flags, aliases and the parameter dictionary in code ([ADR-0011](../../../../docs/adr/0011-lab-parameters-units-and-ranges.md)).
- The infrastructure in Bicep.

## Impact

- New folders `contracts/`, `services/extractor/` and `evals/extraction/`; a new document `docs/data-model.md`.
- New dependencies, pinned, installed in CI only: jsonschema, pydantic, azure-ai-documentintelligence, openai, azure-identity, azure-storage-blob, azure-servicebus.
- The live evals need Azure resources and a GitHub OIDC identity that the owner creates (see design.md, "Live evals"). Until then only the offline run works.
- Cost: a live run on the synthetic documents costs about 1 USD ([ADR-0004](../../../../docs/adr/0004-serverless-hosting-and-operations.md)).
