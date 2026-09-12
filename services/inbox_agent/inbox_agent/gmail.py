"""Gmail over OAuth, so connecting is a normal Google sign-in.

The IMAP adapter needs an app password: turn on 2-step verification, find a
buried settings page, copy sixteen characters, paste them somewhere. This
needs you to click "Continue" on the Google prompt you have clicked a hundred
times, and it is strictly better in three ways beyond being easier.

**Read-only is enforced by Google, not by this code.** `gmail.readonly` cannot
send, delete, or mark anything, whatever this program later tries. The IMAP
adapter's `readonly=True` is a promise made by the client to itself.

**It is revocable without changing anything.** myaccount.google.com/permissions
takes the access away in one click. An app password has to be found and
deleted, and revoking it may break something else you used it for.

**It survives a password change**, which an app password does not.

Messages are fetched with `format=raw`, which returns the whole original
message. That is deliberate: it decodes to exactly the bytes IMAP would have
delivered, so `sources.to_email` parses it, and every parsing test already
written applies to both adapters. A JSON-shaped Gmail-specific parser would
have been a second thing to keep correct.

One real caveat this cannot fix: some colleges lock their Workspace domain so
third-party OAuth apps cannot be authorised at all. If yours does, the consent
screen will refuse and IMAP with an app password may be the only way in - or
the college may have blocked that too, in which case it is their decision and
no client can route around it.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from inbox_agent.messages import Email
from inbox_agent.sources import to_email

API = "https://gmail.googleapis.com/gmail/v1/users/me"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # nosec B105 - an endpoint, not a secret
TIMEOUT_SECONDS = 30

#: Read-only, and only mail. Not `gmail.modify`, not `mail.google.com`: this
#: agent has no business being able to send or delete, and asking for less is
#: what makes the consent screen honest about what it does.
SCOPES = ("https://www.googleapis.com/auth/gmail.readonly",)

#: Which mailbox to watch. INBOX excludes spam and anything already archived.
LABEL = "INBOX"


class GmailError(Exception):
    """Gmail could not be read."""


def _http(url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310 # noqa: S310
            loaded: dict[str, Any] = json.loads(response.read().decode("utf-8", errors="replace"))
            return loaded
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        if exc.code == 403 and "gmail" in detail.lower():
            raise GmailError(
                "Google refused: the Gmail API is probably not enabled on your Cloud project, "
                "or your college blocks third-party apps."
            ) from exc
        raise GmailError(f"HTTP {exc.code} from Gmail: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GmailError(f"could not reach Gmail: {exc}") from exc


@dataclass
class GmailSource:
    """Reads a Gmail inbox over the REST API. Satisfies `MailSource`."""

    client_id: str
    client_secret: str
    refresh_token: str
    label: str = LABEL
    #: Injected for tests, which then need no network and no token.
    fetch: Any = field(default=_http, repr=False)

    def access_token(self) -> str:
        """Trades the refresh token for an access token good for an hour."""
        payload = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode()
        request = urllib.request.Request(TOKEN_URL, data=payload, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310 # noqa: S310
                answer = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            raise GmailError("Google refused the refresh token. Sign in again: python scripts/google_auth.py") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GmailError(f"could not reach Google: {exc}") from exc
        token = answer.get("access_token")
        if not token:
            raise GmailError(f"no access token in Google's reply: {answer}")
        return str(token)

    def fetch_since(self, last_uid: str, limit: int = 25) -> list[Email]:
        """Messages newer than `last_uid`, oldest first.

        `last_uid` is the `internalDate` of the newest message already seen, in
        epoch milliseconds. Gmail's search takes `after:` in whole seconds, so
        the query is deliberately one second wide of the mark and the overlap
        is dropped below: a message arriving in the same second as the last one
        seen would otherwise be skipped forever.
        """
        token = self.access_token()
        since = int(last_uid) if last_uid.isdigit() else 0

        query = f"label:{self.label}"
        if since:
            query += f" after:{since // 1000}"
        url = f"{API}/messages?maxResults={limit}&q={urllib.parse.quote(query)}"

        listing = self.fetch(url, token)
        ids = [str(m.get("id", "")) for m in listing.get("messages", []) or [] if m.get("id")]
        if not ids:
            return []

        found: list[Email] = []
        for message_id in ids:
            body = self.fetch(f"{API}/messages/{message_id}?format=raw", token)
            raw = body.get("raw")
            stamp = int(body.get("internalDate", 0) or 0)
            if not raw or stamp <= since:
                # At or below the watermark: already seen. Gmail's second-wide
                # `after:` hands these back and they must not be re-alerted.
                continue
            # `+ "=="` because Google strips base64 padding and Python's
            # decoder is strict about it. Over-padding is ignored; under-
            # padding raises, which would lose the message.
            decoded = base64.urlsafe_b64decode(str(raw) + "==")
            # The UID is the internalDate, so the watermark orders correctly
            # even though Gmail ids are opaque strings.
            found.append(_stamped(to_email(decoded, str(stamp)), stamp))

        return sorted(found, key=lambda e: e.received_at)


def _stamped(email: Email, stamp: int) -> Email:
    """Trusts Gmail's own receipt time over the Date: header.

    A sender's clock can be wrong or deliberately false; `internalDate` is when
    Google actually took delivery, which is the thing quiet hours and "newest
    first" should be reasoning about.
    """
    return dataclasses.replace(email, received_at=datetime.fromtimestamp(stamp / 1000, tz=UTC))
