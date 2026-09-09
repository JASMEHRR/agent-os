"""The markdown parser, against the real files it has to read.

The parser is the part that can quietly go wrong: a change of shape in a
drafts file would not raise, it would import a post with half a body or
swallow the editorial commentary into the close. So the tests run against the
actual files in `drafts/` as well as against hand-written shapes.
"""

from __future__ import annotations

import pathlib

import pytest

from scripts.import_drafts import ParsedPost, parse_posts

REPO = pathlib.Path(__file__).resolve().parents[1]
DRAFTS = REPO / "drafts"

WEEKLY = """# Weekly drafts

Some preamble that is not a post.

## LinkedIn

**Hook**
A hook that says one thing.

**Body**
A first paragraph.

A second paragraph, with 3 in it.

**Close**
A closing line.

**Hashtags**
#one #two #three

---

## Sourcing

**Persona facts used:** none
"""

WITH_COMMENTARY = """## 2. What I did not know

**Hook**
Four things I had never heard of.

**Body**
The body of it.

**Close**
The close of it.

**Hashtags**
#learninginpublic #github

> **The one I would bet on.** Everybody who has felt locked out recognises
> this list, and it costs nothing to admit.

---
"""

NEWSLETTER = """## Newsletter

**Subject**
A subject line, not a hook

**Body**
The newsletter body.

**Close**
A line that invites a reply.
"""


def only(posts: list[ParsedPost]) -> ParsedPost:
    assert len(posts) == 1, [p.title for p in posts]
    return posts[0]


def test_a_post_is_read_out_of_its_section() -> None:
    post = only(parse_posts(WEEKLY))

    assert post.title == "LinkedIn"
    assert post.hook == "A hook that says one thing."
    assert post.close == "A closing line."
    assert post.hashtags == ("#one", "#two", "#three")


def test_a_body_keeps_its_paragraphs() -> None:
    """A body flattened into one block would publish as a wall of text."""
    post = only(parse_posts(WEEKLY))

    assert post.body.count("\n\n") == 1
    assert post.body.startswith("A first paragraph.")
    assert post.body.endswith("with 3 in it.")


def test_the_sourcing_section_is_not_a_post() -> None:
    """These files carry notes, tables and checklists around the posts."""
    titles = [p.title for p in parse_posts(WEEKLY)]

    assert "Sourcing" not in titles


def test_editorial_commentary_is_not_swallowed_into_the_post() -> None:
    """The series files carry a "why this one" note after the hashtags."""
    post = only(parse_posts(WITH_COMMENTARY))

    assert post.hashtags == ("#learninginpublic", "#github")
    assert "bet on" not in post.close
    assert "bet on" not in post.body


def test_a_newsletter_is_skipped_rather_than_imported_as_a_post() -> None:
    """It has a subject where a post has a hook, and no hashtags at all."""
    assert parse_posts(NEWSLETTER) == []


def test_a_hook_that_wrapped_in_the_file_becomes_one_line() -> None:
    wrapped = "## X\n\n**Hook**\nA hook that was wrapped\nacross two lines.\n\n**Body**\nSomething.\n"

    assert only(parse_posts(wrapped)).hook == "A hook that was wrapped across two lines."


def test_a_section_with_no_hook_is_not_a_post() -> None:
    assert parse_posts("## Notes\n\nJust prose, no fields.\n") == []


def test_a_hook_with_no_body_is_not_imported() -> None:
    """Half a post is worse than none: it would sit in Review looking ready."""
    assert parse_posts("## X\n\n**Hook**\nOnly a hook.\n") == []


def test_empty_input_is_not_an_error() -> None:
    assert parse_posts("") == []


# ------------------------------------------------- Against the real files


def test_the_recap_series_parses_into_its_ten_posts() -> None:
    """The file this exists to import. If its shape changes, this fails."""
    path = DRAFTS / "2026-09-06-recap-series.md"
    if not path.exists():
        pytest.skip("the series file is not in this checkout")

    posts = parse_posts(path.read_text(encoding="utf-8"))

    assert len(posts) == 10
    assert all(p.hook and p.body for p in posts)
    # Every one carries its tags; a post arriving with none would fail the
    # voice gate later and look like the importer had dropped them.
    assert all(p.hashtags for p in posts)


def test_every_post_in_the_real_files_has_a_close() -> None:
    """A missing close is the shape error most likely to pass unnoticed."""
    for path in sorted(DRAFTS.glob("*.md")):
        for post in parse_posts(path.read_text(encoding="utf-8")):
            assert post.close, f"{path.name}: {post.title} parsed without a close"
