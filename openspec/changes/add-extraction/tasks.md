# Tasks

## 1. Contracts and data model (first pull request)

- [x] 1.1 JSON Schemas in `contracts/`: the envelope, `ExtractRequested`, `Extracted`, `Failed`, the minimal manifest, the `text` blob
- [x] 1.2 Examples in `contracts/examples/` and a test that validates them
- [x] 1.3 `docs/data-model.md`: documents, versions, results, dates
- [x] 1.4 CI job for the contract tests
- [x] 1.6 ADR-0015: our own user id, and the identifiers in logs
- [x] 1.5 U2 diagram: the word check, dates zoned in code, the `text` blob written only if it does not exist

## 2. Extractor (second pull request)

- [x] 2.1 Core: pages to the `text` document, with Document Intelligence and the LLM behind interfaces
- [x] 2.2 Prompt `extract.v1` and the pydantic model for structured output
- [x] 2.3 The word check, the dates, validation and one retry
- [x] 2.4 Service shell: the queue, the blobs, lock renewal, retries, idempotency, tested with fakes
- [x] 2.5 A test that the core's output validates against `contracts/text.v1.schema.json`

## 3. Evals (third pull request)

- [x] 3.1 Matching and metrics, with tests
- [x] 3.2 A synthetic document of 7 pages with a result block from page 5 to page 6 (ADR-0007)
- [x] 3.3 Offline run in CI: a layout built from the descriptions, a fake LLM from the truth
- [x] 3.4 Live run workflow, skipped without the Azure variables, also weekly (ADR-0017)

## 4. After merge

- [x] 4.1 The owner sets up Azure for the live evals
- [ ] 4.2 The first live run; prompt fixes until the targets are met (first run 2026-11-26; prompt `extract.v2`, the unit correction, the word regrouping, and ADR-0018: unread results and low confidence)
- [ ] 4.3 Archive the change
