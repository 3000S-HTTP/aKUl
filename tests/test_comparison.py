import unittest

from keylimits.comparison import (
    best_index,
    best_remaining_pct,
    build_comparison,
    collect_bucket_names,
    serialize_key,
)
from keylimits.models import Allowance, Bucket, KeyLimits


def make_key(provider="openai", valid=True, limit=None, remaining=None, used_pct=None, reset=None):
    return KeyLimits(
        provider=provider,
        key="thk_live_x",
        valid=valid,
        status=200 if valid else 401,
        buckets=[Bucket(name="requests", limit=limit, remaining=remaining, reset=reset)],
        allowance=Allowance(used_pct=used_pct, resets_at="2026-10-02T18:32:55+00:00", plan="free"),
    )


class SerializeTests(unittest.TestCase):
    def test_shape(self):
        data = serialize_key(make_key(limit=10, remaining=5, used_pct=40))
        self.assertEqual(data["provider"], "openai")
        self.assertTrue(data["valid"])
        self.assertEqual(data["buckets"][0]["limit"], 10)
        self.assertAlmostEqual(data["allowance"]["remaining_pct"], 60.0)

    def test_no_allowance(self):
        result = make_key()
        result.allowance = None
        self.assertIsNone(serialize_key(result)["allowance"])


class WinnerTests(unittest.TestCase):
    def test_bucket_names_union(self):
        a = serialize_key(make_key(limit=10, remaining=8))
        b = serialize_key(make_key(limit=20, remaining=15))
        b["buckets"][0]["name"] = "tokens"
        self.assertEqual(collect_bucket_names([a, b]), ["requests", "tokens"])

    def test_best_index(self):
        a = serialize_key(make_key(limit=10, remaining=2))
        b = serialize_key(make_key(limit=10, remaining=9))
        self.assertEqual(best_index([a, b], "requests"), 1)

    def test_best_index_ignores_missing(self):
        a = serialize_key(make_key())  # remaining None
        b = serialize_key(make_key(limit=5, remaining=1))
        self.assertEqual(best_index([a, b], "requests"), 1)

    def test_best_index_none(self):
        a = serialize_key(make_key())
        self.assertIsNone(best_index([a], "requests"))

    def test_best_remaining_pct(self):
        a = serialize_key(make_key(used_pct=90))  # 10% left
        b = serialize_key(make_key(used_pct=10))  # 90% left
        self.assertEqual(best_remaining_pct([a, b]), 1)

    def test_best_remaining_pct_none(self):
        result = make_key()
        result.allowance = None
        self.assertIsNone(best_remaining_pct([serialize_key(result)]))


class BuildComparisonTests(unittest.TestCase):
    def test_summary(self):
        keys = [
            serialize_key(make_key(valid=True, limit=10, remaining=3, used_pct=20)),
            serialize_key(make_key(valid=False, limit=10, remaining=None, used_pct=80)),
        ]
        data = build_comparison(keys)
        self.assertEqual(data["key_count"], 2)
        self.assertEqual(data["valid_count"], 1)
        self.assertEqual(data["winners"]["requests"], 0)
        self.assertEqual(data["winners"]["free allowance"], 0)

    def test_empty(self):
        data = build_comparison([])
        self.assertEqual(data["key_count"], 0)
        self.assertEqual(data["winners"], {})
        self.assertEqual(data["valid_count"], 0)


if __name__ == "__main__":
    unittest.main()