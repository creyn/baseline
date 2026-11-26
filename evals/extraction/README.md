# Extraction evals

Measure the extractor ([services/extractor](../../services/extractor/README.md)) on the fictional documents of [evals/synthetic](../synthetic/README.md), against their truth. The rules are in the spec [extraction](../../openspec/specs/extraction/spec.md) and the design of the archived change [add-extraction](../../openspec/changes/archive/2026-11-26-add-extraction/design.md), the targets in [ADR-0007](../../docs/adr/0007-extraction-with-document-intelligence-and-an-llm.md) and when they run in [ADR-0017](../../docs/adr/0017-catching-changes-on-the-ai-services.md).

| Metric | Target |
|---|---|
| Values and units exactly right, over the results read and verified; a wrong one marked `lowConfidence` counts as flagged, not wrong ([ADR-0018](../../docs/adr/0018-unread-results-and-low-confidence-words.md)) | 100% |
| Names, ranges and flags as printed, over the same | 95% |
| Expected results read and verified | 90% (starting value) |
| Every document ends in a `text` blob | all |
| Not returned, unread (for review), extra and flagged results, material, condition, method, dates | reported |

- **Offline** ([offline.py](offline.py), [test_offline.py](test_offline.py)): every document through the real core, with a layout built from the description and a fake LLM that answers from the truth. It tests our code only: word numbering, the word check, the contract, dates, flags, the date for trends, batching and the scoring. It cannot find a wrong name, value or range, because the fake answers from the same truth the scorer compares with; that is the live run's job. Every metric must be 100%. Runs on every pull request and anywhere with jsonschema.
- **Live** ([live.py](live.py), [the workflow](../../.github/workflows/evals.yml)): every form (text, scan, photo) through Document Intelligence and the LLM. Runs on pull requests that change the extractor, its contracts or the evals, every Monday, and on demand. The job summary has a table per document and form, and `report.json` is kept as an artifact for 30 days. Skipped until the Azure variables are set.
- **What went to the AI services and back:** every live run in the workflow also writes `dump/<document>/<form>/` into the artifact: `layout.json` (the words and boxes from Document Intelligence), `call-N-request.json` (the messages sent to the model, with the page text), `call-N-answer.json` (the raw answer, the parsed answer and the token usage) and `text-blob.json`. This is for the fictional documents only. The extractor itself never logs prompts or answers.
- **Scoring** ([score.py](score.py)): an extracted result matches an expected one on the same page with the same printed name, or else the same value and unit (the name then counts as wrong).

```sh
python3 -m unittest discover -s evals/extraction
```

### Running the live evals by hand

From any machine with Python 3.12, signed in with `az login` as a user who has the role "Cognitive Services User" on both AI resources (Owner of the subscription is not enough: it manages resources but cannot call them):

```sh
python3 -m pip install -r evals/synthetic/requirements.txt -r services/extractor/requirements.txt
python3 evals/synthetic/generate.py --out generated --only c3-iron-traps-in-table      # one document, or omit --only
export DOCUMENT_INTELLIGENCE_ENDPOINT=https://<name>.cognitiveservices.azure.com/
export AZURE_OPENAI_ENDPOINT=https://<name>.openai.azure.com/
export AZURE_OPENAI_DEPLOYMENT=gpt-5.4-mini
python3 evals/extraction/live.py --generated generated --out report --only c3-iron-traps-in-table --forms text --dump dump
```

`--only` takes a document id from [evals/synthetic/documents](../synthetic/documents), `--forms` any of `text,scan,photo`.
