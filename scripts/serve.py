"""Starts Post Studio. One command, then open the browser.

    python scripts/serve.py

Everything is stored in agent.db beside the repo, so closing the window loses
nothing. Bound to loopback, so nothing outside this machine can reach it.
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from content_agent import ContentStudio, PostDraft, WeeklyNote  # noqa: E402
from content_agent.web import serve  # noqa: E402
from llm_router.backends import backends_from_environment  # noqa: E402
from persistence import SQLiteRepository, open_database  # noqa: E402
from scripts.env_file import load as load_env  # noqa: E402

DB_PATH = REPO / "agent.db"
PORT = 8765


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
    serve(build_studio(), port=PORT)
