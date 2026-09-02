"""Starts Post Studio. One command, then open the browser.

    python scripts/serve.py

Everything is stored in agent.db beside the repo, so closing the window loses
nothing. Bound to loopback, so nothing outside this machine can reach it.
"""

from __future__ import annotations

import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from content_agent import ContentStudio, PostDraft, WeeklyNote  # noqa: E402
from content_agent.outreach import OutreachDraft, Prospect  # noqa: E402
from content_agent.persona import CheckIn, Fact, Persona  # noqa: E402
from content_agent.samples import Rating, VoiceLibrary, VoiceSample  # noqa: E402
from content_agent.web import serve  # noqa: E402
from llm_router.backends import backends_from_environment  # noqa: E402
from persistence import SQLiteRepository, open_database  # noqa: E402
from scripts.env_file import load as load_env  # noqa: E402

#: On this laptop, beside the repo. On a host, wherever the persistent volume
#: is mounted, because a free host's default disk is wiped on every restart.
DB_PATH = pathlib.Path(os.environ.get("DB_PATH", str(REPO / "agent.db")))
PORT = 8765

#: Repositories the "pull from git" button reads, commit messages only.
#: Override with REPOS in .env as a semicolon-separated list of paths.
DEFAULT_REPOS = (
    str(REPO),
    str(REPO.parent / "ventureadda"),
    str(REPO.parent / "ASCEND"),
    str(REPO.parent / "clipforge"),
)


def repos_from_environment() -> tuple[str, ...]:
    raw = os.environ.get("REPOS", "")
    if raw.strip():
        return tuple(part.strip() for part in raw.split(";") if part.strip())
    return tuple(p for p in DEFAULT_REPOS if pathlib.Path(p).exists())


def build_studio() -> ContentStudio:
    load_env()
    backends = backends_from_environment()

    # Standard first: drafting in a specific voice is the one job where the
    # smaller model is visibly worse, and both tiers are free. Nano is the
    # fallback for when Standard's per-minute window is spent.
    order = ("standard", "nano", "premium")
    chain = [backends[name] for name in order]

    if not any(b.available() for b in chain):
        print("\n  No model configured.")
        print("  Copy .env.example to .env and put your Groq key in it.")
        print("  Free key: https://console.groq.com/keys\n")
        raise SystemExit(1)

    def complete(prompt: str, max_tokens: int) -> str:
        last: Exception | None = None
        for backend in chain:
            if not backend.available():
                continue
            try:
                output, _, _ = backend.complete(prompt, max_tokens)
                return str(output["text"])
            except Exception as exc:  # noqa: BLE001 - fall to the next tier
                last = exc
        # Named rather than generic: "rate limited" and "bad key" need
        # different responses from the person reading it.
        raise RuntimeError(f"every model tier refused. Last error: {last}")

    connection = open_database(DB_PATH)
    return ContentStudio(
        complete=complete,
        notes=SQLiteRepository(connection, "linkedin_notes", WeeklyNote),
        drafts=SQLiteRepository(connection, "linkedin_drafts", PostDraft),
        prospects=SQLiteRepository(connection, "prospects", Prospect),
        outreach=SQLiteRepository(connection, "outreach_drafts", OutreachDraft),
        # Durable on purpose. Samples are the accumulated record of what
        # sounds like you; losing them on restart would reset the voice.
        library=VoiceLibrary(
            SQLiteRepository(connection, "voice_samples", VoiceSample),
            SQLiteRepository(connection, "voice_ratings", Rating),
        ),
        persona=Persona(
            SQLiteRepository(connection, "persona_facts", Fact),
            SQLiteRepository(connection, "persona_checkins", CheckIn),
        ),
    )


def preflight() -> int:
    """Checks configuration without starting anything.

    Used by the launcher so the browser is not opened at a server that is
    about to exit. A window that opens on a connection error and a window that
    opens on a real problem look identical to the person watching.
    """
    load_env()
    backends = backends_from_environment()
    if any(b.available() for b in backends.values()):
        return 0
    print("")
    print("  No model configured.")
    print("  Copy .env.example to .env and put your free Groq key in it.")
    print("  Get a free one at https://console.groq.com/keys")
    print("")
    return 1


if __name__ == "__main__":
    if "--check" in sys.argv:
        raise SystemExit(preflight())
    # STUDIO_PASSWORD set means "hosted": bind every interface and require a
    # login. Unset means "this laptop": loopback only, no login, because
    # reachability is the authorisation there.
    serve(
        build_studio(),
        port=int(os.environ.get("PORT", PORT)),
        repos=repos_from_environment(),
        password=os.environ.get("STUDIO_PASSWORD", ""),
    )
