# 6. Document lifecycle, identifiers, statuses and the mandatory review

Date: 2026-11-23

## Status

Accepted. Point 10 is extended by [ADR-0015](0015-internal-user-id-and-log-identifiers.md): logs also carry `userId` and the trace context, and the Service Bus `CorrelationId` is not used. [ADR-0016](0016-retry-replaces-a-failed-version.md) changes the unique index of point 3 (only live versions) and replaces `Failed → Superseded` in point 2: a new version deletes the failed ones. [ADR-0018](0018-unread-results-and-low-confidence-words.md) extends points 3 and 5 of the review: results that could not be read are shown as places to enter by hand or dismiss, and results with a word OCR is unsure of are marked.

## Context

The states a document goes through, how it is identified, and the review by the user that moves extracted values to `Approved`.

### Document lifecycle, identifiers and status changes

A document goes through upload, the second check, extraction and review ([ADR-0005](0005-asynchronous-import-pipeline.md)). Several services touch it, any of them can crash between two steps, and messages can arrive twice. The same document can be imported again, masked again after a block, or reprocessed after a fix.

Without clear rules, such a system ends with documents stuck in a status forever, or two results for one document.

#### Considered options

**Statuses:**
1. **A status per technical step**: Uploaded, Masked, Checked, Extracting, Extracted, PendingReview, Approved, Indexed. Detailed, but most of them mean nothing to the user and each is one more transition that can get stuck.
2. **Only statuses the user acts on**: Uploaded (shown as "processing"), Blocked, PendingReview, Approved, Failed.

**Identifiers:**
1. **A number from the database** (identity column). Known only after the insert, but the blob is written before it. Easy to guess in URLs.
2. **An identifier made in the browser.** Free idempotency, but an untrusted client chooses it.
3. **An identifier derived from the hash of the original.** The same file of two people gets the same identifier, and the identifier reveals that two people hold the same document.
4. **A composite** of user, hash and a random part. Long (about 140 characters) as a key in every table and URL, and it puts the user and a fingerprint of a health document in every URL and log.
5. **UUIDv7 made by the API**, with duplicates recognised by a unique index on the user and the hash of the original.

**History of changes:**
1. **An event table** (append-only), doubling as outbox and audit. Useful only with an outbox, which [ADR-0005](0005-asynchronous-import-pipeline.md) does not use.
2. **Event sourcing**, the state rebuilt from events. Immutable events conflict with deletion (G5) unless every document has its own key to destroy, and the scale does not need it.
3. **No history table.** The current status with the time of its last change, and logs with the document id.

### Every extracted value is reviewed before it is used

Values are extracted by Document Intelligence and an LLM ([ADR-0007](0007-extraction-with-document-intelligence-and-an-llm.md)). A model can misread a digit, swap a unit or attach a value to the wrong parameter. Trends, the agent's answers and pre-visit summaries are built from these values, and a wrong number in a health record is worse than a missing one.

The masking was already approved by the user in the browser before the upload ([ADR-0003](0003-masking-in-the-browser-and-a-second-check.md)). This review is about the values.

#### Considered options

1. **No review.** Values are used as extracted. Fastest, but a model error goes straight into trends and answers. Fails G4.
2. **Review only values with low confidence.** Less work, but models are often confidently wrong, and a confidence threshold hides exactly those errors.
3. **Review every value before it is used**, next to its place on the masked page. Values are stored at once, so nothing is lost before review.

## Decision

### Document lifecycle, identifiers and status changes

**Statuses:** option 2. **Identifiers:** option 5. **History:** option 3.

1. **A Document is one original of one user. A Version is one masked upload of it.** Masking again after a block, or reprocessing, makes a new version of the same document. Results belong to a version. A version has at most one extraction, because a new extraction always makes a new version, so `verId` identifies it and no separate extraction id is needed.
   - **A document has at most one `Approved` version, and reads filter on `Approved` only.** Approving a version sets the previous `Approved` one to `Archived` in the same transaction, so old results stay visible until the new ones are approved, and are never counted twice.
   - **A newer version is more important than an unfinished older one.** Creating a version sets older `Blocked`, `PendingReview` and `Failed` versions to `Superseded`.
   - **A new version is refused (409) while the newest one is still `Uploaded`.**
   - **The UI's document page shows the newest version and its status.**
