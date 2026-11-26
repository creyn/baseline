"""The offline evals and the scoring. Standard library and jsonschema only.

Run from the repository root: python3 -m unittest discover -s evals/extraction
"""
import copy
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import live  # noqa: E402
import offline  # noqa: E402
import score  # noqa: E402
from extractor import core  # noqa: E402
from extractor.pages import Page  # noqa: E402


class Offline(unittest.TestCase):
    def test_every_document_scores_100_percent(self):
        scores = []
        for doc in common.documents():
            with self.subTest(doc=doc['id']):
                blob, _ = offline.run(doc)
                s = score.score(offline.expected(doc), blob['results'])
                self.assertEqual((s['missing'], s['unread'], s['extra'], s['matched']), (0, 0, 0, s['expected']))
                self.assertEqual(s['ratios'], {k: 1.0 for k in s['ratios']})
                scores.append(s)
        self.assertEqual(score.failures(score.total(scores)), [])

    def test_seven_pages_are_two_batches(self):
        doc = next(d for d in common.documents() if len(d['pages']) == 7)
        blob, calls = offline.run(doc)
        self.assertEqual(calls, 2)
        self.assertEqual({r['source']['page'] for r in blob['results']}, {1, 2, 3, 4, 5, 6, 7})

    def test_known_limitation_a_continued_block_falls_back_to_registration(self):
        """Page 6 continues page 5 in the next batch and loses its block's collection date (design.md, risks)."""
        doc = next(d for d in common.documents() if len(d['pages']) == 7)
        blob, _ = offline.run(doc)
        page6 = [r for r in blob['results'] if r['source']['page'] == 6]
        self.assertTrue(page6)
        for r in page6:
            self.assertEqual(r['dates'], [])
            self.assertEqual(r['collectedAt'], '2026-05-18T07:31:00+02:00')


class Dump(unittest.TestCase):
    def test_every_call_and_the_layout_are_written(self):
        doc = next(d for d in common.documents() if len(d['pages']) == 7)
        pages_words, targets = offline.build(doc)
        llm = offline.FakeLlm(doc, pages_words, targets)
        pages = [Page(i, f'{i:064x}', b'') for i in range(1, 8)]
        with tempfile.TemporaryDirectory() as folder:
            core.extract(pages, live.RecordingLayout(offline.FakeLayout(pages_words), folder),
                         live.RecordingLlm(llm, folder), doc_id='019ab3c4-5d6e-7f80-9a1b-2c3d4e5f6a7b',
                         ver_id='019ab3c4-6e7f-7081-8b2c-3d4e5f6a7b8c', model='offline')
            self.assertEqual(sorted(os.listdir(folder)), ['call-1-answer.json', 'call-1-request.json',
                                                          'call-2-answer.json', 'call-2-request.json', 'layout.json'])
            with open(os.path.join(folder, 'call-2-request.json'), encoding='utf-8') as f:
                self.assertIn('## Page 6', json.load(f)[1]['content'])
            with open(os.path.join(folder, 'call-1-answer.json'), encoding='utf-8') as f:
                self.assertTrue(json.load(f)['parsed']['results'])


    def test_a_failed_call_is_written_with_its_type_and_raised(self):
        class Down:
            def complete(self, messages):
                raise TimeoutError('the text of an error is not written')
        with tempfile.TemporaryDirectory() as folder:
            llm = live.RecordingLlm(Down(), folder)
            with self.assertRaises(TimeoutError):
                llm.complete([{'role': 'user', 'content': 'x'}])
            with open(os.path.join(folder, 'call-1-answer.json'), encoding='utf-8') as f:
                self.assertEqual(json.load(f), {'error': 'TimeoutError'})


