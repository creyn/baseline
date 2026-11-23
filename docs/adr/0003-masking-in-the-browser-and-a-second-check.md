# 3. Masking in the browser, zone rules, a second check on the server, no archive of originals

Date: 2026-11-23

## Status

Accepted

## Context

Documents are masked before anything leaves the user's device. This ADR covers where masking runs and where it is checked again, the rules it applies, and why originals are not archived.

### Mask in the browser, check again on the server

Lab results are health data, a special category of personal data under GDPR (Art. 9). A document also holds personal data of several people: the patient (name, PESEL, date of birth, address), the doctor and the lab staff (names, licence numbers, stamps, signatures), and identifiers that lead back to a person (order and sample numbers, barcodes).

Facts about the managed AI services (checked 2026-11-17):
- **Azure OpenAI** keeps prompts in an abuse-monitoring store by default, where people may review them. Opting out is not available to an individual.
- **Document Intelligence** keeps input for up to 24 hours.
- **The Azure de-identification service** works on text, not images, and does not support Polish.

A PDF from a lab is also untrusted input: it can carry scripts, embedded files, metadata with personal data, and hidden text aimed at the model (prompt injection). A black box drawn over text in a PDF is often only an overlay, with the text still underneath.

The [browser sanitiser spike](../../spikes/browser-sanitiser/README.md) ran the zone masking rules (below) entirely in the browser (PDF.js, Tesseract.js) on 9 real lab results from 2 laboratories (text PDFs, a scan and photos), on a 2017 laptop and a 2020 phone:
- No personal data was left on any page marked clean.
- Every result was kept on 8 of 9 documents.
- 2 documents were blocked with nothing personal on them (fail-closed).
- Time per page: 6–8 s on the phone; 11–21 s for PDFs and 26–28 s for a scan or photo on the laptop. 200 DPI is enough for PDFs.
- It works offline once the page is loaded.
- OCR differs between devices, so the rules must tolerate OCR variants.

#### Considered options

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

### Zone-based masking: keep the results table, mask the rest

Masking runs in the browser and again in the checker (see above). It needs rules that keep every result and remove every person.

The first approach masked word by word: a word stayed visible only if it was in an allowlist (parameter dictionary, units, labelled dates, lab names), with a denylist of the user's known identifiers as a second layer. The browser sanitiser spike found four problems with it:
- **The dictionary decided whether results survived.** Every parameter, unit and OCR variant of a unit (`µIU/ml` read as `ulU/ml`) had to be listed. Anything missing was masked and the result was lost.
- **Context rules grew without end.** Each new layout needed a new rule.
- **A trusted zone leaked a name.** A version that kept the laboratory header passed the name of the person who validated the result.
- **Known identifiers were inconvenient and weak.** The user had to type and store the very data being protected, and they covered only the user, not the doctor or the lab staff.

A lab result has a stable structure. Personal data sits in the header, the patient block and the footer. The results table holds parameters, values, units, ranges, flags, method lines and test codes, and normally no personal data.

#### Considered options

1. **Word-level allowlist with dictionaries, plus the user's known identifiers.** Deterministic, but results depend on the dictionary, rules keep growing, and the user must provide their identifiers.
2. **Option 1 plus a kept laboratory header.** Leaked a validator's name in the spike. Fails G1.
3. **Option 1 with public name lists** (first names and surnames from the PESEL register). Protects everyone and needs no input, but the lists are large, collide with ordinary words (Cukier, Biały), and the dictionary is still needed.
4. **An NER model** (e.g. Presidio). Probabilistic and unproven for Polish; a missed name leaks.
5. **Zones: keep the results table, mask everything outside it except labelled date fields**, with a few denylist rules inside the table. No personal identifiers needed.

### No archive of original documents

The original document never leaves the user's device (see above). The system keeps the masked pages. The question is whether to offer an archive of originals anyway, uploaded separately.

An archive would serve two purposes:
- **Reprocessing** after a masking bug, e.g. a result that was masked by mistake.
- **Provenance:** proof of where every number came from.

