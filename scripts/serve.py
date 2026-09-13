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

import atexit
import json
import os
import pathlib
import sys
from datetime import timedelta
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from classroom_agent import Assignment, ClassroomWatcher, GoogleClassroom, Nudge  # noqa: E402
from classroom_agent.panel import ClassworkPanel  # noqa: E402
from content_agent import ContentStudio, PostDraft, WeeklyNote  # noqa: E402
from content_agent.analytics import Analytics, ApifyMetrics, Snapshot, TrackedPost  # noqa: E402
from content_agent.connect import ConnectPanel  # noqa: E402
from content_agent.outreach import OutreachDraft, Prospect  # noqa: E402
from content_agent.owner import Owner  # noqa: E402
from content_agent.persona import CheckIn, Fact, Persona  # noqa: E402
from content_agent.samples import Rating, VoiceLibrary, VoiceSample  # noqa: E402
from content_agent.schedule import Publisher  # noqa: E402
from content_agent.studio import Completion  # noqa: E402
from content_agent.sync import repo_name, sync_repos  # noqa: E402
from content_agent.web import serve  # noqa: E402
from inbox_agent import CallMeBot, Console, ImapSource, InboxAgent, Notifier, Triage, Twilio, Watermark  # noqa: E402
from inbox_agent.agent import Alert  # noqa: E402
from inbox_agent.filters import Filter, FilterBook  # noqa: E402
from inbox_agent.gmail import GmailSource  # noqa: E402
from inbox_agent.panel import InboxPanel  # noqa: E402
from inbox_agent.sources import KNOWN_HOSTS  # noqa: E402
from llm_router.backends import backends_from_environment  # noqa: E402
from opportunity_agent import Matcher, Opportunity, OpportunityTracker, Profile, Reminder  # noqa: E402
from opportunity_agent.panel import ApplyPanel  # noqa: E402
from persistence import SQLiteRepository, open_database  # noqa: E402
from scheduler import Job, JobState, Lease, Leases, schedule  # noqa: E402
from scheduler.panel import SchedulerPanel  # noqa: E402
from scripts.env_file import ENV_FILE  # noqa: E402
from scripts.env_file import load as load_env  # noqa: E402

#: On this laptop, beside the repo. On a host, wherever the persistent volume
#: is mounted, because a free host's default disk is wiped on every restart.
DB_PATH = pathlib.Path(os.environ.get("DB_PATH", str(REPO / "agent.db")))
PORT = 8765

#: How many sibling checkouts the "pull from git" button will read without
#: being told to. A folder of forty clones would make one button press walk
#: forty git histories, so past this it asks for REPOS rather than guessing.
MAX_DISCOVERED_REPOS = 8


def sibling_repos() -> tuple[str, ...]:
    """This repository, plus any other git checkout sitting beside it.

    This used to be a hardcoded list of four project names - which worked
    perfectly on one laptop and named four folders that do not exist on
    anybody else's. Reading the disk finds whatever is actually there, and
    finds it for everyone.
    """
    found = [str(REPO)]
    try:
        siblings = sorted(REPO.parent.iterdir())
    except OSError:
        return tuple(found)
    for path in siblings:
        if path != REPO and (path / ".git").exists():
            found.append(str(path))
    return tuple(found[:MAX_DISCOVERED_REPOS])


#: Clones made from REPO_URLS live beside the database, which on a host is
#: the one place that may be a persistent volume.
CLONES = DB_PATH.parent / "repos"


def checkouts() -> tuple[str, ...]:
    """Repositories on this machine's disk, given or found beside this one."""
    raw = os.environ.get("REPOS", "")
    if raw.strip():
        return tuple(part.strip() for part in raw.split(";") if part.strip())
    return sibling_repos()


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


