# 4. Zone-based masking: keep the results table, mask the rest

Date: 2026-11-22

## Status

Proposed

## Context

Masking runs in the browser and again in the checker ([ADR-0003](0003-mask-in-the-browser-check-again-on-the-server.md)). It needs rules that keep every result and remove every person.

The first approach masked word by word: a word stayed visible only if it was in an allowlist (parameter dictionary, units, labelled dates, lab names), with a denylist of the user's known identifiers as a second layer. The browser sanitiser spike found four problems with it:
- **The dictionary decided whether results survived.** Every parameter, unit and OCR variant of a unit (`µIU/ml` read as `ulU/ml`) had to be listed. Anything missing was masked and the result was lost.
- **Context rules grew without end.** Each new layout needed a new rule.
- **A trusted zone leaked a name.** A version that kept the laboratory header passed the name of the person who validated the result.
- **Known identifiers were inconvenient and weak.** The user had to type and store the very data being protected, and they covered only the user, not the doctor or the lab staff.

A lab result has a stable structure. Personal data sits in the header, the patient block and the footer. The results table holds parameters, values, units, ranges, flags, method lines and test codes, and normally no personal data.

### Considered options

1. **Word-level allowlist with dictionaries, plus the user's known identifiers.** Deterministic, but results depend on the dictionary, rules keep growing, and the user must provide their identifiers.
2. **Option 1 plus a kept laboratory header.** Leaked a validator's name in the spike. Fails G1.
3. **Option 1 with public name lists** (first names and surnames from the PESEL register). Protects everyone and needs no input, but the lists are large, collide with ordinary words (Cukier, Biały), and the dictionary is still needed.
4. **An NER model** (e.g. Presidio). Probabilistic and unproven for Polish; a missed name leaks.
5. **Zones: keep the results table, mask everything outside it except labelled date fields**, with a few denylist rules inside the table. No personal identifiers needed.

## Decision

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
8. **The same rules run in the checker** ([ADR-0003](0003-mask-in-the-browser-check-again-on-the-server.md)), with the same tests.

## Consequences

- **No personal identifiers are needed anywhere.** The user types nothing, and nothing is stored.
- **Results do not depend on the parameter dictionary.** Unknown parameters and odd units in the table are kept. The dictionary serves trends and LOINC mapping ([ADR-0017](0017-parameter-dictionary.md)).
- **The table is trusted.** A bare name in a comment row inside the table would pass. Rule 2 and the user's review reduce this; it is the main residual risk.
- **The laboratory header is masked.** Identifying the lab is left to extraction and review.
- **A wrong table boundary** either loses results (the user sees it on review) or keeps more text (rule 2, the leak check and the review stand against it).
- **Layouts without a results table** (descriptions, discharge letters) lose their content. They are out of scope.
