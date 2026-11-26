"""Checks of a text blob that JSON Schema cannot express.

Standard library only. The extractor runs them before it writes a blob, and the
contract tests run them on the examples, so both use one implementation.
"""
import re
from datetime import datetime

_SPACES = re.compile(r'\s+')
_LEADING_NUMBER = re.compile(r'^[<>≤≥]?\d+(?:[.,]\d+)?')
_FLAGS = {'H': 'H', '↑': 'H', 'L': 'L', '↓': 'L'}
TREND_DATE_KINDS = ('collected', 'received', 'registered', 'performed', 'released')


def normalise(text):
    """Remove spaces and a trailing footnote marker ("ng/ml*" reads as "ng/ml")."""
    return _SPACES.sub('', text).rstrip('*')


# Units as laboratories print them. OCR misreads some characters in them: "µ" as "u" or the
# Greek "μ", "l" as "I", "1" or "i" ("mln" as "min"), "I" as "l" or "1" ("µIU" as "ulU").
# A unit read with such misreadings is replaced by the known unit it can only come from.
_KNOWN = (
    '%', 'fl', 'pg', 'g/dl', 'g/l', 'g/ml', 'mg/dl', 'mg/l', 'mg/g', 'µg/dl', 'µg/l', 'µg/ml', 'ng/ml', 'ng/dl',
    'ng/l', 'pg/ml', 'mmol/l', 'µmol/l', 'nmol/l', 'pmol/l', 'mEq/l', 'U/l', 'U/ml', 'IU/l', 'IU/ml', 'mIU/l',
    'mIU/ml', 'µIU/ml', 'mU/l', 'µU/ml', 'kU/l', 'tys/µl', 'mln/µl', 'tys/mm3', 'mln/mm3', '/µl', 'mm/h',
    'ml/min/1,73m2', 's',
)
# Each unit also with a capital "L" for litre ("mg/dL", "tys/µL"), as many laboratories print it.
KNOWN_UNITS = _KNOWN + tuple(sorted({re.sub(r'l\b', 'L', u) for u in _KNOWN} - set(_KNOWN)))
_MISREAD = {'µ': 'µuμ', 'l': 'lI1i', 'I': 'Il1'}
# A band of a range: a bound with a comparison ("<190", ">=14,0") or an interval ("0-20", "30 - 400").
_BAND = re.compile(r'[<>≤≥]=?\s*\d[\d,.]*|\d[\d,.]*\s*[-–—]\s*\d')
# Dates, times and year spans ("2019-08-31", "8:00-10:00", "2019-2021") are not bands.
_NOT_BAND = re.compile(r'\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}([-./])\d{1,2}\1\d{2,4}\b|\b\d{1,2}:\d{2}\b'
                       r'|\b(?:19|20)\d\d\s*[-–—]\s*(?:19|20)\d\d\b')


def _misreadings(unit):
    out = ['']
    for c in unit:
        out = [o + x for o in out for x in _MISREAD.get(c, c)]
    return out


def _unit_table():
    table, clash = {}, set()
    for unit in KNOWN_UNITS:
        for read in _misreadings(unit):
            if read in table and table[read] != unit:
                clash.add(read)
            table[read] = unit
    for read in clash | set(KNOWN_UNITS):
        table.pop(read, None)
    return table


_UNIT_TABLE = _unit_table()


def known_unit(read):
    """The known unit that a unit read with OCR misreadings stands for, or None (also when it is read right)."""
    return _UNIT_TABLE.get(normalise(read)) if read else None


def unit_matches(unit, words_text):
    """A unit equals its words as read, or is the known unit those words misread."""
    return field_matches(unit, words_text) or known_unit(words_text) == normalise(unit)


def bands(range_text):
    """How many bands a printed range has: "30 - 400" one, "na czczo: <150 nie na czczo: <175" two."""
    return len(_BAND.findall(_NOT_BAND.sub(' ', range_text or '')))


def mismatch(text, words_text):
    """Why a field does not equal its words, without quoting either (problems never quote the page)."""
    t, w = normalise(text), normalise(words_text)
    if t in w:
        return 'its word ids hold more words than its text; list only the ids of the words in the text, or copy the whole text'
    if w in t:
        return 'its text has words whose ids are missing; list the id of every word in the text'
    return 'does not equal its words'


