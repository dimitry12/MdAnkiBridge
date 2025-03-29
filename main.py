from markdown_it import MarkdownIt
import re
import fire
from urllib.parse import urlparse, parse_qs
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field

from anki.collection import Collection


def write_markdown_file(filepath, lines):
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)


class AnkiLink(BaseModel):
    id: str
    mod: Optional[str] = None

    @property
    def has_mod(self) -> bool:
        return self.mod is not None

    @property
    def lines(self) -> List[str]:
        """Generate the formatted lines for the anki link with trailing newlines."""
        mod_param = f"&mod={self.mod}" if self.mod else ""
        return [f"\n[anki](mdankibridge://notes/?id={self.id}{mod_param})\n\n"]


def normalize_lines(lines):
    while lines and lines[0].strip() == "":
        lines.pop(0)
    while lines and lines[-1].strip() == "":
        lines.pop()

    for idx, line in enumerate(lines):
        lines[idx] = line.rstrip("\n") + "\n"

    if lines:
        lines[-1] = lines[-1].rstrip("\n")

    return lines


class Heading(BaseModel):
    level: int
    heading_start: int
    title_end: int
    title_text: str = ""
    tags: List[str] = Field(default_factory=list)
    is_leaf: bool = False
    heading_body_end: Optional[int] = None
    anki_link: Optional[AnkiLink] = None
    other_content: Optional[List[str]] = None

    @property
    def title_lines(self) -> List[str]:
        """Generate the formatted title lines with proper heading level and tags."""
        heading_prefix = "#" * self.level + " "

        # Format tags as #tag1/tag2 format
        formatted_tags = []
        for tag in self.tags:
            formatted_tag = tag.replace("::", "/")
            formatted_tags.append(f"#{formatted_tag}")

        tags_text = " ".join(formatted_tags)

        # Add space between title and tags if both exist
        if self.title_text and tags_text:
            return [f"{heading_prefix}{self.title_text} {tags_text}\n"]
        elif self.title_text:
            return [f"{heading_prefix}{self.title_text}\n"]
        elif tags_text:
            return [f"{heading_prefix}{tags_text}\n"]
        else:
            return [f"{heading_prefix}\n"]


def parse_markdown_headings(filepath: str) -> Tuple[List[str], List[Heading]]:
    """
    Parse a markdown file and extract all headings with their properties.

    Args:
        filepath: Path to the markdown file

    Returns:
        Tuple containing:
        - List of lines from the markdown file
        - List of Heading objects
    """
    # Load the markdown file
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Parse the markdown into tokens
    md_text = "".join(lines)
    md = MarkdownIt()
    tokens = md.parse(md_text)

    # Extract headings from tokens
    headings = []
    for i, token in enumerate(tokens):
        if token.type == "heading_open":
            level = int(token.tag[1])
            inline_token = tokens[i + 1]
            if inline_token.type == "inline":
                content = inline_token.content

                # Extract tags (#tag or #tag1/tag2)
                tags = re.findall(r"#([\w\d_\/]+)", content)
                tags = [tag.replace("/", "::") for tag in tags]

                stripped_content = content
                stripped_content = re.sub(r"{.*}", "", stripped_content)
                stripped_content = re.sub(r"#([\w\d_\/]+)", "", stripped_content)

                heading = Heading(
                    level=level,
                    heading_start=token.map[0],
                    title_end=token.map[1],
                    title_text=stripped_content.strip(),
                    tags=tags,
                )

                headings.append(heading)

    # Mark leaf headings
    for idx, heading in enumerate(headings):
        current_level = heading.level
        # Assume leaf by default
        heading.is_leaf = True
        # Check if any subsequent heading is a child
        for next_heading in headings[idx + 1 :]:
            if next_heading.level > current_level:
                # found child heading -> current not leaf
                heading.is_leaf = False
                break
            elif next_heading.level <= current_level:
                # sibling or higher-level heading encountered, move to next heading
                break

    # Find heading body ends
    total_lines = len(lines)
    for idx, heading in enumerate(headings):
        # Determine end line for content
        heading_body_end = total_lines
        for next_heading in headings[idx + 1 :]:
            heading_body_end = next_heading.heading_start
            break

        heading.heading_body_end = heading_body_end

    return lines, headings


