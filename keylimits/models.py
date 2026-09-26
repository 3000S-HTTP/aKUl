"""Shared data structures returned by every provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Bucket:
    """A single rate-limit bucket reported by a provider."""

    name: str
    limit: Optional[int] = None
    remaining: Optional[int] = None
    reset: Optional[str] = None
    window: Optional[str] = None
    extra: Dict[str, str] = field(default_factory=dict)

    def as_row(self) -> List[str]:
        from .formatting import humanize

        def num(value):
            return "-" if value is None else humanize(value)

        return [
            self.name,
            self.window or "-",
            num(self.limit),
            num(self.remaining),
            self.reset or "-",
        ]


@dataclass
class Allowance:
    """A quota shown as a 0-100% progress bar (e.g. a free-tier allowance)."""

    label: str = "Allowance"
    used_pct: Optional[float] = None
    resets_at: Optional[str] = None
    plan: Optional[str] = None
    detail: Optional[str] = None

    @property
    def remaining_pct(self) -> Optional[float]:
        if self.used_pct is None:
            return None
        return max(0.0, 100.0 - self.used_pct)


@dataclass
class KeyLimits:
    """Everything we learned about a single API key."""

    provider: str
    key: str
    valid: Optional[bool] = None
    status: int = 0
    message: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    buckets: List[Bucket] = field(default_factory=list)
    details: List[tuple] = field(default_factory=list)
    allowance: Optional[Allowance] = None
    raw: Optional[dict] = None

    def detail(self, label: str, value) -> None:
        self.details.append((label, value))

    @property
    def status_text(self) -> str:
        if self.valid is True:
            return "valid"
        if self.valid is False:
            return "invalid"
        return "unknown"