"""Groq key inspection.

Groq's ``x-ratelimit-*`` headers follow the same convention as OpenAI, so the
shared bucket collector in :class:`Provider` is reused.
"""

from __future__ import annotations

from ..http import request
from ..models import KeyLimits
from .base import Provider, register

BUCKETS = {
    "requests": ("x-ratelimit-limit-requests", "requests"),
    "tokens": ("x-ratelimit-limit-tokens", "tokens"),
}



@register
class GroqProvider(Provider):
    name = "groq"
    label = "Groq"
    env_vars = ("GROQ_API_KEY",)
    base_url = "https://api.groq.com/openai/v1"

    def auth_headers(self):
        return {"Authorization": f"Bearer {self.key}"}

    def check(self) -> KeyLimits:
        result = KeyLimits(provider=self.name, key=self.key)
        headers = dict(self.auth_headers())

        response = request(
            f"{self.base_url}/chat/completions",
            method="POST",
            headers=headers,
            json_body={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
            },
            timeout=self.timeout,
        )

        if response.status in (0, 401, 403):
            probe = request(f"{self.base_url}/models", headers=headers, timeout=self.timeout)
            result.status = probe.status
            result.message = self._error_message(probe)
            self.set_valid_from_status(result, probe.status)
            return result

        result.status = response.status
        result.headers = response.headers
        result.message = self._error_message(response)
        self.set_valid_from_status(result, response.status)
        result.buckets = self.collect_buckets(response.headers, BUCKETS)

        if response.status == 200 and response.json():
            data = response.json()
            result.detail("Checks out", f"model={data.get('model', 'llama')}")

        if not result.buckets:
            result.detail("Note", "no rate-limit headers returned")
        if response.status != 200:
            result.raw = response.json()
        return result

    @staticmethod
    def _error_message(response) -> str:
        if response.ok:
            return ""
        data = response.json()
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])
            if data.get("message"):
                return str(data["message"])
        return response.text[:300]