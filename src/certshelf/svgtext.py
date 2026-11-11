"""Text for SVGs that GitHub shows as images: escaping, conservative width estimates, wrapping.

Viewers render with whatever fonts they have, so widths are estimated on the wide side and
every box is sized from these estimates. Nothing may overflow on a common fallback font.
"""
from __future__ import annotations

import re
import unicodedata

SANS = "Tahoma, Verdana, 'DejaVu Sans', 'Segoe UI', sans-serif"
MONO = "'Lucida Console', Consolas, 'DejaVu Sans Mono', monospace"

_SANS_EM = 0.62
_BOLD_EM = 0.68
_MONO_EM = 0.62
_WIDE_EM = 0.9
_WIDE = set("WMmw@%")
_FULL_EM = 1.25  # emoji and CJK: fallback fonts draw these about a full em wide, often more
ELLIPSIS = "…"

Line = list[tuple[str, bool]]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _full_width(ch: str) -> bool:
    return ord(ch) >= 0x1F000 or unicodedata.east_asian_width(ch) in ("W", "F")


def text_width(s: str, size: float, bold: bool = False, mono: bool = False) -> float:
    base = _MONO_EM if mono else (_BOLD_EM if bold else _SANS_EM)
    total = 0.0
    for ch in s:
        if _full_width(ch):
            total += _FULL_EM
        elif ch in _WIDE and not mono:
            total += _WIDE_EM
        else:
            total += base
    return total * size


def parse_markup(s: str) -> list[tuple[str, bool]]:
    parts = re.split(r"\*\*(.+?)\*\*", s)
    return [(part, i % 2 == 1) for i, part in enumerate(parts) if part]


def _words(markup: str, use_markup: bool = True) -> list[tuple[str, bool, bool]]:
    """(word, bold, space_before). Spacing survives bold boundaries, so "**16 days**." stays glued."""
    words = []
    space = False
    for text, bold in (parse_markup(markup) if use_markup else [(markup, False)]):
        for token in re.findall(r"\s+|\S+", text):
            if token.isspace():
                space = True
            else:
                words.append((token, bold, space))
                space = False
    return words


def _width(line: Line, size: float, mono: bool) -> float:
    return sum(text_width(t, size, bold=b, mono=mono) for t, b in line)


def _append(line: Line, text: str, bold: bool) -> Line:
    if line and line[-1][1] == bold:
        return line[:-1] + [(line[-1][0] + text, bold)]
    return line + [(text, bold)]


def _break_word(word: str, bold: bool, max_width: float, size: float, mono: bool) -> list[str]:
    pieces, cur = [], ""
    for ch in word:
        if cur and text_width(cur + ch, size, bold, mono) > max_width:
            pieces.append(cur)
            cur = ""
        cur += ch
    return pieces + ([cur] if cur else [])


def _truncate(line: Line, max_width: float, size: float, mono: bool) -> Line:
    while line and _width(_append(line, ELLIPSIS, False), size, mono) > max_width:
        t, b = line[-1]
        line = line[:-1] + ([(t[:-1], b)] if len(t) > 1 else [])
    line = [(t.rstrip(), b) if i == len(line) - 1 else (t, b) for i, (t, b) in enumerate(line)]
    return _append(line, ELLIPSIS, False)


def _soft_pieces(word: str, break_after: str) -> list[str]:
    """Split a word after any of `break_after` (e.g. hyphens), keeping the character on the left piece."""
    pieces, cur = [], ""
    for ch in word:
        cur += ch
        if ch in break_after:
            pieces.append(cur)
            cur = ""
    return pieces + ([cur] if cur else [])


def wrap(
    text: str,
    max_width: float,
    size: float,
    mono: bool = False,
    max_lines: int | None = None,
    markup: bool = True,
    break_after: str = "",
) -> list[Line]:
    """Greedy word wrap. Words wider than a line are hard-broken; overflow beyond max_lines ends in an ellipsis.

    With markup=False the text is taken literally (for names and bios typed by people). Characters in
    `break_after` are extra break points inside words (repo names such as "Vulnerable-Drone-PX4-Lab").
    """
    lines: list[Line] = []
    cur: Line = []
    for word, bold, spaced in _words(text, markup):
        for n, soft in enumerate(_soft_pieces(word, break_after)):
            for k, piece in enumerate(_break_word(soft, bold, max_width, size, mono)):
                glue = " " if spaced and not (n or k) else ""
                candidate = _append(cur, glue, False) if cur and glue else cur
                candidate = _append(candidate, piece, bold)
                if cur and _width(candidate, size, mono) > max_width:
                    lines.append(cur)
                    cur = [(piece, bold)]
                else:
                    cur = candidate
    if cur:
        lines.append(cur)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[: max_lines - 1] + [_truncate(lines[max_lines - 1], max_width, size, mono)]
    return lines


def text_block(lines: list[Line], x: float, y: float, size: float, line_height: float, attrs: str) -> str:
    """One <text>, one <tspan> per line, bold segments as nested tspans. `y` is the first baseline."""
    rows = []
    dy = 0.0
    for line in lines:
        inner = "".join(
            f'<tspan font-weight="bold">{esc(t)}</tspan>' if b else esc(t) for t, b in line
        )
        if not inner:  # an empty tspan carries no glyph, so its dy would be lost: fold it into the next line
            dy += line_height
            continue
        rows.append(f'<tspan x="{x:g}" dy="{dy:g}">{inner}</tspan>')
        dy = line_height
    return f'<text xml:space="preserve" x="{x:g}" y="{y:g}" font-size="{size:g}" {attrs}>{"".join(rows)}</text>'
