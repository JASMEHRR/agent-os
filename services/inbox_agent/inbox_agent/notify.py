"""How an alert reaches a phone. A port, and four adapters.

Ordered by how much of your evening they are likely to cost:

* **Telegram** — an official, documented, free API with no account to create
  beyond the one you have, no per-message cost, no rate-limit folklore and no
  relay in the middle that can be down. Setup is: message @BotFather, paste
  the token, press a button. It is the one to reach for, and the only reason
  it is not the only one is that the request here was for WhatsApp.
* **Twilio** — a real API with delivery receipts and support, and the only
  *supported* route to WhatsApp. Needs an account, and outside the 24-hour
  service window Meta requires pre-approved templates, which is a real
  constraint on a bot that texts at unpredictable times.
* **CallMeBot** — one HTTPS GET and no account, which is why it was here
  first. It is one person's free relay: best-effort, no delivery guarantee,
  and it does go down. Kept because when it works it is the shortest setup of
  the three, but it is no longer what the app reaches for.

What is deliberately **not** offered is any of the unofficial WhatsApp Web
automation libraries. They drive a logged-in session of a personal number, they
violate WhatsApp's terms, and the documented penalty is a ban on the number.
That is somebody's actual phone number, which is too much to risk on an inbox
alert.

`Console` exists so the whole agent can be run end-to-end, against a real
mailbox, without sending anything anywhere. It is the sane first run.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

#: Every adapter gives up rather than hanging the run. A notifier that blocks
#: forever turns a five-minute poll into a stuck process.
TIMEOUT_SECONDS = 20

#: WhatsApp renders far more than this, but an alert that does not fit on a
#: lock screen has stopped being an alert.
MAX_CHARS = 900


class NotifyError(Exception):
    """The message did not go out. Carries what the transport said."""


class Notifier(Protocol):
    def send(self, text: str) -> None: ...


def _post(url: str, data: bytes, headers: dict[str, str]) -> str:
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310 # noqa: S310
            return str(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise NotifyError(f"HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise NotifyError(f"could not reach the notifier: {exc}") from exc


@dataclass
class Telegram:
    """A message to yourself, through a bot you own.

    Setup, once, and it really is a couple of minutes:

    1. Message **@BotFather** on Telegram, send `/newbot`, answer two
       questions. It replies with a token like `123456789:AAE...`.
    2. Open your new bot and send it anything at all - "hi" will do. A bot
       cannot start a conversation, so this step is not optional: without it
       Telegram will refuse every message the bot tries to send you.
    3. Paste the token in. `find_chat_id` does the rest.

    No account to create, no number to verify, no third party between the app
    and Telegram, and the API is documented and stable rather than inferred.
    """

    token: str
    chat_id: str
    api: str = "https://api.telegram.org"

    def send(self, text: str) -> None:
        payload = urllib.parse.urlencode({"chat_id": self.chat_id, "text": text[:MAX_CHARS]}).encode()
        body = _post(
            f"{self.api}/bot{self.token}/sendMessage",
            payload,
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            answer = json.loads(body)
        except json.JSONDecodeError:
            # A 200 that is not JSON is not something to treat as delivered.
            raise NotifyError(f"Telegram sent back something unreadable: {body[:200]}") from None
        if not answer.get("ok"):
            raise NotifyError(f"Telegram refused it: {answer.get('description', body[:200])}")


def find_chat_id(token: str, api: str = "https://api.telegram.org") -> str:
    """Your own chat id, read from whatever you last said to the bot.

    Exists so nobody has to open a browser, call `getUpdates` by hand and hunt
    through JSON for an integer - which is what every guide to this tells you
    to do, and is the step where people give up.

    The *most recent* message wins. Somebody who sends "hi" twice because the
    first attempt seemed not to work should get the same answer both times,
    and somebody switching accounts should get the new one rather than a
    stale id from a conversation they have forgotten about.
    """
    url = f"{api}/bot{token}/getUpdates"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:  # nosec B310 # noqa: S310
            answer = json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise NotifyError("Telegram does not recognise that token. Check it with @BotFather.") from exc
        raise NotifyError(f"HTTP {exc.code} from Telegram") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise NotifyError(f"could not reach Telegram: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise NotifyError("Telegram sent back something unreadable.") from exc

    if not answer.get("ok"):
        raise NotifyError(f"Telegram refused the token: {answer.get('description', '')}")

    for update in reversed(answer.get("result", []) or []):
        # `message` for a direct chat; `my_chat_member` arrives when the bot is
        # merely added somewhere, and carries no conversation to reply into.
        chat = (update.get("message") or {}).get("chat") or {}
        if chat.get("id") is not None:
            return str(chat["id"])
    raise NotifyError("Say something to your bot on Telegram first - even just 'hi' - then press this again.")


@dataclass
class CallMeBot:
    """WhatsApp to your own number via the CallMeBot relay.

    Setup, once: follow callmebot.com/blog/free-api-whatsapp-messages, message
    the number *that page* publishes with "I allow callmebot to send me
    messages", and it replies with the API key.

    Deliberately not writing the number down here. It was hardcoded in this
    docstring and in the Connect screen until somebody looked at the contact
    card and asked whether it was really right - a fair question nobody could
    answer from inside this repository. CallMeBot has changed the number
    before, a stale one in help text sends a person to message a stranger, and
    a number nothing here can verify has no business being presented as
    though it were checked.
    """

    phone: str
    apikey: str
    endpoint: str = "https://api.callmebot.com/whatsapp.php"

    def send(self, text: str) -> None:
        query = urllib.parse.urlencode({"phone": self.phone, "text": text[:MAX_CHARS], "apikey": self.apikey})
        url = f"{self.endpoint}?{query}"
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:  # nosec B310 # noqa: S310
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise NotifyError(f"HTTP {exc.code} from CallMeBot") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise NotifyError(f"could not reach CallMeBot: {exc}") from exc
        # CallMeBot answers 200 with an HTML error page on a bad key, so the
        # status code alone does not mean the message was delivered.
        if "error" in body.lower() and "queued" not in body.lower():
            raise NotifyError(f"CallMeBot refused it: {body[:200]}")


@dataclass
class Twilio:
    """WhatsApp via Twilio's Messages API."""

    account_sid: str
    auth_token: str
    from_number: str
    to_number: str

    def send(self, text: str) -> None:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        payload = urllib.parse.urlencode(
            {
                "From": f"whatsapp:{self.from_number}",
                "To": f"whatsapp:{self.to_number}",
                "Body": text[:MAX_CHARS],
            }
        ).encode()
        token = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        body = _post(
            url,
            payload,
            {"Authorization": f"Basic {token}", "Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            answer = json.loads(body)
        except json.JSONDecodeError:
            return
        if answer.get("error_code"):
            raise NotifyError(f"Twilio error {answer['error_code']}: {answer.get('error_message', '')}")


@dataclass
class Console:
    """Prints instead of sending. The right adapter for a first real run."""

    sent: list[str] = field(default_factory=list)

    def send(self, text: str) -> None:
        self.sent.append(text)
        print(f"\n--- would WhatsApp ---\n{text}\n----------------------", flush=True)
