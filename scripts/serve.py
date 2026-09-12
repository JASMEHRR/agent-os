"""Starts Post Studio. One command, then open the browser.

    python scripts/serve.py

Everything is stored in agent.db beside the repo, so closing the window loses
nothing. Bound to loopback, so nothing outside this machine can reach it.

Hosted (docs/HOSTING.md), STUDIO_PASSWORD switches on the login, DB_PATH says
where the database lives, and REPO_URLS lists repositories to clone for the
"pull this week from my git" button, since a container has no checkouts beside
it. None of these are needed on a laptop.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from classroom_agent import Assignment, ClassroomWatcher, GoogleClassroom, Nudge  # noqa: E402
from classroom_agent.panel import ClassworkPanel  # noqa: E402
from content_agent import ContentStudio, PostDraft, WeeklyNote  # noqa: E402
from content_agent.analytics import Analytics, ApifyMetrics, Snapshot, TrackedPost  # noqa: E402
from content_agent.outreach import OutreachDraft, Prospect  # noqa: E402
from content_agent.persona import CheckIn, Fact, Persona  # noqa: E402
from content_agent.samples import Rating, VoiceLibrary, VoiceSample  # noqa: E402
from content_agent.schedule import Publisher  # noqa: E402
from content_agent.sync import repo_name, sync_repos  # noqa: E402
from content_agent.web import serve  # noqa: E402
from inbox_agent import CallMeBot, Console, ImapSource, InboxAgent, Notifier, Triage, Twilio, Watermark  # noqa: E402
from inbox_agent.agent import Alert  # noqa: E402
from inbox_agent.filters import Filter, FilterBook  # noqa: E402
from inbox_agent.panel import InboxPanel  # noqa: E402
from inbox_agent.sources import KNOWN_HOSTS  # noqa: E402
from llm_router.backends import backends_from_environment  # noqa: E402
from opportunity_agent import Matcher, Opportunity, OpportunityTracker, Profile, Reminder  # noqa: E402
from opportunity_agent.panel import ApplyPanel  # noqa: E402
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


#: Clones made from REPO_URLS live beside the database, which on a host is
#: the one place that may be a persistent volume.
CLONES = DB_PATH.parent / "repos"


def checkouts() -> tuple[str, ...]:
    """Repositories on this machine's disk, given or found beside this one."""
    raw = os.environ.get("REPOS", "")
    if raw.strip():
        return tuple(part.strip() for part in raw.split(";") if part.strip())
    return tuple(p for p in DEFAULT_REPOS if pathlib.Path(p).exists())


def clone_urls() -> tuple[str, ...]:
    """REPO_URLS, minus any repository already checked out here.

    A clone of a repository that is also checked out beside this one would be
    the same week read twice, and fetching it would cost a request for nothing.
    """
    present = {pathlib.Path(p).name for p in checkouts()}
    kept: list[str] = []
    for url in (part.strip() for part in os.environ.get("REPO_URLS", "").split(";")):
        name = repo_name(url)
        if url and name and name not in present:
            kept.append(url)
            present.add(name)
    return tuple(kept)


def repos_from_environment() -> tuple[str, ...]:
    return checkouts() + tuple(str(CLONES / repo_name(url)) for url in clone_urls())


def refresh_clones() -> None:
    """Before each capture: clone what is missing, pull what is there."""
    for result in sync_repos(clone_urls(), CLONES):
        if result.error:
            print(f"  {result.url}: {result.error}")


# ------------------------------------------------------------- the agent tabs
#
# Each returns None when that agent is not set up, and a None panel hides its
# tab entirely. A visible tab with nothing in it would read as "nothing to do";
# an absent tab correctly reads as "not wired up".


def inbox_panel() -> InboxPanel | None:
    """The Inbox tab. Present whenever the database is, because the filters
    and the record of past decisions are worth seeing even before the mailbox
    is connected — that is where you set it up from."""
    connection = open_database(DB_PATH)
    filters: SQLiteRepository[Filter] = SQLiteRepository(connection, "inbox_filters", Filter)
    alerts: SQLiteRepository[Alert] = SQLiteRepository(connection, "inbox_alerts", Alert)

    host = os.environ.get("IMAP_HOST") or KNOWN_HOSTS.get(os.environ.get("EMAIL_PROVIDER", "").lower(), "")
    ready = bool(host and os.environ.get("COLLEGE_EMAIL") and os.environ.get("EMAIL_PASSWORD"))
    if not ready:
        missing = [
            name
            for name, value in (
                ("EMAIL_PROVIDER or IMAP_HOST", host),
                ("COLLEGE_EMAIL", os.environ.get("COLLEGE_EMAIL", "")),
                ("EMAIL_PASSWORD", os.environ.get("EMAIL_PASSWORD", "")),
            )
            if not value
        ]
        return InboxPanel(filters=filters, alerts=alerts, setup=f"missing: {', '.join(missing)}")

    agent = InboxAgent(
        source=ImapSource(
            host=host,
            username=os.environ["COLLEGE_EMAIL"],
            password=os.environ["EMAIL_PASSWORD"],
            mailbox=os.environ.get("IMAP_MAILBOX", "INBOX"),
        ),
        triage=Triage(
            me=os.environ.get("COLLEGE_EMAIL", ""),
            vip_senders=_words("VIP_SENDERS"),
            vip_domains=_words("VIP_DOMAINS"),
            muted_senders=_words("MUTED_SENDERS"),
            filters=FilterBook(list(filters.list_all())),
        ),
        notifier=_notifier(),
        alerts=alerts,
        watermarks=SQLiteRepository(connection, "inbox_watermark", Watermark),
        quiet_from=int(os.environ.get("QUIET_FROM", "23")),
        quiet_until=int(os.environ.get("QUIET_UNTIL", "7")),
        max_per_hour=int(os.environ.get("MAX_ALERTS_PER_HOUR", "6")),
    )
    return InboxPanel(filters=filters, alerts=alerts, agent=agent, setup="")


