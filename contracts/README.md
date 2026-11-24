# Contracts

The messages between the pipeline's services and the blob formats that one service writes and another reads, as JSON Schema (draft 2020-12). The rules are in the OpenSpec change [add-extraction](../openspec/changes/add-extraction/design.md); the decisions in [ADR-0005](../docs/adr/0005-asynchronous-import-pipeline.md) and [ADR-0006](../docs/adr/0006-document-lifecycle-and-review.md). The tables the API builds from them are in [docs/data-model.md](../docs/data-model.md).

| Schema | What it describes | Written by | Read by |
|---|---|---|---|
| [messages.schema.json](messages.schema.json) | `ExtractRequested` (queue `extract`), `Extracted` and `Failed` (queue `status`) | checker, extractor, API (sweeper, U9) | extractor, API |
| [manifest.schema.json](manifest.schema.json) | `manifest.json` in a version's ZIP: the page order (minimal) | browser | checker, extractor |
| [text.schema.json](text.schema.json) | `text/{userId}/{docId}/{verId}.json`: words, fragments, dates and results | extractor | API |

## Rules

- **Strict schemas, tolerant receivers.** A schema lists every allowed field, so a sender's tests catch a field that should not be there. A receiver reads only the fields it knows.
- **Versions.** Adding an optional field keeps `schemaVersion`. Removing, renaming or changing the meaning of a field raises it, and receivers accept both versions for one release. A receiver dead-letters a version it does not know.
- **No content in messages.** Messages carry identifiers and a reason. Page text and results travel in blobs.
- **Examples** in [examples/](examples/) are named `{schema}.{name}.json`. Every schema has at least one, and services use them in their tests.
- **Checks JSON Schema cannot express** (word ids exist on the right page, a value equals the words it was read from) are in [text_checks.py](text_checks.py). The extractor runs them before it writes a blob.

## Running the tests

```sh
pip install -r contracts/requirements.txt   # CI does this
python3 -m unittest discover -s contracts
```
