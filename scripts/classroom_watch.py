"""Tracks Google Classroom coursework and nudges you before it is late.

    python scripts/classroom_watch.py --auth      # once: connect your Google account
    python scripts/classroom_watch.py --list      # what is outstanding
    python scripts/classroom_watch.py --check     # nudge about anything due
    python scripts/classroom_watch.py --summary   # one message, everything open

Connecting it, once:

1. console.cloud.google.com -> new project -> enable "Google Classroom API"
2. OAuth consent screen -> External -> add yourself as a test user
3. Credentials -> OAuth client ID -> **Desktop app**
4. Put the id and secret in `.env` as GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
5. Run `--auth`, approve in the browser

It asks for three read-only scopes and nothing else. The `.me` on two of them
is what stops it being able to read anybody else's submissions.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request
import webbrowser

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from classroom_agent import SCOPES, ClassroomWatcher, GoogleClassroom, Nudge  # noqa: E402
from inbox_agent.notify import Console, Notifier  # noqa: E402
from persistence import SQLiteRepository, open_database  # noqa: E402
from scripts.env_file import load  # noqa: E402

DB = pathlib.Path(os.environ.get("DB_PATH", REPO / "agent.db"))
TOKEN_FILE = REPO / ".google.json"
PORT = 8765
REDIRECT = f"http://localhost:{PORT}/"


def authorise() -> int:
    """The one-time browser flow. Writes .google.json, which is gitignored."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        print("Put GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env first.")
        print("See the header of this file for where they come from.")
        return 1

    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            # Both needed, together, or Google returns no refresh token and
            # this works once and then stops.
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
    print(f"\nOpening your browser. If nothing happens, paste this in:\n\n{url}\n")
    webbrowser.open(url)

    code = ""

    class Catch(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - the name http.server requires
            nonlocal code
            code = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("code", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            body = "Connected. You can close this tab." if code else "No code came back."
            self.wfile.write(f"<h2>{body}</h2>".encode())

        def log_message(self, *args: object) -> None:
            return None

    print(f"Waiting on {REDIRECT} ...")
    with http.server.HTTPServer(("127.0.0.1", PORT), Catch) as server:
        server.handle_request()

    if not code:
        print("No authorisation code came back. Try again.")
        return 1

    payload = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT,
            "grant_type": "authorization_code",
        }
    ).encode()
    request = urllib.request.Request("https://oauth2.googleapis.com/token", data=payload, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - https, fixed host
        answer = json.loads(response.read().decode())

    refresh = answer.get("refresh_token")
    if not refresh:
        print("Google returned no refresh token. Revoke the app at")
        print("myaccount.google.com/permissions and run --auth again.")
        return 1

    TOKEN_FILE.write_text(json.dumps({"refresh_token": refresh}, indent=2), encoding="utf-8")
    print(f"\nConnected. Token saved to {TOKEN_FILE.name} (gitignored).")
    print("Try:  python scripts/classroom_watch.py --list")
    return 0


def build(notifier: Notifier) -> ClassroomWatcher:
    if not TOKEN_FILE.exists():
        raise SystemExit("Not connected yet. Run: python scripts/classroom_watch.py --auth")
    refresh = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))["refresh_token"]

    def announce(work: object, why: str) -> None:
        notifier.send(f"{getattr(work, 'course_name', '')}: {getattr(work, 'title', '')}\n{why}")

    return ClassroomWatcher(
        source=GoogleClassroom(
            client_id=os.environ["GOOGLE_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
            refresh_token=refresh,
        ),
        nudges=SQLiteRepository(open_database(DB), "classroom_nudges", Nudge),
        announce=announce,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--auth", action="store_true", help="connect your Google account (once)")
    parser.add_argument("--list", action="store_true", help="what is outstanding, soonest first")
    parser.add_argument("--check", action="store_true", help="nudge about anything due or overdue")
    parser.add_argument("--summary", action="store_true", help="print the one-message summary")
    args = parser.parse_args()

    load()
    if args.auth:
        return authorise()

    watcher = build(Console())

    if args.summary:
        print(watcher.summary())
        return 0
    if args.check:
        report = watcher.check()
        print(
            f"{report.seen} seen | {report.outstanding} outstanding | "
            f"{report.overdue} overdue | {report.reminded} nudges"
        )
        for error in report.errors:
            print(f"  problem: {error}")
        return 1 if report.errors else 0

    pending = watcher.outstanding()
    if not pending:
        print("Nothing outstanding.")
        return 0
    print(f"\n{len(pending)} outstanding:\n")
    for work in pending:
        print(f"  {work.describe()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