class Scoring(unittest.TestCase):
    def setUp(self):
        self.doc = next(d for d in common.documents() if d['id'].startswith('c3'))
        self.blob, _ = offline.run(self.doc)
        self.expected = offline.expected(self.doc)

    def test_a_wrong_value(self):
        results = copy.deepcopy(self.blob['results'])
        results[0]['value'] = '19'
        s = score.score(self.expected, results)
        self.assertEqual(s['counts']['values_units'], len(self.expected) - 1)
        self.assertEqual(s['missing'], 0)
        self.assertIn('values_units', score.failures(s)[0])

    def test_a_wrong_value_with_low_confidence_is_flagged_not_wrong(self):
        results = copy.deepcopy(self.blob['results'])
        results[0]['value'], results[0]['lowConfidence'] = '19', True
        s = score.score(self.expected, results)
        self.assertEqual((s['counts']['values_units'], s['flagged']), (len(self.expected), 1))

    def test_unread_results_are_reported_not_scored(self):
        s = score.score(self.expected, copy.deepcopy(self.blob['results'][1:]), unread=1)
        self.assertEqual((s['matched'], s['missing'], s['unread']), (len(self.expected) - 1, 1, 1))
        self.assertEqual(s['ratios']['values_units'], 1.0)
        t = score.total([s, s])
        self.assertEqual((t['expected'], t['matched'], t['unread']), (2 * len(self.expected), 2 * s['matched'], 2))

    def test_a_wrong_name_still_matches_by_value(self):
        results = copy.deepcopy(self.blob['results'])
        results[0]['name'] = 'Ferrytyna X'
        s = score.score(self.expected, results)
        self.assertEqual((s['missing'], s['counts']['names']), (0, len(self.expected) - 1))

    def test_missing_and_extra(self):
        results = copy.deepcopy(self.blob['results'])
        extra = copy.deepcopy(results[0])
        extra['name'], extra['value'] = 'Transferyna', '250'
        s = score.score(self.expected, results[1:] + [extra])
        self.assertEqual((s['missing'], s['extra']), (1, 1))

    def test_a_method_where_none_is_printed_is_wrong(self):
        expected = copy.deepcopy(self.expected)
        expected[0]['method'] = None  # as if no method were printed for this result
        results = copy.deepcopy(self.blob['results'])
        self.assertEqual(score.score(expected, results)['counts']['method'], len(expected) - 1)
        results[0]['method'] = None
        self.assertEqual(score.score(expected, results)['counts']['method'], len(expected))

    def test_wrong_dates_and_mapped_flags_are_reported(self):
        results = copy.deepcopy(self.blob['results'])
        results[0]['flag'] = 'H'
        results[0]['dates'] = []
        s = score.score(self.expected, results)
        self.assertEqual(s['counts']['mapped_flags'], len(self.expected) - 1)
        self.assertLess(s['counts']['dates'], len(self.expected)) if self.expected[0]['dates'] else None
        self.assertEqual(score.failures(s), [])  # reported, no target

    def test_a_range_of_several_bands(self):
        doc = next(d for d in common.documents() if d['id'].startswith('b1'))
        e = next(x for x in offline.expected(doc) if x['name'].startswith('Cholesterol LDL'))
        whole = ' '.join(e['range_lines'])
        r = lambda text, kind='text', low=None, high=None: {'range': {'text': text, 'kind': kind, 'low': low, 'high': high}}  # noqa: E731
        self.assertTrue(score._range_ok(e, r(whole)))
        self.assertTrue(score._range_ok(e, r(' '.join(e['range_lines'][1:]))))  # the heading left out
        self.assertFalse(score._range_ok(e, r(e['range_lines'][1])))  # one band picked
        self.assertFalse(score._range_ok(e, r(whole, 'lt', '115')))  # bounds from one band
        self.assertFalse(score._range_ok(e, r(whole + ' <40 - dla wszystkich')))  # text not printed
        one = next(x for x in offline.expected(doc) if x['name'].startswith('Cholesterol HDL'))
        self.assertTrue(score._range_ok(one, r('>40', 'gt', '40')))  # one band: bounds are fine

    def test_dates_are_read_as_printed(self):
        self.assertEqual(common.local('02.03.2026 08:50:00'), '2026-03-02T08:50')
        self.assertEqual(common.local('20-10-2026 07:30'), '2026-10-20T07:30')
        self.assertEqual(common.local('2026-04-10'), '2026-04-10')
        self.assertEqual(common.kind('Data/godz. pobrania'), 'collected')
        self.assertEqual(common.kind('Data wydruku'), 'printed')


if __name__ == '__main__':
    unittest.main()