def find_anki_link(lines) -> Optional[Tuple[int, int, AnkiLink]]:
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

    anki_link = AnkiLink(id=id_params[0], mod=mod_params[0] if mod_params else None)

    return matches[0][0], matches[0][1], anki_link


def split_body(lines, headings: list[Heading]):
    for heading in headings:
        content_lines = lines[heading.title_end : heading.heading_body_end]
        anki_metadata = find_anki_link(content_lines)
        if anki_metadata:
            first_heading_line_idx, last_heading_line_idx, anki_link = anki_metadata
            heading.other_content: list[str] = (
                content_lines[:first_heading_line_idx]
                + content_lines[last_heading_line_idx + 1 :]
            )
            heading.anki_link = anki_link
        else:
            heading.anki_link = None
            heading.other_content = content_lines

        heading.other_content = normalize_lines(heading.other_content)

    return headings


def main(filepath: str, colpath: str, modelname: str, deckname: str):
    col = Collection(colpath)

    basic_model = col.models.by_name(modelname)
    deck = col.decks.by_name(deckname)
    col.decks.select(deck["id"])
    col.decks.current()["mid"] = basic_model["id"]

    lines, headings = parse_markdown_headings(filepath)
    headings = split_body(lines, headings)

    # lines before first heading
    updated_lines = lines[: headings[0].heading_start]

    for heading in headings:
        if not heading.is_leaf:
            # leaving non-leaf headings completely unchanged
            updated_lines += lines[heading.heading_start : heading.heading_body_end]
            continue

        if heading.anki_link:
            print("Processing heading with sync_id:", heading.anki_link.id)

            try:
                note = col.get_note(int(heading.anki_link.id))
            except:
                raise ValueError(
                    f"Note with id {heading.anki_link.id} not found in Anki"
                )

            if heading.anki_link.mod and note.mod > int(heading.anki_link.mod):
                print("    Note is newer in anki, syncing md <- anki")

                heading.other_content = normalize_lines(note.fields[1].split("\n"))
                heading.anki_link.mod = str(note.mod)
                heading.title_text = note.fields[0]
                heading.tags = note.tags
            else:
                if not heading.anki_link.mod:
                    print("    Note has no mod, syncing anyway")

                print("    Syncing md -> anki")
                note.fields[0] = heading.title_text
                note.fields[1] = "".join(heading.other_content)

                note.tags = heading.tags
                col.update_note(note)

                # re-read note to get updated mod
                # anki updates mod iff content has changed
                # (i.e. we can resync same content and anki doesn't advance mod)
                note = col.get_note(int(heading.anki_link.id))

                if heading.anki_link.mod and str(note.mod) == heading.anki_link.mod:
                    print("    Note is unchanged")
                heading.anki_link.mod = str(note.mod)

        else:
            note = col.new_note(basic_model)
            note.fields[0] = heading.title_text
            note.fields[1] = "".join(
                lines[heading.title_end : heading.heading_body_end]
            )
            note.tags = heading.tags
            col.add_note(note, deck["id"])

            anki_link = AnkiLink(id=str(note.id))
            heading.anki_link = anki_link
            print("Syncing new heading with sync_id:", heading.anki_link.id)

            note = col.get_note(int(heading.anki_link.id))
            heading.anki_link.mod = str(note.mod)

        updated_lines += (
            heading.title_lines
            + heading.anki_link.lines
            + heading.other_content
            + ["\n", "\n"]  # trailing newline before next heading
        )

    # strip trailing empty lines from very end of file
    while updated_lines and updated_lines[-1].strip() == "":
        updated_lines.pop()

    write_markdown_file(filepath, updated_lines)
    col.close()


if __name__ == "__main__":
    fire.Fire(main)
