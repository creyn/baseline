"""Tests for scan.py. All data here is fictional; valid PESEL numbers are generated, never written down."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import scan  # noqa: E402

# Built at run time, so this file itself passes the scan.
REAL_LOOKING = "jan.testowy" + "@" + "poczta.pl"


def make_pesel(prefix: str) -> str:
    weights = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
    check = (10 - sum(w * int(c) for w, c in zip(weights, prefix)) % 10) % 10
    return prefix + str(check)


class PeselTest(unittest.TestCase):
    def test_valid_checksum_is_found(self):
        self.assertIn("valid PESEL", scan.scan_line("id " + make_pesel("9001010000"), []))

    def test_wrong_checksum_is_ignored(self):
        p = make_pesel("9001010000")
        wrong = p[:10] + str((int(p[10]) + 1) % 10)
        self.assertEqual(scan.scan_line(wrong, []), [])

    def test_impossible_date_is_ignored(self):
        self.assertEqual(scan.scan_line(make_pesel("9013450000"), []), [])

    def test_allowlisted_example_is_ignored(self):
        self.assertEqual(scan.scan_line("PESEL: 44051401359", []), [])

    def test_longer_number_is_ignored(self):
        self.assertEqual(scan.scan_line("1" + make_pesel("9001010000"), []), [])


class EmailTest(unittest.TestCase):
    def test_personal_address_is_found(self):
        self.assertIn("e-mail address", scan.scan_line(REAL_LOOKING, []))

    def test_allowed_addresses_pass(self):
        for a in ("7542275+creyn@users.noreply.github.com", "someone@example.com", "jan@lab.test", "noreply@anthropic.com"):
            self.assertEqual(scan.scan_line(a, []), [], a)


class SecretTest(unittest.TestCase):
    def test_connection_string(self):
        self.assertIn("Azure connection string", scan.scan_line("AccountKey=" + "A" * 40, []))

    def test_private_key(self):
        self.assertIn("private key", scan.scan_line("-----BEGIN " + "RSA PRIVATE KEY-----", []))

    def test_github_token(self):
        self.assertIn("GitHub token", scan.scan_line("ghp_" + "a" * 36, []))


class DenylistTest(unittest.TestCase):
    def test_whole_word_only(self):
        self.assertIn("word from the deny list", scan.scan_line("Patient: Testowy", ["testowy"]))
        self.assertEqual(scan.scan_line("Testowyx", ["testowy"]), [])


class DiffTest(unittest.TestCase):
    def test_only_added_lines_with_numbers(self):
        diff = "+++ b/a.md\n@@ -1,0 +3,2 @@\n+one\n+two\n"
        self.assertEqual(scan.added_lines(diff), {"a.md": [(3, "one"), (4, "two")]})

    def test_binary_and_vendor_files_are_skipped(self):
        self.assertEqual(scan.scan_lines("x/vendor/lib.js", [(1, REAL_LOOKING)], []), [])
        self.assertEqual(scan.scan_lines("img.png", [(1, REAL_LOOKING)], []), [])

    def test_finding_never_prints_the_match(self):
        f = scan.scan_lines("a.md", [(1, REAL_LOOKING)], [])[0]
        self.assertNotIn("testowy", str(f))


if __name__ == "__main__":
    unittest.main()
