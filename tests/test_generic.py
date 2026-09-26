"""Tests for the generic provider's header scanning."""

import unittest

from keylimits.providers.generic import GenericProvider


class GenericScanTests(unittest.TestCase):
    def test_scan(self):
        headers = {
            "X-RateLimit-Limit-Tokens": "100000",
            "X-RateLimit-Remaining-Tokens": "500",
            "X-RateLimit-Reset-Tokens": "20",
            "Content-Type": "application/json",
        }
        buckets = GenericProvider._scan_headers(headers)
        self.assertEqual(len(buckets), 1)
        self.assertEqual(buckets[0].name, "tokens")
        self.assertEqual(buckets[0].limit, 100000)
        self.assertEqual(buckets[0].remaining, 500)
        self.assertEqual(buckets[0].reset, "20")


if __name__ == "__main__":
    unittest.main()