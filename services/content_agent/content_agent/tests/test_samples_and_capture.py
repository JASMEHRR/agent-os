"""The two pieces that reduce what you have to type.

Samples: your voice learned from what you approved, so drafts sound like you.
Capture: your week read from your commits, so you do not write it twice.

The tests that matter are the ones about drift and provenance: that only
text you rated can feed the next draft, and that capture reads history and
never files.
"""

from __future__ import annotations

import json
import pathlib
import subprocess  # nosec B404 - fixtures build a throwaway repo
from datetime import UTC, datetime

import pytest

from content_agent import ContentStudio
from content_agent.capture import MIN_COMMITS_TO_MENTION, capture_week, read_repo, to_note
from content_agent.formats import Channel
from content_agent.samples import SAMPLES_IN_PROMPT, VoiceLibrary, render_examples
from persistence import InMemoryRepository

NOTE = (
    "This week I wired Groq behind the model router. It took 3 attempts because the free "
    "tier rate limits at 429 rather than billing, so I built a cooldown that degrades to a "
    "smaller model. The suite is at 1856 passing tests."
)

SAMPLE = (
    "I spent 3 attempts learning that a free API tier fails differently than a paid one. "
    "A paid tier bills you. A free tier stops answering. So I built a cooldown instead of "
    "a retry, and the whole router got calmer. What is the smallest failure that taught "
    "you the most this week?"
)

PAYLOAD = json.dumps(
    {
        "hook": "I spent 3 attempts learning a free API tier fails differently than a paid one.",
        "body": "A paid tier bills you. A free tier stops answering.",
        "close": "What small failure taught you most this week?",
        "hashtags": ["#agentarchitecture", "#buildinpublic", "#pythontesting"],
    }
)


def _library() -> VoiceLibrary:
    return VoiceLibrary(InMemoryRepository(), InMemoryRepository())


# ----------------------------------------------------------------- Samples


def test_approved_samples_reach_the_prompt() -> None:
    """The whole point: examples of you, in the prompt, every draft."""
    seen: list[str] = []

    def complete(prompt: str, max_tokens: int) -> str:
        seen.append(prompt)
        return PAYLOAD

    library = _library()
    library.add_sample(Channel.LINKEDIN, SAMPLE)
    studio = ContentStudio(complete, InMemoryRepository(), InMemoryRepository(), library=library)

    studio.draft(studio.capture(NOTE))

    assert "approved as sounding like him" in seen[0]
    assert "free tier stops answering" in seen[0]


def test_with_no_samples_the_prompt_carries_no_example_block() -> None:
    """From zero it drafts from rules alone rather than from an empty header."""
    seen: list[str] = []

    def complete(prompt: str, max_tokens: int) -> str:
        seen.append(prompt)
        return PAYLOAD

    studio = ContentStudio(complete, InMemoryRepository(), InMemoryRepository())
    studio.draft(studio.capture(NOTE))

    assert "example" not in seen[0].lower().split("here are this week")[0]


def test_only_rated_text_becomes_a_sample_never_an_unrated_draft() -> None:
    """Otherwise the system trains on its own output and converges on its own
    habits rather than yours."""
    library = _library()
    studio = ContentStudio(lambda p, m: PAYLOAD, InMemoryRepository(), InMemoryRepository(), library=library)

    studio.draft(studio.capture(NOTE))

    assert library.samples() == [], "a draft nobody rated must not become an example"


def test_a_fragment_is_refused_as_a_sample() -> None:
    with pytest.raises(ValueError, match="at least"):
        _library().add_sample(Channel.LINKEDIN, "too short to be an example")


def test_the_prompt_carries_the_newest_few_not_all() -> None:
    """Your voice this year is not your voice two years ago."""
    library = _library()
    for i in range(SAMPLES_IN_PROMPT + 3):
        library.add_sample(Channel.LINKEDIN, f"{SAMPLE} Variant number {i} of this post.")

    assert len(library.for_prompt(Channel.LINKEDIN)) == SAMPLES_IN_PROMPT


