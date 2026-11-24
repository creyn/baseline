# 16. The same ZIP sent again matches only a live version

Date: 2026-11-24

## Status

Accepted. Changes the unique index of point 3 in [ADR-0006](0006-document-lifecycle-and-review.md) ("a unique index on (`docId`, `zipSha256`)").

## Context

ADR-0006 makes (`DocumentId`, `ZipSha256`) unique, so a retry of an upload whose response was lost returns the version made by the first try, instead of a second version.

After `Failed (integrity, check_error, or timeout before the check)` there is no checked ZIP, so "Retry" means: the user picks the original again and sends a new version. The browser masks the same file the same way, so the ZIP is usually identical. The unique index then returns the failed version, and the user can never retry.

### Considered options

1. **Keep the index.** The user is stuck after any failure before the check, unless they change the masking.
2. **A filtered index: unique only among live versions** (`Uploaded`, `Blocked`, `PendingReview`, `Approved`). A retry of a lost response still returns the first version while it is live; after a failure, or after the version was superseded or archived, the same ZIP makes a new version.
3. **An idempotency key per upload attempt**, sent by the browser in a header. The usual pattern for retries, but it adds a field, a column and a rule, and ADR-0006 already chose identifiers made by the server.
4. **No unique index;** rely on the 409 while the newest version is `Uploaded`. A lost response retried after the version moved on (to `Blocked` or `PendingReview`) would make a duplicate version.

All options pass the gates. Option 2 is the smallest change that keeps the retry rule (K1) and needs no new field (K6).

## Decision

We choose option 2.

1. **The unique index on (`DocumentId`, `ZipSha256`) is filtered `WHERE ZipSha256 IS NOT NULL AND Status IN ('Uploaded', 'Blocked', 'PendingReview', 'Approved')`.** A reprocessed copy has no `ZipSha256` (U9), so it never collides.
2. **The upload looks for a live version with the same `ZipSha256`.** Found: 200 with that version (a `Blocked` one would be blocked again; an `Approved` one has nothing new). Not found: a new version, as usual; creating it sets older `Blocked`, `PendingReview` and `Failed` versions to `Superseded`.

## Consequences

- "Retry" after a failure before the check (`integrity`, `check_error`, `timeout` before the check) works with the same original and the same masking.
- A retry of a lost response still returns the version made by the first try, unless that version has failed or was superseded meanwhile; then the retry makes a new version, which is what the user wants.
- After an extraction failure, "Retry" is a U9 copy as before; sending the same ZIP by hand also makes a new version, which is checked again.
- Two parallel uploads of the same ZIP after a failure: the second insert violates the index and returns the version made by the first. The loser's `incoming` ZIP has no row; the 24-hour lifecycle rule deletes it ([ADR-0005](0005-asynchronous-import-pipeline.md)).
