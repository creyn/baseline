# 7. Asynchronous import: a pipeline of queues, without an outbox

Date: 2026-11-22

## Status

Proposed

## Context

After the browser masks a document ([ADR-0003](0003-mask-in-the-browser-check-again-on-the-server.md)), the server has to check it again, extract the results, and let the user review them. The check (OCR) and the extraction (Document Intelligence and an LLM) take from seconds to a minute or more. The user can close the browser after the upload and come back later.

Constraints:
- Only the API writes to the database ([ADR-0002](0002-split-between-dotnet-and-python.md)).
- There is no transaction across SQL, Blob Storage and Service Bus. Every step that writes to two of them must survive a crash between the two writes.
- Service Bus Basic has queues only (no topics, no sessions, no transactions) and **no duplicate detection**. A message can arrive twice, so every receiver must be idempotent.
- A Service Bus message carries at most 256 KB on Basic and Standard.
- Everything scales to zero ([ADR-0006](0006-serverless-hosting-on-azure.md)).

A multi-page result means several masked pages. Sending or storing them one by one means one request per page at every step, with more places to fail and partial states ("3 of 5 pages written").

### Considered options

1. **Synchronous.** The API checks and extracts within the upload request. Simple, but the request lasts up to a minute or more, times out behind proxies, the user must keep the page open, and a failure in the middle loses the work.
2. **Commands over Service Bus, results back over HTTP.** When the API is asleep or restarting, the worker must retry by itself or the status is lost. The worker needs the API's address and an identity to call it.
3. **Blob events (Event Grid) as the trigger.** A `BlobCreated` event can start the check, through a Service Bus queue. Events are delivered at least once, without order and without a time guarantee, one per blob. It replaces only the first message: the API still writes to SQL and Blob without a shared transaction, approval writes no blob, and a blocked document writes nothing to report. It adds a service and a second mechanism.
4. **A: the API orchestrates.** Each step reports to the API, which decides the next step and sends it through a transactional outbox (a relay process sends rows written in the same transaction).
5. **B: a pipeline with an outbox.** Each stage hands work to the next queue (check → extract). Stages report to a status queue only what the user should know. The first message is sent by an outbox relay.
6. **C: a pipeline without an outbox.** Like B, but the API sends the first message itself after COMMIT. If it crashes in between, the document stays `Uploaded` and a sweeper sends the message again.

Options 4, 5 and 6 are drawn in full, with arguments on every arrow, every alternative path and the state after a failure at every step:
- [A: the API orchestrates](0007/a-api-orchestrates.svg)
- [B: a pipeline with an outbox](0007/b-pipeline-with-outbox.svg)
- [C: a pipeline without an outbox](0007/c-pipeline-without-outbox.svg)

Each diagram also shows the most frequent reads (browsing results, asking the agent), which are the same in all three.

| Criterion (weight) | 1: sync | 2: HTTP back | A | B | C |
|---|---|---|---|---|---|
| K1 simple, self-healing (40) | 2 | 3 | 3 | 4 | 5 |
| K2 cost (20) | 5 | 5 | 5 | 5 | 5 |
| K4 engineering practice (15) | 2 | 3 | 3 | 4 | 3 |
| K5 testable in CI (10) | 4 | 3 | 3 | 4 | 4 |
| K6 time to deliver (10) | 5 | 4 | 3 | 3 | 4 |
| K7 performance (5) | 3 | 4 | 4 | 4 | 4 |
| **Result** | **63** | **71** | **69** | **82** | **89** |

C wins on K1. With nothing indexed after approval ([ADR-0011](0011-retrieval-without-ai-search.md)), the only message the outbox would protect is the first one, and the sweeper protects it too, at the price of minutes of delay in a rare failure.

## Decision

We choose option 6 (C).

1. **One ZIP per document version.** The browser sends pages/{pageSha}.png and a manifest (page order, kept regions, the hash of the original) in one request. The ZIP uses no compression, so the PNG bytes and their hashes are unchanged. Every later step reads or writes one blob per stage, and a blob write is atomic: a stage holds all the pages or none.
2. **Blob Storage, one container per stage**, with paths `{userId}/{docId}/{verId}`:
   - `incoming`: the ZIP from the API; deleted by the checker; a lifecycle rule removes leftovers after 24 hours;
   - `clean`: the ZIP that passed the check; used by extraction, review and citations;
   - `text`: the words with their positions and the extracted results, as JSON. It is the claim check for data too large for a message, it lets review highlight where each value came from, and it lets a retry resend results without calling the AI services again.
3. **Three Service Bus queues:**
   - `check`: from the API to the checker (`CheckRequested`);
   - `extract`: from the checker to the extractor (`ExtractRequested`), only for clean documents;
   - `status`: from the checker and the extractor to the API (`Blocked`, `Extracted`, `Failed`).

   A version gets exactly one of `Blocked`, `Extracted` or `Failed`. There is no message for "checked and clean": it tells the user nothing.
4. **Messages carry identifiers and small payloads.** `Blocked` carries the suspicious regions (page and rectangle, never text). `Extracted` carries the results with their page hashes and positions.
5. **Every receiver is idempotent and resumes from what is already stored** (drawn as alternative paths in diagram C):
   - the checker finds the incoming ZIP gone and the clean ZIP present: it sends `ExtractRequested` again;
   - the extractor finds its results already in `text`: it sends `Extracted` again without calling Document Intelligence or the LLM;
   - the API applies a status event with a forward-only update; zero rows changed means a duplicate, an old version or a deleted document, and the event is completed and ignored.
6. **Retries:** an error with `deliveryCount` below 5 abandons the message, so Service Bus delivers it again later. On the fifth try the service sends `Failed` with a reason code. Queues allow more deliveries than that, so a crash on the last try ends in the dead-letter queue, which raises an alert.
7. **The sweeper** in the API runs every 5 minutes. A version still `Uploaded` after 3 minutes gets `CheckRequested` again, up to 3 times, then `Failed (timeout)`. The UI then offers "Retry".
8. **Managed Identity only**, with keys disabled on the namespace. Service Bus Basic has no private endpoint, so the namespace is reached over its public endpoint with Entra ID.

## Consequences

- **No status is lost** while the API is asleep or being deployed: events wait in the status queue.
- **Each stage can be tested alone** against emulators (Azurite, the Service Bus emulator).
- **A crash between the API's COMMIT and its send delays a document by up to a few minutes**, until the sweeper. Accepted for a rare failure.
- **Duplicate messages are expected** and handled by the receivers, not by Service Bus.
- **Statuses, versions and identifiers** are defined in [ADR-0008](0008-document-lifecycle-and-identifiers.md).
- **The user sees progress by polling** the document status every few seconds.
- **A blocked document leaves nothing on the server** except its version row and the suspicious regions.
