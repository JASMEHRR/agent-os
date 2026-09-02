"""Starts Post Studio. One command, then open the browser.

    python scripts/serve.py

Everything is stored in agent.db beside the repo, so closing the window loses
nothing. Bound to loopback, so nothing outside this machine can reach it.

Hosted somewhere instead (START_HERE.md, "Hosting it"), the same script takes
its settings from the environment, and none of them are needed on a laptop:

    PORT                       what to listen on; hosts set this themselves
    POST_STUDIO_HOST           address to bind; anything but loopback needs
    POST_STUDIO_PASSWORD       the password the browser will ask for
    POST_STUDIO_ALLOWED_HOSTS  public hostnames it answers to, comma-separated
    POST_STUDIO_DATA           directory for agent.db and repository clones
    REPO_URLS                  repositories to clone for "pull from git",
                               semicolon-separated
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
from content_agent.samples import Rating, VoiceLibrary, VoiceSample  # noqa: E402
from content_agent.sync import repo_name, sync_repos  # noqa: E402
from content_agent.web import ALLOWED_HOSTS, HOST, LOOPBACK_BINDS, serve  # noqa: E402
from llm_router.backends import backends_from_environment  # noqa: E402
from persistence import SQLiteRepository, open_database  # noqa: E402
from scripts.env_file import load as load_env  # noqa: E402

DB_NAME = "agent.db"
DEFAULT_PORT = 8765

#: Repositories the "pull from git" button reads, commit messages only.
#: Override with REPOS in .env as a semicolon-separated list of paths.
DEFAULT_REPOS = (
    str(REPO),
    str(REPO.parent / "ventureadda"),
    str(REPO.parent / "ASCEND"),
    str(REPO.parent / "clipforge"),
)


def data_dir() -> pathlib.Path:
    """Where agent.db and any clones live. The repo itself unless told otherwise."""
    raw = os.environ.get("POST_STUDIO_DATA", "").strip()
    path = pathlib.Path(raw) if raw else REPO
    path.mkdir(parents=True, exist_ok=True)
    return path


def repo_urls() -> tuple[str, ...]:
    raw = os.environ.get("REPO_URLS", "")
    return tuple(part.strip() for part in raw.split(";") if part.strip())


def checkouts() -> list[str]:
    """Repositories on this machine's disk, given or found beside this one."""
    raw = os.environ.get("REPOS", "")
    if raw.strip():
        return [part.strip() for part in raw.split(";") if part.strip()]
    return [p for p in DEFAULT_REPOS if (pathlib.Path(p) / ".git").exists()]


def clone_urls() -> tuple[str, ...]:
    """REPO_URLS, minus any repository already checked out here.

    A clone of a repository that is also checked out beside this one would be
    the same week read twice, and cloning it would cost a fetch for nothing.
    """
    present = {pathlib.Path(p).name for p in checkouts()}
    kept: list[str] = []
    for url in repo_urls():
        name = repo_name(url)
        if name and name not in present:
            kept.append(url)
            present.add(name)
    return tuple(kept)


def repos_from_environment() -> tuple[str, ...]:
    clones = data_dir() / "repos"
    return tuple(checkouts()) + tuple(str(clones / repo_name(url)) for url in clone_urls())


def refresh_clones() -> None:
    """Before each capture: clone what is missing, pull what is there."""
    for result in sync_repos(clone_urls(), data_dir() / "repos"):
        if result.error:
            print(f"  {result.url}: {result.error}")


def allowed_hosts() -> frozenset[str]:
    names = set(ALLOWED_HOSTS)
    names.update(n.strip() for n in os.environ.get("POST_STUDIO_ALLOWED_HOSTS", "").split(",") if n.strip())
    # Render tells a service its own public hostname, so there is nothing to
    # configure there.
    render = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render:
        names.add(render)
    return frozenset(names)


def bind_host() -> str:
    return os.environ.get("POST_STUDIO_HOST", "").strip() or HOST


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

    connection = open_database(data_dir() / DB_NAME)
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
    )


def preflight() -> int:
    """Checks configuration without starting anything.

    Used by the launcher so the browser is not opened at a server that is
    about to exit. A window that opens on a connection error and a window that
    opens on a real problem look identical to the person watching.
    """
    load_env()
    backends = backends_from_environment()
    if not any(b.available() for b in backends.values()):
        print("")
        print("  No model configured.")
        print("  Copy .env.example to .env and put your free Groq key in it.")
        print("  Get a free one at https://console.groq.com/keys")
        print("")
        return 1
    if bind_host() not in LOOPBACK_BINDS and not os.environ.get("POST_STUDIO_PASSWORD"):
        print("")
        print(f"  POST_STUDIO_HOST is {bind_host()}, which other machines can reach.")
        print("  Set POST_STUDIO_PASSWORD as well, or unset POST_STUDIO_HOST.")
        print("")
        return 1
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        raise SystemExit(preflight())
    studio = build_studio()
    try:
        serve(
            studio,
            port=int(os.environ.get("PORT", str(DEFAULT_PORT))),
            repos=repos_from_environment(),
            host=bind_host(),
            allowed_hosts=allowed_hosts(),
            password=os.environ.get("POST_STUDIO_PASSWORD", ""),
            before_capture=refresh_clones if clone_urls() else None,
        )
    except ValueError as exc:
        print(f"\n  {exc}\n")
        raise SystemExit(1) from None
