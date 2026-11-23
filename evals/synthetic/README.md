# Synthetic lab results

Fictional documents for testing masking, the second check, extraction and their evals. Every person, laboratory and number is invented: the patient is always Jan Testowy, with the public example PESEL from [tools/privacy/allowlist.txt](../../tools/privacy/allowlist.txt).

The layouts follow the structure of real laboratory results (column order, date labels, where blocks sit), never their names or data. The spec is [openspec/specs/synthetic-documents](../../openspec/specs/synthetic-documents/spec.md); the change that added it is in the OpenSpec archive.

## How it works

- **[documents/](documents/)**: one JSON description per document. It is also the ground truth: the results extraction must return, the strings masking must remove, and those it must keep.
- **[generate.py](generate.py)** renders each description in its layout (A, B or C) and its forms:
  - `text`: a PDF with real text;
  - `scan`: an image PDF, slightly turned, with noise;
  - `photo`: JPEG pages with perspective, shadow and blur.

  It also writes `truth.json` next to them: the expected results, what masking must remove (text, and the boxes of the barcode, stamp and signature) and what it must keep. The same descriptions give byte-identical files in the same environment; `sha256.json` records the library versions and the font.
- **[describe.py](describe.py)** reads the descriptions and derives the truth. The generator and the evals both use it.

PDFs and photos are never committed ([AGENTS.md](../../AGENTS.md)). CI generates them on every pull request (artifact `synthetic-documents`), and GitHub Pages publishes them under `synthetic/`.

## Adding a document

1. Copy a description in `documents/` and change it. The file name is the id.
2. Use only fictional data. Add the traps it covers to `traps`.
3. Push. CI checks the description, generates the files and checks that every value and trap is in them.

## Running

```sh
python3 -m unittest discover -s evals/synthetic   # descriptions: standard library only
pip install -r evals/synthetic/requirements.txt   # then the generator and its tests (CI does this)
python3 evals/synthetic/generate.py
```
