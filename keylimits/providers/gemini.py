"""Google Gemini key inspection using the free ``models.list`` endpoint."""

from __future__ import annotations

from ..http import request
from ..models import KeyLimits
from .base import Provider, register


@register
class GeminiProvider(Provider):
    name = "gemini"
    label = "Google Gemini"
    env_vars = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
    base_url = "https://generativelanguage.googleapis.com/v1beta"

    def auth_headers(self):
        return {"x-goog-api-key": self.key}

    def check(self) -> KeyLimits:
        result = KeyLimits(provider=self.name, key=self.key)
        response = request(
            f"{self.base_url}/models",
            headers=self.auth_headers(),
            params={"pageSize": "1"},
            timeout=self.timeout,
        )

        result.status = response.status
        result.headers = response.headers
        result.message = self._error_message(response)
        self.set_valid_from_status(result, response.status)
        if response.status == 400 and "API key not valid" in result.message:
            result.valid = False

        data = response.json()
        if response.status == 200 and isinstance(data, dict):
            models = data.get("models") or []
            result.detail("Checks out", f"{len(models)} model(s) visible")
            if models:
                result.detail("Example model", models[0].get("name", "").replace("models/", ""))
        elif response.status != 200:
            result.raw = data

        result.detail("Note", "Gemini does not expose rate-limit headers; check AI Studio for quotas")
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