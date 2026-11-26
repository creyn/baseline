# Extractor

Turns the masked pages of a checked version into the `text` blob: words with positions, results, dates and fragments ([ADR-0007](../../docs/adr/0007-extraction-with-document-intelligence-and-an-llm.md)). The rules are in the spec [extraction](../../openspec/specs/extraction/spec.md) and the design of the archived change [add-extraction](../../openspec/changes/archive/2026-11-26-add-extraction/design.md); the formats in [contracts/](../../contracts/README.md).

| File | What it does |
|---|---|
| [extractor/service.py](extractor/service.py) | One `ExtractRequested` in, `Extracted` or `Failed` out: idempotency, retries, logs with identifiers only |
| [extractor/core.py](extractor/core.py) | Pages to the blob: batches of 5 pages, the word check, one retry, dates, flags, the date for trends |
| [extractor/prompts/extract.v3.md](extractor/prompts/extract.v3.md) | The prompt. A change is a new file with a new version; older versions stay, because blobs name them |
| [extractor/answer.py](extractor/answer.py) | The LLM's answer as a pydantic model, used for structured output |
| [extractor/azure_clients.py](extractor/azure_clients.py) | Document Intelligence, Azure OpenAI, Blob Storage and Service Bus, with Managed Identity |
| [extractor/main.py](extractor/main.py) | The worker loop; settings from the environment, no secrets |

The core and the service use only the standard library and jsonschema, so their tests run anywhere. The adapters need [requirements.txt](requirements.txt); CI installs it.

```sh
python3 -m unittest discover -s services/extractor -t services/extractor
```
