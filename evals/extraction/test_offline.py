"""The offline evals and the scoring. Standard library and jsonschema only.

Run from the repository root: python3 -m unittest discover -s evals/extraction
"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import offline  # noqa: E402
import score  # noqa: E402


class Offline(unittest.TestCase):
    def test_every_document_scores_100_percent(self):
        scores = []
        for doc in common.documents():
            with self.subTest(doc=doc['id']):
                blob, _ = offline.run(doc)
                s = score.score(offline.expected(doc), blob['results'])
                self.assertEqual((s['missing'], s['extra']), (0, 0))
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

    def test_dates_are_read_as_printed(self):
        self.assertEqual(common.local('02.03.2026 08:50:00'), '2026-03-02T08:50')
        self.assertEqual(common.local('20-10-2026 07:30'), '2026-10-20T07:30')
        self.assertEqual(common.local('2026-04-10'), '2026-04-10')
        self.assertEqual(common.kind('Data/godz. pobrania'), 'collected')
        self.assertEqual(common.kind('Data wydruku'), 'printed')


if __name__ == '__main__':
    unittest.main()
