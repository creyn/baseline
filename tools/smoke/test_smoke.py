"""Offline tests of the smoke test's own parts: no Azure."""
import io
import json
import os
import re
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extractor_smoke as smoke  # noqa: E402
from extractor.pages import Page, read_zip  # noqa: E402

UUID7 = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')


class SmokeTest(unittest.TestCase):
    def test_uuid7(self):
        ids = {smoke.uuid7() for _ in range(100)}
        self.assertEqual(len(ids), 100)
        self.assertTrue(all(UUID7.match(i) for i in ids))
        self.assertTrue(smoke.uuid7(now_ms=1_700_000_000_000).startswith('018bcfe5-6800-7'))

    def test_the_zip_is_what_the_extractor_reads(self):
        import hashlib
        png = b'fake png'
        page = Page(1, hashlib.sha256(png).hexdigest(), png)
        data = smoke.clean_zip([page])
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(z.getinfo('manifest.json').compress_type, zipfile.ZIP_STORED)
            self.assertEqual(json.loads(z.read('manifest.json'))['order'], [page.sha256])
        self.assertEqual([p.sha256 for p in read_zip(data)], [page.sha256])

    def test_the_message_follows_the_contract(self):
        msg = smoke.extract_requested(smoke.uuid7(), smoke.uuid7(), smoke.uuid7())
        self.assertEqual(smoke.errors('messages.v1', msg), [])
        self.assertNotEqual(smoke.errors('messages.v1', {**msg, 'userId': 'not-a-uuid'}), [])

    def test_a_refusal_is_retried_until_the_wait_is_over(self):
        class Refused(Exception):
            status_code = 403
        calls, now = [], [0]

        def call():
            calls.append(1)
            if len(calls) < 3:
                raise Refused()
            return 'done'
        self.assertEqual(smoke.until_roles(call, 100, pause=10, clock=lambda: now[0],
                                           sleep=lambda s: now.__setitem__(0, now[0] + s)), 'done')
        self.assertEqual(len(calls), 3)
        with self.assertRaises(Refused):
            smoke.until_roles(lambda: (_ for _ in ()).throw(Refused()), 20, pause=10, clock=lambda: now[0],
                              sleep=lambda s: now.__setitem__(0, now[0] + s))
        with self.assertRaises(ValueError):  # anything else is not retried
            smoke.until_roles(lambda: (_ for _ in ()).throw(ValueError()), 100, clock=lambda: 0, sleep=lambda s: None)

    def test_the_default_test_user_is_a_uuid7(self):
        with open(os.path.join(smoke._ROOT, 'infra', 'main.bicep')) as f:
            bicep = f.read()
        user = re.search(r"param smokeUserId string = '([^']+)'", bicep).group(1)
        self.assertTrue(UUID7.match(user))


if __name__ == '__main__':
    unittest.main()
