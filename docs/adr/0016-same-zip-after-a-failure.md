# 16. The same ZIP sent again after a failure makes a new version

Date: 2026-11-24

## Status

Accepted. Changes the unique index of point 3 in [ADR-0006](0006-document-lifecycle-and-review.md) ("a unique index on (`docId`, `zipSha256`)").

## Context

ADR-0006 makes (`docId`, `zipSha256`) unique, so a retry of an upload whose response was lost returns the version made by the first try, instead of a second version.

After `Failed (integrity, check_error or timeout)` there is no checked ZIP, so "Retry" means: the user picks the original again and sends a new version. The browser masks the same file the same way, so the ZIP is usually identical. The unique index then returns the failed version, and the user can never retry.

### Considered options

1. **Keep the index.** The user is stuck after any failure before the check, unless they change the masking.
2. **A filtered index: unique only among versions without a fail reason.** A retry of a lost response still returns the first version while it is in progress or done; after a failure the same ZIP makes a new version.
3. **An idempotency key per upload attempt**, sent by the browser in a header. The usual pattern for retries, but ADR-0006 rejected identifiers chosen by an untrusted client, and it adds a field and a rule.
4. **No unique index;** rely on the 409 while the newest version is `Uploaded`. A lost response retried after the version moved on (to `Blocked` or `PendingReview`) would make a duplicate version.

All options pass the gates. Option 2 is the smallest change that keeps the retry rule (K1) and needs no new field (K6).

## Decision

We choose option 2.

1. **The unique index on (`docId`, `zipSha256`) is filtered `WHERE ZipSha256 IS NOT NULL AND FailReason IS NULL`.** A reprocessed copy has no `zipSha256` (U9), so it never collides.
2. **`FailReason` is kept after a version becomes `Superseded`**, so the filter still knows it failed.
3. **The upload looks for an existing version with the same `zipSha256` and no fail reason.** Found: 200 with that version. Not found: a new version, as usual; creating it sets the failed one to `Superseded`.

## Consequences

- "Retry" after a failure before the check works with the same original and the same masking.
- A retry of a lost response still returns the version made by the first try, unless that version has failed meanwhile; then the retry makes a new version, which is what the user wants.
- Two parallel uploads of the same ZIP after a failure: the second insert violates the index and returns the version made by the first.
