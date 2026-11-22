# Spike: masking in the browser

**Question:** can the browser render a lab result, OCR it and mask all personal data well and fast enough, so that the plaintext original never leaves the user's device?

If yes, the server-side sanitiser and the quarantine disappear. The answer was yes: see [ADR-0003](../../docs/adr/0003-mask-in-the-browser-check-again-on-the-server.md) and [ADR-0005](../../docs/adr/0005-no-archive-of-originals.md).

## How it works

1. **Render.** PDF.js renders each page to a canvas at 200 or 300 DPI. Photos are drawn as they are.
2. **OCR.** Tesseract.js (WebAssembly, LSTM, Polish `best_int` model) reads words with their positions.
3. **Rebuild printed rows.** Tesseract splits a page into blocks, so one printed row (a table header with separate columns, a date label and its value) can come back as several lines. Rows are rebuilt from word positions. A date printed slightly higher or lower than its label is attached to the label.
4. **Decide by zones** ([ADR-0004](../../docs/adr/0004-zone-based-masking.md), rules in [rules.js](rules.js)):
   - **Results table:** from the table header (or the first result row on a page without one) to the last result row or method line, extended over the lines right below it (descriptions, word results such as "ujemny") while they keep the table's line spacing and are neither people lines nor date fields. Everything in it is kept, except lines naming the patient or staff (Pacjent, PESEL, mgr, dr, Autoryzował…), valid PESEL numbers and numbers with 7 or more digits.
   - **Outside the table:** only date fields are kept: a date label (with up to three prefix words, e.g. "Data i godz.") (registration, collection, admission, analysis, release…, abbreviations included) with the date and time right after it. The date of birth never.
   - **No table found:** only date fields.
5. **Compose (keep-only).** The output starts as a white page, and only the kept words are copied onto it. Kept words get a vertical margin of a third of the text height, so descenders and accents are not cut. Masked words are shown as dark boxes, or left blank. The boxes are drawn on the new page, so no pixel of the masked text is ever copied. Stamps, signatures, logos, barcodes and unknown text never reach the output, without having to be detected.
6. **Leak check.** A second OCR pass on the output, with the table found on the original. Outside the table any confidently read word that is not a date field blocks the document. In the table, a PESEL number, a long number or a people line does.

All libraries and the language model are served from this site. The page's Content Security Policy only allows requests to its own origin.

## Run it

- Online: the GitHub Pages site of this repository, under `spikes/browser-sanitiser/`.
- Rules tests: `node --test 'spikes/**/*.test.mjs'`.
- A synthetic sample with fake data: [samples/synthetic-lab-result.png](samples/synthetic-lab-result.png), generated from the SVG next to it.

## Acceptance tests

| # | Test | Pass when |
|---|---|---|
| T1 | Synthetic sample on a laptop and a phone | Clean; every result, unit, range and date field kept |
| T2 | 5 or more real documents: 2 or more laboratories, 1 or more with several pages, 1 or more photo of a printout, a scan if available. | No personal data visible on any page marked Clean (hard requirement). A leak on a page marked Blocked is acceptable: it failed closed. |
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
| 2026-11-20 | laptop, Chrome and Edge | 9 real results, 2 labs: 7 text PDFs, 1 scan, 1 photo, 1 to 4 pages | 300 | 4.3–16.9 s | 0 | on 5 of 9; date fields lost on 7 of 9 | round 1. Causes: "Data i godz." kept only two prefix words; header columns and offset date values split into separate OCR lines; word results ("ujemny") did not count as result rows, so the end of a table fell outside it; descenders cut at the box edge; the PDF.js worker was loaded only with the first PDF, so offline failed. Fixes applied, round 2 pending |

Real documents are tested only on the user's own devices and are never committed.

## Known limitations

- GitHub Pages cannot send HTTP headers, so the CSP is a `<meta>` tag. It does not apply to Web Workers. A production deployment sends the policy as a header.
- Up to 5 pages per document.
- Graphics such as the laboratory logo are not kept, only text. Keeping a picture region would also keep barcodes, which often encode the order or patient number.
- An earlier version kept the laboratory header above the first patient label. On a real document a validator's name sat in that zone and leaked, because the leak check trusted the zone. The zone was replaced by the rule above, and the leak check has no exempt areas.
- Dark boxes show the length of each masked run, e.g. how long a name is.
- PDF.js is the legacy build. The modern build uses JavaScript features that current mobile browsers do not have yet.
