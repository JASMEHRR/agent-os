"""Watches your college inbox and WhatsApps you what matters.

    python scripts/inbox_watch.py --once --dry-run     # see what it would send
    python scripts/inbox_watch.py --once               # send for real
    python scripts/inbox_watch.py                      # poll forever

Everything is configured in `.env`. Run `--check` to see what is set and what
is missing without connecting to anything.

**Start with `--dry-run` for a day.** It reads real mail and prints what it
would have texted. An alerting agent you cannot trust is worse than no agent,
and one day of dry runs is what tells you whether the rules fit your inbox.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
import time
from datetime import UTC, datetime

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from inbox_agent import (  # noqa: E402
    Alert,
    CallMeBot,
    Console,
    ImapSource,
    InboxAgent,
    Notifier,
    Triage,
    Twilio,
    Watermark,
)
from inbox_agent.filters import Filter, FilterBook, new_filter  # noqa: E402
from inbox_agent.sources import KNOWN_HOSTS  # noqa: E402
from llm_router.backends import backends_from_environment  # noqa: E402
from persistence import SQLiteRepository, open_database  # noqa: E402
from scripts.env_file import load  # noqa: E402

DB = pathlib.Path(os.environ.get("DB_PATH", REPO / "agent.db"))

CLASSIFY_PROMPT = """You triage a university student's email. Answer with exactly one word.

urgent     - needs action today: interview, shortlist, exam or fee deadline within 24h
important  - matters this week: results, submissions, a person waiting on a reply
routine    - worth reading eventually, no action
noise      - bulk, promotional, automated

From: {sender}
Subject: {subject}
Body: {body}

