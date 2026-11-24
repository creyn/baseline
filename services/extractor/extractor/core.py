"""Pages in, the text blob out (ADR-0007). Standard library and jsonschema only.

The LLM proposes; code checks every field against the words it names, adds the time
zones, maps the flags and picks the date for trends. Nothing here logs page content.
"""
import os
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
        'extraction': {'model': model, 'promptVersion': PROMPT_VERSION, 'dictionaryVersion': None,
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
        problems += text_checks.result_problems(result, words, indexes)
    return (None if problems else result), problems


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
