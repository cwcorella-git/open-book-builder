"""The converter: the author guide's example, each rejection, emphasis nesting and repeatable output."""
from pathlib import Path

import pytest

from open_book_builder.convert import convert
from open_book_builder.convert.body import BOLD, BOTH, ITALIC, PLAIN, SI, SO, transition

HEADER = "---\nid: sample\nversion: 1\ntitle: Sample\ntype: book\nlanguage: en\n---\n"
FIXTURES = Path(__file__).parent / "fixtures" / "works"


def run(body: str, header: str = HEADER):
    return convert(header + body)


def errors(result):
    return [i.message for i in result.report.errors]


def test_guide_example_matches_the_guide_bytes():
    result = convert((FIXTURES / "lighthouse.md").read_bytes())
    assert result.report.ok and result.filename == "lighthouse.txt"
    expected = (
        "---\nTITL: The Lighthouse Keeper\nAUTH: A. Writer\nGNRE: stories;type:article\nLANG: en\n---\n"
        "\x1eThe Lamp\n"
        "The keeper climbed the stairs \x0feveryy\x0e evening. It was the \x0f\x0fonly\x0e thing she was sure of.\n"
        "\x1eThe Storm\n- Wind from the north\n- Rain by midnight\n"
    ).replace("everyy", "every")
    assert result.data == expected.encode()


def test_guide_text_still_shows_the_same_example():
    guide = (Path(__file__).parent.parent / "docs" / "author-guide.md").read_text()
    assert "The keeper climbed the stairs <SI>every<SO> evening. It was the <SI><SI>only<SO> thing she was sure of." in guide


def test_output_is_repeatable():
    source = (FIXTURES / "lighthouse.md").read_bytes()
    assert convert(source).data == convert(source).data


@pytest.mark.parametrize(
    "old,new,codes",
    [
        (PLAIN, ITALIC, SI),
        (PLAIN, BOLD, SI + SI),
        (PLAIN, BOTH, SI + SI + SI),
        (ITALIC, PLAIN, SO),
        (BOLD, PLAIN, SO),
        (BOTH, BOLD, SO),
        (BOTH, PLAIN, SO + SO),
        (BOLD, ITALIC, SO + SI),
        (ITALIC, BOLD, SI),
    ],
)
def test_style_transitions(old, new, codes):
    assert transition(old, new) == codes


def test_nested_emphasis_returns_to_plain():
    result = run("a ***both*** b **bold *and italic* bold** c\n")
    line = result.data.decode().split("\n")[-2]
    expected = f"a {SI*3}both{SO*2} b {SI*2}bold {SI}and italic{SO} bold{SO} c"
    assert line == expected


def test_paragraph_lines_are_joined_and_blank_line_splits():
    lines = run("one\ntwo\n\nthree\n").data.decode().split("\n")
    assert lines[-3:] == ["one two", "three", ""]


def test_link_keeps_text_only_and_quote_is_paragraph():
    lines = run("See [the page](https://example.org) now.\n\n> quoted words\n").data.decode().split("\n")
    assert "See the page now." in lines and "quoted words" in lines


def test_subheading_is_a_bold_line():
    lines = run("## A section\n\ntext\n").data.decode().split("\n")
    assert f"{SI}{SI}A section{SO}" in lines


@pytest.mark.parametrize(
    "body,word",
    [
        ("![alt](pic.png)\n", "image"),
        ("| a | b |\n|---|---|\n| 1 | 2 |\n", "table"),
        ("<div>hello</div>\n", "HTML"),
        ("text[^1]\n\n[^1]: note\n", "footnote"),
        ("```\ncode\n```\n", "code block"),
        ("use `x` here\n", "Code"),
        ("math $$x^2$$\n", "Math"),
        ("an *open emphasis\n", "never closed"),
    ],
)
def test_each_unsupported_item_is_rejected_with_its_line(body, word):
    result = run("first line\n\n" + body)
    assert result.data is None
    assert any(word.lower() in e.lower() for e in errors(result))
    assert all(i.line >= 9 for i in result.report.errors)


def test_long_run_is_flagged_at_its_line():
    result = run("short\n\n" + "x" * 130 + "\n")
    assert result.data is None
    item = result.report.errors[0]
    assert item.line == 10 and "130 bytes" in item.message


def test_run_just_under_limit_is_accepted():
    assert run("x" * 126 + "\n").data is not None


@pytest.mark.parametrize(
    "header,word",
    [
        ("---\nversion: 1\ntitle: T\ntype: book\nlanguage: en\n---\n", "'id'"),
        ("---\nid: Bad Id\nversion: 1\ntitle: T\ntype: book\nlanguage: en\n---\n", "id may use"),
        ("---\nid: a\nversion: x\ntitle: T\ntype: book\nlanguage: en\n---\n", "whole number"),
        ("---\nid: a\nversion: 1\ntitle: T\ntype: poem\nlanguage: en\n---\n", "book, article or document"),
        ("---\nid: a\nversion: 1\ntitle: T\ntype: book\nlanguage: en\ntags: [a;b]\n---\n", "reserved"),
        ("---\nid: a\nversion: 1\ntitle: T\ntype: book\nlanguage: en\ntags: [type:x]\n---\n", "reserved"),
        ("no header\n", "start with a header"),
        ("---\nid: a\n", "never closed"),
    ],
)
def test_header_errors(header, word):
    result = convert(header + "text\n")
    assert result.data is None and any(word in e for e in errors(result))


def test_filename_follows_id_and_crlf_is_noted_and_normalized():
    result = convert((HEADER + "one\r\ntwo\r\n").replace("\n", "\r\n", 0).replace("---\nid", "---\r\nid"))
    assert result.filename == "sample.txt" and result.data is not None
    assert b"\r" not in result.data
    assert any("line ends" in i.message for i in result.report.items)


def test_empty_body_is_rejected():
    assert run("").data is None


def test_unknown_field_is_a_note_not_an_error():
    result = convert("---\nid: a\nversion: 1\ntitle: T\ntype: book\nlanguage: en\ncolor: red\n---\ntext\n")
    assert result.data is not None
    assert any("color" in i.message for i in result.report.items if i.level == "note")


def test_invalid_utf8_is_rejected():
    assert convert(b"---\n\xff\xfe").data is None
