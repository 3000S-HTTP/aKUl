"""Anthropic key inspection.

Anthropic returns unified rate-limit headers on a minimal ``/messages`` call.
The current API version is configurable through ``--api-version``.
"""

from __future__ import annotations

from ..http import request
from ..models import Bucket, KeyLimits
from .base import Provider, register

# header prefix -> bucket label
BUCKET_HEADERS = {
    "anthropic-ratelimit-requests": "requests",
    "anthropic-ratelimit-tokens": "tokens",
    "anthropic-ratelimit-input-tokens": "input tokens",
    "anthropic-ratelimit-output-tokens": "output tokens",
}


@register
class AnthropicProvider(Provider):
    name = "anthropic"
    label = "Anthropic"
    env_vars = ("ANTHROPIC_API_KEY",)
    base_url = "https://api.anthropic.com/v1"
    api_version = "2023-06-01"

    def auth_headers(self):
        return {
            "x-api-key": self.key,
            "anthropic-version": self.api_version,
        }

    def check(self) -> KeyLimits:
        result = KeyLimits(provider=self.name, key=self.key)
        headers = dict(self.auth_headers())

        response = request(
            f"{self.base_url}/messages",
            method="POST",
            headers=headers,
            json_body={
                "model": "claude-3-5-haiku-latest",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}],
            },
            timeout=self.timeout,
        )

        result.status = response.status
        result.headers = response.headers
        result.message = self._error_message(response)
        self.set_valid_from_status(result, response.status)

        if response.status in (401, 403):
            return result

        result.buckets = self._buckets(response.headers)
        if response.status == 200 and response.json():
            data = response.json()
            result.detail("Checks out", f"model={data.get('model', 'claude')}")
            usage = data.get("usage") or {}
            if usage:
                result.detail("Tokens used by probe", (usage.get("input_tokens", 0) + usage.get("output_tokens", 0)))
        if not result.buckets:
            result.detail("Note", "no rate-limit headers returned")
        if response.status != 200:
            result.raw = response.json()
        return result

    @staticmethod
    def _buckets(headers) -> list:
        lowered = {k.lower(): v for k, v in headers.items()}
        buckets = []
        for prefix, label in BUCKET_HEADERS.items():
            limit = lowered.get(f"{prefix}-limit")
            if limit is None:
                continue
            bucket = Bucket(name=label, window="per-minute")
            try:
                bucket.limit = int(float(limit))
            except ValueError:
                bucket.limit = None
            remaining = lowered.get(f"{prefix}-remaining")
            if remaining is not None:
                try:
                    bucket.remaining = int(float(remaining))
                except ValueError:
                    bucket.remaining = None
            bucket.reset = Provider.parse_reset(lowered.get(f"{prefix}-reset"))
            buckets.append(bucket)
        return buckets

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