def apply_panel() -> ApplyPanel:
    """The Apply tab. Always present: adding something by hand and tracking
    its stages needs no external service at all."""
    connection = open_database(DB_PATH)
    notifier = _notifier()

    def announce(row: Opportunity, why: str) -> None:
        notifier.send(f"{row.title}\n{row.organiser} - {why}\n{row.url}")

    return ApplyPanel(
        OpportunityTracker(
            sources=[],
            matcher=Matcher(
                Profile(
                    graduation_year=int(os.environ.get("GRAD_YEAR", "2028")),
                    degree=os.environ.get("DEGREE", ""),
                    branch=os.environ.get("BRANCH", ""),
                    interests=tuple(_words("INTERESTS")),
                    avoid=tuple(_words("AVOID")),
                )
            ),
            store=SQLiteRepository(connection, "opportunities", Opportunity),
            reminders=SQLiteRepository(connection, "opportunity_reminders", Reminder),
            announce=announce,
        )
    )


def classwork_panel() -> ClassworkPanel:
    """The Classwork tab. Shows how to connect Google when it is not."""
    token_file = REPO / ".google.json"
    if not token_file.exists() or not os.environ.get("GOOGLE_CLIENT_ID"):
        return ClassworkPanel(setup="run: python scripts/classroom_watch.py --auth")

    notifier = _notifier()

    def announce(work: Assignment, why: str) -> None:
        notifier.send(f"{work.course_name}: {work.title}\n{why}")

    return ClassworkPanel(
        ClassroomWatcher(
            source=GoogleClassroom(
                client_id=os.environ["GOOGLE_CLIENT_ID"],
                client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
                refresh_token=json.loads(token_file.read_text(encoding="utf-8"))["refresh_token"],
            ),
            nudges=SQLiteRepository(open_database(DB_PATH), "classroom_nudges", Nudge),
            announce=announce,
        )
    )


def _words(name: str) -> frozenset[str]:
    return frozenset(w.strip().lower() for w in os.environ.get(name, "").split(",") if w.strip())


def _notifier() -> Notifier:
    """Where an agent's alert goes. One setup serves all three."""
    if os.environ.get("TWILIO_ACCOUNT_SID"):
        return Twilio(
            account_sid=os.environ["TWILIO_ACCOUNT_SID"],
            auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            from_number=os.environ.get("TWILIO_FROM", "+14155238886"),
            to_number=os.environ["WHATSAPP_TO"],
        )
    if os.environ.get("CALLMEBOT_APIKEY"):
        return CallMeBot(phone=os.environ.get("WHATSAPP_TO", ""), apikey=os.environ["CALLMEBOT_APIKEY"])
    return Console()


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
        # Durable too. A snapshot is only worth taking because the one before
        # it is still there to compare against, so an analytics history that
        # reset on restart would never grow past a single reading.
        analytics=Analytics(
            SQLiteRepository(connection, "tracked_posts", TrackedPost),
            SQLiteRepository(connection, "post_snapshots", Snapshot),
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


def publisher() -> Publisher | None:
    """The real LinkedIn poster, or nothing if this copy cannot post.

    Imported here rather than at module scope so the studio still starts on a
    machine where the posting script's dependencies or token are missing: the
    Post and Schedule buttons then say they are not set up, which is a better
    failure than a server that will not boot.
    """
    try:
        from scripts.linkedin_post import load_credentials, post_text
    except ImportError:
        return None
    creds = load_credentials()
    if creds is None or creds.expired():
        return None
    return post_text


def metrics() -> ApifyMetrics | None:
    """Apify, if a token is set. The numbers screen degrades without one."""
    source = ApifyMetrics()
    return source if source.configured() else None


if __name__ == "__main__":
    if "--check" in sys.argv:
        raise SystemExit(preflight())
    # STUDIO_PASSWORD set means "hosted": bind every interface and require a
    # login. Unset means "this laptop": loopback only, no login, because
    # reachability is the authorisation there.
    load_env()
    serve(
        build_studio(),
        port=int(os.environ.get("PORT", PORT)),
        repos=repos_from_environment(),
        password=os.environ.get("STUDIO_PASSWORD", ""),
        before_capture=refresh_clones if clone_urls() else None,
        publisher=publisher(),
        metrics=metrics(),
        inbox=inbox_panel(),
        apply_panel=apply_panel(),
        classwork=classwork_panel(),
    )
