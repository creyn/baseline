# Design

## Context

The owner's real results show three families of layouts. Each has a block of personal data and the laboratory's header above the table, a results table, date fields in different places, and a footer with staff names. Masking keeps the table and the date fields ([ADR-0003](../../../../docs/adr/0003-masking-in-the-browser-and-a-second-check.md)), and extraction reads the masked table ([ADR-0007](../../../../docs/adr/0007-extraction-with-document-intelligence-and-an-llm.md)).

## Goals / Non-Goals

**Goals:**
- Fictional documents in the three layouts, in three forms, with the traps that matter for masking and extraction.
- One description per document that is also its ground truth.
- The same files on every run, so a change in an eval result means a change in our code or the model.

**Non-Goals:**
- Pixel-perfect copies of any laboratory's document.
- Real laboratory names, addresses, logos or staff.

## Decisions

- **Descriptions are JSON, files are generated.** JSON is text: the privacy scan reads it and a pull request shows every change. A PDF or an image is binary; the scan cannot read it, and a real file could slip in among synthetic ones. So `.gitignore` keeps every PDF and photo out, and CI generates them.
- **Three layouts, modelled on the structure only:**
  - **A:** a header block with the patient's data on the left, a table with the columns "Badanie, Wynik, Jedn., MIN, MAX, FLAGA", each test as a heading with its ICD-9 code, the collection and analysis dates at the right inside the table, a method line and a note on the material below the results.
  - **B:** a centred header, the date fields with labels such as "Data i godz. rejestracji" in the middle of the page, a table with the columns "ICD9, Nazwa, Wynik, j.m., Wartość referencyjna/decyzyjna, Procedura/Instrukcja nr", a profile line, and reference ranges as several lines of text on the right.
  - **C:** the patient block with "Data rejestracji" and "Data/godz. pobrania" on the left, a table with the columns "Badanie, Wynik, Jedn., Zakres referencyjny, LIW", a method line under each test, and an "Informacje dodatkowe" block with the dates of each sample. Units carry the laboratory's footnote marker "*"; the truth has the unit without it.
  - **Every layout** has a footer with the staff, a stamp, a signature and "Data wydruku", and a barcode of the order number at the top.
- **Fictional data only:** the patient is Jan Testowy with the public example PESEL from `tools/privacy/allowlist.txt`; laboratories, staff and addresses are invented ("Laboratorium Alfa", "ul. Przykładowa 1").
- **Forms:**
  - **text:** a PDF with real text, the way laboratories send results.
  - **scan:** each page rasterised at 200 DPI, turned by up to 1°, with noise and a grey background, saved as an image PDF.
  - **photo:** each page as a JPEG with perspective, a shadow and slight blur, like a printout photographed on a desk.
- **Deterministic output:** reportlab runs in invariant mode (fixed dates and identifiers in the PDF), randomness comes from a seed derived from the document id, and the font is DejaVu Sans, which has every Polish letter. Files are byte-identical within one environment: the same library versions and the same font file. `sha256.json` records both, so a change of the CI image shows up as a changed environment, not as a mystery.
- **The ground truth** is read from the description:
  - every result with its name as printed, value, unit, range as printed, the laboratory's flag, the flag code must compute (`computed_flag`, different where the description says so), ICD-9 code, material, condition, method and dates;
  - the strings that must be gone after masking (the patient, staff, numbers), anywhere on the page;
  - the strings that must stay (values, units, ranges, date fields including "Data wydruku", never the date of birth);
  - the barcode, stamp and signature of each page, with their boxes, which masking must remove although they are not text.
- **Known gaps are data, not exceptions:** a line that ADR-0003 accepts as a residual risk (a bare name in a comment inside the table) is listed in `known_gaps`. Only inside that line may the name survive; everywhere else it must still be removed.

## Risks / Trade-offs

- Synthetic layouts are cleaner than real paper. The scan and photo forms add noise, and evals on real documents stay a manual step for the owner, outside the repository.
- reportlab and Pillow change their output between versions, so versions are pinned. An upgrade is a pull request that may change every generated file.
