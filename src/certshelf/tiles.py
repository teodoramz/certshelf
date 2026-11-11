"""One 168x216 SVG tile per entry, in the `card` (GitHub-like, dark/light) or `retro` (window on a shelf) style."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .model import Entry
from .svgtext import SANS, Line, esc, text_block, text_width, wrap

W, H = 168, 216
TEXT_W = 152
CARD = {
    "dark": {"bg": "#161b22", "border": "#30363d", "text": "#e6edf3", "muted": "#8b949e",
             "active": "#3fb950", "expired": "#8b949e", "extra": "#4493f8"},
    "light": {"bg": "#f6f8fa", "border": "#d0d7de", "text": "#1f2328", "muted": "#59636e",
              "active": "#1a7f37", "expired": "#59636e", "extra": "#0969da"},
}
RETRO_STATUS = {"active": "#1a7f37", "expired": "#c0392b", "extra": "#0b5cad"}
GREY = ('<filter id="grey"><feColorMatrix type="saturate" values="0"/></filter>')


@dataclass
class Box:
    name: str
    lines: list[Line]
    size: float
    width: float
    y: float  # first baseline
    line_height: float
    bold: bool = False

    @property
    def bottom(self) -> float:
        return self.y + (len(self.lines) - 1) * self.line_height + 3


def initials(name: str) -> str:
    acronym = re.search(r"\(([A-Za-z0-9+]{2,6})\)\s*$", name)
    if acronym:
        return acronym.group(1).upper()
    words = name.split()
    if words and len(words[0]) <= 5 and words[0].isupper():
        return words[0]
    return "".join(w[0] for w in words[:2]).upper() or "?"


def tile_files(entry: Entry, style: str) -> list[str]:
    return [f"{entry.key}-dark.svg", f"{entry.key}-light.svg"] if style == "card" else [f"{entry.key}.svg"]


def _box(name, text, size, width, y, lh, max_lines, bold=False, break_after="") -> Box:
    lines = wrap(text, width, size, max_lines=max_lines, break_after=break_after) if text else []
    return Box(name, lines, size, width, y, lh, bold)


def layout(entry: Entry, style: str) -> list[Box]:
    """Where every piece of text goes; render_tile draws exactly these boxes."""
    boxes = []
    if style == "card":
        name = _box("name", entry.name, 12.5, TEXT_W, 100, 16, 2, bold=True)
        y = name.y + (len(name.lines) - 1) * 16 + 15
        issuer = _box("issuer", entry.issuer, 11, TEXT_W, y, 14, 1)
        y += 14 if issuer.lines else 0
        when = _box("date", entry.date_line, 10.5, TEXT_W, y, 13, 1)
        y += 14 if when.lines else 0
        pill = _box("pill", entry.status, 10.5, TEXT_W - 16, y + 9.5, 13, 1, bold=True)
        note = _box("note", entry.note or "", 10.5, TEXT_W, y + 30, 13, 2)
        boxes = [name, issuer, when, pill, note]
    else:
        name = _box("name", entry.name, 11, TEXT_W, 128, 14, 2, bold=True)
        y = name.y + (len(name.lines) - 1) * 14 + 15
        detail = " · ".join(p for p in (entry.issuer, entry.date_line) if p)
        info = _box("detail", detail, 10, TEXT_W, y, 13, 2)
        y += len(info.lines) * 13 + 2 if info.lines else 0
        status = _box("status", entry.status.lower() if entry.kind != "expired" else "", 10, TEXT_W, y, 13, 1)
        note = _box("note", entry.note or "", 8, 70, 40, 10, 4, break_after="/-")
        boxes = [name, info, status, note]
    return [b for b in boxes if b.name in ("name", "note") or b.lines]


def _image(entry: Entry, image: str | None, x: float, y: float, size: float, colors: dict) -> str:
    grey = ' filter="url(#grey)" opacity="0.55"' if entry.kind == "expired" else ""
    if image:
        return (f'<image x="{x:g}" y="{y:g}" width="{size:g}" height="{size:g}" preserveAspectRatio="xMidYMid meet" '
                f'href="{image}" xlink:href="{image}"{grey}/>')
    mono = initials(entry.name)
    font = 26 if len(mono) <= 2 else 20
    return (f'<g{grey}><rect x="{x + 1:g}" y="{y + 1:g}" width="{size - 2:g}" height="{size - 2:g}" rx="14" '
            f'fill="{colors["bg"]}" stroke="{colors["border"]}" stroke-width="2"/>'
            f'<text x="{x + size / 2:g}" y="{y + size / 2 + font * 0.35:g}" text-anchor="middle" font-family="{SANS}" '
            f'font-size="{font}" font-weight="bold" fill="{colors["text"]}">{esc(mono)}</text></g>')


def _text(box: Box, fill: str, extra: str = "") -> str:
    weight = ' font-weight="bold"' if box.bold else ""
    return text_block(box.lines, W / 2, box.y, box.size, box.line_height,
                      f'font-family="{SANS}" text-anchor="middle" fill="{fill}"{weight}{extra}')


def _svg(body: str, label: str, grey: bool) -> str:
    defs = f"<defs>{GREY}</defs>" if grey else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" '
            f'height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)}"><title>{esc(label)}</title>'
            f"{defs}{body}</svg>")


def _card(entry: Entry, image: str | None, theme: str) -> str:
    c = CARD[theme]
    boxes = {b.name: b for b in layout(entry, "card")}
    accent = c[entry.kind]
    parts = [f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{c["bg"]}" stroke="{c["border"]}"/>']
    if theme == "dark" and image:  # badges are drawn for white backgrounds; dark ones vanish on a dark tile
        opacity = "0.35" if entry.kind == "expired" else "0.92"
        parts.append(f'<rect class="plate" x="{(W - 80) / 2:g}" y="8" width="80" height="80" rx="14" '
                     f'fill="#f6f8fa" fill-opacity="{opacity}"/>')
    parts += [_image(entry, image, (W - 72) / 2, 12, 72, c), _text(boxes["name"], c["text"])]
    for key in ("issuer", "date"):
        if key in boxes:
            parts.append(_text(boxes[key], c["muted"]))
    pill = boxes["pill"]
    label = "".join(t for t, _ in pill.lines[0])
    pill_w = min(TEXT_W, text_width(label, pill.size, bold=True) + 16)
    parts.append(f'<rect x="{(W - pill_w) / 2:g}" y="{pill.y - 12.5:g}" width="{pill_w:g}" height="18" rx="9" '
                 f'fill="{accent}" fill-opacity="0.15"/>')
    parts.append(text_block([[(label, True)]], W / 2, pill.y, pill.size, 13,
                            f'font-family="{SANS}" text-anchor="middle" fill="{accent}"'))
    if boxes["note"].lines:
        parts.append(_text(boxes["note"], c["muted"], ' font-style="italic"'))
    return _svg("".join(parts), f"{entry.name} ({entry.status})", entry.kind == "expired")


def _retro(entry: Entry, image: str | None) -> str:
    boxes = {b.name: b for b in layout(entry, "retro")}
    colors = {"bg": "#ffffff", "border": "#9a968a", "text": "#000000"}
    title = f"{initials(entry.name).lower()}.cert"
    parts = [
        '<defs><linearGradient id="bar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2f6fe0"/>'
        '<stop offset="1" stop-color="#1a46b0"/></linearGradient>'
        '<linearGradient id="wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f7f5ec"/>'
        '<stop offset="1" stop-color="#ece9d8"/></linearGradient></defs>',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="7" fill="url(#wall)" stroke="#0a246a"/>',
        f'<path d="M0.5,20 V7.5 Q0.5,0.5 7.5,0.5 H{W - 7.5} Q{W - 0.5},0.5 {W - 0.5},7.5 V20 Z" fill="url(#bar)"/>',
        f'<text x="8" y="14" font-family="{SANS}" font-size="10.5" font-weight="bold" fill="#fff">{esc(title)}</text>',
        f'<rect x="{W - 18}" y="4" width="12" height="12" rx="2" fill="#d9462b" stroke="#fff"/>',
        _image(entry, image, (W - 72) / 2, 30, 72, colors),
        f'<rect x="24" y="104" width="{W - 48}" height="7" rx="2" fill="#8a6a3c"/>',
        f'<rect x="24" y="111" width="{W - 48}" height="2" fill="#5e4524"/>',
        _text(boxes["name"], "#000"),
    ]
    if "detail" in boxes:
        parts.append(_text(boxes["detail"], "#333"))
    if "status" in boxes:
        parts.append(_text(boxes["status"], RETRO_STATUS[entry.kind], ' font-style="italic"'))
    if entry.kind == "expired":
        parts.append(f'<g transform="rotate(-14 {W / 2} 70)"><rect x="{W / 2 - 34}" y="60" width="68" height="20" '
                     'fill="#fff" fill-opacity="0.8" stroke="#c0392b" stroke-width="2"/>'
                     f'<text x="{W / 2}" y="75" text-anchor="middle" font-family="{SANS}" font-size="12" '
                     'font-weight="bold" fill="#c0392b">EXPIRED</text></g>')
    note = boxes["note"]
    if note.lines:
        h = len(note.lines) * note.line_height + 8
        parts.append(f'<g transform="rotate(6 124 {28 + h / 2})"><rect x="84" y="28" width="80" height="{h:g}" '
                     'fill="#fff59d" stroke="#e0d36a"/>'
                     + text_block(note.lines, 124, note.y, note.size, note.line_height,
                                  f'font-family="{SANS}" text-anchor="middle" fill="#3a3a00"') + "</g>")
    return _svg("".join(parts), f"{entry.name} ({entry.status})", entry.kind == "expired")


def render_tile(entry: Entry, image: str | None, style: str, theme: str = "dark") -> str:
    return _card(entry, image, theme) if style == "card" else _retro(entry, image)