2. **Statuses of a version:**

   ```
   Uploaded ──► Blocked ─────────────────────────► Superseded
       │                                                ▲
       ├──────► PendingReview ──────────────────────────┤
       │             │                                  │
       │             └──► Approved ──► Archived         │
       │                                                │
       └──────► Failed ─────────────────────────────────┘
                (reason: integrity, check_error, extract_invalid, extract_error, no_results, timeout)
   ```

   - `Uploaded` is shown as "processing".
   - Results are saved with `PendingReview`, so they are not lost before review. Only the user sets `Approved` (see the review below).
   - `Archived` and `Superseded` are final and are kept as history. A new extraction is a new version: reprocessing copies the checked ZIP to the new version (same bytes) and sends it straight to extraction, because the pages were checked already.
   - **"Retry" after `Failed` is the same reprocessing** when the checked ZIP exists (a failure in extraction). When it does not (`integrity`, `check_error`, or a timeout before the check), the user picks the original again and sends a new version.
3. **Identifiers.** `docId` and `verId` are UUIDv7, made by the API before any write, because the blob is written before the database row. The document row has `userId` and `originalSha256`, with a unique index on the pair.
   - The same file imported again by the same user, or a retry after a lost response, returns the existing document.
   - Two parallel uploads of the same file: the second insert violates the index and returns the existing document.
   - Several photos of one paper result: `originalSha256` is the hash of the sorted list of the photos' hashes, so the order of choosing them does not matter.
   - The UI asks for the hash before masking (`GET /documents?originalSha256=…`), so an imported document is not masked and sent again.
   - A version row has `zipSha256`, with a unique index on (`docId`, `zipSha256`). A retry of the same upload returns the version made by the first try.
4. **Blob paths** are `{container}/{userId}/{docId}/{verId}…`, so everything of a user lies under one prefix.
5. **Status changes are forward-only updates:** `UPDATE … SET status = @new WHERE verId = @v AND status = @expected`. Zero rows changed means a duplicate, an old version or a deleted document, and is not an error.
6. **Optimistic concurrency on review:** approval carries the `rowVersion` it was shown. A version changed meanwhile (approved in another tab, or superseded by a newer version) gets 409.
7. **No database transaction spans an external call.** A transaction covers SQL only; calls to Blob, Service Bus or AI services happen before or after it.
8. **Every version records the time of its last status change.** The sweeper ([ADR-0005](0005-asynchronous-import-pipeline.md)) finds versions stuck in `Uploaded` and either resends or fails them, so no status hangs forever.
9. **Timestamps written by the system** (uploads, status changes, consent) are stored in UTC as `datetimeoffset`. The UI shows them in the user's local time.
10. **Every log entry and message carries `docId` and `verId`** as the correlation id, never content.
11. **Every extraction records how it was made:** the model, the prompt version and the dictionary version. After a fix, the UI marks documents whose extraction is older and offers to reprocess them (U9).

### Every extracted value is reviewed before it is used

We choose option 3.

1. **Results are stored as soon as they are extracted**, with the version in `PendingReview` (see the statuses above). Closing the browser loses nothing.
2. **Only `Approved` results are read** by trends, the agent's tools, summaries and the export. Every query filters on it.
3. **The review screen shows every value next to its place on the masked page**, highlighted from the word positions saved by extraction. The user can correct a value, unit, range or date (also by clicking the right word on the page), or reject a row.
4. **Approval is one transaction** with optimistic concurrency. A second approval of the same version (a retry) or an approval of a superseded version gets 409, and the UI shows the current state. The same transaction sets the previous `Approved` version of the document to `Archived`.
5. **At least one row must be accepted.** When the user rejects every row, nothing can be approved, and the UI offers to delete the document or reprocess it.
6. **The laboratory's flag and the computed flag are compared on review** ([ADR-0011](0011-lab-parameters-units-and-ranges.md)). A disagreement is shown, because it often means an extraction error.

## Consequences

### Document lifecycle, identifiers and status changes

- The user sees four meaningful states, plus `Failed` with a reason and a "Retry" button. `Archived` and `Superseded` are history, shown only in the document's version list.
- Every message can be delivered twice and every service can crash at any step without leaving a document stuck: the receivers resume from stored state, and the sweeper ends anything left.
- UUIDv7 values are ordered by time, which helps logs. SQL Server sorts `uniqueidentifier` in its own byte order, so they are not perfectly sequential in the index; at this scale it does not matter.
- There is no stored history of status changes. Diagnosis uses the last-change time and the logs.
- The hash of the original stays in one column and is never part of an identifier or a URL.

### Every extracted value is reviewed before it is used

- No number reaches a trend or an answer without a person having seen it next to its source.
- Every import needs a few minutes of the user's attention. Importing old results is the largest effort.
- Corrections made on review are the best signal of extraction quality. Counting them per field and per model version is a later improvement.
