import pytest
from main import (
    load_markdown_file,
    parse_tokens_with_positions,
    extract_headings,
    mark_leaf_headings,
    find_heading_body_ends,
    attach_anki_link,
    Heading,
)
import pathlib

current_dir = pathlib.Path(__file__).parent


@pytest.fixture
def markdown_1_lines():
    return load_markdown_file(current_dir / "assets/1.md")


@pytest.fixture
def markdown_1_tokens(markdown_1_lines):
    md_text = "".join(markdown_1_lines)
    return parse_tokens_with_positions(md_text)


def test_extract_headings(markdown_1_tokens):
    headings = extract_headings(markdown_1_tokens)
    assert len(headings) == 7
    assert isinstance(headings[0], Heading)


def test_leaf_headings(markdown_1_tokens):
    headings = extract_headings(markdown_1_tokens)
    headings = mark_leaf_headings(headings)
    leaf_headings = [heading for heading in headings if heading.is_leaf]
    assert len(leaf_headings) == 5


def test_content_boundaries(markdown_1_lines, markdown_1_tokens):
    headings = extract_headings(markdown_1_tokens)
    headings = mark_leaf_headings(headings)
    headings = find_heading_body_ends(markdown_1_lines, headings)
    leaf_headings = [heading for heading in headings if heading.is_leaf]

    content_lines = markdown_1_lines[
        leaf_headings[1].title_end : leaf_headings[1].heading_body_end
    ]
    assert content_lines == ["\n", "some content\n", "\n"]


def test_heading_strippped_content(markdown_1_tokens):
    headings = extract_headings(markdown_1_tokens)
    assert headings[1].title_text == "non-leaf heading 1"


def test_heading_tags(markdown_1_tokens):
    headings = extract_headings(markdown_1_tokens)
    assert headings[1].tags == ["tag_a::tag_b", "tag_c"]


def test_heading_ankilink(markdown_1_lines, markdown_1_tokens):
    headings = extract_headings(markdown_1_tokens)
    headings = mark_leaf_headings(headings)
    headings = find_heading_body_ends(markdown_1_lines, headings)
    leaf_headings = [heading for heading in headings if heading.is_leaf]

    leaf_headings = attach_anki_link(markdown_1_lines, leaf_headings[:3])

    assert leaf_headings[0].anki_link.id == "1742583930452"
    assert leaf_headings[0].anki_link.mod == "1742583944"


def test_heading_ankilink_line_idx(markdown_1_lines, markdown_1_tokens):
    headings = extract_headings(markdown_1_tokens)
    headings = mark_leaf_headings(headings)
    headings = find_heading_body_ends(markdown_1_lines, headings)
    leaf_headings = [heading for heading in headings if heading.is_leaf]

    leaf_headings = attach_anki_link(markdown_1_lines, leaf_headings[:3])

    assert leaf_headings[0].anki_link.line_start == 14
    assert leaf_headings[0].anki_link.line_end == 16

    assert leaf_headings[2].anki_link.line_start == 27
    assert leaf_headings[2].anki_link.line_end == 28


def test_heading_ankilink_nomod(markdown_1_lines, markdown_1_tokens):
    headings = extract_headings(markdown_1_tokens)
    headings = mark_leaf_headings(headings)
    headings = find_heading_body_ends(markdown_1_lines, headings)
    leaf_headings = [heading for heading in headings if heading.is_leaf]

    leaf_headings = attach_anki_link(markdown_1_lines, leaf_headings[:3])

    assert leaf_headings[2].anki_link.id == "1742583930452"
    assert leaf_headings[2].anki_link.mod is None


def test_heading_ankilink_noid(markdown_1_lines, markdown_1_tokens):
    headings = extract_headings(markdown_1_tokens)
    headings = mark_leaf_headings(headings)
    headings = find_heading_body_ends(markdown_1_lines, headings)
    leaf_headings = [heading for heading in headings if heading.is_leaf]

    with pytest.raises(Exception):
        leaf_headings = attach_anki_link(markdown_1_lines, leaf_headings[3:4])


def test_heading_ankilink_multiple(markdown_1_lines, markdown_1_tokens):
    headings = extract_headings(markdown_1_tokens)
    headings = mark_leaf_headings(headings)
    headings = find_heading_body_ends(markdown_1_lines, headings)
    leaf_headings = [heading for heading in headings if heading.is_leaf]

    with pytest.raises(Exception):
        leaf_headings = attach_anki_link(markdown_1_lines, leaf_headings[4:5])
