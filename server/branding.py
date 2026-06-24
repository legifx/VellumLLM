"""Vellum brand mark and terminal styling helpers.

Renders the parchment-over-a-wooden-frame symbol with two safety nets:
* a pure-ASCII fallback when the terminal can't do UTF-8, and
* color that turns itself off for non-TTYs, ``NO_COLOR``, ``TERM=dumb``,
  or an explicit ``MMRAG_COLOR=0``.

Both the onboarding flow and the server banner use this so the look is one
thing in one place.
"""
from __future__ import annotations

import os
import sys

RESET = "\x1b[0m"

# 256-color tones: aged parchment + wood frame, kept to a quiet two-color palette.
_PARCHMENT = "\x1b[38;5;223m"
_WOOD = "\x1b[38;5;131m"
_DIM = "\x1b[2m"
_BOLD = "\x1b[1m"

_ART_UNICODE = [
    "┏━━━━━━━━━━┓",
    "┃ ╭──────╮ ┃",
    "┃ │▁▁▁▁▁▁│ ┃",
    "┃ │▁▁▁▁  │ ┃",
    "┃ │▁▁▁▁▁▁│ ┃",
    "┃ ╰──────╯ ┃",
    "┗━━━━━━━━━━┛",
]

_ART_ASCII = [
    "+----------+",
    "| .------. |",
    "| |======| |",
    "| |===   | |",
    "| |======| |",
    "| '------' |",
    "+----------+",
]


def supports_color(force: bool | None = None) -> bool:
    if force is not None:
        return force
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("MMRAG_COLOR", "").strip() in ("0", "false", "no"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return sys.stdout.isatty()


def supports_unicode() -> bool:
    if os.environ.get("MMRAG_ASCII", "").strip() in ("1", "true", "yes"):
        return False
    enc = (getattr(sys.stdout, "encoding", "") or "").lower()
    return "utf" in enc


def hero(color: bool | None = None, unicode: bool | None = None, indent: str = "   ") -> str:
    """The full hero block: brand mark + wordmark + tagline."""
    use_color = supports_color(color)
    use_unicode = supports_unicode() if unicode is None else unicode
    art = _ART_UNICODE if use_unicode else _ART_ASCII
    dot = "·" if use_unicode else "."

    def wood(s: str) -> str:
        return f"{_WOOD}{s}{RESET}" if use_color else s

    lines = [indent + wood(row) for row in art]
    word = "V E L L U M"
    tag = f"local {dot} multimodal {dot} yours"
    if use_color:
        word = f"{_BOLD}{_PARCHMENT}{word}{RESET}"
        tag = f"{_DIM}{tag}{RESET}"
    # center the wordmark/tagline under the ~12-wide mark
    lines.append("")
    lines.append(indent + "  " + word)
    lines.append(indent + tag)
    return "\n".join(lines)


def rule(width: int = 56, color: bool | None = None) -> str:
    use_color = supports_color(color)
    use_unicode = supports_unicode()
    ch = "─" if use_unicode else "-"
    line = ch * width
    return f"{_DIM}{line}{RESET}" if use_color else line
