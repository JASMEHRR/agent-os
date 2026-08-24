"""Weekly notes in, gated LinkedIn drafts out. Usable before any UI exists.

    python scripts/linkedin.py note      # type what you did this week
    python scripts/linkedin.py draft     # write posts from the latest note
    python scripts/linkedin.py review    # read what is waiting, approve or discard
    python scripts/linkedin.py status    # what the pipeline is holding

Drafts live in agent.db beside the repo and survive restarts, which is the
point: you write notes on Tuesday, read drafts on Friday, and the machine in
between does not need to have stayed on.

Nothing here posts to LinkedIn. Approving marks a draft ready and prints it
for you to paste. Publishing through the API is a separate piece of work with
its own OAuth consent, and wiring it into the same command that drafts would
put one keystroke between a model and your real profile.
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from content_agent import ContentStudio, DraftState, PostDraft, WeeklyNote  # noqa: E402
from llm_router.backends import backends_from_environment  # noqa: E402
from persistence import SQLiteRepository, open_database  # noqa: E402
from scripts.env_file import load as load_env  # noqa: E402

DB_PATH = REPO / "agent.db"
PRINCIPAL = "jasmehr"

RULE = "-" * 68


def _studio() -> ContentStudio:
    load_env()
    backends = backends_from_environment()

    # Standard rather than Nano: drafting in a specific voice is the one job
    # where the smaller model's output is visibly worse, and both are free.
    order = ["standard", "nano", "premium"]
    live = [backends[name] for name in order if backends[name].available()]
    if not live:
        print("No model is configured. Put GROQ_API_KEY in .env (see .env.example).")
        raise SystemExit(1)

    def complete(prompt: str, max_tokens: int) -> str:
        last: Exception | None = None
        for backend in live:
            if not backend.available():
                continue
            try:
                output, _, _ = backend.complete(prompt, max_tokens)
                return str(output["text"])
            except Exception as exc:  # noqa: BLE001 - try the next tier, report if none work
                last = exc
        raise RuntimeError(f"every model tier refused: {last}")

    connection = open_database(DB_PATH)
    return ContentStudio(
        complete=complete,
        notes=SQLiteRepository(connection, "linkedin_notes", WeeklyNote),
        drafts=SQLiteRepository(connection, "linkedin_drafts", PostDraft),
    )


def _show(draft: PostDraft) -> None:
    print(f"\n{RULE}\n{draft.draft_id}   [{draft.state.value}]   redrafts: {draft.redraft_count}\n{RULE}")
    print(draft.full_text())
    if draft.outstanding:
        print("\noutstanding:")
        for rule in draft.outstanding:
            print(f"  - {rule}")
    print(RULE)


def cmd_note(studio: ContentStudio) -> int:
    print("What did you do this week? Be specific, include real numbers.")
    print("Finish with a blank line.\n")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip() and lines:
            break
        lines.append(line)

    body = "\n".join(lines).strip()
    if not body:
        print("Nothing captured.")
        return 1

    note = studio.capture(body)
    print(f"\nSaved {note.note_id}.")
    if not note.is_substantive():
        # Said now rather than at draft time, so the fix is one command away
        # instead of one command and a wasted model call away.
        print("Warning: this is thin. Drafting from it will be refused rather than padded out.")
    else:
        print("Run `python scripts/linkedin.py draft` to write from it.")
    return 0


def cmd_draft(studio: ContentStudio) -> int:
    notes = sorted(studio._notes.list_all(), key=lambda n: n.captured_at)
    if not notes:
        print("No notes yet. Run `python scripts/linkedin.py note` first.")
        return 1

    latest = notes[-1]
    print(f"Drafting from {latest.note_id}, captured {latest.captured_at:%d %b %Y}...")
    draft = studio.draft(latest)
    _show(draft)

    if draft.state is DraftState.REJECTED:
        print("\nRejected. The rules above are what it could not satisfy.")
        return 1
    print("\nRun `python scripts/linkedin.py review` to approve or discard.")
    return 0


def cmd_review(studio: ContentStudio) -> int:
    waiting = studio.awaiting_approval()
    if not waiting:
        print("Nothing waiting for you.")
        return 0

    for draft in waiting:
        _show(draft)
        choice = input("\n[a]pprove  [d]iscard  [s]kip  > ").strip().lower()
        if choice == "a":
            approved = studio.approve(draft.draft_id, PRINCIPAL)
            print(f"\nApproved as {approved.approved_by}. Copy the text above into LinkedIn.")
        elif choice == "d":
            studio.discard(draft.draft_id)
            print("Discarded.")
        else:
            print("Skipped, still waiting.")
    return 0


def cmd_status(studio: ContentStudio) -> int:
    health = studio.health()
    print(f"drafts             {health['drafts']}")
    print(f"awaiting approval  {health['awaiting_approval']}")
    print(f"needs attention    {health['needs_attention']}")
    print(f"mean redrafts      {health['mean_redrafts']}")
    for state, count in sorted(health["by_state"].items()):
        print(f"  {state:<16} {count}")

    attention = studio.needs_attention()
    if attention:
        print("\nThese did not work:")
        for draft in attention:
            print(f"  {draft.draft_id}  {', '.join(draft.outstanding) or draft.failure_reason}")
    return 0


COMMANDS = {"note": cmd_note, "draft": cmd_draft, "review": cmd_review, "status": cmd_status}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 1
    return COMMANDS[sys.argv[1]](_studio())


if __name__ == "__main__":
    sys.exit(main())