One word:"""


def _split(name: str) -> frozenset[str]:
    return frozenset(p.strip().lower() for p in os.environ.get(name, "").split(",") if p.strip())


def build_notifier(dry_run: bool) -> tuple[Notifier, str]:
    if dry_run:
        return Console(), "dry run (nothing is sent)"
    if os.environ.get("TWILIO_ACCOUNT_SID"):
        return (
            Twilio(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
                from_number=os.environ.get("TWILIO_FROM", "+14155238886"),
                to_number=os.environ["WHATSAPP_TO"],
            ),
            "Twilio",
        )
    if os.environ.get("CALLMEBOT_APIKEY"):
        return CallMeBot(phone=os.environ["WHATSAPP_TO"], apikey=os.environ["CALLMEBOT_APIKEY"]), "CallMeBot"
    return Console(), "nothing configured, so printing instead"


def filter_store() -> SQLiteRepository[Filter]:
    return SQLiteRepository(open_database(DB), "inbox_filters", Filter)


def build_triage(book: FilterBook | None = None) -> tuple[Triage, str]:
    """Rules always; the model only if a key is present and not switched off."""
    me = os.environ.get("COLLEGE_EMAIL", "")
    book = book if book is not None else FilterBook(filter_store().list_all())
    if os.environ.get("INBOX_RULES_ONLY") or not os.environ.get("GROQ_API_KEY"):
        return Triage(
            me=me,
            vip_senders=_split("VIP_SENDERS"),
            vip_domains=_split("VIP_DOMAINS"),
            muted_senders=_split("MUTED_SENDERS"),
            filters=book,
        ), "rules only"

    # Nano first, unlike the drafting path. Picking one of four words is the
    # job the small model does as well as the large one, and this runs on every
    # ambiguous message rather than a few times a week.
    backends = backends_from_environment()
    live = [backends[name] for name in ("nano", "standard") if backends[name].available()]
    if not live:
        return Triage(
            me=me,
            vip_senders=_split("VIP_SENDERS"),
            vip_domains=_split("VIP_DOMAINS"),
            muted_senders=_split("MUTED_SENDERS"),
            filters=book,
        ), "rules only (no model reachable)"

    def classify(subject: str, sender: str, body: str) -> str:
        # Subject, sender and a short snippet only. The body was already cut to
        # 600 characters when it was parsed; this is the second boundary.
        prompt = CLASSIFY_PROMPT.format(sender=sender, subject=subject, body=body[:400])
        last: Exception | None = None
        for backend in live:
            try:
                output, _, _ = backend.complete(prompt, 5)
                return str(output["text"])
            except Exception as exc:  # noqa: BLE001 - fall to the next tier
                last = exc
        raise RuntimeError(f"every model tier refused. Last error: {last}")

    return (
        Triage(
            me=me,
            vip_senders=_split("VIP_SENDERS"),
            vip_domains=_split("VIP_DOMAINS"),
            muted_senders=_split("MUTED_SENDERS"),
            classify=classify,
            filters=book,
        ),
        "rules, with the model for close calls",
    )


def build_agent(dry_run: bool) -> tuple[InboxAgent, str]:
    host = os.environ.get("IMAP_HOST") or KNOWN_HOSTS.get(os.environ.get("EMAIL_PROVIDER", "").lower(), "")
    if not host:
        raise SystemExit(
            "Set EMAIL_PROVIDER=gmail or EMAIL_PROVIDER=outlook in .env, or IMAP_HOST for anything else.\n"
            "Run with --check to see everything that is missing."
        )

    connection = open_database(DB)
    triage, how = build_triage()
    notifier, where = build_notifier(dry_run)

    agent = InboxAgent(
        source=ImapSource(
            host=host,
            username=os.environ["COLLEGE_EMAIL"],
            password=os.environ["EMAIL_PASSWORD"],
            mailbox=os.environ.get("IMAP_MAILBOX", "INBOX"),
        ),
        triage=triage,
        notifier=notifier,
        alerts=SQLiteRepository(connection, "inbox_alerts", Alert),
        watermarks=SQLiteRepository(connection, "inbox_watermark", Watermark),
        quiet_from=int(os.environ.get("QUIET_FROM", "23")),
        quiet_until=int(os.environ.get("QUIET_UNTIL", "7")),
        max_per_hour=int(os.environ.get("MAX_ALERTS_PER_HOUR", "6")),
    )
    return agent, f"{host} -> {where}; triage: {how}"


def check() -> int:
    """Says what is configured and what is missing. Connects to nothing."""
    required = ("COLLEGE_EMAIL", "EMAIL_PASSWORD")
    provider = os.environ.get("EMAIL_PROVIDER", "").lower()
    host = os.environ.get("IMAP_HOST") or KNOWN_HOSTS.get(provider, "")

    print("Inbox watcher configuration\n")
    for name in required:
        value = os.environ.get(name, "")
        shown = "set" if value else "MISSING"
        print(f"  {name:<24} {shown}")
    print(f"  {'mail server':<24} {host or 'MISSING (set EMAIL_PROVIDER or IMAP_HOST)'}")

    if os.environ.get("TWILIO_ACCOUNT_SID"):
        route = "Twilio"
    elif os.environ.get("CALLMEBOT_APIKEY"):
        route = "CallMeBot"
    else:
        route = "MISSING (set CALLMEBOT_APIKEY or the TWILIO_* keys)"
    print(f"  {'WhatsApp route':<24} {route}")
    print(f"  {'WHATSAPP_TO':<24} {os.environ.get('WHATSAPP_TO') or 'MISSING'}")

    if os.environ.get("INBOX_RULES_ONLY"):
        model = "off (INBOX_RULES_ONLY is set) - nothing leaves this machine"
    elif os.environ.get("GROQ_API_KEY"):
        model = "on for close calls only (subject, sender, 400 chars)"
    else:
        model = "off (no GROQ_API_KEY) - rules only"
    print(f"  {'model':<24} {model}")
    quiet = f"{os.environ.get('QUIET_FROM', '23')}:00 to {os.environ.get('QUIET_UNTIL', '7')}:00"
    print(f"\n  {'quiet hours':<24} {quiet}")
    print(f"  max alerts per hour      {os.environ.get('MAX_ALERTS_PER_HOUR', '6')}")
    print(f"  database                 {DB}")

    missing = [n for n in required if not os.environ.get(n)] + ([] if host else ["mail server"])
    if missing:
        print(f"\nNot ready: {', '.join(missing)}")
        return 1
    print("\nReady. Try:  python scripts/inbox_watch.py --once --dry-run")
    return 0


def manage_filters(args: argparse.Namespace) -> int:
    """Add, list and delete the rules. Separate from watching on purpose: you
    change filters in a spare moment, not while a poll loop is running."""
    store = filter_store()

    for rule, pair in (("always", args.always), ("never", args.never)):
        if not pair:
            continue
        try:
            made = new_filter(rule, pair[0], pair[1])
        except ValueError as exc:
            print(f"Cannot add that: {exc}")
            return 1
        store.save(made.filter_id, made)
        print(f"Added [{made.filter_id}]  {made.describe()}")

    if args.forget:
        try:
            store.delete(args.forget)
            print(f"Deleted {args.forget}")
        except Exception:  # noqa: BLE001 - "no such filter" is the only case
            print(f"No filter with id {args.forget}")
            return 1

    rules = sorted(store.list_all(), key=lambda f: f.added_at)
    if not rules:
        print("\nNo filters yet. Add one:")
        print('  python scripts/inbox_watch.py --never subject "canteen"')
        print('  python scripts/inbox_watch.py --always domain "placements.college.edu"')
        return 0
    print(f"\nYour filters ({len(rules)}):")
    for rule_row in rules:
        fired = f"{rule_row.hits} hits" if rule_row.hits else "not fired yet"
        print(f"  [{rule_row.filter_id}]  {rule_row.describe():<52} {fired}")
    print("\nDelete one with:  python scripts/inbox_watch.py --forget <id>")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--once", action="store_true", help="check once and exit, instead of polling")
    parser.add_argument("--dry-run", action="store_true", help="print what it would send, send nothing")
    parser.add_argument("--check", action="store_true", help="show the configuration and exit")
    parser.add_argument("--every", type=int, default=300, help="seconds between polls (default 300)")
    parser.add_argument("--digest", action="store_true", help="send whatever is waiting right now, then exit")
    parser.add_argument(
        "--always",
        nargs=2,
        metavar=("SENDER|DOMAIN|SUBJECT", "VALUE"),
        help='always tell me about this, e.g. --always subject "robotics"',
    )
    parser.add_argument(
        "--never",
        nargs=2,
        metavar=("SENDER|DOMAIN|SUBJECT", "VALUE"),
        help='never tell me about this, e.g. --never subject "canteen"',
    )
    parser.add_argument("--filters", action="store_true", help="list your filters and exit")
    parser.add_argument("--forget", metavar="ID", help="delete a filter by its id")
    args = parser.parse_args()

    load()
    if args.check:
        return check()
    if args.always or args.never or args.filters or args.forget:
        return manage_filters(args)

    agent, described = build_agent(args.dry_run)
    print(f"Watching {described}", flush=True)

    if args.digest:
        print("sent" if agent.send_digest() else "nothing waiting", flush=True)
        return 0

    while True:
        stamp = datetime.now(UTC).astimezone().strftime("%H:%M")
        try:
            report = agent.run_once()
        except Exception as exc:  # noqa: BLE001 - a watcher must outlive one bad poll
            print(f"[{stamp}] poll failed: {exc.__class__.__name__}: {exc}", flush=True)
            if args.once:
                return 1
            time.sleep(args.every)
            continue

        print(
            f"[{stamp}] {report.seen} new | {report.alerted} texted | {report.held} held | "
            f"{report.routine} routine | {report.noise} ignored"
            + (" | digest sent" if report.digest_sent else "")
            + (f" | FAILURES: {'; '.join(report.failures)}" if report.failures else ""),
            flush=True,
        )
        if args.once:
            return 0
        time.sleep(args.every)


if __name__ == "__main__":
    raise SystemExit(main())
