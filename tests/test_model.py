from datetime import date

import pytest

from certshelf.model import Entry, ExtrasError, month, order, parse_extras, slug

TODAY = date(2026, 11, 11)
TEODOR = """
- name: CC Exam
  issuer: ISC2
  date: 2025-11-18
  status: Exam passed
  note: Certification/badge fee not paid
  image: https://images.credly.com/images/2859c37a-015b-40a6-b570-4bdd7e849b05/image.png
  link: certs/cc-exam-passed.png
"""


def entry(kind, day, name="x"):
    return Entry(slug(name), name, "", None, None, kind, kind, "", None, day)


def test_parse_extras_teodor():
    [cc] = parse_extras(TEODOR, TODAY)
    assert cc.name == "CC Exam"
    assert cc.issuer == "ISC2"
    assert cc.status == "Exam passed"
    assert cc.note == "Certification/badge fee not paid"
    assert cc.kind == "extra"
    assert cc.date_line == "Nov 2025"
    assert cc.key == "cc-exam"
    assert cc.link == "certs/cc-exam-passed.png"
    assert cc.image.endswith("/image.png")
    assert cc.sort_date == date(2025, 11, 18)


def test_extras_defaults_and_quotes():
    text = '# my certs\n\n- name: "Thing: One"\n  date: 2024-01-02\n- name: Two\n'
    one, two = parse_extras(text, TODAY)
    assert one.name == "Thing: One"
    assert one.status == "Earned"
    assert two.date_line == ""
    assert two.link is None and two.image is None and two.note is None


@pytest.mark.parametrize(
    "text, line",
    [
        ("- issuer: ISC2\n", 1),
        ("- name: A\n  date: 18-11-2025\n", 2),
        ("  name: A\n", 1),
        ("- name: A\n  colour blue\n", 2),
    ],
)
def test_extras_errors(text, line):
    with pytest.raises(ExtrasError, match=f"line {line}"):
        parse_extras(text, TODAY)


def test_extra_expired():
    [e] = parse_extras("- name: Old\n  date: 2019-01-01\n  expires: 2020-01-01\n", TODAY)
    assert e.kind == "expired"
    assert e.status == "Expired"


def test_order():
    items = [entry("expired", date(2026, 1, 1), "e1"), entry("extra", date(2025, 1, 1), "x1"),
             entry("active", date(2024, 1, 1), "a1"), entry("active", date(2026, 1, 1), "a2"),
             entry("expired", date(2026, 6, 1), "e2"), entry("extra", date(2026, 1, 1), "x2")]
    assert [e.name for e in order(items)] == ["a2", "a1", "x2", "x1", "e2", "e1"]
    same_day = [entry("active", date(2026, 1, 1), "b"), entry("active", date(2026, 1, 1), "A")]
    assert [e.name for e in order(same_day)] == ["A", "b"]


def test_month_and_slug():
    assert month(date(2025, 11, 18)) == "Nov 2025"
    assert slug("GIAC Penetration Tester (GPEN)") == "giac-penetration-tester-gpen"
    assert slug("ÄÖ  !!") == "ao"
