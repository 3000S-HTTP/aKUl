"""Turning :class:`KeyLimits` results into comparison-ready structures.

Used by the desktop app (and available to library consumers) so the CLI, the
JSON output and the comparison UI all agree on what a key "looks like".
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .formatting import relative_time
from .models import KeyLimits


def serialize_key(result: KeyLimits) -> Dict[str, Any]:
    """Flatten one :class:`KeyLimits` into a JSON-safe dict."""
    return {
        "provider": result.provider,
        "key": result.key,
        "valid": result.valid,
        "status": result.status,
        "message": result.message,
        "allowance": _allowance_dict(result),
        "buckets": [
            {
                "name": bucket.name,
                "window": bucket.window,
                "limit": bucket.limit,
                "remaining": bucket.remaining,
                "reset": bucket.reset,
            }
            for bucket in result.buckets
        ],
        "details": [{"label": label, "value": value} for label, value in result.details],
    }


def _allowance_dict(result: KeyLimits) -> Optional[Dict[str, Any]]:
    allowance = result.allowance
    if allowance is None:
        return None
    return {
        "label": allowance.label,
        "used_pct": allowance.used_pct,
        "remaining_pct": allowance.remaining_pct,
        "resets_at": allowance.resets_at,
        "resets_in": relative_time(allowance.resets_at),
        "plan": allowance.plan,
        "detail": allowance.detail,
    }


def collect_bucket_names(keys: List[Dict[str, Any]]) -> List[str]:
    """Union of bucket names across every key, order of first appearance."""
    names: List[str] = []
    for key in keys:
        for bucket in key.get("buckets", []):
            name = bucket.get("name")
            if name and name not in names:
                names.append(name)
    return names


def best_index(keys: List[Dict[str, Any]], bucket_name: str) -> Optional[int]:
    """Index of the key with the most remaining quota in ``bucket_name``.

    Keys without a numeric ``remaining`` value are ignored; returns ``None``
    when nobody has a usable number.
    """
    best_i: Optional[int] = None
    best_val: Optional[float] = None
    for index, key in enumerate(keys):
        remaining = _remaining(key, bucket_name)
        if remaining is None:
            continue
        if best_val is None or remaining > best_val:
            best_val = remaining
            best_i = index
    return best_i


def best_remaining_pct(keys: List[Dict[str, Any]]) -> Optional[int]:
    """Index of the key with the most free allowance left (by percent)."""
    best_i: Optional[int] = None
    best_val: Optional[float] = None
    for index, key in enumerate(keys):
        allowance = key.get("allowance")
        if not allowance or allowance.get("remaining_pct") is None:
            continue
        value = float(allowance["remaining_pct"])
        if best_val is None or value > best_val:
            best_val = value
            best_i = index
    return best_i


def _remaining(key: Dict[str, Any], bucket_name: str) -> Optional[float]:
    for bucket in key.get("buckets", []):
        if bucket.get("name") == bucket_name:
            remaining = bucket.get("remaining")
            if remaining is None:
                return None
            try:
                return float(remaining)
            except (TypeError, ValueError):
                return None
    return None


def build_comparison(keys: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the summary a comparison UI needs on top of serialized keys.

    Returns::

        {
            "keys": [...],
            "bucket_names": [...],
            "winners": {"requests": 0, "allowance": 1, ...},
            "valid_count": 2,
            "key_count": 3,
        }
    """
    bucket_names = collect_bucket_names(keys)
    winners = {name: best_index(keys, name) for name in bucket_names}
    allowance_winner = best_remaining_pct(keys)
    if allowance_winner is not None:
        winners["free allowance"] = allowance_winner
    valid_count = sum(1 for key in keys if key.get("valid") is True)
    return {
        "keys": keys,
        "bucket_names": bucket_names,
        "winners": winners,
        "valid_count": valid_count,
        "key_count": len(keys),
    }