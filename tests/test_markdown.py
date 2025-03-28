import pytest
from main import (
    parse_markdown_headings,
    split_body,
    Heading,
)
import pathlib

current_dir = pathlib.Path(__file__).parent


@pytest.fixture
def markdown_1_data():
    return parse_markdown_headings(current_dir / "assets/1.md")


@pytest.fixture
def markdown_1_lines(markdown_1_data):
    return markdown_1_data[0]


@pytest.fixture
def markdown_1_headings(markdown_1_data):
    return markdown_1_data[1]


def test_extract_headings(markdown_1_headings):
    assert len(markdown_1_headings) == 7
    assert isinstance(markdown_1_headings[0], Heading)


def test_leaf_headings(markdown_1_headings):
    leaf_headings = [heading for heading in markdown_1_headings if heading.is_leaf]
    assert len(leaf_headings) == 5


def test_content_boundaries(markdown_1_lines, markdown_1_headings):
    leaf_headings = [heading for heading in markdown_1_headings if heading.is_leaf]

    content_lines = markdown_1_lines[
        leaf_headings[1].title_end : leaf_headings[1].heading_body_end
    ]
    assert content_lines == ["\n", "some content\n", "\n"]


def test_heading_strippped_content(markdown_1_headings):
    assert markdown_1_headings[1].title_text == "non-leaf heading 1"


def test_heading_tags(markdown_1_headings):
    assert markdown_1_headings[1].tags == ["tag_a::tag_b", "tag_c"]


def test_heading_ankilink(markdown_1_lines, markdown_1_headings):
    leaf_headings = [heading for heading in markdown_1_headings if heading.is_leaf]

    leaf_headings = split_body(markdown_1_lines, leaf_headings[:3])

    assert leaf_headings[0].anki_link.id == "1742583930452"
    assert leaf_headings[0].anki_link.mod == "1742583944"


def test_heading_ankilink_line_idx(markdown_1_lines, markdown_1_headings):
    leaf_headings = [heading for heading in markdown_1_headings if heading.is_leaf]

    leaf_headings = split_body(markdown_1_lines, leaf_headings[:3])

    # assert leaf_headings[0].anki_link.line_start == 14
    # assert leaf_headings[0].anki_link.line_end == 16
    #
    # assert leaf_headings[2].anki_link.line_start == 27
    # assert leaf_headings[2].anki_link.line_end == 28


def test_heading_ankilink_nomod(markdown_1_lines, markdown_1_headings):
    leaf_headings = [heading for heading in markdown_1_headings if heading.is_leaf]

    leaf_headings = split_body(markdown_1_lines, leaf_headings[:3])

    assert leaf_headings[2].anki_link.id == "1742583930452"
    assert leaf_headings[2].anki_link.mod is None


def test_heading_ankilink_noid(markdown_1_lines, markdown_1_headings):
    leaf_headings = [heading for heading in markdown_1_headings if heading.is_leaf]

    with pytest.raises(Exception):
        leaf_headings = split_body(markdown_1_lines, leaf_headings[3:4])


def test_heading_ankilink_multiple(markdown_1_lines, markdown_1_headings):
    leaf_headings = [heading for heading in markdown_1_headings if heading.is_leaf]

    with pytest.raises(Exception):
        leaf_headings = split_body(markdown_1_lines, leaf_headings[4:5])
