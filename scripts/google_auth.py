"""What Google sign-in this machine holds, and how to let it go.

    python scripts/google_auth.py --status   # what is connected
    python scripts/google_auth.py --forget   # delete the local token

**Signing in happens in the app**, on the Connect screen: fill in the Client
ID and secret, press Save, then press "Sign in with Google".

This script used to do the sign-in too, and it could not work. It stood up its
own callback listener on port 8765 to catch Google's redirect - which is the
port Post Studio itself is listening on. So the two fought for the socket, and
the only way to win was to shut the studio first: the studio being the place
you had just typed the client id. Anyone following the documented order hit a
wall, and the wall looked like "my credentials are wrong".

The studio is already a server at exactly the address Google needs to redirect
to, so it now catches its own callback. One listener, no clash, and one fewer
tool to leave the app for. See `content_agent/google_signin.py`.

Setting the credentials up, once, before any of it:

1. console.cloud.google.com -> new project
2. APIs & Services -> Library -> enable **Gmail API** and **Google Classroom API**
3. OAuth consent screen -> External -> add the address you will sign in as
   under **Test users**
4. Credentials -> Create credentials -> OAuth client ID -> **Web application**,
   with **http://127.0.0.1:8765/oauth/google** as an authorised redirect URI
5. Put the id and secret into the Connect screen, and press the button

Every scope requested is read-only. Nothing here can send, delete or modify
anything in your account, and Google enforces that rather than this code
promising it.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from scripts.env_file import load as load_env  # noqa: E402

TOKEN_FILE = REPO / ".google.json"


def status() -> int:
    if not TOKEN_FILE.exists():
        print("Not connected. Open the app, go to Connect, and press Sign in with Google.")
        return 1
    saved = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    granted = [str(s) for s in saved.get("scopes", [])]
    print(f"Connected, token in {TOKEN_FILE.name}\n")
    # Matched on the substring rather than against the agents' own tuples, so
    # this stays a diagnostic that reads a file rather than a second place
    # that has to be kept in step with what each agent asks for.
    for label, mark in (("Gmail", "gmail"), ("Classroom", "classroom")):
        print(f"  {label:<11} {'yes' if any(mark in s for s in granted) else 'no'}")
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

    print("\nSigning in happens in the app now, not here.\n")
    print("  1. python scripts/serve.py")
    print("  2. Connect -> fill in the Google Client ID and secret -> Save everything")
    print("  3. Press 'Sign in with Google'\n")
    print("Why it moved: this script needed port 8765 to catch Google's reply,")
    print("and that is the studio's port. It only ever worked with the studio shut.\n")
    print("What this can still tell you:  --status   --forget\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