def test_edited_samples_are_preferred() -> None:
    """The diff between draft and edit is exactly where the model was wrong
    about you, so an edited sample carries more signal than a rubber stamp."""
    library = _library()
    for i in range(SAMPLES_IN_PROMPT + 2):
        library.add_sample(Channel.LINKEDIN, f"{SAMPLE} Unedited {i}.", edited=False)
    edited = library.add_sample(Channel.LINKEDIN, f"{SAMPLE} Edited by hand.", edited=True)

    assert edited in library.for_prompt(Channel.LINKEDIN)


def test_another_channels_samples_are_borrowed_when_this_one_has_none() -> None:
    """A LinkedIn post is still a better example of your voice for a newsletter
    than no example, and the prompt says it is borrowed."""
    library = _library()
    library.add_sample(Channel.LINKEDIN, SAMPLE)

    chosen = library.for_prompt(Channel.NEWSLETTER)
    rendered = render_examples(chosen, Channel.NEWSLETTER)

    assert chosen and chosen[0].channel is Channel.LINKEDIN
    assert "other channels" in rendered


def test_a_run_of_negative_ratings_shows_in_health() -> None:
    """The earliest sign the voice has drifted, before anyone notices by reading."""
    library = _library()
    for i in range(4):
        library.rate(f"d{i}", sounds_like_me=False)
    library.rate("d9", sounds_like_me=True)

    assert library.health()["recent_sounds_like_me"] == "1/5"