def _google() -> tuple[str, list[str]]:
    """The shared refresh token and the scopes it was granted.

    `("", [])` when nobody has signed in, which every caller treats as "that
    half of the setup is not done" rather than as an error.
    """
    token_file = REPO / ".google.json"
    if not token_file.exists() or not os.environ.get("GOOGLE_CLIENT_ID"):
        return "", []
    try:
        saved = json.loads(token_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "", []
    return str(saved.get("refresh_token", "")), [str(s) for s in saved.get("scopes", [])]


def _mail_source() -> tuple[Any, str]:
    """Gmail over OAuth when Google is signed in, IMAP otherwise.

    That order because the OAuth grant is read-only by Google's enforcement
    rather than by this client's own promise, and because it is the one the
    person has already clicked through a prompt for.

    The scope is checked rather than assumed: a token granted for Classroom
    alone is a real state, and using it for Gmail would fail at the first
    request with a 403 that looks like something else.
    """
    token, scopes = _google()
    if token and any("gmail" in scope for scope in scopes):
        return (
            GmailSource(
                client_id=os.environ["GOOGLE_CLIENT_ID"],
                client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
                refresh_token=token,
            ),
            "Gmail, signed in with Google",
        )

    host = os.environ.get("IMAP_HOST") or KNOWN_HOSTS.get(os.environ.get("EMAIL_PROVIDER", "").lower(), "")
    if host and os.environ.get("COLLEGE_EMAIL") and os.environ.get("EMAIL_PASSWORD"):
        return (
            ImapSource(
                host=host,
                username=os.environ["COLLEGE_EMAIL"],
                password=os.environ["EMAIL_PASSWORD"],
                mailbox=os.environ.get("IMAP_MAILBOX", "INBOX"),
            ),
            f"{host} over IMAP",
        )
    return None, ""


def inbox_panel() -> InboxPanel | None:
    """The Inbox tab. Present whenever the database is, because the filters
    and the record of past decisions are worth seeing even before the mailbox
    is connected — that is where you set it up from."""
    connection = open_database(DB_PATH)
    filters: SQLiteRepository[Filter] = SQLiteRepository(connection, "inbox_filters", Filter)
    alerts: SQLiteRepository[Alert] = SQLiteRepository(connection, "inbox_alerts", Alert)

    source, how = _mail_source()
    if source is None:
        return InboxPanel(
            filters=filters,
            alerts=alerts,
            setup="sign in with Google, or fill in the college email fields",
        )

    agent = InboxAgent(
        source=source,
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
    return InboxPanel(filters=filters, alerts=alerts, agent=agent, setup=how)


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


# ------------------------------------------------------------- running alone
#
# Until now every agent waited to be pressed. The mailbox was checked when
# somebody opened the Inbox tab; the deadline reminders fired when somebody
# opened Apply. Closing the window turned the whole thing off, which makes
# these tools rather than agents.
#
# These are the cadences that change that. Each is overridable from .env,
# because "how often should this check" is a preference and five minutes is
# only a good default for a mailbox somebody is actually waiting on.


def _minutes(name: str, fallback: float) -> float:
    try:
        return max(1.0, float(os.environ.get(name, fallback)))
    except ValueError:
        return fallback


def jobs(inbox: Any, apply_tab: Any, classwork: Any) -> list[Job | None]:
    """What runs on its own, given whichever agents are actually set up.

    Returns `None` for an agent that is not connected rather than a job that
    would fail on every tick and fill the Automatic tab with red.
    """

    def poll_mail() -> str:
        r = inbox.check_now()
        if r["failures"]:
            # Surfaced rather than swallowed: a poll that read nothing because
            # the connection broke must not report "nothing new".
            raise RuntimeError("; ".join(r["failures"]))
        return f"{r['seen']} new, {r['alerted']} texted, {r['held']} held"

    def scan_deadlines() -> str:
        r = apply_tab.scan()
        if r["errors"]:
            raise RuntimeError("; ".join(r["errors"]))
        return f"{r['added']} added, {r['reminded']} reminders, {r['missed']} missed"

    def check_classwork() -> str:
        r = classwork.check_now()
        if r["errors"]:
            raise RuntimeError("; ".join(r["errors"]))
        return f"{r['outstanding']} outstanding, {r['overdue']} overdue, {r['reminded']} nudges"

    return [
        Job(
            job_id="mail",
            label="Check my email",
            every=timedelta(minutes=_minutes("INBOX_EVERY_MINUTES", 5)),
            run=poll_mail,
            describes="Reads new mail and texts you the ones that matter",
        )
        if inbox is not None and inbox.agent is not None
        else None,
        Job(
            job_id="deadlines",
            label="Watch my deadlines",
            every=timedelta(minutes=_minutes("APPLY_EVERY_MINUTES", 6 * 60)),
            run=scan_deadlines,
            describes="Reminds you before anything you are tracking closes",
        )
        if apply_tab is not None
        else None,
        Job(
            job_id="classwork",
            label="Watch my classwork",
            every=timedelta(minutes=_minutes("CLASSWORK_EVERY_MINUTES", 3 * 60)),
            run=check_classwork,
            describes="Nudges you before an assignment is due",
        )
        if classwork is not None and classwork.watcher is not None
        else None,
    ]


def automatic(inbox: Any, apply_tab: Any, classwork: Any) -> SchedulerPanel | None:
    """The running scheduler, or None when nothing is connected to run.

    A scheduler with no jobs would show an empty tab that reads as "nothing to
    do"; no tab at all correctly reads as "not wired up yet", which is the
    same rule the three agent tabs follow.
    """
    connection = open_database(DB_PATH)
    built = schedule(
        jobs(inbox, apply_tab, classwork),
        SQLiteRepository(connection, "scheduler_runs", JobState),
        # So opening the studio beside a running watcher does not poll the
        # same mailbox twice. Whichever holds the lease does the work; the
        # other shows what it is doing.
        Leases(store=SQLiteRepository(connection, "scheduler_lease", Lease), describes="Post Studio"),
    )
    if not built.jobs:
        return None
    built.start()
    # Registered so Ctrl-C stops the thread before the database closes under
    # it. The thread is a daemon, so this is about a clean last write rather
    # than about the process being able to exit.
    atexit.register(built.stop)
    return SchedulerPanel(built)


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
        # Deliberately not an exit. The Connect screen exists so nobody has to
        # edit a file to supply a key - and refusing to start without one made
        # that screen unreachable until you had already done the thing it
        # replaces. Everything except drafting works without a model, so the
        # studio opens, says what is missing, and lets you fix it in the app.
        print("\n  No model connected yet. Opening anyway - use the Connect screen.")
        print("  Free Groq key: https://console.groq.com/keys\n")

        def refuse(prompt: str, max_tokens: int) -> str:
            raise RuntimeError(
                "No model is connected yet. Open the Connect screen and paste a Groq key, "
                "then restart. A free one takes a minute: https://console.groq.com/keys"
            )

        return _studio_with(refuse)

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

    return _studio_with(complete)


def _owner() -> Owner:
    """Who this copy drafts as. Empty is a real answer, not a missing one."""
    return Owner(name=os.environ.get("OWNER_NAME", ""), about=os.environ.get("OWNER_ABOUT", ""))


def model_ready() -> bool:
    """Whether anything can actually draft. Read by the page, so the Write tab
    can say why the button will not work rather than failing when pressed."""
    return any(b.available() for b in backends_from_environment().values())


def _studio_with(complete: Completion) -> ContentStudio:
    """The studio, given whatever can (or cannot) generate text.

    Split out so the no-model path builds exactly the same object with exactly
    the same storage - the only difference being what happens if you press
    "Write my drafts".
    """
    connection = open_database(DB_PATH)
    return ContentStudio(
        complete=complete,
        owner=_owner(),
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
    # A warning, not a refusal. The studio starts without a model and the
    # Connect screen is how you add one, so blocking the launcher here would
    # leave a first-time user with no way in at all.
    print("")
    print("  No model connected yet - opening anyway.")
    print("  Add a free Groq key in the Connect tab once it opens.")
    print("  https://console.groq.com/keys")
    print("")
    return 0


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
    inbox, apply_tab, classwork = inbox_panel(), apply_panel(), classwork_panel()
    serve(
        build_studio(),
        port=int(os.environ.get("PORT", PORT)),
        repos=repos_from_environment(),
        password=os.environ.get("STUDIO_PASSWORD", ""),
        before_capture=refresh_clones if clone_urls() else None,
        publisher=publisher(),
        metrics=metrics(),
        inbox=inbox,
        apply_panel=apply_tab,
        classwork=classwork,
        connect=ConnectPanel(ENV_FILE),
        scheduler=automatic(inbox, apply_tab, classwork),
        can_draft=model_ready(),
    )
