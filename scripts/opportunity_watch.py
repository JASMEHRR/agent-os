"""Finds things worth applying to and reminds you before they close.

    python scripts/opportunity_watch.py --list              # what is open
    python scripts/opportunity_watch.py --scan              # read the sources
    python scripts/opportunity_watch.py --add "Title" "Org" "https://..." --due "30 Sep 2026"
    python scripts/opportunity_watch.py --applied <id>      # move a stage on
    python scripts/opportunity_watch.py --closing 7         # what shuts this week

Your profile comes from `.env` (GRAD_YEAR, BRANCH, INTERESTS, AVOID). Reminders
go wherever the inbox agent is pointed, so one WhatsApp setup serves both.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from inbox_agent.notify import Console, Notifier  # noqa: E402
from opportunity_agent import (  # noqa: E402
    JsonFeed,
    Kind,
    ListingSource,
    Matcher,
    Opportunity,
    OpportunityTracker,
    Profile,
    Reminder,
    Stage,
    make,
    parse_date,
)
from persistence import SQLiteRepository, open_database  # noqa: E402
from scripts.env_file import load  # noqa: E402

DB = pathlib.Path(os.environ.get("DB_PATH", REPO / "agent.db"))


def _words(name: str) -> tuple[str, ...]:
    return tuple(w.strip().lower() for w in os.environ.get(name, "").split(",") if w.strip())


def build(notifier: Notifier) -> OpportunityTracker:
    connection = open_database(DB)
    store: SQLiteRepository[Opportunity] = SQLiteRepository(connection, "opportunities", Opportunity)

    sources: list[ListingSource] = []
    # A feed is used only when one is configured; otherwise the tracker runs
    # on what you add by hand, which is a complete way to use it.
    if os.environ.get("OPPORTUNITY_FEED_URL"):
        sources.append(
            JsonFeed(
                url=os.environ["OPPORTUNITY_FEED_URL"],
                rows_at=os.environ.get("OPPORTUNITY_FEED_ROWS", ""),
                kind=Kind(os.environ.get("OPPORTUNITY_FEED_KIND", "competition")),
            )
        )

    def announce(opportunity: Opportunity, why: str) -> None:
        notifier.send(f"{opportunity.title}\n{opportunity.organiser} - {why}\n{opportunity.url}")

    return OpportunityTracker(
        sources=sources,
        matcher=Matcher(
            Profile(
                graduation_year=int(os.environ.get("GRAD_YEAR", "2028")),
                degree=os.environ.get("DEGREE", ""),
                branch=os.environ.get("BRANCH", ""),
                interests=_words("INTERESTS"),
                avoid=_words("AVOID"),
            )
        ),
        store=store,
        reminders=SQLiteRepository(connection, "opportunity_reminders", Reminder),
        announce=announce,
    )


def show(tracker: OpportunityTracker, only_closing: int | None = None) -> None:
    rows = tracker.closing_within(only_closing) if only_closing is not None else tracker.open_ones()
    if not rows:
        print("Nothing open." if only_closing is None else f"Nothing closing in {only_closing} days.")
        return
    print(f"\n{'ID':<18}{'STAGE':<12}{'WHEN':<18}TITLE")
    print("-" * 92)
    for row in rows:
        left = row.days_left()
        when = "no deadline" if left is None else (f"{left}d left" if left > 0 else "TODAY")
        print(f"{row.opportunity_id:<18}{row.stage.value:<12}{when:<18}{row.title[:44]}")
    counts = tracker.by_stage()
    print("\n" + "  ".join(f"{s.value}: {n}" for s, n in sorted(counts.items(), key=lambda kv: kv[0].value)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scan", action="store_true", help="read the sources and remind about deadlines")
    parser.add_argument("--list", action="store_true", help="everything still open")
    parser.add_argument("--closing", type=int, metavar="DAYS", help="what shuts within N days")
    parser.add_argument("--add", nargs=3, metavar=("TITLE", "ORG", "URL"), help="add one by hand")
    parser.add_argument("--due", default="", help='deadline for --add, e.g. "30 Sep 2026"')
    parser.add_argument("--kind", default="competition", help="competition, internship, hackathon, certification...")
    for stage in ("applied", "advanced", "won", "rejected", "skipped"):
        parser.add_argument(f"--{stage}", metavar="ID", help=f"mark an opportunity {stage}")
    args = parser.parse_args()

    load()
    tracker = build(Console())

    if args.add:
        title, org, url = args.add
        made = make(title, org, url, Kind(args.kind), parse_date(args.due) if args.due else None)
        tracker.store.save(made.opportunity_id, made)
        print(f"Added [{made.opportunity_id}]  {made.describe()}")
        return 0

    for stage in (Stage.APPLIED, Stage.ADVANCED, Stage.WON, Stage.REJECTED, Stage.SKIPPED):
        given = getattr(args, stage.value, None)
        if given:
            try:
                moved = tracker.move(given, stage)
            except Exception as exc:  # noqa: BLE001 - the message is the point
                print(f"Cannot: {exc}")
                return 1
            print(f"{moved.title} -> {moved.stage.value}")
            return 0

    if args.scan:
        report = tracker.scan()
        print(
            f"{report.found} seen | {report.added} kept ({report.matched} matches, {report.maybe} maybe) | "
            f"{report.rejected} not for you | {report.reminded} reminders | {report.missed} missed"
        )
        for error in report.errors:
            print(f"  source problem: {error}")
        return 0

    show(tracker, args.closing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
