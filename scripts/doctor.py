"""What is connected, what is not, and what to do about it.

    python scripts/doctor.py

Every other answer this program gives about its own setup is a single word in
a corner of a screen - "not connected yet" - which is true and useless. There
are five different reasons a tab can say that, they need five different fixes,
and until now the only way to tell them apart was to read the source.

So this prints the whole chain, in the order it actually runs, and stops being
polite about which link is broken.

It reads the same files the studio reads and calls the same functions the
studio calls. It cannot disagree with the app, because it is the app's own
plumbing asked out loud.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from scripts.env_file import ENV_FILE  # noqa: E402
from scripts.env_file import load as load_env  # noqa: E402

TOKEN_FILE = REPO / ".google.json"

TICK, CROSS, DASH = "  [ok]  ", "  [--]  ", "  [  ]  "


def line(ok: bool, label: str, detail: str = "") -> None:
    print(f"{TICK if ok else CROSS}{label:<34}{detail}")


def main() -> int:  # noqa: C901 - a checklist is a list of checks
    load_env()
    saved = {}
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                name, _, value = stripped.partition("=")
                if value.strip():
                    saved[name.strip()] = value.strip()

    print("\n  POST STUDIO - what is connected\n")

    # ---------------------------------------------------------------- the file
    line(ENV_FILE.exists(), ".env exists", str(ENV_FILE))
    if not ENV_FILE.exists():
        print("\n  Nothing is saved yet. Open the app and use the Connect screen.\n")
        return 1

    # --------------------------------------------------------------- the model
    print()
    has_model = bool(saved.get("GROQ_API_KEY") or saved.get("GEMINI_API_KEY"))
    line(has_model, "A model for writing posts", "" if has_model else "Connect -> The model")

    # -------------------------------------------------------------- the owner
    line(bool(saved.get("OWNER_NAME")), "Your name", saved.get("OWNER_NAME", "posts will not be about anyone"))

    # -------------------------------------------------------------- google
    print("\n  Google (Inbox and Classwork both need all three)\n")
    client = bool(saved.get("GOOGLE_CLIENT_ID") and saved.get("GOOGLE_CLIENT_SECRET"))
    line(client, "1. Client ID and secret saved", "" if client else "Connect -> paste both -> Save everything")

    token, scopes = "", []
    if TOKEN_FILE.exists():
        try:
            blob = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
            token, scopes = str(blob.get("refresh_token", "")), [str(s) for s in blob.get("scopes", [])]
        except (json.JSONDecodeError, OSError) as exc:
            print(f"{CROSS}{'2. Signed in with Google':<34}{TOKEN_FILE.name} is unreadable: {exc}")
    line(bool(token), "2. Signed in with Google", "" if token else "Connect -> Sign in with Google")

    # The third link, and the one that catches people: the file is on disk but
    # this process read its environment at startup and has not looked since.
    live = bool(os.environ.get("GOOGLE_CLIENT_ID"))
    line(live, "3. The running app has read it", "" if live else "restart the studio - it reads .env only at startup")

    if token:
        print()
        for label, mark in (("Gmail", "gmail"), ("Classroom", "classroom")):
            granted = any(mark in s for s in scopes)
            print(
                f"{TICK if granted else CROSS}   {label + ' permission':<31}"
                f"{'' if granted else 'unticked at the consent screen - sign in again'}"
            )

    # ------------------------------------------------------------- what to do
    print("\n  " + "-" * 58 + "\n")
    if client and token and live:
        print("  Everything Google needs is in place.")
        print("  If a tab still says otherwise, the studio is running older")
        print("  code than this: stop it and start it again.\n")
        return 0

    print("  Next step:\n")
    if not client:
        print("    Open the app -> Connect -> paste the Google Client ID and")
        print("    secret -> Save everything.\n")
    elif not token:
        print("    Open the app -> Connect -> Sign in with Google.")
        print("    Register the address the screen shows you first.\n")
    else:
        print("    Stop the studio (Ctrl-C in its window) and run it again:\n")
        print("        python scripts/serve.py\n")
        print("    The credentials are on disk; this copy started before they")
        print("    were saved and reads them only at startup.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
