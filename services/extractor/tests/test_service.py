"""The service shell with fake blobs and a fake queue: idempotency, retries, statuses, logs."""
import json
import unittest

from extractor import core, service
from tests import fakes

IDS = {'userId': '019ab3c4-1a2b-7c3d-8e4f-5a6b7c8d9e0f', 'docId': '019ab3c4-5d6e-7f80-9a1b-2c3d4e5f6a7b',
       'verId': '019ab3c4-6e7f-7081-8b2c-3d4e5f6a7b8c'}
PAGES = [fakes.page(1, 1)]


def body(**changes):
    return json.dumps({'type': 'ExtractRequested', 'schemaVersion': '1.0', **IDS, **changes}).encode()


class Extractor:
    """A bound core.extract with fake services; counts calls to the AI services."""

    def __init__(self, *answers, layout_error=None):
        self.layout = fakes.FakeLayout([fakes.IRON_PAGE])
        self.llm = fakes.FakeLlm(*answers)
        self.layout_error = layout_error

    def __call__(self, pages, ids):
        if self.layout_error:
            raise self.layout_error
        return core.extract(pages, self.layout, self.llm, doc_id=ids['docId'], ver_id=ids['verId'], model='m')


def handle(store, status, extract, delivery=1, msg=None):
    return service.handle(msg or body(), delivery, store, status, extract)


class Service(unittest.TestCase):
    def setUp(self):
        self.store = fakes.FakeStore(clean=fakes.clean_zip(PAGES))
        self.status = fakes.FakeStatus()

    def test_extracted(self):
        extract = Extractor(fakes.iron_answer())
        self.assertEqual(handle(self.store, self.status, extract), service.COMPLETE)
        self.assertEqual(self.status.sent, [{'type': 'Extracted', 'schemaVersion': '1.0', **IDS}])
        self.assertEqual(json.loads(self.store.text)['results'][0]['value'], '18')

    def test_a_second_delivery_does_not_call_the_ai_services(self):
        self.store.text = b'{}'
        extract = Extractor()
        self.assertEqual(handle(self.store, self.status, extract), service.COMPLETE)
        self.assertEqual((extract.layout.calls, extract.llm.calls), (0, []))
        self.assertEqual(self.status.sent[0]['type'], 'Extracted')

    def test_a_parallel_run_wrote_first(self):
        extract = Extractor(fakes.iron_answer())
        original = self.store.write_text_if_absent

        def other_run_first(ids, data):
            self.store.text = b'theirs'
            return original(ids, data)
        self.store.write_text_if_absent = other_run_first
        self.assertEqual(handle(self.store, self.status, extract), service.COMPLETE)
        self.assertEqual(self.store.text, b'theirs')
        self.assertEqual(self.status.sent[0]['type'], 'Extracted')

    def test_the_version_was_deleted(self):
        self.store.clean = None
        self.assertEqual(handle(self.store, self.status, Extractor()), service.COMPLETE)
        self.assertEqual(self.status.sent, [])

    def test_transient_errors_until_the_fifth_delivery(self):
        for delivery in (1, 2, 3, 4):
            with self.subTest(delivery=delivery):
                extract = Extractor(layout_error=service.Transient('down'))
                self.assertEqual(handle(self.store, self.status, extract, delivery), service.ABANDON)
        self.assertEqual(self.status.sent, [])
        extract = Extractor(layout_error=service.Transient('down'))
        self.assertEqual(handle(self.store, self.status, extract, 5), service.COMPLETE)
        self.assertEqual(self.status.sent, [{'type': 'Failed', 'schemaVersion': '1.0', **IDS, 'reason': 'extract_error'}])

    def test_an_unexpected_error_fails_at_once(self):
        extract = Extractor(layout_error=ValueError('a message that could quote the page'))
        with self.assertLogs('extractor', level='ERROR') as logs:
            self.assertEqual(handle(self.store, self.status, extract, 1), service.COMPLETE)
        self.assertEqual(self.status.sent[0]['reason'], 'extract_error')
        self.assertNotIn('quote the page', ' '.join(logs.output))

    def test_the_last_delivery_reports_saved_results(self):
        class SavedMeanwhile(fakes.FakeStore):
            checks = 0

            def text_exists(self, ids):
                self.checks += 1
                return self.checks > 1
        store = SavedMeanwhile(clean=fakes.clean_zip(PAGES))
        extract = Extractor(layout_error=service.Transient('down'))
        self.assertEqual(handle(store, self.status, extract, 5), service.COMPLETE)
        self.assertEqual(self.status.sent[0]['type'], 'Extracted')

    def test_identifiers_that_are_not_uuids_are_not_logged(self):
        with self.assertLogs('extractor', level='ERROR') as logs:
            self.assertEqual(handle(self.store, self.status, Extractor(), msg=body(docId='Jan Testowy')), service.DEAD_LETTER)
        self.assertNotIn('Testowy', ' '.join(logs.output) + str(vars(logs.records[0])))

    def test_status_queue_down(self):
        status = fakes.FakeStatus(fail=service.Transient('down'))
        self.assertEqual(handle(self.store, status, Extractor(fakes.iron_answer())), service.ABANDON)
        self.assertIsNotNone(self.store.text)  # the next delivery reports from the saved blob

    def test_invalid_answer(self):
        bad = fakes.iron_answer(ferritin='16')
        self.assertEqual(handle(self.store, self.status, Extractor(bad, bad)), service.COMPLETE)
        self.assertEqual(self.status.sent[0]['reason'], 'extract_invalid')
        self.assertIsNone(self.store.text)

    def test_no_results(self):
        self.assertEqual(handle(self.store, self.status, Extractor(fakes.EMPTY)), service.COMPLETE)
        self.assertEqual(self.status.sent[0]['reason'], 'no_results')
        self.assertIsNone(self.store.text)

    def test_a_broken_clean_zip(self):
        self.store.clean = b'not a zip'
        self.assertEqual(handle(self.store, self.status, Extractor()), service.COMPLETE)
        self.assertEqual(self.status.sent[0]['reason'], 'extract_error')

    def test_messages_that_go_to_the_dead_letter_queue(self):
        for msg in (b'not json', body(schemaVersion='2.0'), body(type='Extracted'),
                    body(userId='3f2b8c1e-5a4d-4e6f-9b7a-1c2d3e4f5a6b'), json.dumps({'type': 'ExtractRequested'}).encode()):
            with self.subTest(msg=msg[:40]):
                self.assertEqual(handle(self.store, self.status, Extractor(), msg=msg), service.DEAD_LETTER)

    def test_a_newer_minor_version_is_accepted(self):
        self.assertEqual(handle(self.store, self.status, Extractor(fakes.iron_answer()), msg=body(schemaVersion='1.4')),
                         service.COMPLETE)

    def test_logs_carry_identifiers_never_content(self):
        bad = fakes.iron_answer(ferritin='16')
        with self.assertLogs('extractor', level='INFO') as logs:
            handle(self.store, self.status, Extractor(bad, bad))
            handle(fakes.FakeStore(clean=fakes.clean_zip(PAGES)), self.status, Extractor(fakes.iron_answer()))
        for record in logs.records:
            self.assertEqual(record.verId, IDS['verId'])
            self.assertEqual(record.userId, IDS['userId'])
            text = record.getMessage() + json.dumps({k: str(v) for k, v in vars(record).items()})
            for word in ('Ferrytyna', 'ng/ml', '"18"', 'ECLIA'):
                self.assertNotIn(word, text)


if __name__ == '__main__':
    unittest.main()
