"""Post Studio against a canned model, for checking the interface works.

Uses no API key and spends no quota. The drafts are fixed text, so what this
proves is the plumbing and the page, not the writing.

    python scripts/serve_demo.py
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from content_agent import ContentStudio, PostDraft, WeeklyNote  # noqa: E402
from content_agent.web import serve  # noqa: E402
from persistence import SQLiteRepository, open_database  # noqa: E402

CANNED = json.dumps(
    {
        "hook": "I spent 3 attempts learning that a free API tier fails differently than a paid one.",
        "body": (
            "A paid tier bills you.\n\n"
            "A free tier just stops answering. 429, no warning.\n\n"
            "So I built a cooldown instead of a retry. The tier goes dark for a minute "
            "and everything degrades to a smaller model rather than failing."
        ),
        "close": "What is the smallest failure that taught you the most this week?",
        "hashtags": ["#agentarchitecture", "#buildinpublic", "#pythontesting"],
    }
)


def main() -> None:
    connection = open_database(REPO / "demo.db")
    studio = ContentStudio(
        complete=lambda prompt, max_tokens: CANNED,
        notes=SQLiteRepository(connection, "demo_notes", WeeklyNote),
        drafts=SQLiteRepository(connection, "demo_drafts", PostDraft),
    )
    serve(studio, port=8766)


if __name__ == "__main__":
    main()
