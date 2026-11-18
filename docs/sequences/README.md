# Use cases

Sequence diagrams for every use case. They are generated from [tools/diagrams/sequences.js](../../tools/diagrams/sequences.js), so edit the script, not the SVG files.

Arrow colours: red carries the plaintext original or unmasked personal data, teal carries masked data only. Yellow notes are open questions, listed below.

| # | Use case | Open questions |
|---|---|---|
| 1 | [One-time setup](01-setup.svg): sign-in | |
| 2 | [Import a lab result](02-import.svg): upload, masking, extraction, review, indexing | |
| 3 | [Handle a blocked document](03-blocked-document.svg): the leak check stopped a document | Q2 |
| 4 | [Browse results and trends](04-results-and-trends.svg): the most frequent read, no AI | Q3, Q4 |
| 5 | [Ask a question about results](05-question.svg): agent, tools, guardrails, citations | Q5 |
| 6 | [Prepare a pre-visit summary](06-pre-visit-summary.svg): for a chosen period, not stored | |
| 7 | [Delete a document](07-delete-document.svg) | |
| 8 | [Reprocess a document](08-reprocess-document.svg): after an extraction or masking fix | Q8 |

## Out of scope for now

- **Reminders for periodic tests.** They need a notification channel that carries no health data. Postponed.
- **MCP server.** It would expose health data to external MCP clients and their models, outside our Azure boundary.
- **Archive of original documents.** See [ADR-0005](../adr/0005-no-archive-of-originals.md).

## Open questions

Each answered question becomes an ADR or a change to an existing one.

| # | Question | Proposal |
|---|---|---|
| Q1 | ~~Who writes the known identifiers to Key Vault?~~ | Resolved by [ADR-0006](../adr/0006-zone-based-masking.md): masking needs no known identifiers. |
| Q2 | Blocked documents vs. the 24-hour quarantine lifecycle, which would delete them before the user acts. | A separate lifecycle rule by blob index tag (`blocked`), e.g. 7 days. The preview is served by the sanitiser, so the API still cannot read the quarantine. |
| Q3 | ~~Unit normalisation: the same parameter comes in different units (vitamin D in ng/ml or nmol/l).~~ | Resolved by [ADR-0007](../adr/0007-unit-normalisation.md). |
| Q4 | ~~Reference ranges differ between labs and over time.~~ | Resolved by [ADR-0008](../adr/0008-reference-ranges.md). |
| Q5 | ~~The user's own question goes to Azure OpenAI unmasked and may contain personal data.~~ | Resolved by [ADR-0009](../adr/0009-personal-data-in-questions.md). |
| Q6 | ~~Visits are not in the data model yet.~~ | Resolved by [ADR-0010](../adr/0010-store-only-lab-results.md): visits are not stored. |
| Q7 | ~~How complete is deletion?~~ | Resolved by [ADR-0011](../adr/0011-deletion-and-retention.md). |
| Q8 | Where does the parameter dictionary live? | Masking no longer depends on it ([ADR-0006](../adr/0006-zone-based-masking.md)). It maps parameter names to LOINC codes, so a user-editable mapping reveals nothing. |

Masking in the browser instead of the server-side sanitiser is being evaluated with a proof of concept. If it is chosen, the quarantine disappears and Q2 goes with it.
