# Contracts

The messages between the pipeline's services and the blob formats that one service writes and another reads, as JSON Schema (draft 2020-12). The rules are in the OpenSpec change [add-extraction](../openspec/changes/add-extraction/design.md); the decisions in [ADR-0005](../docs/adr/0005-asynchronous-import-pipeline.md) and [ADR-0006](../docs/adr/0006-document-lifecycle-and-review.md). The tables the API builds from them are in [docs/data-model.md](../docs/data-model.md).

| Schema | What it describes | Written by | Read by |
|---|---|---|---|
| [messages.v1.schema.json](messages.v1.schema.json) | `ExtractRequested` (queue `extract`), `Extracted` and `Failed` (queue `status`) | checker, extractor, API (sweeper, U9) | extractor, API |
| [manifest.v1.schema.json](manifest.v1.schema.json) | `manifest.json` in a version's ZIP: the page order (minimal) | browser | checker, extractor |
| [text.v1.schema.json](text.v1.schema.json) | `text/{userId}/{docId}/{verId}.json`: words, fragments, dates and results | extractor | API |

## Rules

- **Strict schemas, tolerant receivers.** A schema lists every allowed field, so a sender's tests catch a field that should not be there. A receiver reads only the fields it knows.
- **Required means the sender must provide it**, whoever reads it. A field that only a later reader needs is still required.
- **Versions.** `schemaVersion` is `major.minor` ("1.0"). Adding an optional field raises the minor version. Removing any field, renaming it, changing its meaning or adding a required field raises the major version, in a new file (`messages.v2.schema.json`) next to the old one; receivers accept both for one release. A receiver decides on the major version only and dead-letters one it does not know. A blob with an unknown major version is handled the same way: the API dead-letters the `Extracted` message that pointed to it, and refuses such a manifest with 422. v1 is a draft until the first release.
- **No content in messages.** Messages carry identifiers and a reason. Page text and results travel in blobs.
- **Service Bus properties.** The sender sets `subject` to the type, the application properties `docId` and `verId`, and the trace context in `Diagnostic-Id`. `CorrelationId` is not used ([ADR-0015](../docs/adr/0015-internal-user-id-and-log-identifiers.md)).
- **Examples** in [examples/](examples/) are named `{schema}.v{major}.{name}.json`. Every schema has at least one, and services use them in their tests.
- **Checks JSON Schema cannot express** (word ids exist on the right page, a value equals the words it was read from) are in [text_checks.py](text_checks.py). The extractor runs them before it writes a blob.

## Running the tests

```sh
pip install -r contracts/requirements.txt   # CI does this
python3 -m unittest discover -s contracts
```
