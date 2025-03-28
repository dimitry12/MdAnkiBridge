import pytest
import pathlib
import shutil
from anki.collection import Collection
from main import main
from main import (
    load_markdown_file,
    parse_tokens_with_positions,
    extract_headings,
    mark_leaf_headings,
    attach_verbatim_content,
    attach_anki_link,
    Heading,
)

current_dir = pathlib.Path(__file__).parent
starter_note_id = 1743032558208
starter_model = "Basic"
starter_deck = "Default"


@pytest.fixture
def history_0_collection_path(tmp_path):
    starter_collection_asset = current_dir / "assets/starter.anki2"
    collection_path = tmp_path / "starter.anki2"

    shutil.copy(starter_collection_asset, collection_path)

    yield collection_path

    collection_path.unlink()


@pytest.fixture
def md_1_path(tmp_path):
    md_1 = current_dir / "assets/history_1.md"
    md_path = tmp_path / "history_1.md"

    shutil.copy(md_1, md_path)

    yield md_path

    md_path.unlink()


@pytest.fixture
def md_2_path(tmp_path):
    md_2 = current_dir / "assets/history_2.md"
    md_path = tmp_path / "history_2.md"

    shutil.copy(md_2, md_path)

    yield md_path

    md_path.unlink()


@pytest.fixture
def md_3_path(tmp_path):
    md_3 = current_dir / "assets/history_3.md"
    md_path = tmp_path / "history_3.md"

    shutil.copy(md_3, md_path)

    yield md_path

    md_path.unlink()


@pytest.fixture
def md_4_path(tmp_path):
    md_4 = current_dir / "assets/history_4.md"
    md_path = tmp_path / "history_4.md"

    shutil.copy(md_4, md_path)

    yield md_path

    md_path.unlink()


def test_starter_has_note(history_0_collection_path):
    colpath = str(history_0_collection_path)
    col = Collection(colpath)

    basic_model = col.models.by_name(starter_model)
    deck = col.decks.by_name(starter_deck)
    col.decks.select(deck["id"])
    col.decks.current()["mid"] = basic_model["id"]

    note = col.get_note(starter_note_id)

    assert note is not None
    assert note.fields[0] == "front"
    assert note.fields[1] == "back"

    col.close()


def test_new_sync(history_0_collection_path, md_1_path):
    colpath = str(history_0_collection_path)
    mdpath = str(md_1_path)

    mdlines = load_markdown_file(mdpath)
    old_lines_count = len(mdlines)

    main(
        filepath=mdpath, colpath=colpath, modelname=starter_model, deckname=starter_deck
    )

    mdlines = load_markdown_file(mdpath)
    mdtokens = parse_tokens_with_positions("".join(mdlines))
    headings = extract_headings(mdtokens)
    headings = mark_leaf_headings(headings)
    headings = attach_verbatim_content(mdlines, headings)
    leaf_headings = [heading for heading in headings if heading.is_leaf]

    leaf_headings = attach_anki_link(mdlines, leaf_headings)

    assert (
        len(mdlines) == old_lines_count + 2
    ), "Adding anki-link to after the heading on md-side only adds one newline if heading is already followed by the newline."
    assert mdlines[1] == "\n", "Newline before the anki-link"
    assert mdlines[3] == "\n", "Newline after the anki-link"
    assert leaf_headings[0].anki_id is not None
    assert leaf_headings[0].anki_mod is not None

    col = Collection(colpath)

    basic_model = col.models.by_name(starter_model)
    deck = col.decks.by_name(starter_deck)
    col.decks.select(deck["id"])
    col.decks.current()["mid"] = basic_model["id"]

    note = col.get_note(int(leaf_headings[0].anki_id))

    assert note is not None
    assert note.fields[0] == "heading title"
    assert (
        note.fields[1] == "\nsome content\n"
    ), "Anki-side of the synced note does not include the link to anki."

    col.close()


def test_md_update(history_0_collection_path, md_2_path):
    colpath = str(history_0_collection_path)
    mdpath = str(md_2_path)

    mdlines = load_markdown_file(mdpath)
    mdtokens = parse_tokens_with_positions("".join(mdlines))
    headings = extract_headings(mdtokens)
    headings = mark_leaf_headings(headings)
    headings = attach_verbatim_content(mdlines, headings)
    leaf_headings = [heading for heading in headings if heading.is_leaf]

    leaf_headings = attach_anki_link(mdlines, leaf_headings)

    assert mdlines[1] == "\n", "Newline before the anki-link"
    assert mdlines[3] == "\n", "Newline after the anki-link"
    assert leaf_headings[0].anki_mod is not None
    old_md_mod = leaf_headings[0].anki_mod

    main(
        filepath=mdpath, colpath=colpath, modelname=starter_model, deckname=starter_deck
    )

    mdlines = load_markdown_file(mdpath)
    mdtokens = parse_tokens_with_positions("".join(mdlines))
    headings = extract_headings(mdtokens)
    headings = mark_leaf_headings(headings)
    headings = attach_verbatim_content(mdlines, headings)
    leaf_headings = [heading for heading in headings if heading.is_leaf]

    leaf_headings = attach_anki_link(mdlines, leaf_headings)

    assert mdlines[1] == "\n", "Newline before the anki-link"
    assert mdlines[3] == "\n", "Newline after the anki-link"
    assert leaf_headings[0].anki_mod > old_md_mod

    col = Collection(colpath)

    basic_model = col.models.by_name(starter_model)
    deck = col.decks.by_name(starter_deck)
    col.decks.select(deck["id"])
    col.decks.current()["mid"] = basic_model["id"]

    note = col.get_note(starter_note_id)

    assert note is not None
    assert note.fields[0] == "heading title"
    assert (
        note.fields[1] == "\nsome content\n"
    ), "Anki-side of the synced note does not include the link to anki."
    assert set(note.tags) == set("tag_a::tag_b tag_c".split())

    col.close()


def test_md_unknown_id(history_0_collection_path, md_4_path):
    colpath = str(history_0_collection_path)
    mdpath = str(md_4_path)

    mdlines = load_markdown_file(mdpath)
    mdtokens = parse_tokens_with_positions("".join(mdlines))
    headings = extract_headings(mdtokens)
    headings = mark_leaf_headings(headings)
    headings = attach_verbatim_content(mdlines, headings)
    leaf_headings = [heading for heading in headings if heading.is_leaf]
    leaf_headings = attach_anki_link(mdlines, leaf_headings)

    assert leaf_headings[0].anki_mod is not None
    assert leaf_headings[0].anki_id is not None

    with pytest.raises(Exception):
        main(
            filepath=mdpath,
            colpath=colpath,
            modelname=starter_model,
            deckname=starter_deck,
        )
