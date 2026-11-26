"""The core and its parts: pages, dates, lines, the word check, retries, the blob contract.

Standard library and jsonschema only. Run from the repository root:
python3 -m unittest discover -s services/extractor -t services/extractor
"""
import copy
import unittest
from datetime import datetime, timezone

from jsonschema import Draft202012Validator

from extractor import core
from extractor.contracts import schema, text_checks
from extractor.dates import BadDate, to_instant
from extractor.layout import box_from_polygon, lines, number, union
from extractor.pages import BadZip, read_zip
from tests import fakes

DOC, VER = '019ab3c4-5d6e-7f80-9a1b-2c3d4e5f6a7b', '019ab3c4-6e7f-7081-8b2c-3d4e5f6a7b8c'
NOW = datetime(2026, 4, 12, 9, 30, tzinfo=timezone.utc)


def run(pages_words, *answers, n=None):
    pages = [fakes.page(i, i) for i in range(1, (n or len(pages_words)) + 1)]
    llm = fakes.FakeLlm(*answers)
    blob, usage = core.extract(pages, fakes.FakeLayout(pages_words), llm, doc_id=DOC, ver_id=VER,
                               model='gpt-5.4-mini', now=NOW)
    return blob, usage, llm


class Pages(unittest.TestCase):
    def test_manifest_order_not_file_order(self):
        pages = [fakes.page(1, 'b'), fakes.page(2, 'a')]
        self.assertEqual([p.sha256 for p in read_zip(fakes.clean_zip(pages))], [p.sha256 for p in pages])

    def test_a_newer_minor_version(self):
        self.assertEqual(len(read_zip(fakes.clean_zip([fakes.page(1, 'a')], '1.3'))), 1)

    def test_broken_zips(self):
        good = fakes.page(1, 'a')
        for data in (b'not a zip', fakes.clean_zip([good], '2.0')):
            with self.subTest(data=data[:10]):
                with self.assertRaises(BadZip):
                    read_zip(data)

    def test_a_page_whose_hash_differs(self):
        bad = fakes.Page(1, '0' * 64, b'fake png')
        with self.assertRaises(BadZip):
            read_zip(fakes.clean_zip([bad]))


class Dates(unittest.TestCase):
    def test_summer_and_winter(self):
        self.assertEqual(to_instant('2026-04-10T07:25'), ('2026-04-10T07:25:00+02:00', True))
        self.assertEqual(to_instant('2026-01-15T07:50'), ('2026-01-15T07:50:00+01:00', True))

    def test_a_date_without_time(self):
        self.assertEqual(to_instant('2026-04-10'), ('2026-04-10T00:00:00+02:00', False))

    def test_the_hour_repeated_in_autumn_takes_the_earlier_offset(self):
        self.assertEqual(to_instant('2026-10-25T02:30'), ('2026-10-25T02:30:00+02:00', True))

    def test_the_hour_skipped_in_spring(self):
        with self.assertRaises(BadDate):
            to_instant('2026-03-29T02:30')

    def test_not_a_date(self):
        for text in ('10.04.2026', '2026-02-30', '', None):
            with self.subTest(text=text), self.assertRaises(BadDate):
                to_instant(text)


class Layout(unittest.TestCase):
    def test_box_from_inches(self):
        self.assertEqual(box_from_polygon([1, 1, 2, 1, 2, 1.5, 1, 1.5], 8.5, 11),
                         {'x': 0.11765, 'y': 0.09091, 'w': 0.11765, 'h': 0.04545})

    def test_lines_and_reading_order(self):
        words = [fakes.w('b', 0.5, 0.401), fakes.w('a', 0.1, 0.40), fakes.w('c', 0.1, 0.5)]
        self.assertEqual([[x['text'] for x in line] for line in lines(words)], [['a', 'b'], ['c']])
        self.assertEqual([x['id'] for x in number([words])[0]], ['p1w1', 'p1w2', 'p1w3'])


