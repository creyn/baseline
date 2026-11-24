# Extraction evals

Measure the extractor ([services/extractor](../../services/extractor/README.md)) on the fictional documents of [evals/synthetic](../synthetic/README.md), against their truth. The rules are in the OpenSpec change [add-extraction](../../openspec/changes/add-extraction/design.md), the targets in [ADR-0007](../../docs/adr/0007-extraction-with-document-intelligence-and-an-llm.md) and when they run in [ADR-0017](../../docs/adr/0017-catching-changes-on-the-ai-services.md).

| Metric | Target |
|---|---|
| Values and units exactly right | 100% |
| Names, ranges and flags as printed | 95% |
| Missing and extra results, material, condition, method | reported |

- **Offline** ([offline.py](offline.py), [test_offline.py](test_offline.py)): every document through the real core, with a layout built from the description and a fake LLM that answers from the truth. It tests our code only; every metric must be 100%. Runs on every pull request and anywhere with jsonschema.
- **Live** ([live.py](live.py), [the workflow](../../.github/workflows/evals.yml)): every form (text, scan, photo) through Document Intelligence and the LLM. Runs on pull requests that change the extractor, its contracts or the evals, every Monday, and on demand. The job summary has a table per document and form, and `report.json` is kept as an artifact for 30 days. Skipped until the Azure variables are set.
- **Scoring** ([score.py](score.py)): an extracted result matches an expected one on the same page with the same printed name, or else the same value and unit (the name then counts as wrong).

```sh
python3 -m unittest discover -s evals/extraction
```
