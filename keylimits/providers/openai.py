"""OpenAI key inspection.

OpenAI only guarantees rate-limit headers on generation endpoints, so a single
tiny chat completion is issued to force them. When that is unavailable we fall
back to the ``/models`` endpoint, which still validates the key.
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
class OpenAIProvider(Provider):
    name = "openai"
    label = "OpenAI"
    env_vars = ("OPENAI_API_KEY",)
    base_url = "https://api.openai.com/v1"

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
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
            },
            timeout=self.timeout,
        )

        if response.status in (0, 401, 403):
            # Try /models so a bad key still produces a clear verdict.
            probe = request(f"{self.base_url}/models", headers=headers, timeout=self.timeout)
            result.status = probe.status
            result.valid = False if probe.status in (401, 403) else None
            result.message = self._error_message(probe)
            return result

        result.status = response.status
        result.headers = response.headers
        result.message = self._error_message(response)
        self.set_valid_from_status(result, response.status)
        result.buckets = self.collect_buckets(response.headers, BUCKETS)

        project = response.header("openai-project")
        org = response.header("openai-organization")
        if project:
            result.detail("Project", project)
        if org:
            result.detail("Organization", org)
        if response.status == 200 and response.json():
            data = response.json()
            result.detail("Checks out", f"model={data.get('model', 'gpt-4o-mini')}")
            usage = data.get("usage") or {}
            if usage:
                result.detail("Tokens used by probe", usage.get("total_tokens"))
        if not result.buckets:
            result.detail("Note", "no rate-limit headers returned")

        # Keep the raw payload only when it is small enough to be useful.
        result.raw = response.json() if response.status != 200 else None
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