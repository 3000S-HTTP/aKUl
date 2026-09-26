"""Terminal rendering of one or more :class:`KeyLimits` results."""

from __future__ import annotations

import json
from typing import List, Optional

from .formatting import (
    BOLD,
    BRAND,
    BRAND_DEEP,
    DARK,
    GRAY,
    WHITE,
    local_time,
    paint,
    pct_label,
    progress_bar,
    relative_time,
    render_table,
    rule,
    status_color,
    unicode_ok,
    verdict_color,
    verdict_symbol,
)
from .models import Allowance, KeyLimits

WIDTH = 62


def mask_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return f"{key[:6]}...{key[-4:]}"


def valid_badge(result: KeyLimits) -> str:
    colour = verdict_color(result.valid)
    symbol = verdict_symbol(result.valid)
    label = {True: "VALID", False: "INVALID", None: "UNKNOWN"}[result.valid]
    return paint(f"{symbol} {label}", colour, BOLD)


def _header(result: KeyLimits) -> str:
    title = paint("KEYLIMITS", BRAND, BOLD)
    provider = paint(f" {result.provider} ", BRAND_DEEP, BOLD)
    return f"{title} {provider}"


def _render_allowance(allowance: Allowance) -> List[str]:
    lines: List[str] = [paint("Free allowance", BOLD, WHITE)]
    bar = progress_bar(allowance.used_pct, width=30)
    left = pct_label(allowance.used_pct)
    lines.append(f"  {bar}  {left} left")

    meta: List[str] = []
    countdown = relative_time(allowance.resets_at)
    if countdown:
        meta.append(f"resets in {paint(countdown, BRAND)}")
    if allowance.plan:
        meta.append(f"plan {paint(allowance.plan, BRAND)}")
    border = paint(" \u00b7 ", DARK) if unicode_ok() else paint(" | ", DARK)
    if meta:
        lines.append("  " + border.join(meta))
    when = local_time(allowance.resets_at)
    if when:
        lines.append(paint(f"  {when}", DARK))
    if allowance.detail:
        lines.append(paint(f"  {allowance.detail}", GRAY))
    return lines


def render_text(result: KeyLimits) -> str:
    lines: List[str] = []
    lines.append(_header(result))
    lines.append(rule(WIDTH))
    lines.append(f"  Key      {paint(mask_key(result.key), WHITE)}")
    status = valid_badge(result)
    http = paint(f"HTTP {result.status}", status_color(result.status))
    lines.append(f"  Status   {status}   {http}")
    if result.message:
        lines.append(f"  Message  {paint(result.message, GRAY)}")

    if result.allowance and (result.allowance.used_pct is not None or result.allowance.resets_at):
        lines.append("")
        lines.extend(_render_allowance(result.allowance))

    if result.buckets:
        lines.append("")
        lines.append(paint("Rate limits", BOLD, WHITE))
        rows = [bucket.as_row() for bucket in result.buckets]
        lines.append(render_table(rows, ["Bucket", "Window", "Limit", "Remaining", "Reset"]))

    visible = [(label, value) for label, value in result.details if value is not None]
    if visible:
        lines.append("")
        lines.append(paint("Details", BOLD, WHITE))
        for label, value in visible:
            lines.append(f"  {paint(label.ljust(22), GRAY)} {value}")

    if result.raw:
        lines.append("")
        lines.append(paint("Raw response", BOLD, WHITE))
        lines.append(json.dumps(result.raw, indent=2))

    return "\n".join(lines)


def _allowance_json(allowance: Optional[Allowance]):
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


def render_json(results: List[KeyLimits]) -> str:
    payload = []
    for result in results:
        payload.append(
            {
                "provider": result.provider,
                "key": mask_key(result.key),
                "status": result.status,
                "valid": result.valid,
                "message": result.message,
                "allowance": _allowance_json(result.allowance),
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
        )
    single = len(payload) == 1
    body = json.dumps(payload[0] if single else payload, indent=2)
    return body


def render(results: List[KeyLimits], as_json: bool = False) -> None:
    if as_json:
        print(render_json(results))
        return
    for index, result in enumerate(results):
        if index:
            print()
        print(render_text(result))