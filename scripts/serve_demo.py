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

LINKEDIN = {
    "hook": "I spent 3 attempts learning that a free API tier fails differently than a paid one.",
    "body": (
        "A paid tier bills you.\n\n"
        "A free tier just stops answering. 429, no warning.\n\n"
        "So I built a cooldown instead of a retry. The tier goes dark for a minute and "
        "everything degrades to a smaller model rather than failing."
    ),
    "close": "What is the smallest failure that taught you the most this week?",
    "hashtags": ["#agentarchitecture", "#buildinpublic", "#pythontesting"],
}

NEWSLETTER = {
    "subject": "The 429 that taught me to stop retrying",
    "body": (
        "Groq's free tier does not bill you when you go past the limit. It stops answering.\n\n"
        "That took 3 attempts to work out, because a 429 looks like a transient error, and the "
        "obvious response to a transient error is to retry it sooner.\n\n"
        "Retrying sooner spends the next window's quota on a request that gets refused again.\n\n"
        "The fix was a cooldown: the tier goes dark for 60 seconds and the router degrades to a "
        "smaller model instead of failing."
    ),
    "close": "Have you hit a failure that looked transient and was not? Reply and tell me.",
}

DEVTO = {
    "title": "A free LLM tier fails differently, and retrying makes it worse",
    "body": (
        "## The problem\n\n"
        "Groq returns 429 when the per-minute window is spent. No bill, no warning.\n\n"
        "## What I tried\n\n"
        "3 attempts, each retrying sooner than the last. Each one spent the next window's quota "
        "on a request that was always going to be refused.\n\n"
        "## What worked\n\n"
        "A cooldown. The tier reports itself unavailable for 60 seconds and the router degrades "
        "down its failover chain to a smaller model."
    ),
    "tags": ["python", "llm", "apidesign", "testing"],
}


def canned(prompt: str, max_tokens: int) -> str:
    """Answers in the shape the prompt asked for.

    The prompt names the JSON keys it wants, so matching on those is enough to
    demonstrate all three channels without a model. A single fixed payload
    would only ever satisfy LinkedIn's gates, and the other two would look
    broken when they were in fact working correctly.
    """
    if '"subject"' in prompt:
        return json.dumps(NEWSLETTER)
    if '"title"' in prompt:
        return json.dumps(DEVTO)
    return json.dumps(LINKEDIN)


def main() -> None:
    connection = open_database(REPO / "demo.db")
    studio = ContentStudio(
        complete=canned,
        notes=SQLiteRepository(connection, "demo_notes", WeeklyNote),
        drafts=SQLiteRepository(connection, "demo_drafts", PostDraft),
    )
    serve(studio, port=8766)


if __name__ == "__main__":
    main()
