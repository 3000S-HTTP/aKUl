"""ANSI helpers, progress bars and table/value formatting for the CLI."""

from __future__ import annotations

import datetime
import os
import sys
from typing import Iterable, List, Optional, Sequence

# --- palette ---------------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# 256-colour codes (fall back gracefully via paint()).
BRAND = "\033[38;5;45m"      # cyan/teal
BRAND_DEEP = "\033[38;5;39m"  # blue
GREEN = "\033[38;5;42m"
YELLOW = "\033[38;5;220m"
RED = "\033[38;5;203m"
GRAY = "\033[38;5;245m"
DARK = "\033[38;5;240m"
WHITE = "\033[97m"

_STATUS_SYMS = {True: "\u2714", False: "\u2718", None: "\u25b3"}
_ASCII_STATUS_SYMS = {True: "[OK]", False: "[X]", None: "[?]"}

# Glyphs, swapped to ASCII when the console cannot encode them.
GLYPH_RULE = "\u2500"
GLYPH_BAR_FILL = "\u2588"
GLYPH_BAR_EMPTY = "\u2591"
GLYPH_DOT = "\u00b7"


def enable_windows_ansi() -> None:
    """Turn on VT (ANSI) processing in legacy Windows consoles."""
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        for handle_id in (-11, -12):  # stdout, stderr
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def configure_console() -> None:
    """Best-effort: make stdout UTF-8 so box/bar glyphs render."""
    enable_windows_ansi()
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def _unicode_ok() -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        for char in ("\u2588", "\u2500", "\u2714", "\u00b7"):
            char.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def unicode_ok() -> bool:
    """True when the current stdout can encode the box/bar glyphs."""
    return _unicode_ok()


def _enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    try:
        return sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def paint(text: str, *codes: str) -> str:
    if not _enabled():
        return text
    return "".join(codes) + text + RESET


def status_color(status: int) -> str:
    if status == 0:
        return RED
    if status < 300:
        return GREEN
    if status < 500:
        return YELLOW
    return RED


def verdict_color(valid: Optional[bool]) -> str:
    if valid is True:
        return GREEN
    if valid is False:
        return RED
    return YELLOW


def verdict_symbol(valid: Optional[bool]) -> str:
    return _STATUS_SYMS.get(valid, "\u25b3") if _unicode_ok() else _ASCII_STATUS_SYMS.get(valid, "[?]")


# --- numbers & time --------------------------------------------------------

def humanize(number) -> str:
    """Turn big numbers into a readable form (1500000 -> 1.5M)."""
    try:
        value = float(number)
    except (TypeError, ValueError):
        return str(number)

    for cutoff, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(value) >= cutoff:
            scaled = value / cutoff
            text = f"{scaled:.1f}".rstrip("0").rstrip(".")
            return f"{text}{suffix}"
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


def parse_datetime(value) -> Optional[datetime.datetime]:
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    iso = text.replace("Z", "+00:00")
    try:
        parsed = datetime.datetime.fromisoformat(iso)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def relative_time(value, now: Optional[datetime.datetime] = None) -> Optional[str]:
    """Human countdown: '19h', '2d 4h', 'in 5m', '3h ago'."""
    moment = parse_datetime(value)
    if moment is None:
        return None
    now = now or datetime.datetime.now(datetime.timezone.utc)
    delta = (moment - now).total_seconds()
    past = delta < 0
    seconds = abs(int(delta))
    if seconds < 60:
        text = f"{seconds}s"
    elif seconds < 3600:
        text = f"{seconds // 60}m"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        text = f"{hours}h" + (f" {minutes}m" if hours < 6 and minutes else "")
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        text = f"{days}d" + (f" {hours}h" if hours else "")
    return f"{text} ago" if past else text


def local_time(value) -> Optional[str]:
    moment = parse_datetime(value)
    if moment is None:
        return None
    return moment.astimezone().strftime("%Y-%m-%d %H:%M")


# --- bars ------------------------------------------------------------------

def _bar_glyphs():
    if _unicode_ok():
        return GLYPH_BAR_FILL, GLYPH_BAR_EMPTY
    return "#", "-"


def _pct_color(pct: float) -> str:
    if pct < 60:
        return GREEN
    if pct < 85:
        return YELLOW
    return RED


def progress_bar(used_pct: Optional[float], width: int = 24, *, remaining: bool = True) -> str:
    """Render a 0-100 progress bar. ``remaining=True`` fills by amount left."""
    fill_char, empty_char = _bar_glyphs()
    if used_pct is None:
        return paint(empty_char * width, DARK)

    used = max(0.0, min(100.0, float(used_pct)))
    filled_ratio = (100.0 - used) / 100.0 if remaining else used / 100.0
    filled = int(round(filled_ratio * width))
    # Colour by how *used* the allowance is, regardless of fill direction.
    colour = _pct_color(used)
    bar = paint(fill_char * filled, colour) + paint(empty_char * (width - filled), DARK)
    return bar


def pct_label(used_pct: Optional[float], *, remaining: bool = True) -> str:
    if used_pct is None:
        return paint("n/a", GRAY)
    value = (100.0 - used_pct) if remaining else used_pct
    value = max(0.0, min(100.0, value))
    colour = _pct_color(used_pct)
    return paint(f"{value:.0f}%", colour, BOLD)


# --- layout ----------------------------------------------------------------

def rule(width: int = 60, char: Optional[str] = None) -> str:
    if char is None:
        char = GLYPH_RULE if _unicode_ok() else "-"
    return paint(char * width, DARK)


def render_table(rows: Sequence[Sequence[str]], headers: Sequence[str]) -> str:
    """Return an aligned, boxless text table."""
    widths = [len(str(h)) for h in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))

    def line(values: Iterable[str]) -> str:
        return "  ".join(str(v).ljust(widths[i]) for i, v in enumerate(values)).rstrip()

    output: List[str] = [paint(line(headers), BOLD, WHITE)]
    output.append(rule_sum(widths))
    output.extend(line(row) for row in rows)
    return "\n".join(output)


def rule_sum(widths: Sequence[int]) -> str:
    char = GLYPH_RULE if _unicode_ok() else "-"
    return paint("  ".join(char * w for w in widths), DARK)