"""Loads posts written as markdown into the studio, so the queue can reach them.

    python scripts/import_drafts.py                    # every file in drafts/
    python scripts/import_drafts.py drafts/series.md   # one file
    python scripts/import_drafts.py --dry-run          # say what it would do

The drafts in `drafts/*.md` were written into files rather than through the
studio, so the Review tab never knew about them: it reads `agent.db`, and
nothing connected the two. That meant nine finished posts could not be
scheduled, approved or archived without being pasted in by hand, which is the
work the studio exists to remove.

IMPORTED AS DRAFTED, NEVER APPROVED. A script that wrote APPROVED rows would
put a file on disk on the far side of the human gate, and the gate is the one
thing in this system that has no bypass. Each post still needs your click in
the Review tab. That is one click per post, against nine copy-pastes.

IDEMPOTENT. Re-running it is the normal case, not the accident: a file gets
another post appended and you want just that one. Posts are matched on their
hook, so anything already in the database is left alone rather than duplicated.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re
import sys
import uuid
from datetime import UTC, datetime

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from content_agent import DraftState, PostDraft, WeeklyNote  # noqa: E402
from content_agent.formats import Channel  # noqa: E402
from content_agent.voice import check  # noqa: E402
from persistence import SQLiteRepository, open_database  # noqa: E402
from scripts.serve import DB_PATH  # noqa: E402

#: A section starts at a level-two heading and runs to the next one. Both the
#: weekly file ("## LinkedIn") and the series ("## 2. What I did not know")
#: are shaped this way.
SECTION = re.compile(r"^## +(.+?)\s*$", re.MULTILINE)

#: The labelled blocks inside a section. A newsletter carries "**Subject**"
#: rather than "**Hook**", so keying on Hook skips newsletters without needing
#: to know what a newsletter is.
FIELD = re.compile(r"^\*\*(Hook|Body|Close|Hashtags)\*\*\s*$", re.MULTILINE)

HASHTAG = re.compile(r"#\w+")


@dataclasses.dataclass(frozen=True)
class ParsedPost:
    """One post lifted out of a markdown file."""

    title: str
    hook: str
    body: str
    close: str
    hashtags: tuple[str, ...]

    def is_complete(self) -> bool:
        return bool(self.hook and self.body)


def parse_posts(text: str) -> list[ParsedPost]:
    """Every LinkedIn-shaped post in one markdown file.

    Deliberately forgiving about what surrounds a post and strict about what
    one is. These files also carry commentary, tables and checklists, and the
    rule that keeps those out is simply that a post has a `**Hook**`.
    """
    found: list[ParsedPost] = []
    headings = list(SECTION.finditer(text))
    for index, heading in enumerate(headings):
        start = heading.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        section = text[start:end]

        fields = _fields(section)
        hook = fields.get("Hook", "")
        if not hook:
            continue
        post = ParsedPost(
            title=heading.group(1).strip(),
            # A hook that wrapped in the file is one line in a post.
            hook=" ".join(hook.split()),
            body=fields.get("Body", ""),
            close=fields.get("Close", ""),
            hashtags=tuple(HASHTAG.findall(fields.get("Hashtags", ""))),
        )
        if post.is_complete():
            found.append(post)
    return found


def _fields(section: str) -> dict[str, str]:
    """The labelled blocks in one section, each running to the next label."""
    out: dict[str, str] = {}
    marks = list(FIELD.finditer(section))
    for index, mark in enumerate(marks):
        start = mark.end()
        end = marks[index + 1].start() if index + 1 < len(marks) else len(section)
        value = section[start:end].strip()
        # A commentary block or a horizontal rule after the last field is not
        # part of it. Both begin a line, so the cut is unambiguous.
        for terminator in ("\n> ", "\n---", "\n***"):
            cut = value.find(terminator)
            if cut != -1:
                value = value[:cut].rstrip()
        out[mark.group(1)] = value
    return out


@dataclasses.dataclass(frozen=True)
class ImportResult:
    title: str
    imported: bool
    reason: str = ""
    violations: tuple[str, ...] = ()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    dry_run = "--dry-run" in args
    given = [a for a in args if not a.startswith("--")]

    paths = [pathlib.Path(p) for p in given] if given else sorted((REPO / "drafts").glob("*.md"))
    paths = [p for p in paths if p.is_file()]
    if not paths:
        print("\n  No markdown files to read.\n")
        return 1

    connection = open_database(DB_PATH)
    notes = SQLiteRepository(connection, "linkedin_notes", WeeklyNote)
    drafts = SQLiteRepository(connection, "linkedin_drafts", PostDraft)

    # One read of what is already there, so a file of forty posts does not
    # become forty scans of the table.
    known: set[str] = {" ".join(d.hook.split()) for d in drafts.list_all()}

    results: list[ImportResult] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"  could not read {path.name}: {exc}", file=sys.stderr)
            continue

        posts = parse_posts(text)
        if not posts:
            continue
        print(f"\n  {path.name}: {len(posts)} post(s)")

        note: WeeklyNote | None = None
        for post in posts:
            if post.hook in known:
                results.append(ImportResult(post.title, imported=False, reason="already in the studio"))
                print(f"    - {post.title[:52]:<52} already there")
                continue

            violations = check(post.hook, post.body, post.close, post.hashtags)
            broken = tuple(f"{v.rule}: {v.detail}" for v in violations)

            if dry_run:
                results.append(ImportResult(post.title, imported=False, reason="dry run", violations=broken))
                print(f"    - {post.title[:52]:<52} would import")
                continue

            if note is None:
                # Written once per file, so every draft from it can be traced
                # back to where it came from rather than appearing from nowhere.
                note = WeeklyNote(
                    note_id=f"note-{uuid.uuid4().hex[:12]}",
                    captured_at=datetime.now(UTC),
                    body=f"Imported from {path.name}. Written as markdown before the studio could hold it.",
                )
                notes.save(note.note_id, note)

            draft = PostDraft(
                draft_id=f"draft-{uuid.uuid4().hex[:12]}",
                note_id=note.note_id,
                # Drafted, never approved: the gate stays where it is.
                state=DraftState.DRAFTED,
                channel=Channel.LINKEDIN,
                hook=post.hook,
                body=post.body,
                close=post.close,
                hashtags=post.hashtags,
                created_at=datetime.now(UTC),
                outstanding=broken,
            )
            drafts.save(draft.draft_id, draft)
            known.add(post.hook)
            results.append(ImportResult(post.title, imported=True, violations=broken))
            flag = f"  [{len(broken)} rule(s) to look at]" if broken else ""
            print(f"    - {post.title[:52]:<52} imported{flag}")

    imported = sum(1 for r in results if r.imported)
    skipped = sum(1 for r in results if not r.imported and r.reason == "already in the studio")
    print("")
    if dry_run:
        would = sum(1 for r in results if r.reason == "dry run")
        print(f"  Dry run: {would} would be imported, {skipped} already there.")
    else:
        print(f"  Imported {imported}. Skipped {skipped} already there.")
        if imported:
            print("  They are in the Review tab now, waiting for you to approve them.")
    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
