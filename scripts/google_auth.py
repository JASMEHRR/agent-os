"""One Google sign-in, covering every agent that needs Google.

    python scripts/google_auth.py            # sign in
    python scripts/google_auth.py --status   # what is connected
    python scripts/google_auth.py --forget   # revoke locally

Both the Inbox agent (Gmail) and the Classwork agent (Classroom) authorise
through here, in one prompt, because Google issues one refresh token per
consent and asking twice would have the second overwrite the first - leaving
whichever agent signed in first quietly broken.

Setting it up, once:

1. console.cloud.google.com -> new project
2. APIs & Services -> Library -> enable **Gmail API** and **Google Classroom API**
3. OAuth consent screen -> External -> add your own address as a test user
4. Credentials -> Create credentials -> OAuth client ID -> **Desktop app**
5. Put the id and secret into the Connect screen, or `.env`
6. Run this

The consent screen will call the app unverified, because it is yours and
Google has not reviewed it. "Advanced" then "Go to ... (unsafe)" is the way
past, and the warning is accurate: you are trusting an app you built.

Every scope requested is read-only. Nothing here can send, delete or modify
anything in your account, and Google enforces that rather than this code
promising it.
"""

from __future__ import annotations

import argparse
import http.server
import json
import pathlib
import sys
import urllib.parse
import urllib.request
import webbrowser

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from classroom_agent.source import SCOPES as CLASSROOM_SCOPES  # noqa: E402
from inbox_agent.gmail import SCOPES as GMAIL_SCOPES  # noqa: E402
from scripts.env_file import load as load_env  # noqa: E402

TOKEN_FILE = REPO / ".google.json"
PORT = 8765
REDIRECT = f"http://localhost:{PORT}/"

#: The union, de-duplicated and ordered so the consent screen reads the same
#: way every time. `openid`/`email` are included only so the token can be
#: attributed to an address in `--status`; neither grants access to anything.
SCOPES: tuple[str, ...] = ("openid", "email", *GMAIL_SCOPES, *CLASSROOM_SCOPES)

PAGE = """<!doctype html><meta charset="utf-8">
<title>{title}</title>
<body style="font:16px system-ui;background:#0b0f14;color:#e6edf3;padding:48px">
<h2>{title}</h2><p>{body}</p></body>"""


def _post(url: str, fields: dict[str, str]) -> dict[str, object]:
    request = urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode(), method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310 # noqa: S310
        loaded: dict[str, object] = json.loads(response.read().decode())
        return loaded


def sign_in(client_id: str, client_secret: str) -> int:
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            # Both, together. Without `prompt=consent` a second sign-in returns
            # no refresh token at all, and this works once and then stops.
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
    print("\nAsking Google for read-only access to:\n")
    print("  - your Gmail inbox        (read, never send or delete)")
    print("  - your Classroom courses  (read, only your own submissions)\n")
    print(f"Opening your browser. If nothing happens, paste this in:\n\n{url}\n")
    webbrowser.open(url)

    code = ""
    error = ""

    class Catch(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - the name http.server requires
            nonlocal code, error
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code = params.get("code", [""])[0]
            error = params.get("error", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            page = (
                PAGE.format(title="Connected", body="You can close this tab and go back to the studio.")
                if code
                else PAGE.format(title="Not connected", body=f"Google said: {error or 'no code came back'}.")
            )
            self.wfile.write(page.encode())

        def log_message(self, *args: object) -> None:
            return None

    print(f"Waiting on {REDIRECT} ...")
    with http.server.HTTPServer(("127.0.0.1", PORT), Catch) as server:
        server.handle_request()

    if not code:
        print(f"\nNot connected. Google said: {error or 'no authorisation code came back'}.")
        if error == "access_denied":
            print("If your college runs the account, it may block third-party apps entirely.")
        return 1

    answer = _post(
        "https://oauth2.googleapis.com/token",
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT,
            "grant_type": "authorization_code",
        },
    )
    refresh = answer.get("refresh_token")
    if not refresh:
        print("\nGoogle returned no refresh token, which means it thinks you are already connected.")
        print("Revoke it at myaccount.google.com/permissions and run this again.")
        return 1

    granted = str(answer.get("scope", ""))
    TOKEN_FILE.write_text(json.dumps({"refresh_token": refresh, "scopes": granted.split()}, indent=2), encoding="utf-8")
    print(f"\nConnected. Saved to {TOKEN_FILE.name}, which git ignores.\n")
    for label, scopes in (("Gmail", GMAIL_SCOPES), ("Classroom", CLASSROOM_SCOPES)):
        ok = all(s in granted for s in scopes)
        print(f"  {label:<11} {'yes' if ok else 'NOT GRANTED - untick nothing on the consent screen'}")
    return 0


def status() -> int:
    if not TOKEN_FILE.exists():
        print("Not connected. Run: python scripts/google_auth.py")
        return 1
    saved = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    granted = set(saved.get("scopes", []))
    print(f"Connected, token in {TOKEN_FILE.name}\n")
    for label, scopes in (("Gmail", GMAIL_SCOPES), ("Classroom", CLASSROOM_SCOPES)):
        print(f"  {label:<11} {'yes' if set(scopes) <= granted else 'no'}")
    print("\nTake it away any time at myaccount.google.com/permissions")
    return 0


def forget() -> int:
    """Deletes the local token. Does not revoke it at Google's end.

    Said plainly rather than implied: deleting a file stops this machine
    using the grant, and leaves the grant itself standing.
    """
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        print(f"Deleted {TOKEN_FILE.name}.")
    else:
        print("Nothing to delete.")
    print("The grant still exists at Google. Remove it at myaccount.google.com/permissions.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--status", action="store_true", help="what is connected")
    parser.add_argument("--forget", action="store_true", help="delete the local token")
    args = parser.parse_args()

    load_env()
    if args.status:
        return status()
    if args.forget:
        return forget()

    import os

    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        print("Put your Google client ID and secret in the Connect screen first,")
        print("or in .env as GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
        print("\nWhere they come from: see the top of this file.")
        return 1
    return sign_in(client_id, client_secret)


if __name__ == "__main__":
    raise SystemExit(main())