Both are mostly covered without it. Every value is shown next to its place on the masked page, and extraction can be rerun from the masked pages. Only a masking bug needs the original, and the user keeps it (e-mail, the lab's portal, their disk) and can import it again.

Standard storage encryption protects against stolen disks, not against anyone with read access in Azure, including a compromised application.

#### Considered options

1. **Keep originals with storage encryption only.** The application and the subscription administrator can read every original. Weakens G1 and G5.
2. **Envelope encryption with the key in Key Vault.** Every decryption is logged, but the key lives in the same cloud as the data.
3. **Envelope encryption with an offline key pair.** Each file has its own data key, encrypted with the user's public key; the private key exists only offline. The cloud can write but never read. Needs a separate storage account, a write-only role, key rotation and regular restore tests.
4. **No archive.** Keep the masked pages only. The user keeps the original.

## Decision

### Mask in the browser, check again on the server

We choose option 6.

1. **The browser masks.** It renders each PDF page to PNG at 200 DPI (photos as they are), runs OCR, applies the zone rules (below) and its own leak check. Rendering to pixels drops scripts, metadata and hidden text, and burns the masks into the image.
2. **The user approves the masked pages** and can add mask boxes. Masking can be added, never removed.
3. **The original never leaves the device.** The browser sends one ZIP ([ADR-0005](0005-asynchronous-import-pipeline.md)) with:
   - the masked PNG pages,
   - the rectangles of the kept regions, without their text,
   - the SHA-256 of each masked page, computed after the user approved it,
   - the SHA-256 of the original, to recognise the same document again ([ADR-0006](0006-document-lifecycle-and-review.md)).
4. **The API validates without reading the content:** a stored ZIP, PNG only, known names, sizes, and each page's hash recomputed. A page that does not match the hash the user approved is rejected.
5. **The checker looks again before anything else.** It is the first step of the pipeline, and no page reaches a managed AI service without passing it.
   - **Shape check:** outside the kept rectangles, only white background or solid mask boxes. Any other ink (text, a signature, a barcode) blocks the document.
   - **OCR check:** Tesseract in memory, with the same zone rules. Outside the table only date fields may remain; in the table no valid PESEL, no long number and no line naming a person.
   - **Nothing personal is needed or kept.** The rules are patterns in code. Logs hold the verdict, the rule that fired and a count, never the text that was read.
6. **Blocked:** the pages are deleted and the user gets the suspicious regions (page and rectangle, no text). They see them on their own copy in the browser, add mask boxes and send again, or give up.
7. **The checker has no access to the AI services.** Its identity has no role on Document Intelligence or Azure OpenAI, and only its own containers and queues in Storage and Service Bus. Blocking its outbound network is not possible without extra paid networking ([ADR-0004](0004-serverless-hosting-and-operations.md)), so least privilege is the boundary.

### Zone-based masking: keep the results table, mask the rest

We choose option 5.

1. **Find the results table on each page.**
   - **Top:** the table header, a line with two or more table words such as "Badanie", "Wynik", "Jedn.", "Zakres". On a continuation page without a header, the first result row.
   - **Bottom:** the last result row, method line or line with an ICD-9 PL code. Following lines belong to the table while the gap stays small and the line is neither personal nor a date line.
   - **Result row:** a line with a value and a unit, a known parameter and a value, or a qualitative result ("ujemny", "dodatni"). It has no date and no personal label.
2. **In the table, everything is kept** except:
   - lines naming the patient or a person who ordered, performed, validated or signed the result ("Pacjent", "PESEL", "mgr", "dr", "Autoryzował");
   - valid PESEL numbers and numbers with 7 or more digits.
3. **Outside the table, only date fields are kept:** a date label, the date and time right after it, and nothing else on that line. Labels are matched as stems, so abbreviations ("Data rej.:") and words glued by OCR ("Datarej:") work. The date of birth is never a date field.
4. **No table found:** the page keeps only its date fields. The user sees at once that results are missing, and nothing personal leaks.
5. **Keep-only composition.** The output starts as a white page. Kept words are copied onto it; masked words become dark boxes. Stamps, signatures, logos and barcodes are not text, so they never reach the output.
6. **Leak check per zone.** A second OCR pass reads the masked image. Outside the table, any confidently read word that is not part of a date field blocks the document. In the table, a PESEL, a long number or a people line blocks it. Words that lie entirely on a mask box are ignored.
7. **The user reviews the masked pages before anything is sent,** and can accept them, give up, or draw extra mask boxes.
8. **The same rules run in the checker** (see above), with the same tests.

### No archive of original documents

We choose option 4.

1. **No original is stored or sent.** The system cannot archive one even by mistake.
2. **The SHA-256 of the original is stored** with every document. It recognises the same document imported again ([ADR-0006](0006-document-lifecycle-and-review.md)), and would let a future archive be filled with old originals and matched to existing documents.
3. **If an archive is ever needed, option 3 is the design**, added as one more step of the upload.

## Consequences

### Mask in the browser, check again on the server

- **Our Azure subscription never receives an original.** There is no quarantine, no quarantine key and no lifecycle for plaintext. The decision not to archive originals (below) follows from this.
- **The browser does more work and depends on the device.** A slow laptop needs up to about 30 s per photo page. Import is rare, so this is accepted.
- **OCR differs between devices**, so a rule that works on the server may fail in a browser. Rules are tested against OCR variants, and synthetic documents that reproduce real layouts with fictional data run in CI.
- **Known gaps from the spike, to fix in the implementation:** words are joined to the first matching row instead of the nearest; curved lines on photos split rows; the leak check reads dark mask boxes as letters (false Blocked). The OCR check must ignore words that lie entirely on a mask box.
- **A bare name inside the results table, without a label, passes both checks.** The user's review of the masked pages is the safeguard (zone rules, rule 7).
- **The UI framework must run OCR and PDF rendering in the browser** ([ADR-0002](0002-languages-dotnet-python-and-typescript.md)).

### Zone-based masking: keep the results table, mask the rest

- **No personal identifiers are needed anywhere.** The user types nothing, and nothing is stored.
- **Results do not depend on the parameter dictionary.** Unknown parameters and odd units in the table are kept. The dictionary serves trends and LOINC mapping ([ADR-0011](0011-lab-parameters-units-and-ranges.md)).
- **The table is trusted.** A bare name in a comment row inside the table would pass. Rule 2 and the user's review reduce this; it is the main residual risk.
- **The laboratory header is masked.** Identifying the lab is left to extraction and review.
- **A wrong table boundary** either loses results (the user sees it on review) or keeps more text (rule 2, the leak check and the review stand against it).
- **Layouts without a results table** (descriptions, discharge letters) lose their content. They are out of scope.

### No archive of original documents

- No archive storage, no key pair, no write-only role, no restore tests.
- Nothing of the original can leak from storage, backups or logs.
- Fixing a masking bug for an existing document needs the user to import the original again. This is deliberate.
- If the user loses their copy, the masked pages and the approved results remain; the original cannot be recovered from Baseline.
