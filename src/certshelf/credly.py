"""Badges from a public Credly profile (credly.com/users/<username>)."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

from .model import Entry, month, slug

PAGE_SIZE = 48
MAX_PAGES = 20
USER_AGENT = "certshelf (+https://github.com/teodoramz/certshelf)"
SKIPPED_STATES = {"revoked", "rejected", "pending"}


class CredlyError(Exception):
    """Credly could not be read."""


def _issuer(badge: dict) -> str:
    entities = (badge.get("issuer") or {}).get("entities") or []
    chosen = next((e for e in entities if e.get("primary")), entities[0] if entities else {})
    name = (chosen.get("entity") or {}).get("name", "")
    short = re.search(r"\(([^()]+)\)\s*$", name)
    return short.group(1) if short else name


def _date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def parse_badges(pages: list[dict], today: date) -> list[Entry]:
    entries = []
    for page in pages:
        for badge in page.get("data") or []:
            if badge.get("state") in SKIPPED_STATES or badge.get("public") is False:
                continue
            template = badge.get("badge_template") or {}
            name = template.get("name") or "Badge"
            issued = _date(badge.get("issued_at_date")) or date.min
            expires = _date(badge.get("expires_at_date"))
            expired = badge.get("state") == "expired" or (expires is not None and expires < today)
            if expired:
                line = f"Expired {month(expires)}" if expires else "Expired"
            elif expires:
                line = f"Expires {month(expires)}"
            else:
                line = f"Issued {month(issued)}" if issued != date.min else ""
            badge_id = badge.get("id", "")
            entries.append(Entry(
                key=f"{slug(name)}-{badge_id[:8]}".strip("-"),
                name=name,
                issuer=_issuer(badge),
                image=badge.get("image_url") or template.get("image_url"),
                link=f"https://www.credly.com/badges/{badge_id}" if badge_id else None,
                status="Expired" if expired else "Active",
                kind="expired" if expired else "active",
                date_line=line,
                note=None,
                sort_date=(expires or issued) if expired else issued,
            ))
    return entries


def _get(url: str, urlopen) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as reply:
            data = json.loads(reply.read())
    except urllib.error.HTTPError as exc:
        raise CredlyError(f"Credly answered HTTP {exc.code} for {url}") from exc
    except (OSError, ValueError) as exc:
        raise CredlyError(f"could not read {url}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise CredlyError(f"unexpected answer from {url}")
    return data


def fetch_badges(username: str, today: date, urlopen=urllib.request.urlopen) -> list[Entry]:
    user = urllib.parse.quote(username.strip(), safe="")
    url = f"https://www.credly.com/users/{user}/badges.json?page=1&page_size={PAGE_SIZE}"
    pages = []
    for _ in range(MAX_PAGES):
        page = _get(url, urlopen)
        pages.append(page)
        nxt = (page.get("metadata") or {}).get("next_page_url")
        if not nxt or not str(nxt).startswith("https://www.credly.com/"):
            break
        url = nxt
    return parse_badges(pages, today)
