"""Certifications as plain entries, wherever they came from."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

KINDS = ("active", "extra", "expired")
EXTRA_KEYS = ("name", "issuer", "date", "status", "note", "image", "link", "expires")


@dataclass(frozen=True)
class Entry:
    key: str  # stable file name stem
    name: str
    issuer: str
    image: str | None  # URL or path in the repo
    link: str | None
    status: str  # pill text: "Active", "Expired", or the extra's own status
    kind: str  # one of KINDS
    date_line: str
    note: str | None
    sort_date: date


class ExtrasError(ValueError):
    """The `extra` input could not be read."""


def month(d: date) -> str:
    return d.strftime("%b %Y")


def slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _parse_date(value: str, line: int) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ExtrasError(f"line {line}: {value!r} is not a date like 2025-11-18") from None


def parse_extras(text: str, today: date) -> list[Entry]:
    """Read a small YAML-like list of flat entries ("- name: …" then indented "key: value" lines)."""
    raw: list[tuple[int, dict[str, str], dict[str, int]]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            raw.append((number, {}, {}))
            stripped = stripped[2:].strip()
        elif not raw:
            raise ExtrasError(f"line {number}: start each entry with '- name: …'")
        key, sep, value = stripped.partition(":")
        key = key.strip()
        if not sep or key not in EXTRA_KEYS:
            raise ExtrasError(f"line {number}: expected 'key: value' with key one of {', '.join(EXTRA_KEYS)}")
        raw[-1][1][key] = _unquote(value)
        raw[-1][2][key] = number

    entries: list[Entry] = []
    seen: set[str] = set()
    for number, fields, lines in raw:
        name = fields.get("name", "")
        if not name:
            raise ExtrasError(f"line {number}: every entry needs a name")
        earned = _parse_date(fields["date"], lines["date"]) if fields.get("date") else None
        expires = _parse_date(fields["expires"], lines["expires"]) if fields.get("expires") else None
        expired = expires is not None and expires < today
        key = slug(name) or "entry"
        while key in seen:
            key += "-2"
        seen.add(key)
        entries.append(Entry(
            key=key,
            name=name,
            issuer=fields.get("issuer", ""),
            image=fields.get("image") or None,
            link=fields.get("link") or None,
            status="Expired" if expired else (fields.get("status") or "Earned"),
            kind="expired" if expired else "extra",
            date_line=f"Expired {month(expires)}" if expired else (month(earned) if earned else ""),
            note=fields.get("note") or None,
            sort_date=expires if expired else (earned or date.min),
        ))
    return entries


def order(entries: list[Entry]) -> list[Entry]:
    """Active first, then extras, then expired; newest first within each group."""
    return sorted(entries, key=lambda e: (KINDS.index(e.kind), -e.sort_date.toordinal(), e.name.lower()))
