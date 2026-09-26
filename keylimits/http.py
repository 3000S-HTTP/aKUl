"""Small dependency-free HTTP helper library reused by every provider."""

from __future__ import annotations

import json as _json
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Optional, Union

USER_AGENT = "keylimits/0.1 (+https://github.com/anomalyco/opencode)"

Body = Union[dict, list, str]


class Response:
    """A trimmed-down version of an HTTP response."""

    def __init__(self, status: int, headers: Dict[str, str], body: Body):
        self.status = status
        self.headers = headers
        self.body = body

    def json(self):
        if isinstance(self.body, (dict, list)):
            return self.body
        try:
            return _json.loads(self.body)
        except (TypeError, ValueError):
            return None

    @property
    def text(self) -> str:
        if isinstance(self.body, str):
            return self.body
        return _json.dumps(self.body, indent=2, sort_keys=True)

    def header(self, name: str) -> Optional[str]:
        lowered = name.lower()
        for key, value in self.headers.items():
            if key.lower() == lowered:
                return value
        return None

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


def request(
    url: str,
    *,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
    json_body: Optional[dict] = None,
    timeout: float = 30.0,
) -> Response:
    """Perform an HTTP request and return a :class:`Response`.

    Network and protocol errors are converted into responses with a status of
    ``0`` (connection failure) or ``4xx``/``5xx`` (HTTP error), so callers never
    have to deal with exceptions just to inspect rate-limit headers.
    """
    all_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    all_headers.update(headers or {})

    if params:
        query = urllib.parse.urlencode(params)
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{query}"

    payload = None
    if json_body is not None:
        payload = _json.dumps(json_body).encode("utf-8")
        all_headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=payload, headers=all_headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return Response(resp.status, dict(resp.headers), raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return Response(exc.code, dict(exc.headers or {}), raw)
    except urllib.error.URLError as exc:
        return Response(0, {}, f"Connection failed: {exc.reason}")
    except TimeoutError:
        return Response(0, {}, "Connection timed out")
    except Exception as exc:  # pragma: no cover - defensive
        return Response(0, {}, f"Unexpected error: {exc}")