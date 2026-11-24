"""Checks of a text blob that JSON Schema cannot express.

Standard library only. The extractor runs them before it writes a blob, and the
contract tests run them on the examples, so both use one implementation.
"""
import re

_SPACES = re.compile(r'\s+')


def normalise(text):
    """Remove spaces and a trailing footnote marker ("ng/ml*" reads as "ng/ml")."""
    return _SPACES.sub('', text).rstrip('*')


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
        out += [f'result {n}: {m}' for m in _result_problems(r, words, indexes)]
    return out


def _result_problems(r, words, indexes):
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
    texts = {'name': r['name'], 'value': r['value'], 'unit': r['unit'], 'range': r['range']['text']}
    for field in ('unit', 'range'):
        if (texts[field] is None) != (not src[field]):
            out.append(f'{field}: text and word ids must be both present or both empty')
    if out:
        return out
    if not field_matches(texts['name'], joined(words, src['name'])):
        out.append('name: does not equal its words')
    if texts['range'] is not None and not field_matches(texts['range'], joined(words, src['range'])):
        out.append('range: does not equal its words')
    value_words = joined(words, src['value'])
    if texts['unit'] is not None and src['unit'] == src['value']:
        # A value printed together with its unit in one word, e.g. "18ng/ml".
        if not field_matches(texts['value'] + texts['unit'], value_words):
            out.append('value and unit: do not equal their shared words')
    else:
        if not field_matches(texts['value'], value_words):
            out.append('value: does not equal its words')
        if texts['unit'] is not None and not field_matches(texts['unit'], joined(words, src['unit'])):
            out.append('unit: does not equal its words')
    return out
