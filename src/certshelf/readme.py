"""The README block between the certshelf markers: one linked tile per entry."""
from __future__ import annotations

from .model import Entry
from .svgtext import esc
from .tiles import W, tile_files

START = "<!-- certshelf:start -->"
END = "<!-- certshelf:end -->"


def _tile(entry: Entry, folder: str, style: str) -> str:
    files = [f"{folder}/{name}" for name in tile_files(entry, style)]
    alt = esc(entry.name)
    if style == "card":
        tile = (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{esc(files[0])}">'
                f'<img src="{esc(files[1])}" width="{W}" alt="{alt}"></picture>')
    else:
        tile = f'<img src="{esc(files[0])}" width="{W}" alt="{alt}">'
    return f'<a href="{esc(entry.link)}">{tile}</a>' if entry.link else tile


def build_block(entries: list[Entry], folder: str, style: str) -> str:
    rows = "\n".join(f"  {_tile(e, folder, style)}" for e in entries)
    return f'<p align="center">\n{rows}\n</p>'


def replace_block(text: str, block: str) -> str | None:
    """`text` with the block between the markers replaced, or None when the markers are missing."""
    start = text.find(START)
    end = text.find(END, start + len(START)) if start >= 0 else -1
    if start < 0 or end < 0:
        return None
    return f"{text[:start + len(START)]}\n{block}\n{text[end:]}"
