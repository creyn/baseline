"""Checks of the generated files. Needs requirements.txt and DejaVu Sans, so it runs in CI.
Without them every test is skipped. Run: python3 -m unittest discover -s evals/synthetic
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import describe  # noqa: E402

try:
    import generate
    import pypdfium2
    generate.register_fonts()
    MISSING = None
except (ImportError, SystemExit) as e:  # no reportlab, Pillow, pypdfium2 or font here
    MISSING = str(e) or 'dependencies missing'


def pdf_text(path_or_bytes):
    doc = pypdfium2.PdfDocument(path_or_bytes)
    try:
        return ['\n'.join(doc[i].get_textpage().get_text_bounded().split()) for i in range(len(doc))], len(doc)
    finally:
        doc.close()


def squash(s):
    return ''.join(s.split())


@unittest.skipIf(MISSING, f'generator dependencies: {MISSING}')
class GenerateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out1, cls.out2 = os.path.join(cls.tmp.name, '1'), os.path.join(cls.tmp.name, '2')
        generate.main(['--out', cls.out1])
        generate.main(['--out', cls.out2])
        cls.docs = describe.load_all()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_two_runs_give_identical_files(self):
        with open(os.path.join(self.out1, 'sha256.json')) as a, open(os.path.join(self.out2, 'sha256.json')) as b:
            self.assertEqual(json.load(a), json.load(b))

    def test_every_form_is_written(self):
        for d in self.docs:
            files = os.listdir(os.path.join(self.out1, d['id']))
            self.assertIn('truth.json', files)
            self.assertEqual('text.pdf' in files, 'text' in d['forms'], d['id'])
            self.assertEqual('scan.pdf' in files, 'scan' in d['forms'], d['id'])
            photos = [f for f in files if f.startswith('photo-')]
            self.assertEqual(len(photos), len(d['pages']) if 'photo' in d['forms'] else 0, d['id'])

    def test_rendered_page_holds_the_whole_truth(self):
        # The text PDF of every document, also of those published only as a scan or a photo,
        # because the scan and the photo are rendered from it.
        for d in self.docs:
            pages, count = pdf_text(generate.text_pdf(d))
            self.assertEqual(count, len(d['pages']), d['id'])
            text = squash(''.join(pages))
            for s in describe.must_keep(d) + describe.must_remove(d) + d.get('known_gaps', []):
                self.assertIn(squash(s), text, f'{d["id"]}: {s}')
            for r in describe.results(d):
                self.assertIn(squash(r['name']), text, f'{d["id"]}: {r["name"]}')

    def test_every_page_lists_its_barcode_stamp_and_signature(self):
        for d in self.docs:
            with open(os.path.join(self.out1, d['id'], 'truth.json'), encoding='utf-8') as f:
                marks = json.load(f)['marks_to_remove']
            for p in range(1, len(d['pages']) + 1):
                self.assertEqual(sorted(m['kind'] for m in marks if m['page'] == p), ['barcode', 'signature', 'stamp'], d['id'])

    def test_continuation_page_has_no_table_header(self):
        header_word = {'A': 'FLAGA', 'B': 'Procedura/', 'C': 'Zakresreferencyjny'}
        for d in self.docs:
            pages, _ = pdf_text(generate.text_pdf(d))
            for page, text in zip(d['pages'], pages):
                self.assertEqual(header_word[d['layout']] in squash(text), page['table_header'], d['id'])

    def test_scan_has_one_image_page_per_page(self):
        for d in self.docs:
            path = os.path.join(self.out1, d['id'], 'scan.pdf')
            if os.path.exists(path):
                pages, count = pdf_text(path)
                self.assertEqual(count, len(d['pages']), d['id'])
                self.assertEqual(squash(''.join(pages)), '', f'{d["id"]}: a scan must have no text layer')

    def test_truth_matches_the_description(self):
        for d in self.docs:
            with open(os.path.join(self.out1, d['id'], 'truth.json'), encoding='utf-8') as f:
                t = json.load(f)
            self.assertEqual(t['results'], describe.expected_extraction(d))
            self.assertNotIn(d['patient']['birth_date'], t['must_keep'])


if __name__ == '__main__':
    unittest.main()
