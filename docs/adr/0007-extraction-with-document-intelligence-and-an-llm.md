# 7. Extraction with Document Intelligence and an LLM

Date: 2026-11-22

## Status

Accepted

## Context

From the masked pages, extraction must return for every result: the parameter as printed, value, unit, reference range, flag, material, measurement condition, method, analyser, every date on the result except the date of birth, and the page and position it came from. Positions are needed to highlight values on review ([ADR-0006](0006-document-lifecycle-and-review.md)) and for citations.

Numbers must be exact. Every value is reviewed, but every error costs the user time.

### Considered options

1. **An LLM with vision only**, reading the page images. Simple, one call. But a vision model gives no reliable word positions, and its reading of digits cannot be checked against an OCR layer.
2. **Document Intelligence only** (layout, tables). Exact text and positions, but it does not know what a parameter, a range or a measurement condition is, so the mapping becomes our rule code for every layout.
3. **Our own OCR (Tesseract) and an LLM.** No Document Intelligence cost, but Tesseract is weaker on tables and scans than Document Intelligence, and we would maintain the OCR quality ourselves.
4. **Document Intelligence (layout) and an LLM on its text**, with the output validated by a schema in code.

## Decision

We choose option 4.

1. **The extractor builds one image-only PDF of all pages in memory** and sends it to Document Intelligence `prebuilt-layout` in one call. The PDF is never stored. Page numbers in the answer are mapped back to page hashes by the order in the manifest.
2. **The LLM gets the masked text and tables in batches of pages** (5 pages to start, tuned with evals), because documents have no page limit and one prompt for all pages could exceed the model's context or output. It answers in a JSON schema (structured output). Each result carries its page hash and position.
   - The prompt includes the list of known parameters from the repository ([ADR-0011](0011-lab-parameters-units-and-ranges.md)). For each result the model also returns the printed ICD-9 PL code if there is one, the material, the measurement condition, and a suggested parameter from that list or none. The suggestion is only a proposal for review.
   - **Every date has a time zone.** Laboratories print local time without a zone, so a printed date and time are read in the laboratory's time zone, `Europe/Warsaw` by default, and stored as a `datetimeoffset` with the offset in force on that day (summer or winter time). The zone name is stored with the result, so a result from abroad can carry its own. A date printed without a time is stored at midnight in that zone, marked as having no time. In the hour repeated when clocks go back, the earlier offset is used.
3. **The output is validated with pydantic:** schema, numbers, units, dates. An invalid answer gets one retry with the validation errors; still invalid ends in `Failed (extract_invalid)`. A valid answer with no results at all ends in `Failed (no_results)`: the document is not a lab result ([ADR-0009](0009-agent-questions-and-summaries.md)).
4. **The words with positions, the descriptive fragments (comments and descriptions, never result rows) and the results are saved** in the `text` container before reporting ([ADR-0005](0005-asynchronous-import-pipeline.md)).
5. **The model is gpt-5.4 mini**, deployed in the EU Data Zone. A larger model is used only where evals show the smaller one is not good enough.
6. **Evals run in CI** on synthetic documents with fictional data that reproduce real layouts. Values and units must be 100% correct; normalised names and ranges target at least 95%.

## Consequences

- Document Intelligence costs 0.01 USD per page and the LLM about 0.02 USD per result.
- Exact word positions make highlighting and citations possible.
- A result that spans two batches may be split or repeated. The evals include such documents; how well batching works is checked in practice.
- Document Intelligence keeps its input for up to 24 hours. It receives masked pages only.
- Two services are called per document; both failures are handled by retries and `Failed (extract_error)` ([ADR-0005](0005-asynchronous-import-pipeline.md)).
- The free tier of Document Intelligence analyses only the first 2 pages, so development and evals need the S0 tier.
