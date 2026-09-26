"""Token Harbor key inspection.

Token Harbor (https://tokenharbor.ai) is an OpenAI- and Anthropic-compatible
gateway fronting many upstream models behind one ``thk_live_...`` key.

The dashboard's "Free allowance" bar (used %, reset time, plan) is not exposed
through a documented endpoint, but the gateway returns it as response headers
on any call, including one to a free (``:free``) model:

    X-Th-Free-Used-Pct: 0
    X-Th-Free-Resets:   2026-10-02T18:32:55+00:00
    X-Th-Plan:          free

So checking a key validates it against ``/v1/models`` first, then issues one
tiny free-model completion to read the allowance headers. If the account has no
free models, only key validity and documented limits are reported.
"""

from __future__ import annotations

from ..http import request
from ..models import Allowance, Bucket, KeyLimits
from .base import Provider, register

# Buckets the gateway may report via headers.
BUCKETS = {
    "requests": ("x-ratelimit-limit-requests", "requests"),
    "tokens": ("x-ratelimit-limit-tokens", "tokens"),
}

# Documented free-account limits, surfaced as a fallback when no headers exist.
# Source: https://tokenharbor.ai/docs/api/rate-limits
FREE_LIMITS = (
    ("requests/min (account)", 60),
    ("requests/hour (account)", 1800),
    ("requests/min (per IP)", 100),
    ("requests/hour (per IP)", 3000),
    ("images/min", 10),
    ("images/hour", 150),
)


@register
class TokenHarborProvider(Provider):
    name = "tokenharbor"
    label = "Token Harbor"
    env_vars = ("TOKENHARBOR_API_KEY", "TH_API_KEY")
    base_url = "https://tokenharbor.ai/v1"

    #: model used for the allowance probe; overridable via ``--model``.
    probe_model = "mimo-v2.5:free"

    def __init__(self, key, base_url=None, timeout=30.0, *, model=None):
        super().__init__(key, base_url, timeout)
        self.model = model or self.probe_model

    def auth_headers(self):
        return {"Authorization": f"Bearer {self.key}"}

    def check(self) -> KeyLimits:
        result = KeyLimits(provider=self.name, key=self.key)
        headers = dict(self.auth_headers())

        catalog = request(f"{self.base_url}/models", headers=headers, timeout=self.timeout)
        result.status = catalog.status
        result.headers = catalog.headers
        result.message = self._error_message(catalog)
        self.set_valid_from_status(result, catalog.status)

        if catalog.status == 429:
            self._note_retry(result, catalog)
            return result
        if catalog.status in (401, 403) or catalog.status == 0:
            if catalog.status != 0:
                result.raw = catalog.json()
            return result

        models = self._models(catalog)
        free_models = [m for m in models if m.endswith(":free")]
        result.detail("Checks out", f"{len(models)} model(s) available")
        if free_models:
            result.detail("Free models", f"{len(free_models)} (e.g. {free_models[0]})")
        if models:
            result.detail("Example model", models[0])

        self._probe_allowance(result, headers, free_models)
        self._fill_buckets(result, catalog.headers)
        return result

    # -- helpers --------------------------------------------------------

    def _probe_allowance(self, result: KeyLimits, headers, free_models) -> None:
        model = self.model if self.model in free_models or self.model.endswith(":free") else None
        if model is None and free_models:
            model = free_models[0]
        if model is None:
            result.detail(
                "Free allowance",
                "no free models on this account (dashboard link: /dashboard)",
            )
            return

        probe = request(
            f"{self.base_url}/chat/completions",
            method="POST",
            headers=headers,
            json_body={
                "model": model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
            },
            timeout=self.timeout,
        )

        if probe.status == 429:
            self._note_retry(result, probe)

        used = probe.header("x-th-free-used-pct")
        resets = probe.header("x-th-free-resets")
        plan = probe.header("x-th-plan")
        if used is None and resets is None:
            return

        used_pct = None
        if used is not None:
            try:
                used_pct = float(used)
            except ValueError:
                used_pct = None

        result.allowance = Allowance(
            label="Free allowance",
            used_pct=used_pct,
            resets_at=resets,
            plan=plan,
            detail=f"probed {model}",
        )

    def _fill_buckets(self, result: KeyLimits, headers) -> None:
        result.buckets = self.collect_buckets(headers, BUCKETS)
        if result.buckets:
            return
        result.buckets = [
            Bucket(name=label, limit=limit, window="documented free tier")
            for label, limit in FREE_LIMITS
        ]
        result.detail("Note", "no rate-limit headers; showing documented free-tier limits")

    @staticmethod
    def _note_retry(result: KeyLimits, response) -> None:
        retry = response.header("retry-after")
        if retry:
            result.detail("Retry after", f"{retry}s (free-tier limit reached)")

    @staticmethod
    def _models(response) -> list:
        data = response.json()
        names = []
        if isinstance(data, dict):
            for entry in data.get("data") or data.get("models") or []:
                model_id = TokenHarborProvider._model_id(entry)
                if model_id:
                    names.append(model_id)
        return names

    @staticmethod
    def _model_id(entry) -> str:
        if isinstance(entry, dict):
            return str(entry.get("id") or entry.get("name") or "")
        return ""

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