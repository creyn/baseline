# Spec Delta

## Purpose

Fictional lab result documents, generated from text descriptions, for testing masking, the second check, extraction and their evals without any real data.

## ADDED Requirements

### Requirement: Descriptions are the source and the ground truth

Every synthetic document SHALL be described by one JSON file in `evals/synthetic/documents/`. The description MUST list every result with its name as printed, value, unit, range, flag and ICD-9 code, the strings masking must remove, and the strings masking must keep.

#### Scenario: A valid description

- **WHEN** the description tests run
- **THEN** every description has a unique id, a known layout, at least one result, at least one form, and only fictional personal data

#### Scenario: Personal data is fictional

- **WHEN** a description contains a PESEL number
- **THEN** it is the public example number from `tools/privacy/allowlist.txt`

### Requirement: No document files in the repository

The repository MUST NOT contain a PDF, a scan or a photo of a document, synthetic or real. Generated files SHALL exist only in CI, in its artifacts and on GitHub Pages.

#### Scenario: A generated file in the working tree

- **WHEN** the generator writes to `evals/synthetic/out/`
- **THEN** Git ignores the folder and every PDF and JPEG in it

### Requirement: Three layouts and three forms

The generator SHALL render each description in its layout (A, B or C) and in each of its forms: `text` (a PDF with real text), `scan` (an image PDF with a slight rotation and noise) and `photo` (JPEG pages with perspective, shadow and blur).

#### Scenario: The rendered page holds the whole truth

- **WHEN** any description is rendered (the scan and the photo are made from the same page)
- **THEN** the page text contains every name, value, unit, range and date field of the description, and every string masking must remove

#### Scenario: Marks that are not text

- **WHEN** a page is rendered
- **THEN** its truth lists the box of its barcode, stamp and signature

#### Scenario: Several pages

- **WHEN** a description has two pages
- **THEN** the PDF has two pages, and the second page has no table header when the description says so

### Requirement: The same files on every run

Generating the same description twice MUST give byte-identical files.

#### Scenario: Two runs

- **WHEN** the generator runs twice on the same descriptions
- **THEN** every file has the same SHA-256 in both runs

### Requirement: Traps for masking and extraction

The set of descriptions SHALL include, across its documents:
- the patient's name, PESEL, address and date of birth outside the table;
- a staff line ("Autoryzował", "dr", "mgr") and a number of 11 digits inside the table;
- a name in a comment inside the table, marked as a known gap of ADR-0003;
- a continuation page without a table header;
- the same parameter in two units, a measurement condition (fasting, after a glucose load), qualitative results, ranges given as "<" or as text, and a laboratory flag that disagrees with the range.

#### Scenario: Coverage of the traps

- **WHEN** the description tests run
- **THEN** each trap above appears in at least one description