def map_flag(printed):
    """The laboratory's marker as printed, mapped to H, L or None. Anything unknown is None, never a guess."""
    return _FLAGS.get(normalise(printed)) if printed else None


def collected_at(result_dates, document_dates):
    """The date a result's trend uses, as (at, hasTime), or (None, None).

    By kind in the order of TREND_DATE_KINDS (never "printed"); within a kind the
    result's own dates before the document's, and the earliest first. Times are
    compared as instants, so different offsets order correctly.
    """
    for kind in TREND_DATE_KINDS:
        for dates in (result_dates, document_dates):
            found = [d for d in dates if d['kind'] == kind]
            if found:
                first = min(found, key=lambda d: _instant(d['at']))
                return first['at'], first['hasTime']
    return None, None


def _instant(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00'))


def joined(words_by_id, ids):
    return ''.join(words_by_id[i]['text'] for i in ids)


def field_matches(text, words_text):
    return normalise(text) == normalise(words_text)


def problems(doc):
    """Reasons the blob breaks the rules; empty when it is valid. Never includes page text."""
    out = []
    indexes = [p['index'] for p in doc['pages']]
    if indexes != list(range(1, len(indexes) + 1)):
        out.append('pages must be numbered 1..n in order')
    words = {}
    for p in doc['pages']:
        for w in p['words']:
            if w['id'] in words:
                out.append(f'word id {w["id"]} is not unique')
            if not w['id'].startswith(f'p{p["index"]}w'):
                out.append(f'word id {w["id"]} is not on page {p["index"]}')
            words[w['id']] = w
    for f in doc['fragments']:
        if f['page'] not in indexes:
            out.append(f'a fragment names page {f["page"]}, which does not exist')
    for n, r in enumerate(doc['results'], 1):
        out += [f'result {n}: {m}' for m in result_problems(r, words, indexes)]
        if (r['collectedAt'], r['collectedHasTime'] if r['collectedAt'] else None) != collected_at(r['dates'], doc['documentDates']):
            out.append(f'result {n}: collectedAt: is not the date the rule picks')
    return out


def result_problems(r, words, indexes):
    """Problems of one result: its page exists, its word ids exist on that page, each field equals its words."""
    src = r['source']
    if src['page'] not in indexes:
        return [f'page {src["page"]} does not exist']
    out = []
    prefix = f'p{src["page"]}w'
    for field in ('name', 'value', 'unit', 'range'):
        for i in src[field]:
            if i not in words:
                out.append(f'{field}: word {i} does not exist')
            elif not i.startswith(prefix):
                out.append(f'{field}: word {i} is not on page {src["page"]}')
    if out:
        return out
    if r['flag'] != map_flag(r['flagPrinted']):
        out.append('flag: does not match the printed marker')
    texts = {'name': r['name'], 'value': r['value'], 'unit': r['unit'], 'range': r['range']['text']}
    for field in ('unit', 'range'):
        if (texts[field] is None) != (not src[field]):
            out.append(f'{field}: text and word ids must be both present or both empty')
    if out:
        return out
    if not field_matches(texts['name'], joined(words, src['name'])):
        out.append('name: ' + mismatch(texts['name'], joined(words, src['name'])))
    if texts['range'] is not None and not field_matches(texts['range'], joined(words, src['range'])):
        out.append('range: ' + mismatch(texts['range'], joined(words, src['range'])))
    rng = r['range']
    if bands(rng['text']) > 1 and (rng['kind'] != 'text' or rng['low'] is not None or rng['high'] is not None):
        out.append('range: a range with several bands must have kind text and no bounds')
    value_words = joined(words, src['value'])
    if texts['unit'] is not None and src['unit'] == src['value']:
        # A value printed together with its unit in one word, e.g. "18ng/ml".
        number = _LEADING_NUMBER.match(normalise(value_words))
        if not number or number.group() != normalise(texts['value']) \
                or not unit_matches(texts['unit'], normalise(value_words)[len(number.group()):]):
            out.append('value and unit: do not equal their shared words')
    else:
        if not field_matches(texts['value'], value_words):
            out.append('value: does not equal its words')
        if texts['unit'] is not None and not unit_matches(texts['unit'], joined(words, src['unit'])):
            out.append('unit: does not equal its words')
    return out
