from markdown_it import MarkdownIt
import re
import fire

from anki.collection import Collection


def load_markdown_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return lines


def write_markdown_file(filepath, lines):
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)


def parse_tokens_with_positions(md_text):
    md = MarkdownIt()
    tokens = md.parse(md_text)
    return tokens


def extract_headings(tokens):
    headings = []
    for i, token in enumerate(tokens):
        if token.type == "heading_open":
            level = int(token.tag[1])
            inline_token = tokens[i + 1]
            if inline_token.type == "inline":
                content = inline_token.content
                heading = {
                    "level": level,
                    "token_index": i,
                    "start_line": token.map[0],
                    "end_line": token.map[1],
                    "raw_content": content,  # Original heading content
                    "strippped_content": None,
                    "tags": [],
                    "sync_id": None,
                    "verbatim_content": [],  # added this property
                }

                # Extract tags (#tag or #tag1/tag2)
                heading["tags"] = re.findall(r"#([\w\d_\/]+)", content)
                heading["tags"] = [tag.replace("/", "::") for tag in heading["tags"]]

                # Extract Markdown Extra custom attribute { sync_id=xxx }
                attr_match = re.search(r"{\s*anki_note=([\w-]+)\s*}", content)
                if attr_match:
                    heading["sync_id"] = attr_match.group(1)

                stripped_content = content
                stripped_content = re.sub(r"{.*}", "", stripped_content)
                stripped_content = re.sub(r"#([\w\d_\/]+)", "", stripped_content)
                heading["stripped_content"] = stripped_content

                headings.append(heading)
    return headings


def mark_leaf_headings(headings):
    """Add an 'is_leaf' flag to headings that have no child headings."""
    for idx, heading in enumerate(headings):
        current_level = heading["level"]
        # Assume leaf by default
        heading["is_leaf"] = True
        # Check if any subsequent heading is a child
        for next_heading in headings[idx + 1 :]:
            if next_heading["level"] > current_level:
                # found child heading -> current not leaf
                heading["is_leaf"] = False
                break
            elif next_heading["level"] <= current_level:
                # sibling or higher-level heading encountered, move to next heading
                break
    return headings


def replace_heading_in_lines(lines, heading, new_text):
    heading_markdown = "#" * heading["level"]
    lines[heading["start_line"]] = f"{heading_markdown} {new_text}\n"
    return lines


def attach_verbatim_content(lines, headings):
    total_lines = len(lines)
    for idx, heading in enumerate(headings):
        content_start = heading["end_line"]
        # Determine end line for content
        content_end = total_lines
        for next_heading in headings[idx + 1 :]:
            if next_heading["level"] <= heading["level"]:
                content_end = next_heading["start_line"]
                break

        # Only leaf headings get content
        if heading["is_leaf"]:
            # Extract lines verbatim, preserve whitespace, line endings.
            heading["verbatim_content"] = lines[content_start:content_end]
    return headings


def insert_sync_id(lines, heading, sync_id):
    """Insert `{ sync_id=ID }` at the end of the heading line"""
    line_idx = heading["start_line"]
    line = lines[line_idx].rstrip("\n")

    # Check if already has attributes {}, append if found or create new block
    if re.search(r"{.*}$", line):  # if heading already ends with {...} attributes
        line = re.sub(r"{(.*)}$", rf"{{\1 anki_note={sync_id}}}", line)
    else:
        line = f"{line} {{ anki_note={sync_id} }}"

    lines[line_idx] = line + "\n"
    return lines


def main(filepath: str, colpath: str, modelname: str, deckname: str):
    col = Collection(colpath)

    basic_model = col.models.by_name(modelname)
    deck = col.decks.by_name(deckname)
    col.decks.select(deck["id"])
    col.decks.current()["mid"] = basic_model["id"]

    lines = load_markdown_file(filepath)
    md_text = "".join(lines)
    tokens = parse_tokens_with_positions(md_text)
    headings = extract_headings(tokens)
    headings = mark_leaf_headings(headings)
    headings = attach_verbatim_content(lines, headings)

    for heading in headings:
        if heading["is_leaf"]:
            if heading["sync_id"]:
                print("Re-syncing heading with sync_id:", heading["sync_id"])

                note = col.get_note(int(heading["sync_id"]))
                note.fields[0] = heading["stripped_content"]
                note.fields[1] = "".join(heading["verbatim_content"])
                note.tags = ["_sync_on"] + heading["tags"]
                col.update_note(note)
            else:
                note = col.new_note(basic_model)
                note.fields[0] = heading["stripped_content"]
                note.fields[1] = "".join(heading["verbatim_content"])
                note.tags = ["_sync_on"] + heading["tags"]
                col.add_note(note, deck["id"])
                print("Syncing new heading with sync_id:", note.id)
                print("New content:", heading["raw_content"])

                lines = insert_sync_id(lines, heading, note.id)
            print("=" * 80)
            print("Header:", heading["raw_content"])
            print("Tags:", heading["tags"])
            print("Content:\n", "".join(heading["verbatim_content"]))

    write_markdown_file(filepath, lines)
    col.close()


if __name__ == "__main__":
    fire.Fire(main)
