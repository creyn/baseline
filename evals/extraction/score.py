"""Compares extracted results with the truth of a synthetic document (design: "Evals").

Standard library only. Targets (ADR-0007, design.md):
- values and units exactly right: 100% (a unit misread by OCR and corrected to a known unit counts as right);
- names, ranges and flags as printed: 95%;
- missing and extra results, the mapped flag, material, condition, method and dates: reported, no target yet.

ADR-0018: the ratios are over the results the extractor verified and returned (matched), not over all
expected ones. A result in `unread` is not an error of a value: the review asks the user for it. It is
reported with the missing ones. A result marked lowConfidence whose value or unit is wrong counts as
"flagged", not wrong: the review marks it for checking.
"""
import re

import common  # noqa: F401  sets the paths to the extractor
from extractor.dates import to_instant

TARGETS = {'values_units': 1.0, 'names': 0.95, 'ranges': 0.95, 'flags': 0.95}
# The share of expected results read and verified. Without it, a run where the model reads nothing would
# pass, because the targets above are over the verified results (ADR-0018). Starting value.
READ_TARGET = 0.9
_SPACES = re.compile(r'\s+')


def norm(text):
    return _SPACES.sub('', text or '').rstrip('*').lower()


def score(expected, extracted, unread=0):
    """expected: describe.expected_extraction(doc); extracted: the blob's results; unread: len(blob['unread']).
    Returns counts and ratios over the matched results."""
    pairs, extra = match(expected, extracted)
    n = sum(1 for _, x in pairs if x is not None)
    flagged = 0
    counts = {k: 0 for k in ('values_units', 'names', 'ranges', 'flags', 'mapped_flags', 'material', 'condition',
                             'method', 'dates')}
    for e, x in pairs:
        if x is None:
            continue
        right = (x['value'] or '').strip() == e['value'] and norm(x['unit']) == norm(e['unit'] or None)
        flagged += not right and x.get('lowConfidence', False)
        counts['values_units'] += right or x.get('lowConfidence', False)
        counts['names'] += norm(x['name']) == norm(e['name'])
        counts['ranges'] += _range_ok(e, x)
        counts['flags'] += (x['flagPrinted'] or None) == (e['flag'] or None)
        counts['material'] += norm(x['material']) == norm(e['material'])
        counts['condition'] += norm(x['condition']) == norm(e['condition'])
        counts['mapped_flags'] += x['flag'] == (e['flag'] if e['flag'] in ('H', 'L') else None)
        method = norm(x['method'])
        counts['method'] += (not method) if not e['method'] else bool(method) and method in norm(e['method'])
        counts['dates'] += _dates(x['dates']) == _dates_expected(e['dates'])
    missing = max(0, sum(1 for _, x in pairs if x is None) - unread)  # not returned at all; unread ones are counted apart
    ratios = {k: (v / n if n else 1.0) for k, v in counts.items()}
    return {'expected': len(expected), 'matched': n, 'missing': missing, 'unread': unread, 'flagged': flagged,
            'extra': len(extra), 'counts': counts, 'ratios': ratios}


def match(expected, extracted):
    """Pairs each expected result with one extracted result: first by page and printed name,
    then by page, value and unit (the name is then counted as wrong). Each is used once."""
    left = list(extracted)
    pairs = []
    for e in expected:
        x = _take(left, lambda x: x['source']['page'] == e['page'] and norm(x['name']) == norm(e['name']))
        pairs.append([e, x])
    for pair in pairs:
        if pair[1] is None:
            e = pair[0]
            pair[1] = _take(left, lambda x: x['source']['page'] == e['page'] and (x['value'] or '').strip() == e['value']
                            and norm(x['unit']) == norm(e['unit'] or None))
    return [tuple(p) for p in pairs], left


def _take(items, test):
    for i, x in enumerate(items):
        if test(x):
            return items.pop(i)
    return None


_BAND = re.compile(r'[<>≤≥]|\d\s*[-–—]\s*\d')
_BAND_START = re.compile(r'[<>≤≥]|\d')


def _range_ok(e, x):
    if e.get('range_lines') and e.get('min') is None:
        # Several lines or bands: the whole printed text, never one band picked (owner, 2026-11-26).
        # Every band must be there; a heading or a citation line may be left out.
        got = norm(x['range']['text'])
        whole = norm(' '.join(e['range_lines']))
        bands = [norm(line[_BAND_START.search(line).start():]) for line in e['range_lines'] if _BAND.search(line)]
        several = len(bands) > 1
        no_bounds = x['range']['kind'] == 'text' and x['range']['low'] is None and x['range']['high'] is None
        return bool(got) and got in whole and all(b in got for b in bands) and (no_bounds or not several)
    if e.get('min') is not None or e.get('max') is not None:
        return norm(x['range']['low']) == norm(e.get('min')) and norm(x['range']['high']) == norm(e.get('max'))
    return norm(x['range']['text']) == norm(e.get('range'))


def _dates(dates):
    return sorted((norm(d['label']), d['at'][:16]) for d in dates)


def _dates_expected(dates):
    return sorted((norm(d['label']), to_instant(common.local(d['value']))[0][:16]) for d in dates)


def total(scores):
    """Sums per-document scores into one, weighted by the number of matched results."""
    if not scores:
        return score([], [])
    n = sum(s['matched'] for s in scores)
    counts = {k: sum(s['counts'][k] for s in scores) for k in scores[0]['counts']}
    out = {k: sum(s[k] for s in scores) for k in ('expected', 'missing', 'unread', 'flagged', 'extra')}
    return {**out, 'matched': n, 'counts': counts, 'ratios': {k: (v / n if n else 1.0) for k, v in counts.items()}}


def failures(summary, outcomes=()):
    """Why the run fails: a document that did not end in 'ok', too few results read, or a metric below its target."""
    out = [f'{n} document(s) failed: {", ".join(sorted(set(o for o in outcomes if o != "ok")))}'
           for n in [sum(1 for o in outcomes if o != 'ok')] if n]
    read = summary['matched'] / summary['expected'] if summary['expected'] else 1.0
    if read < READ_TARGET:
        out.append(f'read {read:.3f} < {READ_TARGET}')
    return out + [f'{k} {summary["ratios"][k]:.3f} < {t}' for k, t in TARGETS.items() if summary['ratios'][k] < t]
