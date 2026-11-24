"""Fictional pages and fake services for the tests. No real data: the results are from
the synthetic document c3 (evals/synthetic/documents), with Jan Testowy masked out."""
import hashlib
import io
import json
import zipfile

from extractor.pages import Page


def page(index, tag):
    png = f'fake png {tag}'.encode()
    return Page(index, hashlib.sha256(png).hexdigest(), png)


def clean_zip(pages, version='1.0'):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_STORED) as z:
        z.writestr('manifest.json', json.dumps({'schemaVersion': version, 'order': [p.sha256 for p in pages]}))
        for p in pages:
            z.writestr(f'pages/{p.sha256}.png', p.png)
    return buffer.getvalue()


def w(text, x, y, width=0.05):
    return {'text': text, 'box': {'x': x, 'y': y, 'w': width, 'h': 0.012}, 'confidence': 0.99}


# One results page: a date line, two result rows and a method line.
IRON_PAGE = [
    w('Data/godz.', 0.08, 0.20, 0.08), w('pobrania', 0.17, 0.20, 0.07), w('2026-04-10', 0.25, 0.20, 0.08), w('07:25', 0.34, 0.20),
    w('Ferrytyna', 0.08, 0.40, 0.10), w('18', 0.40, 0.40, 0.03), w('ng/ml*', 0.50, 0.40, 0.06),
    w('30', 0.62, 0.40, 0.03), w('-', 0.655, 0.40, 0.01), w('400', 0.67, 0.40, 0.04),
    w('Żelazo', 0.08, 0.46, 0.07), w('64', 0.40, 0.46, 0.03), w('µg/dl*', 0.50, 0.46, 0.06),
    w('65', 0.62, 0.46, 0.03), w('-', 0.655, 0.46, 0.01), w('175', 0.67, 0.46, 0.04), w('L', 0.75, 0.46, 0.01),
    w('Metoda', 0.08, 0.50, 0.06), w('ECLIA', 0.15, 0.50, 0.05),
]
# Reading order: line 0.20 -> w1..w4, line 0.40 -> w5..w10, line 0.46 -> w11..w17, line 0.50 -> w18..w19


def result(page_no, name, value, unit, low, high, flag, ids):
    p = f'p{page_no}w'
    return {
        'page': page_no, 'name': name, 'nameWords': [p + str(ids[0])],
        'value': value, 'valueWords': [p + str(ids[1])],
        'unit': unit, 'unitWords': [p + str(ids[2])],
        'range': f'{low} - {high}', 'rangeWords': [p + str(i) for i in ids[3]],
        'rangeLow': low, 'rangeHigh': high, 'rangeKind': 'interval', 'flagPrinted': flag,
        'icd9': None, 'material': 'surowica', 'condition': None, 'method': None, 'analyser': None,
        'dates': [], 'suggestedParameter': None,
    }


def iron_answer(page_no=1, ferritin='18'):
    return {
        'results': [result(page_no, 'Ferrytyna', ferritin, 'ng/ml', '30', '400', None, (5, 6, 7, (8, 9, 10))),
                    result(page_no, 'Żelazo', '64', 'µg/dl', '65', '175', 'L', (11, 12, 13, (14, 15, 16)))],
        'documentDates': [{'label': 'Data/godz. pobrania', 'text': '2026-04-10 07:25',
                           'local': '2026-04-10T07:25', 'kind': 'collected'}],
        'fragments': [{'page': page_no, 'words': [f'p{page_no}w18', f'p{page_no}w19']}],
    }


EMPTY = {'results': [], 'documentDates': [], 'fragments': []}


class FakeLayout:
    def __init__(self, pages_words):
        self.pages_words = pages_words
        self.calls = 0

    def analyze(self, pages):
        self.calls += 1
        return self.pages_words[:len(pages)]


class FakeLlm:
    """Answers from a list, one per call; records the messages it got."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []
        self.model = None

    def complete(self, messages):
        self.calls.append(messages)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return json.loads(json.dumps(answer)), {'input': 100, 'output': 50, **({'model': self.model} if self.model else {})}


class FakeStore:
    def __init__(self, clean=None, text=None):
        self.clean, self.text, self.writes = clean, text, 0

    def text_exists(self, ids):
        return self.text is not None

    def read_clean(self, ids):
        return self.clean

    def write_text_if_absent(self, ids, data):
        self.writes += 1
        if self.text is not None:
            return False
        self.text = data
        return True


class FakeStatus:
    def __init__(self, fail=None):
        self.sent, self.fail = [], fail

    def send(self, msg):
        if self.fail:
            raise self.fail
        self.sent.append(msg)
