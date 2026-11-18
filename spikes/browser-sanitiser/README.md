# Spike: masking in the browser

**Question:** can the browser render a lab result, OCR it and mask all personal data well and fast enough, so that the plaintext original never leaves the user's device?

If yes, the server-side sanitiser and the quarantine disappear (see [ADR-0003](../../docs/adr/0003-mask-personal-data-before-ai.md), [ADR-0004](../../docs/adr/0004-rasterise-pdf-to-png.md) and [ADR-0005](../../docs/adr/0005-no-archive-of-originals.md)).

## How it works

1. **Render.** PDF.js renders each page to a canvas at 200 or 300 DPI. Photos are drawn as they are.
2. **OCR.** Tesseract.js (WebAssembly, LSTM, Polish `best_int` model) reads words with their positions.
3. **Decide.** [rules.js](rules.js) keeps a word only if:
   - it is a known parameter, a header word or a unit, or a number or flag on a line with a parameter, unit or ICD-9 PL code;
   - it is a date or time next to a date label (collection, admission, analysis, release);
   - it is the test name and code before or in an ICD-9 PL marker, e.g. `TSH (ICD-9: L69)`, so tests missing from the dictionary are kept too;
   - it is on a method line ("Badanie wykonano metodą … na aparacie …");
   - it is in the laboratory header: the lines above the first patient or referrer label, within the top quarter of the page. Without such a label there is no header zone.

   Lines with personal labels (patient, PESEL, date of birth, address, doctor, order number) are masked in full. A valid PESEL, any number with 7 or more digits and the user's known identifiers are always masked, also in the header and on method lines.
4. **Compose (keep-only).** The output starts as a white page, and only the kept words are copied onto it. Masked words are shown as dark boxes, or left blank. The boxes are drawn on the new page, so no pixel of the masked text is ever copied. Stamps, signatures, logos, barcodes and unknown text never reach the output, without having to be detected.
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
| 2026-11-17 | server, headless Chromium, 1 vCPU | real result, text PDF, 1 page | 300 | 13.9 s (OCR 8.9, leak check 4.3) | 0 | units, fixed | the PDF failed on mobile browsers until PDF.js was switched to its legacy build; units with a footnote marker (pg/ml*) were masked until markers were stripped |

Real documents are tested only on the user's own devices and are never committed.

## Known limitations

- GitHub Pages cannot send HTTP headers, so the CSP is a `<meta>` tag. It does not apply to Web Workers. A production deployment sends the policy as a header.
- The parameter dictionary in [rules.js](rules.js) is a starting list. An unknown parameter is masked, which is safe but loses data.
- Up to 5 pages per document.
- Graphics such as the laboratory logo are not kept, only text. Keeping a picture region would also keep barcodes, which often encode the order or patient number.
- Dark boxes show the length of each masked run, e.g. how long a name is.
- PDF.js is the legacy build. The modern build uses JavaScript features that current mobile browsers do not have yet.
