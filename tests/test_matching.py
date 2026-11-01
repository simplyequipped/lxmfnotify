import os
import tempfile
import unittest

from lxmfnotify.reader import Matcher, load_pattern_file


class MatchingTests(unittest.TestCase):
    def test_plain_substring(self):
        m = Matcher(["N0CALL", "W1ABC"])
        self.assertTrue(m.matches("033215 -12  0.3 7.078512 normal N0CALL: HELLO"))
        self.assertFalse(m.matches("033215 -12  0.3 7.078512 normal W1AW: HELLO"))
        self.assertFalse(m.matches("n0call lower case"))

    def test_regex(self):
        m = Matcher([], [r"normal\s+[A-Z0-9]+:"])
        self.assertTrue(m.matches("033215 -12 0.3 7.078512 normal N0CALL: HELLO"))
        self.assertFalse(m.matches("033215 -12 0.3 7.078512 fast N0CALL: HELLO"))

    def test_plain_and_regex_together(self):
        m = Matcher(["W1AW"], [r"SNR [+-]0[0-9]$"])
        self.assertTrue(m.matches("N0CALL: W1AW HEARTBEAT SNR -18"))
        self.assertTrue(m.matches("N0CALL: K1ABC HEARTBEAT SNR +02"))
        self.assertFalse(m.matches("N0CALL: K1ABC HEARTBEAT SNR -18"))

    def test_no_patterns_matches_everything(self):
        m = Matcher([])
        self.assertTrue(m.matches("anything"))
        self.assertTrue(m.matches(""))

    def test_one_line_two_patterns_is_one_match(self):
        m = Matcher(["N0CALL", "HELLO"])
        line = "N0CALL: HELLO"
        self.assertEqual(sum(1 for _ in [line] if m.matches(_)), 1)

    def test_pattern_file(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("# comment\n\nN0CALL  \nW1ABC\n   \n/SNR [+-]0[0-9]$/\n/\n")
            path = f.name
        try:
            patterns, regexes = load_pattern_file(path)
        finally:
            os.unlink(path)
        self.assertEqual(patterns, ["N0CALL", "W1ABC", "/"])
        self.assertEqual(regexes, ["SNR [+-]0[0-9]$"])


if __name__ == "__main__":
    unittest.main()
