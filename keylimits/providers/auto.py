"""Auto-detect a provider from the shape of the API key, then probe it."""

from __future__ import annotations

from typing import Optional, Type

from ..models import KeyLimits
from .base import Provider, register
from .anthropic import AnthropicProvider
from .gemini import GeminiProvider
from .groq import GroqProvider
from .openai import OpenAIProvider
from .tokenharbor import TokenHarborProvider

# Ordered (prefix-fragment, provider) pairs. Longest/most specific first.
_PREFIXES = (
    ("sk-ant-", AnthropicProvider),
    ("thk_live_", TokenHarborProvider),
    ("thk_test_", TokenHarborProvider),
    ("gsk_", GroqProvider),
    ("AIza", GeminiProvider),
    ("sk-proj-", OpenAIProvider),
    ("sk-svcacct-", OpenAIProvider),
    ("sk-", OpenAIProvider),
)


def guess_provider(key: str) -> Optional[Type[Provider]]:
    for prefix, provider in _PREFIXES:
        if key.startswith(prefix):
            return provider
    return None


@register
class AutoProvider(Provider):
    name = "auto"
    label = "Auto-detect"
    env_vars = (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "TOKENHARBOR_API_KEY",
        "TH_API_KEY",
        "API_KEY",
    )

    def __init__(self, key: str, base_url: Optional[str] = None, timeout: float = 30.0, *, model: Optional[str] = None):
        super().__init__(key, base_url, timeout)
        self.detected: Optional[Type[Provider]] = guess_provider(key)
        self.model = model

    def auth_headers(self):
        return {}

    def check(self) -> KeyLimits:
        if self.detected is None:
            result = KeyLimits(provider=self.name, key=self.key)
            result.message = (
                "Could not recognise the key format. "
                "Pass --provider explicitly (openai, anthropic, groq, gemini, tokenharbor, generic)."
            )
            return result

        if self.detected is TokenHarborProvider:
            delegate = self.detected(self.key, base_url=self.base_url or None, timeout=self.timeout, model=self.model)
        else:
            delegate = self.detected(self.key, base_url=self.base_url or None, timeout=self.timeout)
        result = delegate.check()
        result.detail("Detected as", self.detected.label)
        return result