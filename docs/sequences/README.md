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

| Use cases | Diagram |
|---|---|
| U2 import, U3 review, U4 blocked document, U5 browse results, U6 ask the agent | [The chosen import pipeline (C)](../adr/0007/c-pipeline-without-outbox.svg), with the variants it was compared to in [ADR-0007](../adr/0007-asynchronous-import-pipeline.md) |
| U1 sign-in and consent, U7 summary, U8 delete a document, U9 reprocess, U10 delete the account, U11 export | Not drawn yet. The decisions are in [ADR-0013](../adr/0013-identity-users-and-consent.md), [ADR-0012](../adr/0012-one-agent-with-tools-and-guardrails.md) and [ADR-0019](../adr/0019-deletion-and-retention.md). |