# ----------------------------------------------------------------- Capture


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A throwaway repository with three real commits and one merge-like noise."""
    path = tmp_path / "proj"
    path.mkdir()

    def git(*args: str) -> None:
        subprocess.run(  # nosec B603 B607 - test fixture, fixed argv
            ["git", "-C", str(path), *args],
            check=True,
            capture_output=True,
            env={
                "GIT_AUTHOR_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "t",
                "GIT_COMMITTER_EMAIL": "t@t",
                "PATH": __import__("os").environ["PATH"],
            },
        )

    git("init", "-q")
    for i, subject in enumerate(("Wire the router", "Add a cooldown on 429", "Bump version", "Reach 1856 tests")):
        (path / f"f{i}.txt").write_text("x", encoding="utf-8")
        git("add", ".")
        git("commit", "-q", "-m", subject)
    return path


def test_capture_reads_commit_subjects_and_skips_noise(repo: pathlib.Path) -> None:
    activity = read_repo(repo, days=7)

    assert activity.error == ""
    assert "Wire the router" in activity.commits
    assert "Bump version" not in activity.commits, "automated noise says nothing about the week"


def test_capture_never_reads_file_contents(repo: pathlib.Path) -> None:
    """Enforced by construction: the only git invocation is `log`.

    Checked here by planting a secret in a file and asserting it never appears
    anywhere in what capture produces.
    """
    (repo / "secret.txt").write_text("SECRET_TOKEN_VALUE_9931", encoding="utf-8")

    note, activity = capture_week([repo], days=7)

    assert "SECRET_TOKEN_VALUE_9931" not in note
    assert all("SECRET_TOKEN_VALUE_9931" not in c for a in activity for c in a.commits)


def test_the_note_carries_a_real_number_so_the_voice_gate_can_pass(repo: pathlib.Path) -> None:
    """The gates demand a concrete number. Commit counts are one the note can
    honestly supply."""
    note, _ = capture_week([repo], days=7)

    assert "3 commits" in note


def test_a_quiet_repository_is_left_out_and_a_broken_one_is_reported(tmp_path: pathlib.Path) -> None:
    """Silence and failure must not look the same."""
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()

    note, activity = capture_week([not_a_repo], days=7)

    assert note == ""
    assert activity[0].error == "not a git repository"


def test_to_note_omits_repositories_below_the_mention_threshold() -> None:
    from content_agent.capture import Commit, RepoActivity

    quiet = RepoActivity("quiet", "/q", (Commit("one commit"),))
    busy = RepoActivity("busy", "/b", tuple(Commit(f"c{i}") for i in range(MIN_COMMITS_TO_MENTION)))

    note = to_note([quiet, busy], days=7)

    assert "busy" in note
    assert "quiet" not in note


def test_a_captured_note_is_substantive_enough_to_draft_from(repo: pathlib.Path) -> None:
    """The point of capture is to skip typing, so what it produces has to
    clear the same thin-note bar a typed note would."""
    note, _ = capture_week([repo], days=7)
    studio = ContentStudio(
        lambda p, m: PAYLOAD, InMemoryRepository(), InMemoryRepository(), clock=lambda: datetime(2026, 9, 2, tzinfo=UTC)
    )

    assert studio.capture(note).is_substantive()


# ------------------------------------------------------------ Commit bodies


@pytest.fixture
def explained(tmp_path: pathlib.Path) -> pathlib.Path:
    """A repository whose commits explain themselves, like his actually do."""
    path = tmp_path / "explained"
    path.mkdir()

    def git(*args: str) -> None:
        subprocess.run(  # nosec B603 B607 - test fixture, fixed argv
            ["git", "-C", str(path), *args],
            check=True,
            capture_output=True,
            env={
                "GIT_AUTHOR_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "t",
                "GIT_COMMITTER_EMAIL": "t@t",
                "PATH": __import__("os").environ["PATH"],
            },
        )

    git("init", "-q")
    messages = [
        (
            "Find a photo for an item nobody photographed",
            "Most sellers here photograph nothing. They are running a shop out of a hostel\n"
            "room between classes, and forty items with forty blank tiles is the normal\n"
            "outcome.\n\nNOT A WEB IMAGE SEARCH, and that is the whole design rather than a\n"
            "limitation of it.\n\nCo-Authored-By: Somebody <nobody@example.com>",
        ),
        ("Tidy the imports", ""),
        ("Rename a variable", "One line."),
    ]
    for i, (subject, body) in enumerate(messages):
        (path / f"f{i}.txt").write_text("x", encoding="utf-8")
        git("add", ".")
        git("commit", "-q", "-m", subject, "-m", body) if body else git("commit", "-q", "-m", subject)
    return path


def test_the_body_is_captured_not_only_the_subject(explained: pathlib.Path) -> None:
    """The subject says what changed. The body says what was tried and why,
    and that is what a post is made of."""
    activity = read_repo(explained, days=7)

    photo = next(e for e in activity.entries if e.subject.startswith("Find a photo"))
    assert "hostel" in photo.body
    assert "NOT A WEB IMAGE SEARCH" in photo.body


def test_trailers_are_stripped_from_the_body(explained: pathlib.Path) -> None:
    """Who co-authored it is not part of the week."""
    activity = read_repo(explained, days=7)

    assert all("Co-Authored-By" not in entry.body for entry in activity.entries)


def test_commits_still_reads_as_subjects_for_everything_that_counts(explained: pathlib.Path) -> None:
    """Callers that only wanted to count commits should not have to learn that
    a body exists."""
    activity = read_repo(explained, days=7)

    assert "Tidy the imports" in activity.commits
    assert len(activity.commits) == 3


def test_only_explained_commits_reach_the_note(explained: pathlib.Path) -> None:
    """A one-line body is a tidy commit, not an explained one, and fifty of
    those would crowd out the ones worth reading."""
    note, _ = capture_week([explained], days=7)

    assert "hostel" in note, "the explained commit's reasoning must reach the note"
    assert "In my own words" in note
    assert note.count("## ") == 1, "only the substantial body is expanded"
    assert "Tidy the imports" in note, "every subject is still listed"


def test_a_long_body_is_truncated_on_a_thought(tmp_path: pathlib.Path) -> None:
    from content_agent.capture import BODY_CHARS, _clean_body

    body = ("First paragraph, which is the reason.\n\n" + "padding sentence. " * 200).strip()

    cleaned = _clean_body(body)

    assert len(cleaned) <= BODY_CHARS + len(" [...]")
    assert cleaned.endswith("[...]")
    assert cleaned.startswith("First paragraph")
