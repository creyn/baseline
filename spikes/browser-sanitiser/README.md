# Spike: masking in the browser

**Question:** can the browser render a lab result, OCR it and mask all personal data well and fast enough, so that the plaintext original never leaves the user's device?

If yes, the server-side sanitiser and the quarantine disappear (see [ADR-0003](../../docs/adr/0003-mask-personal-data-before-ai.md), [ADR-0004](../../docs/adr/0004-rasterise-pdf-to-png.md) and [ADR-0005](../../docs/adr/0005-no-archive-of-originals.md)).

## How it works

1. **Render.** PDF.js renders each page to a canvas at 200 or 300 DPI. Photos are drawn as they are.
2. **OCR.** Tesseract.js (WebAssembly, LSTM, Polish `best_int` model) reads words with their positions.
3. **Decide.** [rules.js](rules.js) keeps a word only if it is a known parameter, a header, a unit, or a number or flag on a line with a parameter or unit. Dates are kept only next to a date label. Lines with personal labels (patient, PESEL, date of birth, address, doctor, order number) are masked in full. A valid PESEL, any number with 7 or more digits and the user's known identifiers are always masked.
4. **Compose (keep-only).** The output starts as a white page, and only the kept words are copied onto it. Stamps, signatures, logos, barcodes and unknown text never reach the output, without having to be detected.
5. **Leak check.** A second OCR pass on the output. Any denylist hit or any confidently read word outside the allowlist blocks the document.

All libraries and the language model are served from this site. The page's Content Security Policy only allows requests to its own origin.

## Run it

- Online: the GitHub Pages site of this repository, under `spikes/browser-sanitiser/`.
- Rules tests: `node --test 'spikes/**/*.test.mjs'`.
- A synthetic sample with fake data: [samples/synthetic-lab-result.png](samples/synthetic-lab-result.png), generated from the SVG next to it.

## Success criteria

| Criterion | Target |
|---|---|
| Leaks | none, on every tested document |
| Results kept | every value, unit and range readable after masking |
| Time per page, laptop | under about 10 s at 300 DPI |
| Time per page, phone | under about 30 s |
| OCR quality | comparable to native Tesseract on the same pages |

## Results

| Date | Device | Document | DPI | Time per page | Leaks | Values lost | Notes |
|---|---|---|---|---|---|---|---|
| 2026-11-17 | server, Node 22, 1 vCPU | synthetic sample, 1 page | 300 | 10.4 s (OCR 5.8, compose 1.9, leak check 2.7) | 0 | 0 | after adding OCR variants of µ in units |

Real documents are tested only on the user's own devices and are never committed.

## Known limitations

- GitHub Pages cannot send HTTP headers, so the CSP is a `<meta>` tag. It does not apply to Web Workers. A production deployment sends the policy as a header.
- The parameter dictionary in [rules.js](rules.js) is a starting list. An unknown parameter is masked, which is safe but loses data.
- Up to 5 pages per document.
