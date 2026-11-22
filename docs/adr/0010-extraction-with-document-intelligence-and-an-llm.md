# 10. Extraction with Document Intelligence and an LLM

Date: 2026-11-22

## Status

Proposed

## Context

From the masked pages, extraction must return for every result: the parameter as printed, value, unit, reference range, flag, material, measurement condition, method, analyser, every date on the result except the date of birth, and the page and position it came from. Positions are needed to highlight values on review ([ADR-0009](0009-mandatory-review-of-extracted-values.md)) and for citations.

Numbers must be exact. Every value is reviewed, but every error costs the user time.

### Considered options

1. **An LLM with vision only**, reading the page images. Simple, one call. But a vision model gives no reliable word positions, and its reading of digits cannot be checked against an OCR layer.
2. **Document Intelligence only** (layout, tables). Exact text and positions, but it does not know what a parameter, a range or a measurement condition is, so the mapping becomes our rule code for every layout.
3. **Our own OCR (Tesseract) and an LLM.** No Document Intelligence cost, but Tesseract is weaker on tables and scans than Document Intelligence, and we would maintain the OCR quality ourselves.
4. **Document Intelligence (layout) and an LLM on its text**, with the output validated by a schema in code.

## Decision

We choose option 4.

1. **The extractor builds one image-only PDF of all pages in memory** and sends it to Document Intelligence `prebuilt-layout` in one call. The PDF is never stored. Page numbers in the answer are mapped back to page hashes by the order in the manifest.
2. **The LLM gets the masked text and tables of all pages in one prompt**, so it sees the whole result, and answers in a JSON schema (structured output). Each result carries its page hash and position.
3. **The output is validated with pydantic:** schema, numbers, units, dates. An invalid answer gets one retry with the validation errors; still invalid ends in `Failed (extract_invalid)`.
4. **The words with positions and the results are saved** in the `text` container before reporting ([ADR-0007](0007-asynchronous-import-pipeline.md)).
5. **The model is gpt-5.4 mini**, deployed in the EU Data Zone. A larger model is used only where evals show the smaller one is not good enough.
6. **Evals run in CI** on synthetic documents with fictional data that reproduce real layouts. Values and units must be 100% correct; normalised names and ranges target at least 95%.

## Consequences

- Document Intelligence costs 0.01 USD per page and the LLM about 0.02 USD per result.
- Exact word positions make highlighting and citations possible.
- Document Intelligence keeps its input for up to 24 hours. It receives masked pages only.
- Two services are called per document; both failures are handled by retries and `Failed (extract_error)` ([ADR-0007](0007-asynchronous-import-pipeline.md)).
- The free tier of Document Intelligence analyses only the first 2 pages, so development and evals need the S0 tier.
