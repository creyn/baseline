# 11. Deletion and retention

Date: 2026-11-18

## Status

Accepted

## Context

When the user deletes a document, they expect it to disappear everywhere. Copies of it, or data derived from it, live in several places, each with its own rules:

| Store | What is there | Can it be deleted at once |
|---|---|---|
| Azure SQL | results, ranges, dates | yes, but it stays in automated backups. Point-in-time restore keeps 1 to 35 days (7 by default) and cannot be switched off. |
| Clean blob | masked page images | yes, unless soft delete or versioning is on |
| AI Search | chunks for search | yes, there is no undo |
| Chat history | questions and answers that quote results | depends on whether it is stored |
| Azure OpenAI | prompts in the abuse-monitoring store | no, kept for up to 30 days, but they contain masked data only ([ADR-0003](0003-mask-personal-data-before-ai.md)) |
| Document Intelligence | input data | no, kept for up to 24 hours, masked pages only |
| Application Insights | whatever is logged | depends on what we log |

Original documents are not kept ([ADR-0005](0005-no-archive-of-originals.md)). The user keeps them, and uploading one again rebuilds everything derived from it.

### Considered options

1. **Hard delete at once, with as few copies as possible.** No soft delete, the shortest SQL backups. Closest to "really gone", but a mistake or a bug loses data with no way back.
2. **A recycle bin in the application**, emptied after 30 days. A mistake can be undone, but "deleted" data stays for another month, plus backups.
3. **Hard delete at once from the live stores; backups expire after a fixed, stated period.** An honest, checkable promise, with a way back from a failure. The data exists in backups for that period, out of reach of the application.

## Decision

We choose option 3.

1. **Deleting a document removes, in one operation:**
   - the results and the document row in SQL,
   - the masked pages in the clean blob,
   - the chunks in AI Search.

   An integration test checks every store.
2. **SQL backups are kept for 7 days.** The application and the README say so: "Deleted from the application at once, from backups after 7 days."
3. **No soft delete and no versions on the clean blob.**
   - It would only help with a mistaken delete, and the user's own original rebuilds the document.
   - The data export is the user's backup.
   - A SQL restore can bring back results whose page images are gone. Their citations then show that the page is unavailable and ask for the original to be uploaded again.
4. **Chat history is not stored on the server.** It lives in the open browser tab only, so deleting a document leaves no stored answers that quote it.
5. **Logs contain identifiers only**, never document content, prompts or answers. Retention is 30 days.
6. **Known limits, stated in the README:**
   - Azure OpenAI may keep masked prompts for up to 30 days,
   - Document Intelligence may keep masked pages for up to 24 hours.
7. **A confirmation before deleting, instead of a recycle bin.**

## Consequences

- Seven days after a delete, no copy of the document's data is left in our stores, apart from masked data in the managed AI services, for at most 30 days.
- A mistaken delete is fixed by uploading the original again, not by restoring a backup.
- A SQL restore is for disasters only, and may leave citations without a page image.
- Conversations are lost when the tab is closed. Questions are cheap to ask again, and answers come from stored results.
- Logging must be reviewed so that no content reaches Application Insights, including from SDKs that log prompts when sensitive-data logging is enabled.
