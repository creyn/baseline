# 9. Every extracted value is reviewed before it is used

Date: 2026-11-22

## Status

Proposed

## Context

Values are extracted by Document Intelligence and an LLM ([ADR-0010](0010-extraction-with-document-intelligence-and-an-llm.md)). A model can misread a digit, swap a unit or attach a value to the wrong parameter. Trends, the agent's answers and pre-visit summaries are built from these values, and a wrong number in a health record is worse than a missing one.

The masking was already approved by the user in the browser before the upload ([ADR-0003](0003-mask-in-the-browser-check-again-on-the-server.md)). This review is about the values.

### Considered options

1. **No review.** Values are used as extracted. Fastest, but a model error goes straight into trends and answers. Fails G4.
2. **Review only values with low confidence.** Less work, but models are often confidently wrong, and a confidence threshold hides exactly those errors.
3. **Review every value before it is used**, next to its place on the masked page. Values are stored at once, so nothing is lost before review.

## Decision

We choose option 3.

1. **Results are stored as soon as they are extracted**, with the version in `PendingReview` ([ADR-0008](0008-document-lifecycle-and-identifiers.md)). Closing the browser loses nothing.
2. **Only `Approved` results are read** by trends, the agent's tools, summaries and the export. Every query filters on it.
3. **The review screen shows every value next to its place on the masked page**, highlighted from the word positions saved by extraction. The user can correct a value, unit, range or date (also by clicking the right word on the page), or reject a row.
4. **Approval is one transaction** with optimistic concurrency. A second approval of the same version (a retry) or an approval of an outdated extraction gets 409, and the UI shows the current state.
5. **The laboratory's flag and the computed flag are compared on review** ([ADR-0016](0016-reference-ranges.md)). A disagreement is shown, because it often means an extraction error.

## Consequences

- No number reaches a trend or an answer without a person having seen it next to its source.
- Every import needs a few minutes of the user's attention. Importing old results is the largest effort.
- Corrections made on review are the best signal of extraction quality. Counting them per field and per model version is a later improvement.
