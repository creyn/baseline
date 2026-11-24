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



try:
    import openai
    from azure.core.exceptions import HttpResponseError, ResourceExistsError, ServiceRequestError
    from extractor import azure_clients
    from extractor.service import Transient
    HAVE_AZURE = True
except ImportError:
    HAVE_AZURE = False


@unittest.skipUnless(HAVE_AZURE, 'needs services/extractor/requirements.txt')
class Adapters(unittest.TestCase):
    def test_which_errors_are_transient(self):
        def http(status):
            e = HttpResponseError(message='x')
            e.status_code = status
            return e
        self.assertTrue(azure_clients._transient(http(429)))
        self.assertTrue(azure_clients._transient(http(503)))
        self.assertFalse(azure_clients._transient(http(400)))
        self.assertTrue(azure_clients._transient(ServiceRequestError('down')))

    def test_the_openai_errors_we_catch_exist(self):
        for name in ('RateLimitError', 'APIConnectionError', 'APITimeoutError', 'InternalServerError',
                     'LengthFinishReasonError', 'ContentFilterFinishReasonError'):
            self.assertTrue(hasattr(openai, name), name)

    def test_a_blob_written_first_by_another_run_is_kept(self):
        class Blob:
            def upload_blob(self, data, overwrite, content_type):
                assert overwrite is False
                raise ResourceExistsError('exists')

        class Service:
            def get_blob_client(self, container, name):
                assert (container, name) == ('text', 'u/d/v.json')
                return Blob()
        store = azure_clients.BlobStore.__new__(azure_clients.BlobStore)
        store.service = Service()
        self.assertFalse(store.write_text_if_absent({'userId': 'u', 'docId': 'd', 'verId': 'v'}, b'{}'))

    def test_a_storage_outage_is_transient(self):
        store = azure_clients.BlobStore.__new__(azure_clients.BlobStore)

        def down():
            raise ServiceRequestError('down')
        with self.assertRaises(Transient):
            store._call(down)

    def test_status_message_properties(self):
        sent = []

        class Sender:
            def send_messages(self, message):
                sent.append(message)
        azure_clients.StatusSender(Sender()).send({'type': 'Extracted', 'schemaVersion': '1.0', 'userId': 'u',
                                                  'docId': 'd', 'verId': 'v'})
        m = sent[0]
        self.assertEqual(m.subject, 'Extracted')
        self.assertEqual(m.application_properties, {'docId': 'd', 'verId': 'v'})
        self.assertIsNone(m.correlation_id)
        self.assertEqual(json.loads(b''.join(m.body)), {'type': 'Extracted', 'schemaVersion': '1.0', 'userId': 'u',
                                                        'docId': 'd', 'verId': 'v'})


if __name__ == '__main__':
    unittest.main()
