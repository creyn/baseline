"""Pages in, the text blob out (ADR-0007). Standard library and jsonschema only.

The LLM proposes; code checks every field against the words it names, adds the time
zones, maps the flags and picks the date for trends. Nothing here logs page content.
"""
import os
import re
from datetime import datetime, timezone

from jsonschema import Draft202012Validator

from . import PROMPT_VERSION, VERSION
from .contracts import schema, text_checks
from .dates import DEFAULT_ZONE, BadDate, to_instant
from .layout import number, page_text, union

BATCH_PAGES = 5
_PROMPT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prompts', f'{PROMPT_VERSION}.md')

_TEXT_SCHEMA = schema('text.v1')
_BLOB = Draft202012Validator(_TEXT_SCHEMA)


def _definition(name):
    return Draft202012Validator({'$schema': _TEXT_SCHEMA['$schema'], '$defs': _TEXT_SCHEMA['$defs'],
                                 '$ref': f'#/$defs/{name}'})


_RESULT = _definition('result')
_DATE = _definition('date')


class InvalidAnswer(Exception):
    """A batch stayed invalid after one retry. `problems` never quote page text."""

    def __init__(self, problems):
        super().__init__(f'{len(problems)} problems')
        self.problems = problems


class NoResults(Exception):
    """Every batch was valid and none had a result: not a lab result."""


def prompt():
    with open(_PROMPT_FILE, encoding='utf-8') as f:
        return f.read()


def messages(page_texts, errors=None):
    """The chat messages for one batch; on a retry, the problems of the first answer."""
    user = '\n\n'.join(page_texts)
    if errors:
        user += '\n\n## Problems in your previous answer\nFix every one and answer again in full.\n' + '\n'.join(f'- {e}' for e in errors)
    return [{'role': 'system', 'content': prompt()}, {'role': 'user', 'content': user}]


def batches(items, size=BATCH_PAGES):
    return [items[i:i + size] for i in range(0, len(items), size)]


def extract(pages, layout, llm, *, doc_id, ver_id, model, zone=DEFAULT_ZONE, now=None, batch_pages=BATCH_PAGES):
    """pages: [Page]; layout.analyze(pages) -> [[word]] per page; llm.complete(messages) -> answer dict.

    Returns (text blob, usage) or raises InvalidAnswer or NoResults. Transient errors of
    the services propagate unchanged.
    """
    numbered = number(layout.analyze(pages))
    blob_pages = [{'index': p.index, 'sha256': p.sha256, 'words': words} for p, words in zip(pages, numbered)]
    words = {w['id']: w for p in blob_pages for w in p['words']}
    usage = {'input': 0, 'output': 0, 'calls': 0}
    results, document_dates, fragments = [], [], []
    for batch in batches(blob_pages, batch_pages):
        texts = [page_text(p['index'], p['words']) for p in batch]
        indexes = {p['index'] for p in batch}
        errors = None
        for attempt in (1, 2):
            answer, used = llm.complete(messages(texts, errors))
            for k in ('input', 'output'):
                usage[k] += used.get(k, 0)
            if used.get('model'):
                usage['model'] = used['model']  # the version that answered, not only the deployment name
            usage['calls'] += 1
            part, errors = convert(answer, words, indexes, zone)
            if not errors:
                break
        if errors:
            raise InvalidAnswer(errors)
        results += part['results']
        fragments += part['fragments']
        for d in part['documentDates']:
            if (d['label'], d['at']) not in {(x['label'], x['at']) for x in document_dates}:
                document_dates.append(d)
    if not results:
        raise NoResults()
    for r in results:
        r['collectedAt'], r['collectedHasTime'] = text_checks.collected_at(r['dates'], document_dates)
        if r['collectedAt'] is None:
            r['collectedHasTime'] = False
    blob = {
        'schemaVersion': '1.0', 'docId': doc_id, 'verId': ver_id,
        'extraction': {'model': usage.get('model') or model, 'promptVersion': PROMPT_VERSION, 'dictionaryVersion': None,
                       'extractorVersion': VERSION,
                       'extractedAt': (now or datetime.now(timezone.utc)).isoformat(timespec='seconds').replace('+00:00', 'Z')},
        'pages': blob_pages, 'fragments': fragments, 'documentDates': document_dates, 'results': results,
    }
    problems = [_where(e) for e in _BLOB.iter_errors(blob)] + text_checks.problems(blob)
    if problems:
        raise InvalidAnswer(problems)
    return blob, usage


def convert(answer, words, indexes, zone):
    """One batch's answer -> blob parts and problems. Problems name fields and rules, never page text."""
    problems = []
    out = {'results': [], 'documentDates': [], 'fragments': []}
    if answer.get('refused'):
        return out, ['the model refused to answer']
    for n, d in enumerate(answer.get('documentDates', []), 1):
        date, p = _date(d, zone)
        problems += [f'document date {n}: {m}' for m in p]
        if date:
            out['documentDates'].append(date)
    for n, f in enumerate(answer.get('fragments', []), 1):
        ids = f.get('words') or []
        if f.get('page') not in indexes or not ids or any(i not in words or not i.startswith(f'p{f["page"]}w') for i in ids):
            problems.append(f'fragment {n}: words must exist on its page, which must be in this batch')
            continue
        out['fragments'].append({'page': f['page'], 'text': ' '.join(words[i]['text'] for i in ids),
                                 'box': union([words[i]['box'] for i in ids])})
    for n, a in enumerate(answer.get('results', []), 1):
        result, p = _result(a, words, indexes, zone)
        problems += [f'result {n}: {m}' for m in p]
        if result:
            out['results'].append(result)
    return out, problems


