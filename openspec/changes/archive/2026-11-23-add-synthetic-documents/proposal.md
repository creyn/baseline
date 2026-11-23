# Proposal

## Why

Masking, the second check, extraction and their evals need lab results to work on. Real results must never enter the repository ([AGENTS.md](../../../../AGENTS.md)). We need fictional documents that look like real ones: the same table layouts, the same date labels, the same traps for masking, in the same forms (a text PDF, a scan, a phone photo).

## What Changes

- `evals/synthetic/documents/`: one JSON description per fictional document. The description is also the ground truth: the results extraction must return, and the personal data masking must remove.
- `evals/synthetic/generate.py`: renders each description in three layouts modelled on real laboratories (the layouts only, never their names or data), as a text PDF, a scan and a phone photo. The output is the same, byte for byte, for the same description.
- Tests: a check of the descriptions that runs anywhere with Python, and a check of the generated files that runs in CI.
- CI builds the documents on every pull request. GitHub Pages publishes them next to the masking spike.
- `AGENTS.md`: no PDF, scan or photo of a document is ever committed, not even a synthetic one.

## Capabilities

### New Capabilities

- `synthetic-documents`

### Modified Capabilities

None.

## Impact

- New files under `evals/synthetic/` and in the two workflows; one rule in `AGENTS.md` and `.gitignore`.
- New dependencies in CI only: reportlab, Pillow and pypdfium2, with pinned versions. Nothing is installed on the development server.
