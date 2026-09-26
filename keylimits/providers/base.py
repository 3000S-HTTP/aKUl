"""Base class and registry for providers."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Type

from ..models import Bucket, KeyLimits

# Providers are registered here via the @register decorator so the CLI can
# discover them without hard-coding imports.
_REGISTRY: Dict[str, Type["Provider"]] = {}


def register(cls: Type["Provider"]) -> Type["Provider"]:
    _REGISTRY[cls.name] = cls
    return cls


def get_provider(name: str) -> Optional[Type["Provider"]]:
    return _REGISTRY.get(name.lower())


def all_providers() -> List[Type["Provider"]]:
    return [_REGISTRY[key] for key in sorted(_REGISTRY)]


class Provider:
    """Base class describing how to probe one API vendor."""

    #: short machine name used with ``--provider``
    name: str = ""
    #: human readable label
    label: str = ""
    #: environment variables searched, in order, for the key
    env_vars: Tuple[str, ...] = ()
    #: default API base URL
    base_url: str = ""

    def __init__(self, key: str, base_url: Optional[str] = None, timeout: float = 30.0):
        self.key = key
        self.base_url = (base_url or self.base_url).rstrip("/")
        self.timeout = timeout

    def auth_headers(self) -> Dict[str, str]:
        raise NotImplementedError

    def check(self) -> KeyLimits:
        raise NotImplementedError

    # -- shared helpers -------------------------------------------------

    @staticmethod
    def parse_reset(value: Optional[str]) -> Optional[str]:
        """Normalise a provider reset value into a short human string."""
        if value is None:
            return None
        value = str(value).strip()
        if not value:
            return None
        if value.isdigit():
            # Unix timestamp (seconds or milliseconds) -> local time.
            if len(value) >= 10:
                import datetime

                seconds = int(value)
                if len(value) >= 13:
                    seconds //= 1000
                try:
                    moment = datetime.datetime.fromtimestamp(seconds)
                    return moment.strftime("%Y-%m-%d %H:%M:%S")
                except (OverflowError, OSError, ValueError):
                    return value
            return value
        # ISO-8601 timestamps: keep date + time, drop fractional seconds/zone.
        match = re.match(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})", value)
        if match:
            return f"{match.group(1)} {match.group(2)}"
        return value

    @staticmethod
    def collect_buckets(
        headers: Dict[str, str],
        mapping: Dict[str, Tuple[str, Optional[str]]],
    ) -> List[Bucket]:
        """Build :class:`Bucket` objects from response headers.

        ``mapping`` maps a bucket name to a ``(header, window)`` pair, e.g.
        ``{"requests": ("x-ratelimit-limit-requests", "requests")}``.
        """
        lowered = {k.lower(): v for k, v in headers.items()}
        buckets: List[Bucket] = []
        for name, (header, window) in mapping.items():
            raw = lowered.get(header.lower())
            if raw is None:
                continue
            try:
                limit: Optional[int] = int(float(raw))
            except ValueError:
                limit = None
            bucket = Bucket(name=name, limit=limit, window=window)
            rem_header = header.replace("-limit", "-remaining")
            reset_header = header.replace("-limit", "-reset")
            rem_raw = lowered.get(rem_header.lower())
            reset_raw = lowered.get(reset_header.lower())
            if rem_raw is not None:
                try:
                    bucket.remaining = int(float(rem_raw))
                except ValueError:
                    bucket.remaining = None
            bucket.reset = Provider.parse_reset(reset_raw)
            buckets.append(bucket)
        return buckets

    @staticmethod
    def set_valid_from_status(result: KeyLimits, status: int, invalid_codes=(401, 403)):
        if status == 0:
            result.valid = None
        elif status in invalid_codes:
            result.valid = False
        elif 200 <= status < 300:
            result.valid = True
        elif status == 429:
            # Rate-limited, but the key itself authenticated fine.
            result.valid = True
        else:
            result.valid = None