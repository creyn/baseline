# Tasks

## 1. Contracts and data model (first pull request)

- [x] 1.1 JSON Schemas in `contracts/`: the envelope, `ExtractRequested`, `Extracted`, `Failed`, the minimal manifest, the `text` blob
- [x] 1.2 Examples in `contracts/examples/` and a test that validates them
- [x] 1.3 `docs/data-model.md`: documents, versions, results, dates
- [x] 1.4 CI job for the contract tests
- [x] 1.5 U2 diagram: the word check, dates zoned in code, the `text` blob written only if it does not exist

## 2. Extractor (second pull request)

- [ ] 2.1 Core: pages to the `text` document, with Document Intelligence and the LLM behind interfaces
- [ ] 2.2 Prompt `extract.v1` and the pydantic model for structured output
- [ ] 2.3 The word check, the dates, validation and one retry
- [ ] 2.4 Service shell: the queue, the blobs, lock renewal, retries, idempotency, tested with fakes
- [ ] 2.5 A test that the core's output validates against `contracts/text.schema.json`

## 3. Evals (third pull request)

- [ ] 3.1 Matching and metrics, with tests
- [ ] 3.2 Offline run in CI: layout from the text PDFs, a fake LLM from the truth
- [ ] 3.3 Live run workflow, skipped without the Azure variables
- [ ] 3.4 `evals/extraction/README.md` with the owner's Azure setup

## 4. After merge

- [ ] 4.1 The owner sets up Azure for the live evals
- [ ] 4.2 The first live run; prompt fixes until the targets are met
- [ ] 4.3 Archive the change
