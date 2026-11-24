"""The live run: every form of every synthetic document through Document Intelligence and
the LLM, scored against the truth. Writes report.json and a Markdown table; exits 1 when a
target is missed (ADR-0007). Never touches storage or queues (ADR-0004).

Usage: python3 evals/extraction/live.py --generated DIR --out DIR
Settings: DOCUMENT_INTELLIGENCE_ENDPOINT, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT,
AZURE_OPENAI_API_VERSION (optional). Sign-in: the Azure CLI session of the workflow (OIDC).

The documents are fictional and unmasked: the header holds the invented patient. Production
pages are masked first. How much that changes the results is to check, once masking runs on
the server side and the evals can mask the pages first.
"""
import argparse
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import score  # noqa: E402
from extractor import core  # noqa: E402
from extractor.pages import Page  # noqa: E402

RENDER_DPI = 200


def pages_of(folder, form, n_pages):
    """The PNG pages of one form, as the browser would send them."""
    import hashlib

    import pypdfium2
    from PIL import Image
    images = []
    if form in ('text', 'scan'):
        pdf = pypdfium2.PdfDocument(os.path.join(folder, f'{form}.pdf'))
        try:
            images = [pdf[i].render(scale=RENDER_DPI / 72).to_pil() for i in range(len(pdf))]
        finally:
            pdf.close()
    else:
        images = [Image.open(os.path.join(folder, f'photo-{i}.jpg')) for i in range(1, n_pages + 1)]
    pages = []
    for i, image in enumerate(images, 1):
        buffer = io.BytesIO()
        image.convert('RGB').save(buffer, format='PNG')
        png = buffer.getvalue()
        pages.append(Page(i, hashlib.sha256(png).hexdigest(), png))
    return pages


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--generated', required=True, help='the output folder of evals/synthetic/generate.py')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    from extractor.azure_clients import AzureOpenAILlm, DocumentIntelligenceLayout
    env = os.environ
    layout = DocumentIntelligenceLayout(env['DOCUMENT_INTELLIGENCE_ENDPOINT'])
    llm = AzureOpenAILlm(env['AZURE_OPENAI_ENDPOINT'], env['AZURE_OPENAI_DEPLOYMENT'],
                         env.get('AZURE_OPENAI_API_VERSION') or '2024-10-21')
    rows, scores, models = [], [], set()
    for doc in common.documents():
        expected = common.describe.expected_extraction(doc)
        for form in doc['forms']:
            started = time.monotonic()
            pages = pages_of(os.path.join(args.generated, doc['id']), form, len(doc['pages']))
            outcome, results, usage = 'ok', [], {}
            try:
                blob, usage = core.extract(pages, layout, llm, doc_id='019ab3c4-5d6e-7f80-9a1b-2c3d4e5f6a7b',
                                           ver_id='019ab3c4-6e7f-7081-8b2c-3d4e5f6a7b8c',
                                           model=env['AZURE_OPENAI_DEPLOYMENT'])
                results = blob['results']
                models.add(blob['extraction']['model'])
            except core.InvalidAnswer as e:
                outcome = f'extract_invalid ({len(e.problems)} problems)'
            except core.NoResults:
                outcome = 'no_results'
            except Exception as e:  # a service error ends this document, not the run; the type only
                outcome = f'error ({type(e).__name__})'
            s = score.score(expected, results)
            scores.append(s)
            rows.append({'document': doc['id'], 'form': form, 'pages': len(pages), 'outcome': outcome,
                         'seconds': round(time.monotonic() - started, 1), 'tokens': usage, **s})
    summary = score.total(scores)
    failed = score.failures(summary)
    os.makedirs(args.out, exist_ok=True)
    report = {'models': sorted(models), 'summary': summary, 'failures': failed, 'runs': rows}
    with open(os.path.join(args.out, 'report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(os.path.join(args.out, 'summary.md'), 'w', encoding='utf-8') as f:
        f.write(markdown(report))
    print(markdown(report))
    return 1 if failed else 0


def markdown(report):
    pct = lambda v: f'{100 * v:.1f}%'  # noqa: E731
    s = report['summary']
    out = ['## Extraction evals (live)', '',
           f'Models: {", ".join(report["models"]) or "none answered"}', '',
           '| Metric | Result | Target |', '|---|---|---|']
    for k, t in score.TARGETS.items():
        out.append(f'| {k} | {pct(s["ratios"][k])} | {pct(t)} |')
    out += [f'| missing / extra | {s["missing"]} / {s["extra"]} of {s["expected"]} | reported |', '',
            '| Document | Form | Outcome | Values and units | Names | Ranges | Flags | Missing | Extra |',
            '|---|---|---|---|---|---|---|---|---|']
    for r in report['runs']:
        q = r['ratios']
        out.append(f'| {r["document"]} | {r["form"]} | {r["outcome"]} | {pct(q["values_units"])} | {pct(q["names"])} '
                   f'| {pct(q["ranges"])} | {pct(q["flags"])} | {r["missing"]} | {r["extra"]} |')
    out += ['', 'Failed: ' + ('; '.join(report['failures']) if report['failures'] else 'none'), '']
    return '\n'.join(out)


if __name__ == '__main__':
    sys.exit(main())
