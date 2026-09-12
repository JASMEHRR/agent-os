"""Where mail comes from. A port, and one IMAP adapter.

IMAP rather than a provider SDK because a college mailbox is Gmail at one
institution and Microsoft 365 at the next, and IMAP is the one protocol both
speak. Changing provider is then a hostname in `.env` rather than a rewrite.

**Read-only, always.** The mailbox is opened with `readonly=True`, so the agent
cannot mark, move or delete anything. An alerting agent has no business
mutating the inbox it watches, and the flag makes that a property of the
connection rather than a promise in a docstring. It also means the mailbox
still looks untouched in the mail client, which is what you want when the thing
reading your mail is a program you wrote last week.

Which messages are new is tracked by this agent, not by the unread flag, for
the same reason: reading your mail on your phone must not make the agent go
quiet.
"""

from __future__ import annotations

import email as email_lib
import email.utils
import imaplib
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from email.header import decode_header, make_header
from email.message import Message
from typing import Protocol

from inbox_agent.messages import Email

#: How much of a body is ever kept. A privacy boundary: enough for a model to
#: tell a shortlist from a seminar invitation, far short of the whole message.
BODY_CHARS = 600

#: Hosts for the two providers a college is realistically on.
KNOWN_HOSTS = {
    "gmail": "imap.gmail.com",
    "outlook": "outlook.office365.com",
}


class MailSource(Protocol):
    """Returns messages newer than the last one seen, oldest first."""

    def fetch_since(self, last_uid: str, limit: int) -> list[Email]: ...


def _decoded(value: str | None) -> str:
    """RFC 2047 header text as readable characters.

    Subjects arrive as `=?UTF-8?B?...?=` often enough that skipping this makes
    every keyword rule useless on exactly the mail that matters.
    """
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except (UnicodeDecodeError, LookupError, ValueError):
        # A header that will not decode is still worth its raw form: the
        # keyword rules can often read it anyway.
        return value.strip()


def _addresses(message: Message, header: str) -> tuple[str, ...]:
    raw = message.get_all(header, [])
    return tuple(addr for _, addr in email.utils.getaddresses([str(r) for r in raw]) if addr)


def _plain_body(message: Message) -> str:
    """The text/plain part, falling back to HTML with the tags stripped."""
    html_fallback = ""
    for part in message.walk() if message.is_multipart() else [message]:
        if part.get_content_maintype() != "text":
            continue
        if part.get_content_disposition() == "attachment":
            continue
        try:
            payload = part.get_payload(decode=True)
        except (AssertionError, ValueError):
            continue
        if not isinstance(payload, bytes):
            continue
        charset = part.get_content_charset() or "utf-8"
        try:
            text = payload.decode(charset, errors="replace")
        except LookupError:
            text = payload.decode("utf-8", errors="replace")
        if part.get_content_subtype() == "plain":
            return _collapse(text)
        if not html_fallback:
            html_fallback = text
    return _collapse(re.sub(r"<[^>]+>", " ", html_fallback)) if html_fallback else ""


def _collapse(text: str) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()


def to_email(raw: bytes, uid: str) -> Email:
    """Parses one fetched message. Total: every field has a usable default.

    A mailbox will eventually hand you something malformed, and a triage agent
    that raises on it stops watching the inbox. Everything here degrades to a
    value the rules can still score.
    """
    message = email_lib.message_from_bytes(raw)
    sender_name, sender_addr = email.utils.parseaddr(str(message.get("From", "")))

    received = datetime.now(UTC)
    date_header = message.get("Date")
    if date_header:
        try:
            parsed = email.utils.parsedate_to_datetime(str(date_header))
            received = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            pass

    return Email(
        message_id=str(message.get("Message-ID", "")).strip() or f"uid:{uid}",
        sender=sender_addr.lower(),
        sender_name=_decoded(sender_name),
        subject=_decoded(str(message.get("Subject", ""))),
        body=_plain_body(message)[:BODY_CHARS],
        received_at=received,
        to=_addresses(message, "To"),
        cc=_addresses(message, "Cc"),
        is_bulk=bool(message.get("List-Id") or message.get("List-Unsubscribe") or message.get("Precedence")),
        in_reply_to=str(message.get("In-Reply-To", "")).strip(),
        uid=uid,
    )


@dataclass
class ImapSource:
    """Reads a mailbox over IMAP. Read-only by construction."""

    host: str
    username: str
    password: str
    mailbox: str = "INBOX"
    port: int = 993

    @contextmanager
    def _mailbox(self) -> Iterator[imaplib.IMAP4_SSL]:
        client = imaplib.IMAP4_SSL(self.host, self.port)
        try:
            client.login(self.username, self.password)
            client.select(self.mailbox, readonly=True)
            yield client
        finally:
            try:
                client.logout()
            except (imaplib.IMAP4.error, OSError):
                # The run is already over; a failed logout must not mask
                # whatever the caller was actually doing.
                pass

    def fetch_since(self, last_uid: str, limit: int = 25) -> list[Email]:
        """Messages with a UID above `last_uid`, oldest first.

        UID rather than unread state, so reading mail on a phone does not make
        the agent skip it. `limit` bounds a first run against a mailbox with
        ten thousand messages in it.
        """
        start = (int(last_uid) + 1) if last_uid.isdigit() else 1
        with self._mailbox() as client:
            status, data = client.uid("SEARCH", None, f"UID {start}:*")
            if status != "OK" or not data or not data[0]:
                return []
            # The `UID n:*` form always returns at least the newest message
            # even when none is above n, so anything at or below the mark is
            # dropped rather than re-alerted.
            uids = [u.decode() for u in data[0].split()]
            fresh = [u for u in uids if u.isdigit() and int(u) >= start][-limit:]

            found: list[Email] = []
            for uid in fresh:
                status, payload = client.uid("FETCH", uid, "(RFC822)")
                if status != "OK" or not payload:
                    continue
                for part in payload:
                    if isinstance(part, tuple) and isinstance(part[1], bytes):
                        found.append(to_email(part[1], uid))
                        break
        return found
