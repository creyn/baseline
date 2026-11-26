"""Reads the descriptions of synthetic documents and derives their ground truth.

Standard library only, so the checks run anywhere. The generator and the evals use
the same functions, so the truth and the rendered document cannot drift apart.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DOCUMENTS = os.path.join(HERE, 'documents')
LAYOUTS = {'A', 'B', 'C'}
FORMS = {'text', 'scan', 'photo'}
TRAPS = {
    'name_outside_table', 'pesel_outside_table', 'address_outside_table', 'birth_date_outside_table',
    'staff_in_table', 'long_number_in_table', 'name_in_table_comment', 'continuation_page',
    'unit_change', 'condition', 'qualitative', 'less_than_range', 'text_range', 'flag_disagrees',
}


def load_all(folder=DOCUMENTS):
    docs = []
    for name in sorted(os.listdir(folder)):
        if name.endswith('.json'):
            with open(os.path.join(folder, name), encoding='utf-8') as f:
                d = json.load(f)
            d['_file'] = name
            docs.append(d)
    return docs


def results(doc):
    """Every result with the page it is on, in reading order."""
    out = []
    for p, page in enumerate(doc['pages'], 1):
        for section in page['sections']:
            for r in section['results']:
                out.append({**r, 'page': p, 'icd9': r.get('icd9') or section.get('icd9'),
                            'method': r.get('method') or section.get('method'),
                            'dates': section.get('dates', [])})
    return out


def date_fields(doc):
    """Labelled dates that masking must keep (never the date of birth), including the printed date in the footer."""
    fields = list(doc['dates']) + [{'label': 'Data wydruku', 'value': doc['printed'], 'where': 'footer'}]
    for page in doc['pages']:
        for section in page['sections']:
            fields += section.get('dates', [])
        for sample in page.get('samples', []):
            fields += sample['dates']
    return fields


def must_remove(doc):
    """Strings that must not survive masking, anywhere on the page.

    A known gap (a line where ADR-0003 accepts a residual risk) is listed separately:
    only inside that line may such a string survive.
    """
    p, lab = doc['patient'], doc['lab']
    out = [p['name'], p['pesel'], p['birth_date'], p['address'], doc['orderer'], doc['order_no'],
           lab['name'], lab['address'], lab['phone']]
    out += [s['name'] for s in doc['staff']]
    out += doc.get('must_remove_extra', [])
    return out


def must_keep(doc):
    """Strings that must survive masking: values, units, ranges and labelled dates."""
    out = []
    for r in results(doc):
        out.append(r['value'])
        if r['unit']:
            out.append(r['unit'])
        out += [r[k] for k in ('min', 'max') if r.get(k)]
        if r.get('range') and r.get('min') is None:
            out.append(r['range'])
    for f in date_fields(doc):
        out.append(f['value'])
    return out


def expected_extraction(doc):
    """What extraction must return for each result.

    flag is the laboratory's flag as printed; computed_flag is what code must compute from the range
    (ADR-0011). They differ only where the description says so.
    """
    keys = ('name', 'value', 'unit', 'range', 'range_lines', 'min', 'max', 'flag', 'icd9', 'material', 'condition', 'method',
            'dates', 'page')
    out = []
    for r in results(doc):
        e = {k: r.get(k) for k in keys}
        e['computed_flag'] = r['computed_flag'] if 'computed_flag' in r else r.get('flag')
        out.append(e)
    return out


def problems(doc, allowed_pesel):
    """Reasons a description is not valid; empty when it is."""
    out = []
    need = ['id', 'layout', 'forms', 'lab', 'patient', 'orderer', 'order_no', 'dates', 'staff', 'printed', 'pages', 'traps']
    out += [f'missing {k}' for k in need if k not in doc]
    if out:
        return out
    if doc['_file'] != doc['id'] + '.json':
        out.append('file name differs from id')
    if doc['layout'] not in LAYOUTS:
        out.append(f'unknown layout {doc["layout"]}')
    if not doc['forms'] or set(doc['forms']) - FORMS:
        out.append(f'forms must be a non-empty subset of {sorted(FORMS)}')
    if set(doc['traps']) - TRAPS:
        out.append(f'unknown traps {sorted(set(doc["traps"]) - TRAPS)}')
    if doc['patient']['pesel'] != allowed_pesel:
        out.append('PESEL is not the public example number')
    if doc['patient']['name'] != 'Jan Testowy':
        out.append('the patient must be Jan Testowy')
    if not results(doc):
        out.append('no results')
    for r in results(doc):
        for k in ('name', 'value', 'unit'):
            if k not in r:
                out.append(f'a result has no {k}')
        if not (r.get('range') is not None or ('min' in r and 'max' in r)):
            out.append(f'{r.get("name")}: give range, or min and max')
        for k in ('flag', 'computed_flag'):
            if r.get(k) not in (None, 'H', 'L'):
                out.append(f'{r.get("name")}: {k} must be H, L or null')
    if doc['layout'] in ('A', 'C') and any('icd9' not in r and not r.get('icd9') for r in results(doc)):
        out.append('every result needs an ICD-9 code in this layout')
    return out


def allowed_pesel(repo_root):
    with open(os.path.join(repo_root, 'tools', 'privacy', 'allowlist.txt'), encoding='utf-8') as f:
        numbers = re.findall(r'\b\d{11}\b', f.read())
    return numbers[0]
