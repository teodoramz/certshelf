import base64
import io
import re
import struct
import urllib.error
import xml.dom.minidom
import zlib
from datetime import date

from certshelf.images import load_image
from certshelf.model import Entry
from certshelf.svgtext import text_width
from certshelf.tiles import initials, layout, render_tile, tile_files


def png(width=2, height=2) -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


PNG_URI = "data:image/png;base64," + base64.b64encode(png()).decode()


def make(kind="active", name="GIAC Penetration Tester (GPEN)", note=None, status=None):
    return Entry("k", name, "GIAC", None, "https://example.org", status or {"active": "Active", "expired": "Expired",
                 "extra": "Exam passed"}[kind], kind, "Expires Oct 2030", note, date(2026, 10, 20))


def parse(svg):
    return xml.dom.minidom.parseString(svg)


def words(svg):
    """The tile's text with line breaks turned into spaces."""
    return " ".join(re.sub(r"<[^>]+>", " ", svg.replace("</tspan>", " </tspan>")).split())


def test_card_tiles_parse():
    for theme in ("dark", "light"):
        svg = render_tile(make("extra", note="Certification/badge fee not paid & more"), PNG_URI, "card", theme)
        parse(svg)
        assert 'width="168" height="216"' in svg
        assert "<script" not in svg
        assert set(re.findall(r"https?://[^\"' ]+", svg)) <= {"http://www.w3.org/2000/svg", "http://www.w3.org/1999/xlink"}
        for text in ("GIAC", "Exam passed", "Expires Oct 2030", "Certification/badge fee not paid &amp; more"):
            assert text in words(svg)
    assert render_tile(make(), PNG_URI, "card", "dark") != render_tile(make(), PNG_URI, "card", "light")


def test_expired_is_grey():
    assert "saturate" in render_tile(make("expired"), PNG_URI, "card", "dark")
    assert "saturate" not in render_tile(make("active"), PNG_URI, "card", "dark")


def test_monogram_without_image():
    assert initials("CC Exam") == "CC"
    assert initials("GIAC Penetration Tester (GPEN)") == "GPEN"
    assert initials("cloud practitioner") == "CP"
    svg = render_tile(make(name="CC Exam"), None, "card", "dark")
    parse(svg)
    assert ">CC<" in svg and "<image" not in svg


def test_retro_tile():
    svg = render_tile(make("expired", note="Fee not paid"), PNG_URI, "retro")
    parse(svg)
    assert "EXPIRED" in svg and "Fee not paid" in words(svg) and 'width="168" height="216"' in svg
    assert "EXPIRED" not in render_tile(make("active"), PNG_URI, "retro")


def test_long_text_fits():
    entry = make("extra", name="Very " * 18, note="A rather long note that keeps going " * 4)
    for style in ("card", "retro"):
        boxes = layout(entry, style)
        for box in boxes:
            for line in box.lines:
                assert sum(text_width(t, box.size, bold=b) for t, b in line) <= box.width + 0.01, (style, box.name)
        names = [b for b in boxes if b.name == "name"][0]
        notes = [b for b in boxes if b.name == "note"][0]
        assert len(names.lines) <= 2 and len(notes.lines) <= (2 if style == "card" else 4)
        assert "".join(t for t, _ in notes.lines[-1]).endswith("…")
        assert max(b.bottom for b in boxes) <= 216 - 8


def test_tile_files():
    assert tile_files(make(), "card") == ["k-dark.svg", "k-light.svg"]
    assert tile_files(make(), "retro") == ["k.svg"]


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_load_image_credly_size_fallback(tmp_path):
    asked = []

    def urlopen(request, timeout=None):
        asked.append(request.full_url)
        if "/size/" in request.full_url:
            raise urllib.error.HTTPError(request.full_url, 404, "no", {}, None)
        return Reply(png())

    uri = load_image("https://images.credly.com/images/abc/image.png", tmp_path, urlopen=urlopen)
    assert uri.startswith("data:image/png;base64,")
    assert asked == ["https://images.credly.com/size/160x160/images/abc/image.png",
                     "https://images.credly.com/images/abc/image.png"]


def test_load_image_from_repo_and_failures(tmp_path):
    (tmp_path / "certs").mkdir()
    (tmp_path / "certs" / "cc.png").write_bytes(png())
    (tmp_path / "notes.txt").write_text("not an image")
    assert load_image("certs/cc.png", tmp_path).startswith("data:image/png;base64,")
    assert load_image("missing.png", tmp_path) is None
    assert load_image("notes.txt", tmp_path) is None
    assert load_image("../../etc/passwd", tmp_path) is None
    assert load_image(None, tmp_path) is None


def test_dark_cards_put_a_light_plate_behind_the_badge():
    assert 'class="plate"' in render_tile(make(), PNG_URI, "card", "dark")
    assert 'class="plate"' not in render_tile(make(), PNG_URI, "card", "light")


def test_sticky_note_breaks_at_slashes():
    boxes = {b.name: b for b in layout(make("extra", name="CC Exam", note="Certification/badge fee not paid"), "retro")}
    assert ["".join(t for t, _ in line) for line in boxes["note"].lines][0] == "Certification/"
