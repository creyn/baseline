"""Tests of the contracts: schemas, examples and the text blob checks.

Needs jsonschema (contracts/requirements.txt). Run: python3 -m unittest discover -s contracts
"""
import copy
import json
import os
import sys
import unittest

from jsonschema import Draft202012Validator

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(HERE, 'examples')
sys.path.insert(0, HERE)
import text_checks  # noqa: E402


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


SCHEMAS = {name[:-len('.schema.json')]: load(os.path.join(HERE, name))
           for name in sorted(os.listdir(HERE)) if name.endswith('.schema.json')}
EXAMPLE_FILES = sorted(n for n in os.listdir(EXAMPLES) if n.endswith('.json'))


def validator(schema_name, definition=None):
    schema = SCHEMAS[schema_name]
    if definition:
        schema = {**schema, '$ref': f'#/$defs/{definition}'}
        schema.pop('oneOf', None)
    return Draft202012Validator(schema)


def errors(schema_name, doc, definition=None):
    return [e.message for e in validator(schema_name, definition).iter_errors(doc)]


def schema_of(example_name):
    """messages.v1.extracted.json belongs to messages.v1.schema.json."""
    return '.'.join(example_name.split('.')[:2])


def example(name):
    return load(os.path.join(EXAMPLES, name))


class SchemasAndExamples(unittest.TestCase):
    def test_schemas_are_valid(self):
        for name, schema in SCHEMAS.items():
            with self.subTest(schema=name):
                Draft202012Validator.check_schema(schema)

    def test_every_schema_has_an_example(self):
        named = {schema_of(n) for n in EXAMPLE_FILES}
        self.assertEqual(set(SCHEMAS), named)

    def test_examples_are_valid(self):
        for name in EXAMPLE_FILES:
            with self.subTest(example=name):
                schema = schema_of(name)
                self.assertIn(schema, SCHEMAS, 'an example must start with its schema name')
                self.assertEqual(errors(schema, example(name)), [])

    def test_message_examples_match_their_own_type(self):
        for name in EXAMPLE_FILES:
            if name.startswith('messages.v1.'):
                with self.subTest(example=name):
                    doc = example(name)
                    self.assertEqual(errors('messages.v1', doc, doc['type']), [])


class Messages(unittest.TestCase):
    def setUp(self):
        self.extracted = example('messages.v1.extracted.json')
        self.failed = example('messages.v1.failed.json')

    def test_timeout_is_never_sent(self):
        self.failed['reason'] = 'timeout'
        self.assertTrue(errors('messages.v1', self.failed))

    def test_failed_needs_a_reason(self):
        del self.failed['reason']
        self.assertTrue(errors('messages.v1', self.failed))

    def test_no_content_in_a_message(self):
        self.extracted['value'] = '18'
        self.assertTrue(errors('messages.v1', self.extracted))

    def test_a_reason_only_on_failed(self):
        self.extracted['reason'] = 'no_results'
        self.assertTrue(errors('messages.v1', self.extracted))

    def test_a_newer_minor_version_is_accepted(self):
        self.extracted['schemaVersion'] = '1.1'
        self.assertEqual(errors('messages.v1', self.extracted), [])

    def test_another_major_version_is_not_v1(self):
        for version in ('2.0', '1', 1, '1.01'):
            with self.subTest(version=version):
                self.extracted['schemaVersion'] = version
                self.assertTrue(errors('messages.v1', self.extracted))

    def test_user_id_is_ours_not_the_oid(self):
        self.extracted['userId'] = '3f2b8c1e-5a4d-4e6f-9b7a-1c2d3e4f5a6b'
        self.assertTrue(errors('messages.v1', self.extracted))

    def test_ids_must_be_uuidv7(self):
        self.extracted['verId'] = '3f2b8c1e-5a4d-4e6f-9b7a-1c2d3e4f5a6b'
        self.assertTrue(errors('messages.v1', self.extracted))

    def test_unknown_type(self):
        self.extracted['type'] = 'Checked'
        self.assertTrue(errors('messages.v1', self.extracted))


