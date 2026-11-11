import copy
import io
import json
import urllib.error
from datetime import date
from pathlib import Path

import pytest

from certshelf.credly import CredlyError, fetch_badges, parse_badges

TODAY = date(2026, 11, 11)
PAGE = json.loads((Path(__file__).parent / "fixtures" / "credly-teodor.json").read_text())


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_parse_teodor():
    entries = {e.name: e for e in parse_badges([PAGE], TODAY)}
    assert len(entries) == 3
    gpen = entries["GIAC Penetration Tester (GPEN)"]
    assert (gpen.kind, gpen.status, gpen.date_line, gpen.issuer) == ("active", "Active", "Expires Oct 2030", "GIAC")
    assert gpen.link == "https://www.credly.com/badges/923f7509-40c9-471e-b2af-8e0dc40874e8"
    assert gpen.image.startswith("https://images.credly.com/images/394a708e")
    old = entries["ISC2 Candidate"]
    assert (old.kind, old.status, old.date_line, old.issuer) == ("expired", "Expired", "Expired Oct 2026", "ISC2")


def test_skips_revoked_and_private():
    page = copy.deepcopy(PAGE)
    page["data"][0]["state"] = "revoked"
    page["data"][1]["public"] = False
    assert len(parse_badges([page], TODAY)) == 1


def test_no_expiry():
    page = copy.deepcopy(PAGE)
    page["data"] = page["data"][:1]
    page["data"][0]["expires_at_date"] = None
    [e] = parse_badges([page], TODAY)
    assert (e.kind, e.date_line) == ("active", "Issued Oct 2026")


def test_fetch_follows_pages():
    first = copy.deepcopy(PAGE)
    first["data"] = PAGE["data"][:2]
    first["metadata"]["next_page_url"] = "https://www.credly.com/users/someone/badges.json?page=2&page_size=48"
    second = copy.deepcopy(PAGE)
    second["data"] = PAGE["data"][2:]
    seen = []

    def urlopen(request, timeout=None):
        seen.append(request)
        return Reply(json.dumps(first if len(seen) == 1 else second).encode())

    entries = fetch_badges("someone", TODAY, urlopen=urlopen)
    assert len(entries) == 3
    assert "users/someone/badges.json" in seen[0].full_url and "page_size=48" in seen[0].full_url
    assert seen[0].get_header("Accept") == "application/json"
    assert seen[0].get_header("User-agent")
    assert "page=2" in seen[1].full_url


def test_fetch_errors():
    def not_found(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

    with pytest.raises(CredlyError, match="404"):
        fetch_badges("nobody", TODAY, urlopen=not_found)
    with pytest.raises(CredlyError):
        fetch_badges("x", TODAY, urlopen=lambda r, timeout=None: Reply(b"<html>"))
