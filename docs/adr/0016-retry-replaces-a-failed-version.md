# 16. A retry replaces a failed version; an upload sent again matches only a live version

Date: 2026-11-24

## Status

Accepted. Changes two rules of [ADR-0006](0006-document-lifecycle-and-review.md): the unique index of point 3 ("a unique index on (`docId`, `zipSha256`)"), and the `Failed → Superseded` transition of point 2. `Blocked` versions stay as history, unchanged.

## Context

ADR-0006 makes (`DocumentId`, `ZipSha256`) unique, so a retry of an upload whose response was lost returns the version made by the first try, instead of a second version.

After `Failed (integrity, check_error, or timeout before the check)` there is no checked ZIP, so "Retry" means: the user picks the original again and sends a new version. The browser masks the same file the same way, so the ZIP is usually identical. The unique index then returns the failed version, and the user can never retry.

ADR-0006 also keeps every failed version as `Superseded` history. A failed version holds no results and nothing the user can act on once a retry exists; its reason is in the logs.

### Considered options

**Sending the same ZIP again:**
1. **Keep the index.** The user is stuck after any failure before the check, unless they change the masking.
2. **A filtered index: unique only among live versions** (`Uploaded`, `Blocked`, `PendingReview`, `Approved`). A retry of a lost response still returns the first version while it is live; after a failure the same ZIP makes a new version.
3. **An idempotency key per upload attempt**, sent by the browser in a header. The usual pattern for retries, but it adds a field, a column and a rule, and ADR-0006 already chose identifiers made by the server.
4. **No unique index;** rely on the 409 while the newest version is `Uploaded`. A lost response retried after the version moved on (to `Blocked` or `PendingReview`) would make a duplicate version.

**What a retry does with the failed version:**
1. **Keep it as `Superseded`** (ADR-0006). History nobody uses.
2. **Reset the same version to `Uploaded`** and run the pipeline again. No row to delete, but a late message from the first attempt (an extractor that finishes after the sweeper's timeout) would be applied to the second attempt. Every message, status update and blob path would need an attempt number, and statuses would move backwards for the first time.
3. **Make a new version and delete the failed one.** A late message from the first attempt names a `verId` that no longer exists and changes zero rows, as any message for a deleted version does today. Statuses still only move forward.

All options pass the gates. Option 2 for the index and option 3 for the failed version keep the existing protections (K1) and add no field to the contracts (K6).

## Decision

Index: option 2. Failed version: option 3 (decided by the owner on 2026-11-24).

1. **The unique index on (`DocumentId`, `ZipSha256`) is filtered `WHERE ZipSha256 IS NOT NULL AND Status IN ('Uploaded', 'Blocked', 'PendingReview', 'Approved')`.** A reprocessed copy has no `ZipSha256` (U9), so it never collides.
2. **The upload looks for a live version with the same `ZipSha256`.** Found: 200 with that version (a `Blocked` one would be blocked again; an `Approved` one has nothing new). Not found: a new version.
3. **Creating a version deletes the document's `Failed` versions** in the same transaction, and sets older `Blocked` and `PendingReview` versions to `Superseded` as before. After the commit, the API deletes their blobs (`incoming`, `clean`, `text`). For a U9 retry after an extraction failure, the checked ZIP is copied first, then the failed version is deleted.
4. **The transaction checks again before it inserts.** It locks the `Document` row (`UPDLOCK`), refuses with 409 when a version of the document is `Uploaded`, and for a U9 retry requires that deleting the source version `WHERE Status = 'Failed'` changes one row. So two retries at once, or a retry and an upload at once, cannot both make a version.
5. **`Superseded` is reached only from `Blocked` and `PendingReview`.** `Failed` ends by deletion, or stays while it is the newest version, so the UI can offer "Retry".

## Consequences

- "Retry" after any failure leaves no failed version of the document in the database.
- "Retry" after a failure before the check (`integrity`, `check_error`, `timeout` before the check) works with the same original and the same masking.
- A retry of a lost response still returns the version made by the first try, unless that version has failed meanwhile; then the retry makes a new version.
- A late message or blob from the deleted attempt finds no version: the status consumer changes zero rows, the daily orphan sweep deletes a late `clean` or `text` blob ([ADR-0012](0012-deletion-and-retention.md)), and the 24-hour lifecycle rule deletes a late `incoming` ZIP ([ADR-0005](0005-asynchronous-import-pipeline.md)). A crash between the commit and the blob deletion leaves orphans for the same two.
- A `CheckRequested` still queued for a deleted version (the checker was down) can lead to a full check and extraction that nobody reads. It costs a few cents; ADR-0012 accepts the same for a deleted document.
- The reason of a failure is kept only in the logs (30 days, with `verId`).
- Two parallel uploads of the same ZIP after a failure: the second insert violates the index and returns the version made by the first. The loser's `incoming` ZIP has no row; the 24-hour lifecycle rule deletes it ([ADR-0005](0005-asynchronous-import-pipeline.md)).
