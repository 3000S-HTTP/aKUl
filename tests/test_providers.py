import unittest

from keylimits.models import KeyLimits
from keylimits.providers.auto import guess_provider
from keylimits.providers.anthropic import AnthropicProvider
from keylimits.providers.gemini import GeminiProvider
from keylimits.providers.groq import GroqProvider
from keylimits.providers.openai import OpenAIProvider
from keylimits.providers.tokenharbor import TokenHarborProvider


class DetectTests(unittest.TestCase):
    def test_openai(self):
        self.assertIs(guess_provider("sk-proj-abc"), OpenAIProvider)
        self.assertIs(guess_provider("sk-abc"), OpenAIProvider)

    def test_anthropic(self):
        self.assertIs(guess_provider("sk-ant-api03-xyz"), AnthropicProvider)

    def test_groq(self):
        self.assertIs(guess_provider("gsk_abc"), GroqProvider)

    def test_gemini(self):
        self.assertIs(guess_provider("AIzaSyAbc"), GeminiProvider)

    def test_tokenharbor(self):
        self.assertIs(guess_provider("thk_live_abcdef"), TokenHarborProvider)

    def test_unknown(self):
        self.assertIsNone(guess_provider("totally-opaque-key"))


class HeaderParsingTests(unittest.TestCase):
    def test_buckets(self):
        headers = {
            "x-ratelimit-limit-requests": "10000",
            "x-ratelimit-remaining-requests": "9999",
            "x-ratelimit-reset-requests": "1s",
        }
        buckets = OpenAIProvider.collect_buckets(
            headers, {"requests": ("x-ratelimit-limit-requests", "requests")}
        )
        self.assertEqual(len(buckets), 1)
        self.assertEqual(buckets[0].limit, 10000)
        self.assertEqual(buckets[0].remaining, 9999)
        self.assertEqual(buckets[0].reset, "1s")

    def test_anthropic_reset_normalised(self):
        self.assertEqual(AnthropicProvider.parse_reset("2026-09-26T10:30:00Z"), "2026-09-26 10:30")


class TokenHarborAllowanceTests(unittest.TestCase):
    class _FakeResponse:
        def __init__(self, body, headers):
            self.body = body
            self.headers = headers

        def json(self):
            return self.body

        def header(self, name):
            lowered = {k.lower(): v for k, v in self.headers.items()}
            return lowered.get(name.lower())

        @property
        def ok(self):
            return True

        status = 200
        text = ""

    def _result(self, headers):
        provider = TokenHarborProvider("thk_live_x")
        result = KeyLimits(provider="tokenharbor", key="thk_live_x")
        provider._probe_allowance(result, {"Authorization": "Bearer x"}, ["mimo:free"])
        return result

    def test_models_list(self):
        response = self._FakeResponse({"data": [{"id": "a:free"}, {"id": "b"}]}, {})
        self.assertEqual(TokenHarborProvider._models(response), ["a:free", "b"])

    def test_probe_allowance_from_headers(self):
        import keylimits.providers.tokenharbor as module

        captured = {}

        def fake_request(url, **kwargs):
            captured["url"] = url
            return self._FakeResponse(
                {"choices": [{"message": {"content": "hi"}}]},
                {
                    "X-Th-Free-Used-Pct": "42",
                    "X-Th-Free-Resets": "2026-10-02T18:32:55+00:00",
                    "X-Th-Plan": "free",
                },
            )

        original = module.request
        module.request = fake_request
        try:
            result = self._result({})
        finally:
            module.request = original

        self.assertIsNotNone(result.allowance)
        self.assertEqual(result.allowance.used_pct, 42.0)
        self.assertEqual(result.allowance.remaining_pct, 58.0)
        self.assertEqual(result.allowance.plan, "free")


if __name__ == "__main__":
    unittest.main()