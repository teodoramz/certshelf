import xml.dom.minidom

from certshelf.svgtext import esc, parse_markup, text_block, text_width, wrap


def line_width(line, size, mono=False):
    return sum(text_width(seg, size, bold=bold, mono=mono) for seg, bold in line)


def test_esc():
    assert esc("<a&b>\"") == "&lt;a&amp;b&gt;&quot;"


def test_parse_markup():
    assert parse_markup("a **b** c") == [("a ", False), ("b", True), (" c", False)]
    assert parse_markup("plain") == [("plain", False)]


def test_wrap_keeps_width_and_bold():
    lines = wrap("I tried to run **sudo**, but I'm not in the purr-sudoers file.", 200, 13)
    assert len(lines) > 1
    assert all(line_width(line, 13) <= 200 for line in lines)
    bold = [seg for line in lines for seg, b in line if b]
    assert "".join(bold).strip() == "sudo"


def test_wrap_truncates_with_ellipsis():
    lines = wrap("word " * 60, 150, 12, max_lines=2)
    assert len(lines) == 2
    assert "".join(seg for seg, _ in lines[-1]).endswith("…")
    assert all(line_width(line, 12) <= 150 for line in lines)


def test_wrap_hard_breaks_long_words():
    lines = wrap("x" * 60, 100, 12)
    assert len(lines) > 1
    assert all(line_width(line, 12) <= 100 for line in lines)
    assert "".join(seg for line in lines for seg, _ in line) == "x" * 60


def test_wide_glyphs_count_more():
    assert text_width("WWWW", 10) > text_width("iiii", 10)


def test_text_block_parses():
    lines = wrap("a & b < **c**", 300, 12)
    block = text_block(lines, 10, 20, 12, 16, "fill='#000'")  # outside the f-string: 3.10 forbids backslashes there
    svg = f'<svg xmlns="http://www.w3.org/2000/svg">{block}</svg>'
    doc = xml.dom.minidom.parseString(svg)
    assert doc.getElementsByTagName("tspan")
    assert "a &amp; b &lt; " in svg


def test_wrap_can_treat_text_as_plain():
    lines = wrap("a **b** c", 300, 12, markup=False)
    assert lines == [[("a **b** c", False)]]


def test_blank_line_keeps_its_space():
    svg = text_block([[("a", False)], [], [("b", False)]], 0, 10, 12, 16, "")
    dys = [m for m in __import__("re").findall(r'dy="([\d.]+)"', svg)]
    assert dys == ["0", "32"]


def test_wrap_prefers_breaking_after_hyphens():
    lines = wrap("Vulnerable-Drone-PX4-Lab", 92, 11, markup=False, break_after="-_.")
    texts = ["".join(t for t, _ in line) for line in lines]
    assert texts == ["Vulnerable-", "Drone-PX4-Lab"]
    assert all(line_width(line, 11) <= 92 for line in lines)


def test_wrap_keeps_punctuation_glued_to_bold_text():
    lines = wrap("committed in **16 days**. I'll nap", 400, 13)
    assert "".join(t for t, _ in lines[0]) == "committed in 16 days. I'll nap"


def test_emoji_and_wide_characters_are_measured_wide():
    for mono in (False, True):
        assert text_width("🔥", 12, mono=mono) >= 12 * 1.2
        assert text_width("猫", 12, mono=mono) >= 12 * 1.2
    lines = wrap("🔥🔥🔥 security 🐱🐱🐱 engineer 📍📍", 120, 12, mono=True, markup=False)
    assert all(line_width(line, 12, mono=True) <= 120 for line in lines)
