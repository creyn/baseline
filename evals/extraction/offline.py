"""The offline run: every synthetic document through the real core, with fake AI services.

- The "layout" is built from the description: one line per section title, date, result row
  and method, every token a word with a box. It is not the rendered page; the live run
  covers real rendering, OCR and models.
- The "LLM" answers from the truth, naming the ids of the words it put on the page.

So the offline run tests our code only: batching, the word check, dates, flags, the date
for trends, the text contract and the scoring. Every metric must be 100%.
Standard library and jsonschema only.
"""
import json
import re

from common import describe, kind, local
from extractor import core
from extractor.layout import lines
from extractor.pages import Page

_LINE_H = 0.012
_PAGE = re.compile(r'^## Page (\d+)$', re.M)


class SyntheticPage:
    """Words of one page, with a record of which words hold each field of each result."""

    def __init__(self):
        self.words, self.y = [], 0.05

    def line(self, *cells):
        """cells: (x, text, key) — key names the field the words belong to, or None."""
        placed = {}
        for x, text, key in cells:
            for token in (text or '').split():
                w = {'text': token, 'box': {'x': round(x, 4), 'y': round(self.y, 4), 'w': 0.04, 'h': _LINE_H},
                     'confidence': 0.99}
                self.words.append(w)
                placed.setdefault(key, []).append(w)
                x += 0.045
        self.y += 0.02
        return placed


def build(doc):
    """pages_words for FakeLayout, and for each expected result the words of its fields."""
    pages, targets = [], []
    for page in doc['pages']:
        sp = SyntheticPage()
        for d in doc['dates']:
            sp.line((0.05, f'{d["label"]}: {d["value"]}', None))
        for section in page['sections']:
            if section.get('title'):
                sp.line((0.05, section['title'], None))
            for d in section.get('dates', []):
                sp.line((0.55, f'{d["label"]}: {d["value"]}', None))
            for r in section['results']:
                if r.get('min') is not None:
                    range_cells = [(0.62, r['min'], 'range'), (0.70, r['max'], 'range')]
                else:
                    range_cells = [(0.62, r.get('range'), 'range')]
                if r.get('range_lines') and r.get('min') is None:
                    range_cells = []
                placed = sp.line((0.05, r['name'], 'name'), (0.35, r['value'], 'value'), (0.45, r['unit'], 'unit'),
                                 *range_cells, (0.90, r.get('flag'), None))
                if not range_cells:
                    for text in r['range_lines']:  # printed under the result, every line
                        placed.setdefault('range', []).extend(sp.line((0.62, text, 'range')).get('range', []))
                targets.append({'page': len(pages) + 1, 'r': r, 'section': section, 'words': placed})
            if section.get('method'):
                targets_method = sp.line((0.05, section['method'], 'fragment'))
                targets.append({'page': len(pages) + 1, 'fragment': targets_method['fragment']})
        sp.line((0.05, f'Data wydruku: {doc["printed"]}', None))
        pages.append(sp.words)
    return pages, targets


class FakeLayout:
    def __init__(self, pages_words):
        self.pages_words = pages_words

    def analyze(self, pages):
        return self.pages_words


class FakeLlm:
    """Answers each batch from the truth, with the ids the core gave to the words."""

    def __init__(self, doc, pages_words, targets):
        self.doc, self.targets = doc, targets
        self.ids = {}
        for index, words in enumerate(pages_words, 1):
            ordered = [w for line in lines(words) for w in line]
            for n, w in enumerate(ordered, 1):
                self.ids[id(w)] = f'p{index}w{n}'
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        pages = {int(p) for p in _PAGE.findall(messages[1]['content'])}
        results, fragments = [], []
        for t in self.targets:
            if t['page'] not in pages:
                continue
            if 'fragment' in t:
                fragments.append({'page': t['page'], 'words': self._ids(t['fragment'])})
                continue
            r, words = t['r'], t['words']
            has_range = bool(words.get('range'))
            range_text = ' '.join(w['text'] for w in words.get('range', [])) if has_range else None
            bounded = r.get('min') is not None
            results.append({
                'page': t['page'], 'name': r['name'], 'nameWords': self._ids(words['name']),
                'value': r['value'], 'valueWords': self._ids(words['value']),
                'unit': r['unit'] or None, 'unitWords': self._ids(words.get('unit', [])) if r['unit'] else [],
                'range': range_text, 'rangeWords': self._ids(words.get('range', [])),
                'rangeLow': r.get('min'), 'rangeHigh': r.get('max'),
                'rangeKind': 'interval' if bounded else ('text' if has_range else 'none'),
                'flagPrinted': r.get('flag'), 'icd9': r.get('icd9') or t['section'].get('icd9'), 'material': r.get('material'),
                'condition': r.get('condition'), 'method': r.get('method') or t['section'].get('method'), 'analyser': None,
                'dates': [_date(d) for d in t['section'].get('dates', [])], 'suggestedParameter': None,
            })
        document_dates = [_date(d) for d in self.doc['dates']] + [_date({'label': 'Data wydruku', 'value': self.doc['printed']})]
        answer = {'results': results, 'documentDates': document_dates, 'fragments': fragments}
        return json.loads(json.dumps(answer)), {'input': 0, 'output': 0}

    def _ids(self, words):
        return [self.ids[id(w)] for w in words]


def _date(d):
    return {'label': d['label'], 'text': d['value'], 'local': local(d['value']), 'kind': kind(d['label'])}


def run(doc):
    """(blob, llm calls) for one description."""
    pages_words, targets = build(doc)
    pages = [Page(i, f'{i:064x}', b'') for i in range(1, len(doc['pages']) + 1)]
    llm = FakeLlm(doc, pages_words, targets)
    blob, _ = core.extract(pages, FakeLayout(pages_words), llm, doc_id='019ab3c4-5d6e-7f80-9a1b-2c3d4e5f6a7b',
                           ver_id='019ab3c4-6e7f-7081-8b2c-3d4e5f6a7b8c', model='offline')
    return blob, llm.calls


def expected(doc):
    return describe.expected_extraction(doc)
