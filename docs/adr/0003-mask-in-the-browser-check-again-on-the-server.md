# 3. Mask in the browser, check again on the server

Date: 2026-11-22

## Status

Proposed

## Context

Lab results are health data, a special category of personal data under GDPR (Art. 9). A document also holds personal data of several people: the patient (name, PESEL, date of birth, address), the doctor and the lab staff (names, licence numbers, stamps, signatures), and identifiers that lead back to a person (order and sample numbers, barcodes).

Facts about the managed AI services (checked 2026-11-17):
- **Azure OpenAI** keeps prompts in an abuse-monitoring store by default, where people may review them. Opting out is not available to an individual.
- **Document Intelligence** keeps input for up to 24 hours.
- **The Azure de-identification service** works on text, not images, and does not support Polish.

A PDF from a lab is also untrusted input: it can carry scripts, embedded files, metadata with personal data, and hidden text aimed at the model (prompt injection). A black box drawn over text in a PDF is often only an overlay, with the text still underneath.

The [browser sanitiser spike](../../spikes/browser-sanitiser/README.md) ran the masking rules of [ADR-0004](0004-zone-based-masking.md) entirely in the browser (PDF.js, Tesseract.js) on 9 real lab results from 2 laboratories (text PDFs, a scan and photos), on a 2017 laptop and a 2020 phone:
- No personal data was left on any page marked clean.
- Every result was kept on 8 of 9 documents.
- 2 documents were blocked with nothing personal on them (fail-closed).
- Time per page: 6–8 s on the phone; 11–21 s for PDFs and 26–28 s for a scan or photo on the laptop. 200 DPI is enough for PDFs.
- It works offline once the page is loaded.
- OCR differs between devices, so the rules must tolerate OCR variants.

### Considered options

1. **No masking; rely on Azure's contractual terms.** Personal data ends up in the abuse-monitoring store. Fails G1.
2. **Mask text after Document Intelligence.** The LLM is protected, but Document Intelligence sees the whole document. Fails G1.
3. **Azure de-identification service.** Text only, no Polish, and it sees the data before masking. Fails G1.
4. **A server-side sanitiser** in an isolated container, fed from an encrypted quarantine blob. Every device gives the same result. But the plaintext original reaches Azure, and the quarantine needs its own key, lifecycle and handling of blocked documents.
5. **Masking in the browser only.** The original never leaves the device. But the server has to trust the client: a broken or modified client could send unmasked pages straight to the AI services.
6. **Masking in the browser, and a second check on the server before any AI service.** Like option 5, plus defence in depth. The check uses generic patterns only and stores nothing.

| Criterion (weight) | 4: server sanitiser | 5: browser only | 6: browser + check |
|---|---|---|---|
| K1 simple, self-healing (40) | 2 | 5 | 4 |
| K2 cost (20) | 4 | 5 | 5 |
| K4 engineering practice (15) | 4 | 3 | 5 |
| K5 testable in CI (10) | 4 | 3 | 4 |
| K6 time to deliver (10) | 2 | 5 | 4 |
| K7 performance (5) | 4 | 4 | 4 |
| **Result** | **60** | **89, but fails G1** | **87** |

Option 5 scores highest but fails G1: the server cannot know that what it received is masked, so a broken or modified client could send personal data to the AI services. Option 6 keeps G1 even then, for a small cost in simplicity.

## Decision

We choose option 6.

1. **The browser masks.** It renders each PDF page to PNG at 200 DPI (photos as they are), runs OCR, applies the rules of [ADR-0004](0004-zone-based-masking.md) and its own leak check. Rendering to pixels drops scripts, metadata and hidden text, and burns the masks into the image.
2. **The user approves the masked pages** and can add mask boxes. Masking can be added, never removed.
3. **The original never leaves the device.** The browser sends one ZIP ([ADR-0007](0007-asynchronous-import-pipeline.md)) with:
   - the masked PNG pages,
   - the rectangles of the kept regions, without their text,
   - the SHA-256 of each masked page, computed after the user approved it,
   - the SHA-256 of the original, to recognise the same document again ([ADR-0008](0008-document-lifecycle-and-identifiers.md)).
4. **The API validates without reading the content:** a stored ZIP, PNG only, known names, sizes, and each page's hash recomputed. A page that does not match the hash the user approved is rejected.
5. **The checker looks again before anything else.** It is the first step of the pipeline, and no page reaches a managed AI service without passing it.
   - **Shape check:** outside the kept rectangles, only white background or solid mask boxes. Any other ink (text, a signature, a barcode) blocks the document.
   - **OCR check:** Tesseract in memory, with the same zone rules. Outside the table only date fields may remain; in the table no valid PESEL, no long number and no line naming a person.
   - **Nothing personal is needed or kept.** The rules are patterns in code. Logs hold the verdict, the rule that fired and a count, never the text that was read.
6. **Blocked:** the pages are deleted and the user gets the suspicious regions (page and rectangle, no text). They see them on their own copy in the browser, add mask boxes and send again, or give up.
7. **The checker has no access to the AI services.** Its identity has no role on Document Intelligence or Azure OpenAI, and only its own containers and queues in Storage and Service Bus. Blocking its outbound network is not possible without extra paid networking ([ADR-0006](0006-serverless-hosting-on-azure.md)), so least privilege is the boundary.

## Consequences

- **Our Azure subscription never receives an original.** There is no quarantine, no quarantine key and no lifecycle for plaintext. [ADR-0005](0005-no-archive-of-originals.md) follows from this.
- **The browser does more work and depends on the device.** A slow laptop needs up to about 30 s per photo page. Import is rare, so this is accepted.
- **OCR differs between devices**, so a rule that works on the server may fail in a browser. Rules are tested against OCR variants, and synthetic documents that reproduce real layouts with fictional data run in CI.
- **Known gaps from the spike, to fix in the implementation:** words are joined to the first matching row instead of the nearest; curved lines on photos split rows; the leak check reads dark mask boxes as letters (false Blocked). The OCR check must ignore words that lie entirely on a mask box.
- **A bare name inside the results table, without a label, passes both checks.** The user's review of the masked pages is the safeguard ([ADR-0004](0004-zone-based-masking.md)).
- **The UI framework must run OCR and PDF rendering in the browser** ([ADR-0021](0021-ui-in-typescript-and-react.md)).
