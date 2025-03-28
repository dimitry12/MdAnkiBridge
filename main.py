from markdown_it import MarkdownIt
import re
import fire
from urllib.parse import urlparse, parse_qs

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
                    "verbatim_content": [],  # added this property
                }

                # Extract tags (#tag or #tag1/tag2)
                heading["tags"] = re.findall(r"#([\w\d_\/]+)", content)
                heading["tags"] = [tag.replace("/", "::") for tag in heading["tags"]]

                stripped_content = content
                stripped_content = re.sub(r"{.*}", "", stripped_content)
                stripped_content = re.sub(r"#([\w\d_\/]+)", "", stripped_content)
                heading["stripped_content"] = stripped_content.strip()

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
            # if next_heading["level"] <= heading["level"]:
            #    content_end = next_heading["start_line"]
            #    break
            content_end = next_heading["start_line"]
            break

        # # Only leaf headings get content
        # if heading["is_leaf"]:
        #     # Extract lines verbatim, preserve whitespace, line endings.
        #     heading["verbatim_content"] = lines[content_start:content_end]
        heading["verbatim_content"] = lines[content_start:content_end]
        heading["content_start"] = content_start
        heading["content_end"] = content_end
    return headings


def find_anki_link(lines):
    anki_link_pattern = re.compile(r"\[anki\]\((mdankibridge://notes/[^\s]*)\)")
    matches = []

    for idx, content_line in enumerate(lines):
        match = anki_link_pattern.search(content_line)

        if match:
            if (
                idx > 0
                and idx < (len(lines) - 1)
                and lines[idx - 1].strip() == ""
                and lines[idx + 1].strip() == ""
            ):
                # if newline before and after, then link and newline after are together
                matches.append((idx, idx + 1, match))
            else:
                matches.append((idx, idx, match))

    if len(matches) > 1:
        raise ValueError("Multiple Anki links found in the same heading")

    if len(matches) == 0:
        return None

    anki_url = matches[0][2].group(1)
    parsed_url = urlparse(anki_url)
    query_params = parse_qs(parsed_url.query)
    id_params = query_params.get("id")
    mod_params = query_params.get("mod")

    if not id_params or not id_params[0]:
        raise ValueError("Anki link missing id parameter")

    return (
        matches[0][0],
        matches[0][1],
        id_params[0],
        mod_params[0] if mod_params else None,
    )


def attach_anki_link(headings):
    for heading in headings:
        anki_metadata = find_anki_link(heading["verbatim_content"])
        if anki_metadata:
            first_heading_line_idx, last_heading_line_idx, anki_id, anki_mod = (
                anki_metadata
            )
            heading["anki_id"] = anki_id
            heading["anki_mod"] = anki_mod
            heading["anki_link_lines"] = (
                first_heading_line_idx + heading["start_line"] + 1,
                last_heading_line_idx + 1 + heading["start_line"] + 1,
            )
        else:
            heading["anki_id"] = None
            heading["anki_mod"] = None
            heading["anki_link_lines"] = None

    return headings


def get_heading_attributes(lines, heading):
    """
    Extract attribute key-value pairs from a Markdown Extra attributes block.

    Args:
        lines: list of markdown file lines
        heading: dict with 'start_line' indicating the heading position

    Returns:
        dict of attributes extracted from the heading
    """
    attr_dict = {}
    line_idx = heading["start_line"]
    line = lines[line_idx]

    # TODO: preserve other non-key-value attributes

    attr_match = re.search(r"\{(.*?)\}\s*$", line.strip())
    if attr_match:
        attr_string = attr_match.group(1)
        # Split attribute pairs, separated by spaces
        for attr_pair in re.findall(r"(\w+)=([\w\-\_]+)", attr_string):
            key, value = attr_pair
            attr_dict[key] = value
    return attr_dict


def set_heading_attributes(lines, heading, new_attrs):
    """
    Set heading's attribute markdown block from provided attribute dictionary.

    Args:
        lines: list of markdown file lines
        heading: dict with 'start_line' indicating heading position
        new_attrs: dict of attributes to insert/update in the heading

    Returns:
        Modified lines with updated attributes for the heading
    """
    line_idx = heading["start_line"]
    line = lines[line_idx].rstrip("\n")

    # TODO: preserve other non-key-value attributes

    existing_attrs_match = re.search(r"(.*?)(\s*\{.*\}\s*)?$", line)
    heading_text = existing_attrs_match.group(1).rstrip()

    # Create new attribute string from new_attrs dict
    attrs_string = " ".join(f"{k}={v}" for k, v in new_attrs.items())
    new_line = f"{heading_text} {{ {attrs_string} }}\n"

    lines[line_idx] = new_line
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
    headings = attach_anki_link(headings)

    updated_lines = lines[: headings[0]["start_line"]]

    for heading in headings:
        if not heading["is_leaf"]:
            updated_lines += lines[heading["start_line"] : heading["content_end"]]

        if heading["anki_id"]:
            print("Processing heading with sync_id:", heading["anki_id"])

            try:
                note = col.get_note(int(heading["anki_id"]))
            except:
                raise ValueError(f"Note with id {heading['anki_id']} not found in Anki")

            if heading["anki_mod"] and note.mod > int(heading["anki_mod"]):
                print("    Note is newer in anki, skipping sync")
                raise ValueError("Note is newer in anki, skipping sync")
            else:
                if not heading["anki_mod"]:
                    print("    Note has no mod, syncing anyway")

                print("    Syncing heading with sync_id:", heading["anki_id"])
                note.fields[0] = heading["stripped_content"]
                note.fields[1] = "".join(
                    lines[heading["content_start"] : heading["anki_link_lines"][0]]
                    + lines[heading["anki_link_lines"][1] : heading["content_end"]]
                )

                note.tags = heading["tags"]
                col.update_note(note)

                # re-read note to get updated mod
                # anki updates mod iff content has changed
                # (i.e. we can resync same content and anki doesn't advance mod)
                note = col.get_note(int(heading["anki_id"]))

                if str(note.mod) == heading["anki_mod"]:
                    print("    Note is unchanged")
                heading["anki_mod"] = str(note.mod)

            updated_lines += (
                lines[heading["start_line"] : heading["anki_link_lines"][0]]
                + [
                    f"[anki](mdankibridge://notes/?id={heading['anki_id']}&mod={heading['anki_mod']})\n\n"
                ]
                + lines[heading["anki_link_lines"][1] : heading["content_end"]]
            )
        else:
            note = col.new_note(basic_model)
            note.fields[0] = heading["stripped_content"]
            note.fields[1] = "".join(
                lines[heading["content_start"] : heading["content_end"]]
            )
            note.tags = heading["tags"]
            col.add_note(note, deck["id"])
            heading["anki_id"] = str(note.id)
            print("Syncing new heading with sync_id:", heading["anki_id"])

            note = col.get_note(int(heading["anki_id"]))

            heading["anki_mod"] = str(note.mod)

            updated_lines += (
                lines[heading["start_line"] : heading["end_line"]]
                + [
                    f"\n[anki](mdankibridge://notes/?id={heading['anki_id']}&mod={heading['anki_mod']})\n"  # newline-separated
                    + ("" if lines[heading["end_line"]].strip() == "" else "\n")
                ]
                + lines[heading["end_line"] : heading["content_end"]]
            )

        # print("=" * 80)
        # print("Header:", heading["raw_content"])
        # print("Tags:", heading["tags"])
        # print("Content:\n", "".join(heading["verbatim_content"]))

    write_markdown_file(filepath, updated_lines)
    col.close()


if __name__ == "__main__":
    fire.Fire(main)
