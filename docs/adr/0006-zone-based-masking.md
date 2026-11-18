# 6. Zone-based masking: keep the results table, mask the rest

Date: 2026-11-18

## Status

Accepted. Amends steps 2, 4 and 6 of [ADR-0003](0003-mask-personal-data-before-ai.md). Where masking runs (browser or server) is decided separately, after the [browser sanitiser spike](../../spikes/browser-sanitiser/README.md).

## Context

ADR-0003 masks word by word. A word stays visible only if it is in an allowlist (parameter dictionary, units, numbers next to a parameter, labelled dates, lab names). A denylist of the user's known identifiers runs as a second layer, and the leak check uses both.

The [browser sanitiser spike](../../spikes/browser-sanitiser/README.md) applied this to real lab results and found four problems:

- **The dictionary decides whether results survive.** Every parameter, unit and OCR variant of a unit (`µIU/ml` read as `ulU/ml`, `pg/ml*` with a footnote marker) has to be listed. Anything missing is masked, and the result is lost.
- **Context rules grow without end.** Each new layout needed a new rule: method lines, ICD-9 PL codes, abbreviated date labels.
- **A trusted zone leaked a name.** One version kept the laboratory header above the first patient label. On a real document, the name of the person who validated the result was printed there. It passed, and the leak check did not catch it, because it trusted the same zone.
- **Known identifiers are inconvenient and weak.** The user has to type and store their own name, PESEL and address, which is exactly the data being protected. They only cover the user, not the doctor or lab staff, so they would not have caught that name.

A lab result has a stable structure. Personal data sits in the header, the patient block and the footer. The results table holds parameters, values, units, ranges, flags, method lines and test codes, and normally no personal data.

### Considered options

1. **Word-level allowlist with dictionaries, plus the user's known identifiers (ADR-0003).** Deterministic. However, results depend on the dictionary, the rules keep growing, and the user has to provide their identifiers.
2. **Option 1 plus a kept laboratory header zone.** Keeps the lab's name and address. Tried in the spike, where it leaked a validator's name.
3. **Option 1 with public name lists instead of known identifiers.** The PESEL register lists of first names and surnames are published on dane.gov.pl. They protect everyone and need no input, but they are large, collide with ordinary words (e.g. Cukier, Biały), and still need the parameter dictionary.
4. **In-house NER model** (e.g. Presidio). See ADR-0003: probabilistic and unproven for Polish. A missed name leaks.
5. **Zones: keep the results table, mask everything outside it except labelled date fields.** Has a few small denylist rules inside the table, and needs no personal identifiers.

## Decision

We choose option 5.

1. **Find the results table on each page.**
   - **Top:** the table header, i.e. a line with two or more table words such as "Badanie", "Wynik", "Jedn.", "Zakres". On a continuation page without a header, the top is the first result row instead.
   - **Bottom:** the last result row, method line or line with an ICD-9 PL code.
   - **Result row:** a line with a value and a unit, or with a known parameter and a value. It contains no date and no personal label.
2. **In the table, everything is kept** except:
   - lines naming the patient or a person who ordered, performed, validated or signed the result, e.g. "Pacjent", "PESEL", "mgr", "dr", "Autoryzował", "Zatwierdził";
   - valid PESEL numbers and numbers with 7 or more digits.
3. **Outside the table, only date fields are kept.**
   - A date field is a date label, the date and time right after it, and nothing else on that line. Examples: registration, collection, admission, analysis, release, authorisation, issue.
   - Labels are matched as stems, so abbreviations such as "Data rej.:" work.
   - The date of birth ("urodzenia", "ur.") is never a date field.
   - Date fields are kept above the table (registration, collection) and below it (admission, analysis and release per test).
4. **No table found:** the page keeps only its date fields. The user sees at once that results are missing, and no personal data leaks (fail-safe).
5. **Keep-only composition.** The output starts as a white page. Kept words are copied onto it. Masked words are drawn as dark boxes, so the page looks like a properly redacted document. Stamps, signatures, logos and barcodes are not text, so they never reach the output.
6. **Leak check per zone.** A second OCR pass reads the masked image and uses the table found on the original.
   - Outside the table, any confidently read word that is not part of a date field blocks the document.
   - In the table, a PESEL number, a long number or a people line blocks it.
7. **The user reviews the masked pages before anything is sent.** They see every page and can:
   - accept it,
   - reject the document,
   - draw extra mask boxes over anything that should not be sent (drag and drop).

   Extra boxes are burned into the pixels like the others. Masking can be added, never removed. The masked image is the only thing that leaves the masking step.

## Consequences

- **No personal identifiers are needed anywhere.** The user types nothing, and nothing is stored in the browser or in Key Vault. Question Q1 (who writes the known identifiers) is gone.
- **Results no longer depend on the parameter dictionary.** Unknown parameters, odd units and OCR variants in the table are kept. The dictionary is still used for LOINC mapping and trends, not for masking.
- **The rules are short and mostly structural.** They use small word lists for table headers, date labels, the birth label and people labels.
- **The table is trusted.** Personal data printed inside it without a label, e.g. a bare name in a comment row, would pass. Rule 2 and the user's review (rule 7) reduce this risk; it is the main residual risk of this design.
- **The laboratory header and the lab's address are masked.** The lab's name often appears again in the date table below the results, where it is masked too. Identifying the lab (e.g. by a lab code) is left to extraction and review.
- **A wrong table boundary has two possible outcomes.** A table found too narrow loses results, which the user sees on review. A table found too wide keeps more text, which rule 2, the leak check and the review stand against.
- **Layouts without a results table** (descriptions, discharge letters) lose all their content. They are out of scope for now.