class TextBlob(unittest.TestCase):
    def setUp(self):
        self.doc = example('text.v1.iron-one-page.json')

    def words(self):
        return {w['id']: w for p in self.doc['pages'] for w in p['words']}

    def test_example_passes_the_checks(self):
        self.assertEqual(text_checks.problems(self.doc), [])

    def test_no_results_is_not_a_blob(self):
        self.doc['results'] = []
        self.assertTrue(errors('text.v1', self.doc))

    def test_a_date_needs_an_offset(self):
        self.doc['documentDates'][0]['at'] = '2026-04-10T07:25:00'
        self.assertTrue(errors('text.v1', self.doc))

    def test_a_date_needs_a_kind(self):
        del self.doc['documentDates'][0]['kind']
        self.assertTrue(errors('text.v1', self.doc))

    def test_a_result_needs_collected_at_or_null(self):
        self.doc['results'][0]['collectedAt'] = None
        self.assertEqual(errors('text.v1', self.doc), [])
        del self.doc['results'][0]['collectedAt']
        self.assertTrue(errors('text.v1', self.doc))

    def date(self, kind, at, has_time=True):
        return {'label': kind, 'text': at, 'at': at, 'timeZone': 'Europe/Warsaw', 'hasTime': has_time, 'kind': kind}

    def test_collected_at_rule(self):
        pick = text_checks.collected_at
        own = [self.date('performed', '2026-04-11T00:00:00+02:00', False)]
        document = [self.date('printed', '2026-04-12T10:00:00+02:00'),
                    self.date('registered', '2026-04-10T07:00:00+02:00'),
                    self.date('collected', '2026-04-10T07:25:00+02:00'),
                    self.date('collected', '2026-04-10T05:20:00Z')]
        self.assertEqual(pick(own, document), ('2026-04-10T05:20:00Z', True))
        self.assertEqual(pick(own, document[:2]), ('2026-04-10T07:00:00+02:00', True))
        self.assertEqual(pick(own, document[:1]), ('2026-04-11T00:00:00+02:00', False))
        self.assertEqual(pick([], document[:1]), (None, None))
        result_collected = [self.date('collected', '2026-04-09T08:00:00+02:00')]
        self.assertEqual(pick(result_collected, document), ('2026-04-09T08:00:00+02:00', True))

    def test_collected_at_must_follow_the_rule(self):
        self.doc['results'][0]['collectedAt'] = '2026-04-12T10:00:00+02:00'
        self.assertEqual(text_checks.problems(self.doc), ['result 1: collectedAt: is not the date the rule picks'])

    def test_a_box_is_a_fraction_of_the_page(self):
        self.doc['pages'][0]['words'][0]['box']['x'] = 120
        self.assertTrue(errors('text.v1', self.doc))

    def test_a_value_the_model_did_not_read(self):
        self.doc['results'][0]['value'] = '16'
        self.assertEqual(text_checks.problems(self.doc), ['result 1: value: does not equal its words'])

    def test_a_word_that_does_not_exist(self):
        self.doc['results'][0]['source']['value'] = ['p1w99']
        self.assertEqual(text_checks.problems(self.doc), ['result 1: value: word p1w99 does not exist'])

    def test_a_word_on_another_page(self):
        page2 = {'index': 2, 'sha256': '0' * 64, 'words': [
            {'id': 'p2w1', 'text': '18', 'box': {'x': 0.4, 'y': 0.1, 'w': 0.03, 'h': 0.01}, 'confidence': 0.9}]}
        self.doc['pages'].append(page2)
        self.doc['results'][0]['source']['value'] = ['p2w1']
        self.assertEqual(text_checks.problems(self.doc), ['result 1: value: word p2w1 is not on page 1'])

    def test_a_footnote_marker_on_the_unit(self):
        self.assertEqual(self.words()['p1w3']['text'], 'ng/ml*')
        self.assertEqual(self.doc['results'][0]['unit'], 'ng/ml')
        self.assertEqual(text_checks.problems(self.doc), [])

    def test_a_range_with_spaces(self):
        self.doc['results'][0]['range']['text'] = '30 – 400'
        self.assertEqual(text_checks.problems(self.doc), ['result 1: range: does not equal its words'])
        self.doc['results'][0]['range']['text'] = '30  -  400'
        self.assertEqual(text_checks.problems(self.doc), [])

    def test_value_and_unit_in_one_word(self):
        self.doc['pages'][0]['words'][1]['text'] = '18ng/ml'
        self.doc['results'][0]['source']['unit'] = ['p1w2']
        self.assertEqual(text_checks.problems(self.doc), [])
        self.doc['results'][0]['value'] = '1'
        self.assertEqual(text_checks.problems(self.doc), ['result 1: value and unit: do not equal their shared words'])

    def test_value_and_unit_split_inside_the_number(self):
        self.doc['pages'][0]['words'][1]['text'] = '18ng/ml'
        r = self.doc['results'][0]
        r['source']['unit'] = ['p1w2']
        r['value'], r['unit'] = '1', '8ng/ml'
        self.assertEqual(text_checks.problems(self.doc), ['result 1: value and unit: do not equal their shared words'])

    def test_a_unit_misread_by_ocr_is_the_known_unit(self):
        k = text_checks.known_unit
        self.assertEqual([k(u) for u in ('tys/ul', 'min/ul', 'U/I', 'ulU/ml', 'μIU/ml', 'mlU/l', 'ug/dl', 'fI')],
                         ['tys/µl', 'mln/µl', 'U/l', 'µIU/ml', 'µIU/ml', 'mIU/l', 'µg/dl', 'fl'])
        self.assertEqual([k(u) for u in ('IU/ml', 'ng/ml', 'xyz', 'HbAlc', None)], [None] * 5)  # right, or unknown
        self.pages_word('p1w3', 'ug/dl*')
        r = self.doc['results'][0]
        r['unit'] = 'µg/dl'
        self.assertEqual(text_checks.problems(self.doc), [])
        r['unit'] = 'mg/dl'  # not what the words can stand for
        self.assertEqual(text_checks.problems(self.doc), ['result 1: unit: does not equal its words'])

    def test_a_misread_unit_in_one_word_with_the_value(self):
        self.pages_word('p1w2', '18ug/dl')
        r = self.doc['results'][0]
        r['source']['unit'], r['unit'] = ['p1w2'], 'µg/dl'
        self.assertEqual(text_checks.problems(self.doc), [])

    def test_capital_l_units_and_no_clashes(self):
        self.assertEqual(text_checks.known_unit('tys/uL'), 'tys/µL')
        self.assertIsNone(text_checks.known_unit('mg/dL'))
        for read, unit in text_checks._UNIT_TABLE.items():  # a reading stands for one unit and is never a unit itself
            self.assertNotIn(read, text_checks.KNOWN_UNITS)
            self.assertEqual(sum(read in text_checks._misreadings(u) for u in text_checks.KNOWN_UNITS), 1, read)

    def test_a_range_of_several_bands_has_no_bounds(self):
        cases = {'30 - 400': 1, '<190': 1, 'ujemny': 0, 'na czczo: <150 nie na czczo: <175': 2, '12,0-14,0': 1,
                 '0,5 – 4,5': 1, 'M: 13–17 K: 12–16': 2, 'wg ESC 2019-2021: <115': 1, '8:00-10:00 <20': 1,
                 '2019-08-31': 0, '01-02-2026': 0, '0-20 ng/ml Deficyt >20-30 ng/ml': 2,
                 'K: 12.0-16.0 M: 13.5-17.5': 2, '0.5-10': 1}
        self.assertEqual({t: text_checks.bands(t) for t in cases}, cases)
        r = self.doc['results'][0]
        r['range'] = {'text': '30 - 400', 'low': '30', 'high': '400', 'kind': 'interval'}
        self.assertEqual(text_checks.problems(self.doc), [])
        self.pages_word('p1w4', '<30')
        self.pages_word('p1w6', '<400')
        r['range'] = {'text': '<30 - <400', 'low': '30', 'high': '400', 'kind': 'interval'}
        self.assertEqual(text_checks.problems(self.doc),
                         ['result 1: range: a range with several bands must have kind text and no bounds'])
        r['range'] = {'text': '<30 - <400', 'low': None, 'high': None, 'kind': 'text'}
        self.assertEqual(text_checks.problems(self.doc), [])

    def test_the_word_check_says_which_way_it_differs(self):
        src = self.doc['results'][0]['source']
        src['range'] = src['range'] + ['p1w3']
        self.assertEqual(text_checks.problems(self.doc), ['result 1: range: its word ids hold more words than its text; '
                                                          'list only the ids of the words in the text, '
                                                          'or copy the whole text'])
        src['range'] = src['range'][:1]
        self.assertEqual(text_checks.problems(self.doc), ['result 1: range: its text has words whose ids are missing; '
                                                          'list the id of every word in the text'])

    def test_low_confidence_is_set_by_the_words(self):
        word = next(w for p in self.doc['pages'] for w in p['words'] if w['id'] == 'p1w3')
        word['confidence'] = 0.43
        self.assertEqual(text_checks.problems(self.doc), ['result 1: lowConfidence: is not what the word confidences say'])
        self.doc['results'][0]['lowConfidence'] = True
        self.assertEqual(text_checks.problems(self.doc), [])

    def test_unread_results(self):
        self.doc['unread'] = [{'page': 1, 'box': {'x': 0.1, 'y': 0.2, 'w': 0.3, 'h': 0.02}, 'fields': ['range']},
                              {'page': 1, 'box': None, 'fields': ['name', 'other']}]
        self.assertEqual(errors('text.v1', self.doc), [])
        self.assertEqual(text_checks.problems(self.doc), [])
        self.doc['unread'][0]['page'] = 2
        self.assertEqual(text_checks.problems(self.doc), ['unread 1: page 2 does not exist'])
        self.doc['unread'][0]['fields'] = []
        self.assertTrue(errors('text.v1', self.doc))

    def pages_word(self, word_id, text):
        next(w for p in self.doc['pages'] for w in p['words'] if w['id'] == word_id)['text'] = text

    def test_flags_are_mapped_by_code(self):
        self.assertEqual([text_checks.map_flag(m) for m in ('H', '↑', 'L', '↓', '*', '+', None)],
                         ['H', 'H', 'L', 'L', None, None, None])
        r = self.doc['results'][0]
        r['flagPrinted'], r['flag'] = '*', 'H'
        self.assertEqual(text_checks.problems(self.doc), ['result 1: flag: does not match the printed marker'])
        r['flag'] = None
        self.assertEqual(text_checks.problems(self.doc), [])

    def test_text_that_does_not_fit_its_column(self):
        self.doc['results'][0]['value'] = '1' * 101
        self.assertTrue(errors('text.v1', self.doc))

    def test_a_unit_without_words(self):
        self.doc['results'][0]['source']['unit'] = []
        self.assertEqual(text_checks.problems(self.doc),
                         ['result 1: unit: text and word ids must be both present or both empty'])

    def test_no_unit(self):
        r = self.doc['results'][0]
        r['unit'], r['source']['unit'] = None, []
        self.assertEqual(text_checks.problems(self.doc), [])

    def test_pages_in_order(self):
        doc = copy.deepcopy(self.doc)
        doc['pages'][0]['index'] = 2
        self.assertIn('pages must be numbered 1..n in order', text_checks.problems(doc))

    def test_problems_never_quote_the_page(self):
        self.doc['results'][0]['value'] = '16'
        self.doc['results'][1]['name'] = 'Transferyna'
        found = text_checks.problems(self.doc)
        self.assertEqual(len(found), 2)
        for p in found:
            for text in ('16', '18', 'Transferyna', 'Żelazo', 'Ferrytyna'):
                self.assertNotIn(text, p)


if __name__ == '__main__':
    unittest.main()
