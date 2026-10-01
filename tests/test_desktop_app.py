import unittest

from desktop.app import MAX_KEYS, parse_keys


class ParseKeysTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_keys("a\nb\nc"), ["a", "b", "c"])

    def test_ignores_blank_and_comments(self):
        self.assertEqual(parse_keys("# comment\n\na\n  \nb"), ["a", "b"])

    def test_empty(self):
        self.assertEqual(parse_keys(""), [])
        self.assertEqual(parse_keys(None), [])

    def test_strips_whitespace(self):
        self.assertEqual(parse_keys("  a  \n\tb\t"), ["a", "b"])

    def test_caps(self):
        text = "\n".join(f"k{i}" for i in range(MAX_KEYS + 20))
        self.assertEqual(len(parse_keys(text)), MAX_KEYS)


if __name__ == "__main__":
    unittest.main()