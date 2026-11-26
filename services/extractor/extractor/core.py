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
    the services propagate unchanged. A result that is still invalid after the retry goes to
    `unread`, with its place on the page, and the other results are kept (ADR-0018).
    """
    numbered = number(layout.analyze(pages))
    blob_pages = [{'index': p.index, 'sha256': p.sha256, 'words': words} for p, words in zip(pages, numbered)]
    words = {w['id']: w for p in blob_pages for w in p['words']}
    usage = {'input': 0, 'output': 0, 'calls': 0}
    results, document_dates, fragments, unread, unread_problems = [], [], [], [], []
    for batch in batches(blob_pages, batch_pages):
        texts = [page_text(p['index'], p['words']) for p in batch]
        indexes = {p['index'] for p in batch}
        errors, first = None, None
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
            if attempt == 1:
                first = (part, errors)
        if errors and first and _usable(first[1]) and (not _usable(errors) or len(first[0]['results']) > len(part['results'])):
            part, errors = first  # the retry was worse: keep the first answer
        if not _usable(errors):
            raise InvalidAnswer(errors)  # a refusal, a document date or a fragment: the version cannot be trusted
        unread += part['unread']
        unread_problems += errors
        results += part['results']
        fragments += part['fragments']
        for d in part['documentDates']:
            if (d['label'], d['at']) not in {(x['label'], x['at']) for x in document_dates}:
                document_dates.append(d)
    if not results:
        if unread:
            raise InvalidAnswer(unread_problems)  # nothing verified to review
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
        'unread': unread,
    }
    problems = [_where(e) for e in _BLOB.iter_errors(blob)] + text_checks.problems(blob)
    if problems:
        raise InvalidAnswer(problems)
    return blob, usage


def _usable(errors):
    """Only problems of single results: they go to `unread`, and the rest of the batch is kept."""
    return all(e.startswith('result ') for e in errors)


def convert(answer, words, indexes, zone):
    """One batch's answer -> blob parts and problems. Problems name fields and rules, never page text."""
    problems = []
    out = {'results': [], 'documentDates': [], 'fragments': [], 'unread': []}
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
        if result:
            out['results'].append(result)
        elif a.get('page') in indexes:
            problems += [f'result {n}: {m}' for m in p]
            out['unread'].append(_unread(a, p, words))
        else:
            problems += [f'page of result {n}: {m}' for m in p]  # no place to show it: the batch is invalid
    return out, problems


_FIELDS = ('name', 'value', 'unit', 'range')


def _failed_fields(problem):
    if problem.startswith('value and unit'):
        return {'value', 'unit'}
    head = problem.split(':', 1)[0]
    field = head.split('/')[1] if head.startswith('source/') and '/' in head else head
    return {field} if field in _FIELDS else {'other'}


def _unread(a, problems, words):
    """A result that failed the check: its page, a box and which fields failed. The box is around the words
    of the fields that passed (the name first), as a failed field may name words of another row; around all
    the words it named on that page when no field passed; none when it named none there."""
    prefix = f'p{a["page"]}w'
    fields = set().union(*(_failed_fields(m) for m in problems)) if problems else {'other'}
    def ids(names):
        return [i for f in names for i in (a.get(f + 'Words') or [])
                if isinstance(i, str) and i in words and i.startswith(prefix)]
    passed = [f for f in _FIELDS if f not in fields]
    chosen = ids(['name']) if 'name' in passed else []
    chosen = chosen or ids(passed) or ids(_FIELDS)
    return {'page': a['page'], 'box': union([words[i]['box'] for i in chosen]) if chosen else None,
            'fields': sorted(fields, key=lambda f: (_FIELDS + ('other',)).index(f))}


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
        'suggestedParameter': a.get('suggestedParameter') or None, 'lowConfidence': False,
        'source': {'page': a['page'], 'name': a.get('nameWords') or [], 'value': a.get('valueWords') or [],
                   'unit': (a.get('unitWords') or []) if a.get('unit') else [],
                   'range': (a.get('rangeWords') or []) if a.get('range') else []},
    }
    problems += [_where(e) for e in _RESULT.iter_errors(result)]
    if not problems:
        for field in ('name', 'range'):
            _regroup_words(result, field, words)
        result['lowConfidence'] = text_checks.low_confidence(result, words)
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
    word. Inside it, it may skip only marks and words on another line than the last word found, and only
    when every skipped word lies outside the horizontal span of the words found (another column). It
    keeps the words found when they hold every listed word except such skipped ones. So a cut name, a
    word left out, one band picked from a range or a text not printed still fails. The text never changes."""
    text = result['name'] if field == 'name' else result['range']['text']
    ids = result['source'][field]
    page = f'p{result["source"]["page"]}w'
    if not text or not ids or any(i not in words or not i.startswith(page) for i in ids):
        return  # the word check reports it
    if text_checks.field_matches(text, text_checks.joined(words, ids)):
        return
    order = sorted((i for i in words if i.startswith(page)), key=lambda i: int(i[len(page):]))
    rank = {i: n for n, i in enumerate(order)}
    target = text_checks.normalise(text)
    start = rank[ids[0]]
    for first in range(max(0, start - 3), min(len(order), start + 4)):  # the model may start a word early or late
        found, skipped, pos = [], [], 0
        for i in order[first:]:
            w = text_checks.normalise(words[i]['text'])
            if w and target.startswith(w, pos):
                found.append(i)
                pos += len(w)
                if pos == len(target):
                    break
            elif found and (_MARK.fullmatch(words[i]['text']) or not _same_line(words[i], words[found[-1]])):
                skipped.append(i)
            else:
                break
        if pos != len(target) or not found:
            continue
        skipped = [i for i in skipped if rank[i] < rank[found[-1]]]
        left = min(words[f]['box']['x'] for f in found)
        right = max(words[f]['box']['x'] + words[f]['box']['w'] for f in found)
        if any(left < words[i]['box']['x'] + words[i]['box']['w'] and words[i]['box']['x'] < right for i in skipped):
            continue  # a skipped word inside the span of the text: not another column
        if set(ids) - set(skipped) <= set(found):
            result['source'][field] = found
            return


def _same_line(word, other):
    return abs(word['box']['y'] - other['box']['y']) <= other['box']['h'] / 2


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