def _result(a, words, indexes, zone):
    if a.get('page') not in indexes:
        return None, ['page is not in this batch']
    problems, dates = [], []
    for m, d in enumerate(a.get('dates', []), 1):
        date, p = _date(d, zone)
        problems += [f'date {m}: {x}' for x in p]
        if date:
            dates.append(date)
    flag_printed = a.get('flagPrinted') or None
    result = {
        'name': a.get('name'), 'value': a.get('value'), 'unit': a.get('unit') or None,
        'range': {'text': a.get('range') or None, 'low': a.get('rangeLow') or None,
                  'high': a.get('rangeHigh') or None, 'kind': a.get('rangeKind') or 'none'},
        'flagPrinted': flag_printed, 'flag': text_checks.map_flag(flag_printed),
        'icd9': a.get('icd9') or None, 'material': a.get('material') or None,
        'condition': a.get('condition') or None, 'method': a.get('method') or None,
        'analyser': a.get('analyser') or None,
        'dates': dates, 'collectedAt': None, 'collectedHasTime': False,
        'suggestedParameter': a.get('suggestedParameter') or None,
        'source': {'page': a['page'], 'name': a.get('nameWords') or [], 'value': a.get('valueWords') or [],
                   'unit': (a.get('unitWords') or []) if a.get('unit') else [],
                   'range': (a.get('rangeWords') or []) if a.get('range') else []},
    }
    problems += [_where(e) for e in _RESULT.iter_errors(result)]
    if not problems:
        for field in ('name', 'range'):
            _regroup_words(result, field, words)
        problems += text_checks.result_problems(result, words, indexes)
    if not problems and text_checks.known_unit(result['unit']):
        # A unit read with OCR misreadings ("tys/ul") becomes the known unit ("tys/µl"); the words keep the reading.
        result['unit'] = text_checks.known_unit(result['unit'])
    return (None if problems else result), problems


_MARK = re.compile(r'[A-Z]|[A-Z]{1,3}\d+(?:[.,]\d+)*')


def _regroup_words(result, field, words):
    """Long names and ranges run over several lines, between other columns, and the model often lists
    their word ids a little wrong: a mark printed between the lines (an accreditation "A", a procedure
    code "V2.4") or a word of another column added, or a word left out. When the text does not equal
    the listed words, code looks for the text on the page itself, in reading order from the first listed
    word, skipping inside it only such marks and words of another column (another line, no horizontal
    overlap). It keeps the words it found when they hold every listed word that is not a mark or such a
    word, so a cut name or one band picked from a range still fails. The text is never changed."""
    text = result['name'] if field == 'name' else result['range']['text']
    ids = result['source'][field]
    if not text or not ids or any(i not in words for i in ids):
        return
    if text_checks.field_matches(text, text_checks.joined(words, ids)):
        return
    page = f'p{result["source"]["page"]}w'
    order = sorted((i for i in words if i.startswith(page)), key=lambda i: int(i[len(page):]))
    target = text_checks.normalise(text)
    start = order.index(ids[0])
    for first in range(max(0, start - 3), min(len(order), start + 4)):  # the model may start a word early or late
        found, pos = [], 0
        for i in order[first:]:
            w = text_checks.normalise(words[i]['text'])
            if w and target.startswith(w, pos):
                found.append(i)
                pos += len(w)
                if pos == len(target):
                    break
            elif found and (_MARK.fullmatch(words[i]['text']) or _other_column(words[i], [words[f] for f in found])):
                continue
            else:
                break
        if not found:
            continue
        rank = {i: n for n, i in enumerate(order)}
        before = lambda i: [words[f] for f in found if rank[f] < rank[i]]  # noqa: E731  as skipped in the scan
        listed = {i for i in ids if not _MARK.fullmatch(words[i]['text'])
                  and not (rank[found[0]] < rank[i] < rank[found[-1]] and _other_column(words[i], before(i)))}
        if pos == len(target) and found and listed <= set(found):
            result['source'][field] = found
            return


def _other_column(word, found):
    """A word printed in another column than the words found so far: on another line than the last of
    them, and with no horizontal overlap with any of them. A word on the same line is never skipped."""
    last = found[-1]['box']
    if abs(word['box']['y'] - last['y']) < last['h'] / 2:
        return False
    left = min(w['box']['x'] for w in found)
    right = max(w['box']['x'] + w['box']['w'] for w in found)
    return word['box']['x'] + word['box']['w'] <= left or word['box']['x'] >= right


def _date(d, zone):
    try:
        at, has_time = to_instant(d.get('local'), zone)
    except BadDate as e:
        return None, [str(e)]
    date = {'label': d.get('label'), 'text': d.get('text'), 'at': at, 'timeZone': zone,
            'hasTime': has_time, 'kind': d.get('kind')}
    problems = [_where(e) for e in _DATE.iter_errors(date)]
    return (None if problems else date), problems


def _where(error):
    """A schema error as a field path and a rule, without the value that broke it."""
    path = '/'.join(str(p) for p in error.absolute_path) or '(root)'
    return f'{path}: breaks "{error.validator}"'
