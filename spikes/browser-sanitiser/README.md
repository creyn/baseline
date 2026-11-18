# Spike: masking in the browser

**Question:** can the browser render a lab result, OCR it and mask all personal data well and fast enough, so that the plaintext original never leaves the user's device?

If yes, the server-side sanitiser and the quarantine disappear (see [ADR-0003](../../docs/adr/0003-mask-personal-data-before-ai.md), [ADR-0004](../../docs/adr/0004-rasterise-pdf-to-png.md) and [ADR-0005](../../docs/adr/0005-no-archive-of-originals.md)).

## How it works

1. **Render.** PDF.js renders each page to a canvas at 200 or 300 DPI. Photos are drawn as they are.
2. **OCR.** Tesseract.js (WebAssembly, LSTM, Polish `best_int` model) reads words with their positions.
3. **Decide.** [rules.js](rules.js) keeps a word only if:
   - it is a known parameter, a header word or a unit, or a number or flag on a line with a parameter, unit or ICD-9 PL code;
   - it is a date field: a date label (registration, collection, admission, analysis, release, authorisation) with the date and time right after it. The date of birth is never kept;
   - it is the test name and code before or in an ICD-9 PL marker, e.g. `TSH (ICD-9: L69)`, so tests missing from the dictionary are kept too;
   - it is on a method line ("Badanie wykonano metodą … na aparacie …");

   Above the results table (the first table header or result row) only date fields are kept. The patient, the referrer, the ordering clinic and the laboratory header are masked there.

   Lines with personal labels (patient, PESEL, date of birth, address, doctor, order number) or with people who performed, validated or signed the result (mgr, dr, "zatwierdził", "wykonał" and similar) are masked in full, except their date fields. A valid PESEL, any number with 7 or more digits and the user's known identifiers are always masked, also in the header and on method lines.
4. **Compose (keep-only).** The output starts as a white page, and only the kept words are copied onto it. Masked words are shown as dark boxes, or left blank. The boxes are drawn on the new page, so no pixel of the masked text is ever copied. Stamps, signatures, logos, barcodes and unknown text never reach the output, without having to be detected.
5. **Leak check.** A second OCR pass on the output. Any denylist hit or any confidently read word outside the allowlist blocks the document.

All libraries and the language model are served from this site. The page's Content Security Policy only allows requests to its own origin.

## Run it

- Online: the GitHub Pages site of this repository, under `spikes/browser-sanitiser/`.
- Rules tests: `node --test 'spikes/**/*.test.mjs'`.
- A synthetic sample with fake data: [samples/synthetic-lab-result.png](samples/synthetic-lab-result.png), generated from the SVG next to it.

## Acceptance tests

| # | Test | Pass when |
|---|---|---|
| T1 | Synthetic sample on a laptop and a phone | Clean; every result, unit, range and date field kept |
| T2 | 5 or more real documents: 2 or more laboratories, 1 or more with several pages, 1 or more photo of a printout, a scan if available. Known identifiers filled in. | No personal data visible on any page marked Clean (hard requirement). A leak on a page marked Blocked is acceptable: it failed closed. |
| T3 | The same documents, results kept | Every value, unit and range kept on 4 of 5 documents or more |
| T4 | The same documents, date fields kept | Every date field except the date of birth kept on 4 of 5 documents or more |
| T5 | False blocks | At most 1 document Blocked with nothing personal left on it |
| T6 | Phone, 300 DPI, a document with 2 or more pages | Finishes without a crash; time per page recorded |
| T7 | 200 DPI vs 300 DPI on a laptop, 2 documents | Time and lost values recorded for both |
| T8 | Offline: load the page, switch the device to airplane mode, process a document | Works offline, which shows that nothing is sent |

Time targets, revised after the first measurements: under about 20 s per page on a laptop and under about 60 s per page on a phone, at the DPI chosen in T7. Import is occasional and runs in the background, so the first target of 10 s was stricter than needed.

Results are recorded per document as: laboratory, kind (text PDF, scan, photo), pages, device, DPI, time per page, verdict, kinds of personal data left (no values), lost results (names only), lost date fields (labels only).

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
- An earlier version kept the laboratory header above the first patient label. On a real document a validator's name sat in that zone and leaked, because the leak check trusted the zone. The zone was replaced by the rule above, and the leak check has no exempt areas.
- Dark boxes show the length of each masked run, e.g. how long a name is.
- PDF.js is the legacy build. The modern build uses JavaScript features that current mobile browsers do not have yet.
