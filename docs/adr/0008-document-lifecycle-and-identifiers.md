# 8. Document lifecycle, identifiers and status changes

Date: 2026-11-22

## Status

Proposed

## Context

A document goes through upload, the second check, extraction and review ([ADR-0007](0007-asynchronous-import-pipeline.md)). Several services touch it, any of them can crash between two steps, and messages can arrive twice. The same document can be imported again, masked again after a block, or reprocessed after a fix.

Without clear rules, such a system ends with documents stuck in a status forever, or two results for one document.

### Considered options

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
1. **An event table** (append-only), doubling as outbox and audit. Useful only with an outbox, which [ADR-0007](0007-asynchronous-import-pipeline.md) does not use.
2. **Event sourcing**, the state rebuilt from events. Immutable events conflict with deletion (G5) unless every document has its own key to destroy, and the scale does not need it.
3. **No history table.** The current status with the time of its last change, and logs with the document id.

## Decision

**Statuses:** option 2. **Identifiers:** option 5. **History:** option 3.

1. **A Document is one original of one user. A Version is one masked upload of it.** Masking again after a block, or reprocessing, makes a new version of the same document. Results belong to an extraction of a version.
2. **Statuses of a version:**

   ```
   Uploaded ──► Blocked
       │
       ├──────► PendingReview ──► Approved
       │
       └──────► Failed (reason: integrity, check_error, extract_invalid, extract_error, timeout)
   ```

   - `Uploaded` is shown as "processing".
   - Results are saved with `PendingReview`, so they are not lost before review. Only the user sets `Approved` ([ADR-0009](0009-mandatory-review-of-extracted-values.md)).
   - `Approved` is final. A new extraction is a new version.
3. **Identifiers.** `docId` and `verId` are UUIDv7, made by the API before any write, because the blob is written before the database row. The document row has `userId` and `originalSha256`, with a unique index on the pair.
   - The same file imported again by the same user, or a retry after a lost response, returns the existing document.
   - Two parallel uploads of the same file: the second insert violates the index and returns the existing document.
   - Several photos of one paper result: `originalSha256` is the hash of the sorted list of the photos' hashes, so the order of choosing them does not matter.
4. **Blob paths** are `{container}/{userId}/{docId}/{verId}…`, so everything of a user lies under one prefix.
5. **Status changes are forward-only updates:** `UPDATE … SET status = @new WHERE verId = @v AND status = @expected`. Zero rows changed means a duplicate, an old version or a deleted document, and is not an error.
6. **Optimistic concurrency on review:** approval carries the `rowVersion` it was shown. A changed version (a new extraction, another tab) gets 409.
7. **No database transaction spans an external call.** A transaction covers SQL only; calls to Blob, Service Bus or AI services happen before or after it.
8. **Every version records the time of its last status change.** The sweeper ([ADR-0007](0007-asynchronous-import-pipeline.md)) finds versions stuck in `Uploaded` and either resends or fails them, so no status hangs forever.
9. **Every log entry and message carries `docId` and `verId`** as the correlation id, never content.

## Consequences

- The user sees four meaningful states, plus `Failed` with a reason and a "Retry" button.
- Every message can be delivered twice and every service can crash at any step without leaving a document stuck: the receivers resume from stored state, and the sweeper ends anything left.
- UUIDv7 values are ordered by time, which helps logs. SQL Server sorts `uniqueidentifier` in its own byte order, so they are not perfectly sequential in the index; at this scale it does not matter.
- There is no stored history of status changes. Diagnosis uses the last-change time and the logs.
- The hash of the original stays in one column and is never part of an identifier or a URL.
