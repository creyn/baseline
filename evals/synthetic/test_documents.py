"""Checks of the descriptions. Standard library only. Run: python3 -m unittest discover -s evals/synthetic"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import describe  # noqa: E402

REPO = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))


class DescriptionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = describe.load_all()
        cls.pesel = describe.allowed_pesel(REPO)

    def test_there_are_documents_in_every_layout_and_form(self):
        self.assertGreaterEqual(len(self.docs), 12)
        self.assertEqual({d['layout'] for d in self.docs}, describe.LAYOUTS)
        self.assertEqual({f for d in self.docs for f in d['forms']}, describe.FORMS)

    def test_every_description_is_valid(self):
        for d in self.docs:
            self.assertEqual(describe.problems(d, self.pesel), [], d['_file'])

    def test_ids_are_unique(self):
        ids = [d['id'] for d in self.docs]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_trap_appears_somewhere(self):
        used = {t for d in self.docs for t in d['traps']}
        self.assertEqual(used, describe.TRAPS)

    def test_traps_are_really_in_the_document(self):
        for d in self.docs:
            pages = d['pages']
            if 'continuation_page' in d['traps']:
                self.assertTrue(len(pages) > 1 and not all(p['table_header'] for p in pages), d['id'])
            if 'staff_in_table' in d['traps']:
                self.assertTrue(any(s['in_table'] for s in d['staff']), d['id'])
            comments = [c for p in pages for s in p['sections'] for c in s.get('comment', [])]
            if 'long_number_in_table' in d['traps']:
                self.assertTrue(any(len(n) >= 11 for c in comments for n in c.split() if n.isdigit()), d['id'])
            if 'name_in_table_comment' in d['traps']:
                gap = [c for c in comments if d['patient']['name'] in c]
                self.assertTrue(gap, d['id'])
                self.assertEqual(d.get('known_gaps'), gap, d['id'])
                self.assertIn(d['patient']['name'], describe.must_remove(d), 'a known gap must not excuse the name elsewhere')
            res = describe.results(d)
            if 'condition' in d['traps']:
                self.assertTrue(any(r.get('condition') for r in res), d['id'])
            if 'qualitative' in d['traps']:
                self.assertTrue(any(not any(ch.isdigit() for ch in r['value']) for r in res), d['id'])
            if 'less_than_range' in d['traps']:
                self.assertTrue(any((r.get('range') or '').startswith('<') or r['value'].startswith('<') for r in res), d['id'])
            if 'text_range' in d['traps']:
                self.assertTrue(any(r.get('range_lines') for r in res), d['id'])
            if 'flag_disagrees' in d['traps']:
                self.assertTrue(any('computed_flag' in r and r['computed_flag'] != r.get('flag') for r in res), d['id'])

    def test_unit_change_has_a_pair(self):
        units = {}
        for d in self.docs:
            for r in describe.results(d):
                if r.get('material') == 'mocz':
                    continue  # glucose in urine is another parameter (ADR-0011)
                key = r['name'].split(' ')[0].lower()
                units.setdefault(key, set()).add(r['unit'])
        self.assertIn({'µIU/ml', 'mIU/l'}, units.values())
        self.assertTrue({'mg/dl', 'mmol/l'} <= units['glukoza'])

    def test_generated_files_are_ignored_by_git(self):
        import subprocess
        for path in ('evals/synthetic/out/a/text.pdf', 'evals/synthetic/out/a/photo-1.jpg', 'evals/synthetic/out/index.html',
                     'docs/scan.png', 'anything/real.pdf'):
            r = subprocess.run(['git', '-C', REPO, 'check-ignore', '-q', path])
            self.assertEqual(r.returncode, 0, f'{path} must be ignored')

    def test_truth_is_complete(self):
        for d in self.docs:
            remove, keep = describe.must_remove(d), describe.must_keep(d)
            self.assertIn(self.pesel, remove)
            self.assertNotIn(d['patient']['birth_date'], keep)
            self.assertTrue(keep)
            for r in describe.expected_extraction(d):
                self.assertTrue(r['value'] and r['name'])


if __name__ == '__main__':
    unittest.main()