class Extract(unittest.TestCase):
    def test_one_page(self):
        blob, usage, llm = run([fakes.IRON_PAGE], fakes.iron_answer())
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual([r['value'] for r in blob['results']], ['18', '64'])
        self.assertEqual([r['flag'] for r in blob['results']], [None, 'L'])
        self.assertEqual(blob['results'][0]['collectedAt'], '2026-04-10T07:25:00+02:00')
        self.assertEqual(blob['fragments'][0]['text'], 'Metoda ECLIA')
        self.assertEqual(blob['extraction']['promptVersion'], 'extract.v2')
        self.assertEqual(usage, {'input': 100, 'output': 50, 'calls': 1})

    def test_the_model_version_that_answered_is_recorded(self):
        pages = [fakes.page(1, 1)]
        llm = fakes.FakeLlm(fakes.iron_answer())
        llm.model = 'gpt-5.4-mini-2026-01-01'
        blob, _ = core.extract(pages, fakes.FakeLayout([fakes.IRON_PAGE]), llm, doc_id=DOC, ver_id=VER,
                               model='deployment', now=NOW)
        self.assertEqual(blob['extraction']['model'], 'gpt-5.4-mini-2026-01-01')
        blob, _, _ = run([fakes.IRON_PAGE], fakes.iron_answer())
        self.assertEqual(blob['extraction']['model'], 'gpt-5.4-mini')  # no version reported: the deployment name

    def test_the_blob_meets_the_contract(self):
        blob, _, _ = run([fakes.IRON_PAGE], fakes.iron_answer())
        self.assertEqual(list(Draft202012Validator(schema('text.v1')).iter_errors(blob)), [])
        self.assertEqual(text_checks.problems(blob), [])

    def test_the_prompt_shows_every_word_with_its_id(self):
        _, _, llm = run([fakes.IRON_PAGE], fakes.iron_answer())
        user = llm.calls[0][1]['content']
        self.assertIn('## Page 1', user)
        self.assertIn('[p1w5]Ferrytyna [p1w6]18 [p1w7]ng/ml*', user)

    def test_a_unit_misread_by_ocr_becomes_the_known_unit(self):
        page = copy.deepcopy(fakes.IRON_PAGE)
        page[12]['text'] = 'ug/dI*'  # OCR read "µg/dl*"
        answer = fakes.iron_answer()
        answer['results'][1]['unit'] = 'ug/dI'  # the model copies what OCR read
        blob, _, llm = run([page], answer)
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(blob['results'][1]['unit'], 'µg/dl')
        self.assertEqual(blob['pages'][0]['words'][12]['text'], 'ug/dI*')  # the reading stays in the words
        self.assertEqual(text_checks.problems(blob), [])

    def test_a_word_left_out_of_the_range_is_found_on_the_page(self):
        answer = fakes.iron_answer()
        answer['results'][0]['rangeWords'] = ['p1w8', 'p1w10']  # "-" left out
        blob, _, llm = run([fakes.IRON_PAGE], answer)
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(blob['results'][0]['source']['range'], ['p1w8', 'p1w9', 'p1w10'])

    def test_a_name_not_printed_still_fails(self):
        answer = fakes.iron_answer()
        answer['results'][0]['name'] = 'Ferrytyna surowica'  # not on the page as one run of words
        blob, _, _ = run([fakes.IRON_PAGE], answer, answer)
        self.assertEqual([r['name'] for r in blob['results']], ['Żelazo'])
        self.assertEqual([u['fields'] for u in blob['unread']], [['name']])

    def test_regrouping_skips_only_marks_and_other_columns(self):
        w = fakes.w
        words = {'p1w1': w('Cholesterol', 0.05, 0.40), 'p1w2': w('LDL', 0.11, 0.40), 'p1w3': w('bezp.', 0.16, 0.40),
                 'p1w4': w('<115', 0.60, 0.40), 'p1w5': w('A', 0.80, 0.40, 0.01), 'p1w6': w('w', 0.05, 0.42, 0.01),
                 'p1w7': w('surowicy', 0.07, 0.42), 'p1w8': w('<100', 0.60, 0.42)}
        def regroup(field, text, ids):
            r = {'name': text if field == 'name' else 'x', 'range': {'text': text if field == 'range' else None},
                 'source': {'page': 1, 'name': ids if field == 'name' else [], 'range': ids if field == 'range' else []}}
            core._regroup_words(r, field, words)
            return r['source'][field]
        # A mark and a word of another column on the next line are skipped
        self.assertEqual(regroup('range', '<115 <100', ['p1w4', 'p1w5', 'p1w6', 'p1w7', 'p1w8']), ['p1w4', 'p1w8'])
        # A word left out on the same line is not: the name stays as listed and fails the check
        self.assertEqual(regroup('name', 'Cholesterol bezp.', ['p1w1', 'p1w2', 'p1w3']), ['p1w1', 'p1w2', 'p1w3'])
        self.assertEqual(regroup('name', 'Cholesterol', ['p1w1', 'p1w2']), ['p1w1', 'p1w2'])

    def test_regrouping_never_passes_a_cut_or_a_word_left_out(self):
        w = fakes.w
        def regroup(words, text, ids):
            r = {'name': text, 'range': {'text': None}, 'source': {'page': 1, 'name': ids, 'range': []}}
            core._regroup_words(r, 'name', words)
            return r['source']['name']
        last_mark = {'p1w1': w('Witamina', 0.05, 0.40, 0.08), 'p1w2': w('B12', 0.14, 0.40, 0.03)}
        self.assertEqual(regroup(last_mark, 'Witamina', ['p1w1', 'p1w2']), ['p1w1', 'p1w2'])
        inner_mark = {'p1w1': w('Witamina', 0.05, 0.40, 0.08), 'p1w2': w('D', 0.14, 0.40, 0.01),
                      'p1w3': w('25-OH', 0.16, 0.40)}
        self.assertEqual(regroup(inner_mark, 'Witamina 25-OH', ['p1w1', 'p1w2', 'p1w3']), ['p1w1', 'p1w2', 'p1w3'])
        indented = {'p1w1': w('Ab', 0.05, 0.40), 'p1w2': w('anty', 0.12, 0.415), 'p1w3': w('TPO', 0.18, 0.415)}
        self.assertEqual(regroup(indented, 'Ab TPO', ['p1w1', 'p1w2', 'p1w3']), ['p1w1', 'p1w2', 'p1w3'])
        bands = {'p1w1': w('M', 0.60, 0.40, 0.01), 'p1w2': w('13-17', 0.62, 0.40), 'p1w3': w('K', 0.68, 0.40, 0.01)}
        self.assertEqual(regroup(bands, '13-17', ['p1w1', 'p1w2', 'p1w3']), ['p1w1', 'p1w2', 'p1w3'])
        other_page = dict(last_mark, p2w1=w('Witamina', 0.05, 0.40))
        self.assertEqual(regroup(other_page, 'Witamina', ['p2w1']), ['p2w1'])  # left to the word check

    def test_an_id_on_another_page_gets_the_retry(self):
        bad = fakes.iron_answer()
        bad['results'][0]['nameWords'] = ['p2w5', 'p2w6']
        blob, _, llm = run([fakes.IRON_PAGE, fakes.IRON_PAGE], bad, fakes.iron_answer())
        self.assertEqual(len(llm.calls), 2)
        self.assertIn('result 1: name: word p2w5 is not on page 1', llm.calls[1][1]['content'])

    def test_a_cut_name_or_range_still_fails(self):
        answer = fakes.iron_answer()
        answer['results'][0]['range'] = '30 -'  # the last word dropped from the text, all ids listed
        blob, _, llm = run([fakes.IRON_PAGE], answer, answer)
        self.assertIn('result 1: range: its word ids hold more words than its text; '
                      'list only the ids of the words in the text, or copy the whole text', llm.calls[1][1]['content'])
        self.assertEqual(blob['unread'], [{'page': 1, 'box': blob['unread'][0]['box'], 'fields': ['range']}])
        self.assertEqual([r['name'] for r in blob['results']], ['Żelazo'])

    def test_an_answer_that_breaks_the_schema_gets_the_retry(self):
        bad = fakes.iron_answer()
        bad['results'][0]['name'] = 7
        bad['results'][0]['nameWords'] = [['p1w5']]
        blob, _, llm = run([fakes.IRON_PAGE], bad, fakes.iron_answer())
        self.assertEqual(len(llm.calls), 2)
        self.assertEqual(blob['results'][0]['name'], 'Ferrytyna')

    def test_a_value_not_read_from_the_page_gets_one_retry(self):
        blob, usage, llm = run([fakes.IRON_PAGE], fakes.iron_answer(ferritin='16'), fakes.iron_answer())
        self.assertEqual(len(llm.calls), 2)
        self.assertIn('result 1: value: does not equal its words', llm.calls[1][1]['content'])
        self.assertEqual(blob['results'][0]['value'], '18')

    def test_still_invalid_after_the_retry_goes_to_unread(self):
        """ADR-0018: the verified results are kept; the other one is shown on review to enter by hand."""
        blob, usage, _ = run([fakes.IRON_PAGE], fakes.iron_answer(ferritin='16'), fakes.iron_answer(ferritin='16'))
        self.assertEqual([r['name'] for r in blob['results']], ['Żelazo'])
        u = blob['unread'][0]
        self.assertEqual((u['page'], u['fields']), (1, ['value']))
        name_box = next(w['box'] for w in blob['pages'][0]['words'] if w['id'] == 'p1w5')
        self.assertEqual(u['box'], name_box)  # around the name, which passed
        self.assertEqual(list(Draft202012Validator(schema('text.v1')).iter_errors(blob)), [])
        self.assertEqual(text_checks.problems(blob), [])

    def test_the_unread_box_and_fields(self):
        answer = fakes.iron_answer()
        answer['results'][0]['name'], answer['results'][0]['valueWords'] = 'Ferrytynaa', ['p1w12']  # 64: another row
        blob, _, _ = run([fakes.IRON_PAGE], answer, answer)
        u = blob['unread'][0]
        self.assertEqual(u['fields'], ['name', 'value'])
        words = {w['id']: w['box'] for w in blob['pages'][0]['words']}
        self.assertEqual(u['box'], union([words['p1w7'], words['p1w8'], words['p1w9'], words['p1w10']]))  # unit, range
        answer['results'][0]['nameWords'] = answer['results'][0]['valueWords'] = ['p1w99']
        answer['results'][0]['unitWords'] = answer['results'][0]['rangeWords'] = []
        answer['results'][0]['unit'] = answer['results'][0]['range'] = None
        blob, _, _ = run([fakes.IRON_PAGE], answer, answer)
        self.assertEqual(blob['unread'][0]['box'], None)
        self.assertEqual(core._failed_fields('value and unit: do not equal their shared words'), {'value', 'unit'})
        self.assertEqual(core._failed_fields('source/unit: breaks "type"'), {'unit'})
        self.assertEqual(core._failed_fields('dates/0/kind: breaks "enum"'), {'other'})

    def test_a_worse_retry_keeps_the_first_answer(self):
        first = fakes.iron_answer(ferritin='16')  # one result unread, one verified
        worse = fakes.iron_answer()
        worse['documentDates'][0]['local'] = '2026-03-29T02:30'  # a document date that does not exist
        blob, _, llm = run([fakes.IRON_PAGE], first, worse)
        self.assertEqual(len(llm.calls), 2)
        self.assertEqual(([r['name'] for r in blob['results']], len(blob['unread'])), (['Żelazo'], 1))

    def test_one_batch_unread_and_another_verified(self):
        pages = [fakes.IRON_PAGE] * 6
        bad = fakes.iron_answer(ferritin='16')
        bad['results'][1]['value'] = '63'  # nothing verified in the first batch
        blob, _, _ = run(pages, bad, bad, fakes.iron_answer(page_no=6))
        self.assertEqual([r['source']['page'] for r in blob['results']], [6, 6])
        self.assertEqual([u['page'] for u in blob['unread']], [1, 1])

    def test_nothing_verified_is_still_invalid(self):
        bad = fakes.iron_answer(ferritin='16')
        bad['results'][1]['value'] = '63'
        with self.assertRaises(core.InvalidAnswer) as e:
            run([fakes.IRON_PAGE], bad, bad)
        self.assertEqual(e.exception.problems, ['result 1: value: does not equal its words',
                                                'result 2: value: does not equal its words'])

    def test_problems_never_quote_the_page(self):
        bad = fakes.iron_answer(ferritin='16')
        bad['results'][1]['unit'] = 'x' * 60
        with self.assertRaises(core.InvalidAnswer) as e:
            run([fakes.IRON_PAGE], bad, bad)  # both results fail: nothing verified
        for p in e.exception.problems:
            for text in ('16', '18', 'xxx', 'Ferrytyna', 'Żelazo'):
                self.assertNotIn(text, p)

    def test_a_word_from_another_batch(self):
        answer = fakes.iron_answer()
        answer['results'][0]['page'] = 6
        with self.assertRaises(core.InvalidAnswer) as e:  # no page to show it on: the batch is invalid
            run([fakes.IRON_PAGE], answer, answer)
        self.assertEqual(e.exception.problems, ['page of result 1: page is not in this batch'])

    def test_a_date_that_does_not_exist(self):
        answer = fakes.iron_answer()
        answer['documentDates'][0]['local'] = '2026-03-29T02:30'
        with self.assertRaises(core.InvalidAnswer) as e:
            run([fakes.IRON_PAGE], answer, answer)
        self.assertEqual(e.exception.problems, ['document date 1: the time does not exist in this zone (clocks went forward)'])

    def test_flags_are_mapped_by_code(self):
        answer = fakes.iron_answer()
        answer['results'][1]['flagPrinted'] = '↓'
        blob, _, _ = run([fakes.IRON_PAGE], answer)
        self.assertEqual(blob['results'][1]['flag'], 'L')

    def test_no_results(self):
        with self.assertRaises(core.NoResults):
            run([fakes.IRON_PAGE], fakes.EMPTY)

    def test_a_refusal_is_invalid(self):
        refused = {**fakes.EMPTY, 'refused': True}
        with self.assertRaises(core.InvalidAnswer):
            run([fakes.IRON_PAGE], refused, refused)

    def test_seven_pages_in_two_batches(self):
        pages = [fakes.IRON_PAGE] * 7
        blob, usage, llm = run(pages, fakes.EMPTY, fakes.iron_answer(page_no=6))
        self.assertEqual(len(llm.calls), 2)
        self.assertIn('## Page 5', llm.calls[0][1]['content'])
        self.assertNotIn('## Page 6', llm.calls[0][1]['content'])
        self.assertIn('## Page 6', llm.calls[1][1]['content'])
        self.assertEqual(blob['results'][0]['source']['page'], 6)
        self.assertEqual(len(blob['pages']), 7)

    def test_document_dates_repeated_on_every_page_are_kept_once(self):
        blob, _, _ = run([fakes.IRON_PAGE] * 6, fakes.iron_answer(page_no=1), fakes.iron_answer(page_no=6))
        self.assertEqual(len(blob['documentDates']), 1)
        self.assertEqual(len(blob['results']), 4)

    def test_without_any_trend_date(self):
        answer = fakes.iron_answer()
        answer['documentDates'][0]['kind'] = 'printed'
        blob, _, _ = run([fakes.IRON_PAGE], answer)
        self.assertEqual((blob['results'][0]['collectedAt'], blob['results'][0]['collectedHasTime']), (None, False))


if __name__ == '__main__':
    unittest.main()
