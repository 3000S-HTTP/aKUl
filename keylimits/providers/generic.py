"""Generic provider: point it at any JSON endpoint that returns rate-limit headers.

Useful for self-hosted gateways (LiteLLM, OpenRouter-compatible proxies, ...).
Any ``x-ratelimit-*`` header is collected automatically.
"""

from __future__ import annotations

from typing import Dict, Optional

from ..http import request
from ..models import Bucket, KeyLimits
from .base import Provider, register


@register
class GenericProvider(Provider):
    name = "generic"
    label = "Generic HTTP endpoint"
    env_vars = ("API_KEY",)
    base_url = ""

    auth_header = "Authorization"
    auth_scheme = "Bearer"
    method = "GET"

    def __init__(
        self,
        key: str,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        *,
        url: Optional[str] = None,
        auth_header: Optional[str] = None,
        auth_scheme: Optional[str] = None,
        method: Optional[str] = None,
    ):
        super().__init__(key, base_url, timeout)
        self.url = url or base_url or ""
        if auth_header:
            self.auth_header = auth_header
        if auth_scheme is not None:
            self.auth_scheme = auth_scheme
        if method:
            self.method = method.upper()

    def auth_headers(self):
        token = f"{self.auth_scheme} {self.key}".strip() if self.auth_scheme else self.key
        return {self.auth_header: token}

    def check(self) -> KeyLimits:
        result = KeyLimits(provider=self.name, key=self.key)
        response = request(self.url, method=self.method, headers=self.auth_headers(), timeout=self.timeout)

        result.status = response.status
        result.headers = response.headers
        result.message = response.text[:300] if response.status != 200 else ""
        self.set_valid_from_status(result, response.status)
        result.buckets = self._scan_headers(response.headers)

        if response.status == 200:
            result.detail("Endpoint", self.url)
            result.detail("Checks out", "endpoint reachable")
        if not result.buckets:
            result.detail("Note", "no x-ratelimit-* headers returned")
        return result

    @staticmethod
    def _scan_headers(headers: Dict[str, str]) -> list:
        lowered = {k.lower(): v for k, v in headers.items()}
        buckets = []
        for header, value in lowered.items():
            if not header.startswith("x-ratelimit-limit"):
                continue
            suffix = header[len("x-ratelimit-limit"):].strip("-")
            name = suffix or "requests"
            bucket = Bucket(name=name)
            try:
                bucket.limit = int(float(value))
            except ValueError:
                bucket.limit = None
            tail = f"-{suffix}" if suffix else ""
            remaining = lowered.get(f"x-ratelimit-remaining{tail}")
            reset = lowered.get(f"x-ratelimit-reset{tail}")
            if remaining is not None:
                try:
                    bucket.remaining = int(float(remaining))
                except ValueError:
                    bucket.remaining = None
            bucket.reset = Provider.parse_reset(reset)
            buckets.append(bucket)
        return buckets