"""Publishes what Post Studio has learned about you into the repository.

The weekly cloud run cannot see agent.db on this laptop. It can see the
repository. So this writes two files it already looks for:

    voice/persona.md    the facts you have confirmed about yourself
    voice/samples.md    the posts you rated "sounds like me"

then commits and pushes them. Run it whenever you have rated a few drafts or
done a check-in, and the next Monday's drafts are written from the current
you rather than from rules alone.

    python scripts/publish_voice.py

Nothing private beyond what you confirmed leaves the machine: notes, drafts,
prospects and ratings stay in agent.db. Only confirmed facts and approved
samples are written, because those are the two things you explicitly said
were true and were yours.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess  # nosec B404 - fixed argv, no shell
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from content_agent.persona import CheckIn, Fact, Persona  # noqa: E402
from content_agent.samples import Rating, VoiceLibrary, VoiceSample  # noqa: E402
from persistence import SQLiteRepository, open_database  # noqa: E402

DB_PATH = REPO / "agent.db"
VOICE_DIR = REPO / "voice"


def render_samples(library: VoiceLibrary) -> str:
    samples = library.samples()
    if not samples:
        return "# Voice samples\n\nNone approved yet.\n"
    blocks = []
    for sample in samples[:12]:
        tag = f"{sample.channel.value}" + (", edited by Jasmehr" if sample.edited else "")
        blocks.append(f"## {tag}\n\n{sample.text}\n")
    return (
        "# Voice samples\n\nPosts Jasmehr approved as sounding like him. Match the register, not the content.\n\n"
        + "\n".join(blocks)
    )


def main() -> int:
    if not DB_PATH.exists():
        print("No agent.db yet. Open Post Studio, do a check-in or rate a draft, then run this.")
        return 1
    connection = open_database(DB_PATH)
    persona = Persona(
        SQLiteRepository(connection, "persona_facts", Fact),
        SQLiteRepository(connection, "persona_checkins", CheckIn),
    )
    library = VoiceLibrary(
        SQLiteRepository(connection, "voice_samples", VoiceSample),
        SQLiteRepository(connection, "voice_ratings", Rating),
    )

    VOICE_DIR.mkdir(exist_ok=True)
    (VOICE_DIR / "persona.md").write_text(persona.render_markdown(), encoding="utf-8")
    (VOICE_DIR / "samples.md").write_text(render_samples(library), encoding="utf-8")
    print(f"wrote voice/persona.md ({persona.health()['facts']} facts)")
    print(f"wrote voice/samples.md ({len(library.samples())} samples)")

    git = shutil.which("git")
    if git is None:
        print("git not found; files written but not committed")
        return 1

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # nosec B603 - absolute git, fixed argv, no shell
            [git, "-C", str(REPO), *args], check=False, capture_output=True, text=True
        )

    run("add", "voice/persona.md", "voice/samples.md")
    committed = run("commit", "-q", "-m", "Publish voice: persona and approved samples")
    if committed.returncode != 0:
        print("nothing new to publish")
        return 0
    pushed = run("push", "-q")
    print("pushed" if pushed.returncode == 0 else f"committed but push failed: {pushed.stderr.strip()[:200]}")
    return 0 if pushed.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
