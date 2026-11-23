# 12. Deletion of documents and accounts, and retention

Date: 2026-11-22

## Status

Accepted

## Context

When a person deletes a document, they expect it to disappear everywhere. When they withdraw consent or delete their account, everything of theirs must go (G5). Data derived from a document lives in several places, each with its own rules:

| Store | What is there | Deleted at once? |
|---|---|---|
| Azure SQL | versions, results, fragments with vectors, consent, daily usage counters | yes, but it stays in automated backups (point-in-time restore keeps 1 to 35 days, 7 by default, and cannot be switched off) |
| Blob `incoming` | the masked ZIP before the check | yes; a lifecycle rule removes leftovers after 24 hours |
| Blob `clean` | the checked masked ZIP | yes, without soft delete or versions |
| Blob `text` | words with positions, extracted results | yes, without soft delete or versions |
| Service Bus | messages in flight, with identifiers only | they expire or are processed; they hold no content |
| Azure OpenAI | prompts in the abuse-monitoring store | no; kept up to 30 days; masked data only |
| Document Intelligence | input | no; kept up to 24 hours; masked pages only |
| Application Insights | logs | identifiers only, never content; 30 days |
| Entra External ID tenant | the user object with the e-mail from Google; sign-in logs | the user object: deleted by the owner by hand after an alert, then purged at once or by Entra after 30 days; sign-in logs: 7 days, not exported |

There is no transaction across SQL and Blob Storage, so deleting "in one operation" is not possible. A document can also be deleted while its pipeline is still running.

### Considered options

1. **Hard delete at once, with the fewest copies possible.** Closest to "really gone", but a mistake or a bug loses data with no way back.
2. **A recycle bin in the application**, emptied after 30 days. A mistake can be undone, but "deleted" data stays for another month, plus backups.
3. **Hard delete at once from the live stores; backups expire after a fixed, stated period.** An honest, checkable promise, with a way back from a disaster.

## Decision

We choose option 3.

1. **Deleting a document is a short saga, run by the API:**
   1. one SQL transaction deletes the document's rows (versions, results, fragments) and records a deletion marker with its blob prefix;
   2. the API deletes every blob under `{userId}/{docId}/` in `incoming`, `clean` and `text`;
   3. the marker is removed.

   If the API stops between the steps, the sweeper finds the marker and finishes step 2. The marker is written only when the transaction deleted something. Deleting a blob that is already gone is not an error.
2. **A pipeline still running for a deleted document finds nothing to work on.** The checker and the extractor complete their message when the blob is missing, and the API ignores status events for versions that no longer exist ([ADR-0005](0005-asynchronous-import-pipeline.md)). A late write of `text` by the extractor, or of `clean` by the checker, is removed by the sweeper, which once a day deletes blobs whose version does not exist.
3. **Deleting an account** is the same saga for the whole person:
   1. one SQL transaction sets the user to `Deleting`, deletes the consent and records a deletion marker for the prefix `{userId}/`; from then on the person cannot use the application, and status events for their documents change nothing;
   2. the API deletes every blob under `{userId}/` in the three containers;
   3. one SQL transaction deletes all the person's rows and the user row;
   4. the API logs `AccountDeleted` and removes the marker.

   The marker keeps the person's `oid`, so the last step can run after the user row is gone: the API logs `AccountDeleted` with the `oid` only, and an alert e-mails the owner, who removes the user object in the External ID tenant by hand ([ADR-0010](0010-identity-users-and-consent.md)). Because every blob path starts with `userId`, the sweeper can confirm that nothing is left under the prefix.
4. **Withdrawing consent deletes the account** ([ADR-0010](0010-identity-users-and-consent.md)).
5. **SQL backups are kept for 7 days.** The application and the README say: "Deleted from the application at once, from backups after 7 days."
6. **No soft delete and no versions** on the blob containers. A mistaken delete is fixed by importing the original again; the data export is the person's own backup.
7. **Chat history is not stored on the server.** It lives in the browser tab only.
8. **Logs contain identifiers only**, never document content, prompts or answers. Retention is 30 days.
9. **A confirmation before deleting**, instead of a recycle bin.
10. **An integration test** deletes a document and an account and checks every store.

## Consequences

- Seven days after a delete, no copy of the data is left in our stores, including the Entra sign-in logs. The sign-in account in Entra depends on the owner: it goes when the owner removes it, at the latest 30 days after that. Masked data may stay in the managed AI services for up to 30 days, as stated in the README.
- A SQL restore is for disasters only. It can bring back results whose page images are gone; their citations then say the page is unavailable.
- The sweeper is part of deletion, not only of import. If it stops, deletions are finished late, not lost.
- Conversations are lost when the tab is closed. Answers come from stored results, so asking again gives the same facts.
- SDKs that can log prompts (sensitive-data logging) must stay switched off, and a test checks the logging configuration.
