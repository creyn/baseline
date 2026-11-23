# Sequence diagrams

Sequence diagrams are generated from scripts in [tools/diagrams](../../tools/diagrams/). Edit the scripts, never the SVG files.

## Conventions

- **Every actor has its own column**, including each Blob container and each queue, so every arrow is unambiguous.
- **Arrows carry their arguments:** requests, messages with their fields, blob paths, SQL with its conditions.
- **Alternative paths are `alt` frames with arrows**, never a description. The success path in a frame has a green background.
- **A red "✗" note under an arrow** says what state the system is left in if that step fails because of an infrastructure failure (a service is down, a process stops before it acknowledges a message).
- **Arrow colours:** red carries the original or unmasked personal data, teal carries masked data only.
- **Grey notes** state facts (what happens when the user closes the browser, states that do not exist on purpose). Yellow notes are open questions.
- **Sections** carry the target time (p95) and the frequency from [use-cases.md](../use-cases.md).

## Diagrams

One diagram per use case of [use-cases.md](../use-cases.md), for the chosen architecture.

| # | Use case | Diagram | Decisions |
|---|---|---|---|
| U1 | Account, sign in and consent | [01-sign-in-and-consent](01-sign-in-and-consent.svg) | [ADR-0010](../adr/0010-identity-users-and-consent.md) |
| U2 | Import a lab result | [02-import](02-import.svg) | [ADR-0003](../adr/0003-masking-in-the-browser-and-a-second-check.md), [ADR-0005](../adr/0005-asynchronous-import-pipeline.md), [ADR-0006](../adr/0006-document-lifecycle-and-review.md) |
| U3 | Review and approve the extracted values | [03-review](03-review.svg) | [ADR-0006](../adr/0006-document-lifecycle-and-review.md), [ADR-0008](../adr/0008-retrieval-without-ai-search.md) |
| U4 | Fix a blocked document and send it again | [04-blocked-document](04-blocked-document.svg) | [ADR-0003](../adr/0003-masking-in-the-browser-and-a-second-check.md) |
| U5 | Browse results and trends | [05-browse-results](05-browse-results.svg) | [ADR-0008](../adr/0008-retrieval-without-ai-search.md) |
| U6 | Ask the agent a question | [06-ask-the-agent](06-ask-the-agent.svg) | [ADR-0009](../adr/0009-agent-questions-and-summaries.md) |
| U7 | Pre-visit summary | [07-pre-visit-summary](07-pre-visit-summary.svg) | [ADR-0009](../adr/0009-agent-questions-and-summaries.md) |
| U8 | Delete a document | [08-delete-document](08-delete-document.svg) | [ADR-0012](../adr/0012-deletion-and-retention.md) |
| U9 | Reprocess or retry a document | [09-reprocess-document](09-reprocess-document.svg) | [ADR-0006](../adr/0006-document-lifecycle-and-review.md) |
| U10 | Delete the account or withdraw consent | [10-delete-account](10-delete-account.svg) | [ADR-0010](../adr/0010-identity-users-and-consent.md), [ADR-0012](../adr/0012-deletion-and-retention.md) |
| U11 | Export my data | [11-export](11-export.svg) | [ADR-0012](../adr/0012-deletion-and-retention.md) |

The import flows A and B, compared with the chosen C, are in [ADR-0005](../adr/0005-asynchronous-import-pipeline.md).

## Open questions

None at the moment.
