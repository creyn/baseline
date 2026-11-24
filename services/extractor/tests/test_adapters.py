"""The pydantic answer and the PDF builder. They need requirements.txt, so they run in CI
and are skipped where the packages are missing."""
import io
import json
import unittest

try:
    import pydantic  # noqa: F401
    from PIL import Image
    from extractor import answer
    from extractor.azure_clients import pdf_of
    HAVE_PACKAGES = True
except ImportError:
    HAVE_PACKAGES = False

from extractor.pages import Page
from tests import fakes


@unittest.skipUnless(HAVE_PACKAGES, 'needs services/extractor/requirements.txt')
class Answer(unittest.TestCase):
    def test_parse(self):
        parsed = answer.parse(json.dumps(fakes.iron_answer()))
        self.assertEqual(parsed, fakes.iron_answer())

    def test_extra_fields_are_refused(self):
        bad = fakes.iron_answer()
        bad['results'][0]['flag'] = 'H'
        with self.assertRaises(pydantic.ValidationError):
            answer.parse(json.dumps(bad))

    def test_unknown_date_kind(self):
        bad = fakes.iron_answer()
        bad['documentDates'][0]['kind'] = 'birth'
        with self.assertRaises(pydantic.ValidationError):
            answer.parse(json.dumps(bad))

    def test_schema_fits_strict_structured_output(self):
        """Strict structured output needs every property required and no extra properties."""
        schema = answer.Answer.model_json_schema()
        objects = [schema] + list(schema.get('$defs', {}).values())
        for obj in objects:
            with self.subTest(obj=obj.get('title')):
                self.assertEqual(set(obj['required']), set(obj['properties']))
                self.assertIs(obj.get('additionalProperties'), False)
                for prop in obj['properties'].values():
                    self.assertNotIn('default', prop)


@unittest.skipUnless(HAVE_PACKAGES, 'needs services/extractor/requirements.txt')
class Pdf(unittest.TestCase):
    def test_one_pdf_page_per_png_in_order(self):
        pages = []
        for i, colour in enumerate(('white', 'black'), 1):
            buffer = io.BytesIO()
            Image.new('RGB', (40, 60), colour).save(buffer, format='PNG')
            pages.append(Page(i, '0' * 64, buffer.getvalue()))
        pdf = pdf_of(pages)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(pdf.count(b'/Type /Page\n') + pdf.count(b'/Type /Page\r') + pdf.count(b'/Type /Page '), 2)


if __name__ == '__main__':
    unittest.main()
