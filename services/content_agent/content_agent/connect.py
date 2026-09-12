"""Connecting the agents to your accounts, from the app rather than Notepad.

Every agent here needs credentials, and the only way to supply them was to
open `.env` in a text editor and know what to type. That is a worse first
experience than the agents deserve, and it is where people give up.

Three rules this module keeps, and each exists because the alternative is a
real failure rather than an untidy one:

**A value goes in and never comes back out.** The state this serves says
`set` or `not set` and the name of the thing; it never returns a secret it was
given. A settings screen that redisplays a key for convenience turns every
screenshot, screen share and cached page into a disclosure.

**Other lines in `.env` are preserved exactly.** The file is read, the named
keys are replaced in place, and everything else - comments, ordering, keys
this module has never heard of - is written back untouched. Rewriting the file
from a template would silently delete whatever a person had put there.

**A real environment variable still wins.** `env_file.load` refuses to
override one, so writing `.env` from here cannot quietly change what a shell
or a container already exported. Saved values therefore take effect on the
next restart, which the screen says rather than implying otherwise.

On the trade-off: on a laptop the studio binds loopback and anything running
as you can already read `.env`, so writing it from the page lowers no bar. On
a hosted copy every route is behind the password, and a host that gives its
own secret manager is the better place for these; `docs/HOSTING.md` says so.
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field
from typing import Any

#: Characters a value may not contain. `.env` is one key per line, so a
#: newline in a value would silently become a different setting on reload.
FORBIDDEN = re.compile(r"[\r\n]")


@dataclass(frozen=True)
class Setting:
    """One thing you can set, and enough words to know what to put in it."""

    key: str
    label: str
    #: Where the value comes from, in one sentence. Shown under the field.
    help: str = ""
    #: Secret values are never sent back to the page, only their set-ness.
    secret: bool = True
    placeholder: str = ""
    #: Optional fixed choices, rendered as a dropdown rather than a text box.
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Group:
    """A thing you connect, and what it needs to work."""

    group_id: str
    name: str
    what: str
    settings: tuple[Setting, ...]
    #: Which keys must all be present for this to count as connected.
    requires: tuple[str, ...] = ()
    #: Anything else worth saying once the fields are filled in.
    then: str = ""

    def connected(self, present: set[str]) -> bool:
        return bool(self.requires) and all(key in present for key in self.requires)


GROUPS: tuple[Group, ...] = (
    Group(
        "model",
        "The model",
        "Drafts your posts and settles the emails the rules cannot. Free, no card.",
        (Setting("GROQ_API_KEY", "Groq API key", "console.groq.com/keys - starts with gsk_", placeholder="gsk_..."),),
        requires=("GROQ_API_KEY",),
    ),
    Group(
        "mail",
        "College email",
        "Read-only. The Inbox agent watches it and never marks, moves or deletes anything.",
        (
            Setting(
                "EMAIL_PROVIDER",
                "Who runs your college mail",
                "Gmail for most Indian colleges. Pick 'other' to type a server yourself.",
                secret=False,
                choices=("gmail", "outlook", "other"),
            ),
            Setting(
                "IMAP_HOST", "Mail server", "Only if you picked 'other'.", secret=False, placeholder="imap.example.edu"
            ),
            Setting("COLLEGE_EMAIL", "Your college address", "", secret=False, placeholder="you@college.edu"),
            Setting(
                "EMAIL_PASSWORD",
                "App password",
                "Not your normal password. Gmail: turn on 2-step, then myaccount.google.com/apppasswords.",
                placeholder="16 characters, no spaces",
            ),
        ),
        requires=("COLLEGE_EMAIL", "EMAIL_PASSWORD"),
        then="Run it with --dry-run for a day before letting it text you.",
    ),
    Group(
        "whatsapp",
        "WhatsApp",
        "Where every agent's alert lands. One setup serves all of them.",
        (
            Setting("WHATSAPP_TO", "Your number, with country code", "", secret=False, placeholder="+919876543210"),
            Setting(
                "CALLMEBOT_APIKEY",
                "CallMeBot key",
                'Message +34 644 94 46 04 on WhatsApp with "I allow callmebot to send me messages".',
            ),
            Setting("TWILIO_ACCOUNT_SID", "Twilio SID", "Only if you would rather use Twilio than CallMeBot."),
            Setting("TWILIO_AUTH_TOKEN", "Twilio auth token", ""),
        ),
        requires=("WHATSAPP_TO",),
        then="Twilio is used when its keys are set; otherwise CallMeBot. Neither set means alerts print instead.",
    ),
    Group(
        "google",
        "Google Classroom",
        "Read-only, and only your own submissions. It cannot see another student's work.",
        (
            Setting(
                "GOOGLE_CLIENT_ID",
                "Client ID",
                "console.cloud.google.com - OAuth client, type Desktop app.",
                secret=False,
                placeholder="....apps.googleusercontent.com",
            ),
            Setting("GOOGLE_CLIENT_SECRET", "Client secret", ""),
        ),
        requires=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
        then="Then run once in a terminal: python scripts/classroom_watch.py --auth",
    ),
    Group(
        "you",
        "About you",
        "What the Apply agent matches listings against. No account needed.",
        (
            Setting(
                "GRAD_YEAR",
                "Graduating in",
                "Listings say 'the 2028 batch'. This is that number.",
                secret=False,
                placeholder="2028",
            ),
            Setting("BRANCH", "Your branch", "", secret=False, placeholder="computer science"),
            Setting(
                "INTERESTS",
                "Worth telling you about",
                "Comma separated.",
                secret=False,
                placeholder="python, ai, web, design",
            ),
            Setting("AVOID", "Never tell you about", "Comma separated.", secret=False, placeholder="unpaid, mlm"),
        ),
        requires=("GRAD_YEAR",),
    ),
    Group(
        "numbers",
        "Post numbers",
        "Optional. Reads how your LinkedIn posts did, and how other people's compare.",
        (Setting("APIFY_TOKEN", "Apify token", "console.apify.com/account/integrations"),),
        requires=("APIFY_TOKEN",),
    ),
)

BY_KEY = {setting.key: setting for group in GROUPS for setting in group.settings}


def read(path: pathlib.Path) -> dict[str, str]:
    """The keys `.env` currently sets. Values included; callers must not leak them."""
    if not path.exists():
        return {}
    found: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        cleaned = value.strip().strip('"').strip("'")
        if name.strip() and cleaned:
            found[name.strip()] = cleaned
    return found


def write(path: pathlib.Path, changes: dict[str, str]) -> list[str]:
    """Updates the named keys in place, preserving everything else.

    A key already present is replaced on its own line, so its surrounding
    comments stay with it. A key that is new is appended under a heading. An
    empty value removes the line, which is how a setting gets unset without
    editing the file by hand.
    """
    for key, value in changes.items():
        if key not in BY_KEY:
            raise ValueError(f"'{key}' is not a setting this screen knows about")
        if FORBIDDEN.search(value):
            raise ValueError(f"'{BY_KEY[key].label}' cannot contain a line break")

    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    out: list[str] = []

    for raw in lines:
        stripped = raw.strip()
        name = stripped.partition("=")[0].strip() if "=" in stripped and not stripped.startswith("#") else ""
        if name and name in changes:
            seen.add(name)
            if changes[name]:
                out.append(f"{name}={changes[name]}")
            # An empty new value drops the line entirely rather than leaving
            # `KEY=`, which reads as "set to nothing" rather than "not set".
            continue
        out.append(raw)

    fresh = [k for k in changes if k not in seen and changes[k]]
    if fresh:
        if out and out[-1].strip():
            out.append("")
        out.append("# Added from the Connect screen.")
        out.extend(f"{k}={changes[k]}" for k in fresh)

    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    return sorted(changes)


@dataclass
class ConnectPanel:
    """What the Connect screen shows, and the one thing it can change."""

    env_path: pathlib.Path
    #: True once something has been saved, so the screen can say that a
    #: restart is what makes it take effect rather than implying it is live.
    saved: list[str] = field(default_factory=list)

    def state(self) -> dict[str, Any]:
        present = set(read(self.env_path))
        return {
            "path": str(self.env_path),
            "exists": self.env_path.exists(),
            "saved": self.saved,
            "groups": [
                {
                    "id": group.group_id,
                    "name": group.name,
                    "what": group.what,
                    "then": group.then,
                    "connected": group.connected(present),
                    "settings": [
                        {
                            "key": s.key,
                            "label": s.label,
                            "help": s.help,
                            "secret": s.secret,
                            "placeholder": s.placeholder,
                            "choices": list(s.choices),
                            # Set-ness only for secrets. The value itself is
                            # never sent back to the page.
                            "set": s.key in present,
                            "value": "" if s.secret else read(self.env_path).get(s.key, ""),
                        }
                        for s in group.settings
                    ],
                }
                for group in GROUPS
            ],
        }

    def save(self, changes: dict[str, str]) -> dict[str, Any]:
        self.saved = write(self.env_path, {k: str(v).strip() for k, v in changes.items()})
        return self.state()
