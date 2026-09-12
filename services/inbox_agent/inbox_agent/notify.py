"""How an alert reaches a phone. A port, and three adapters.

Two real WhatsApp routes are offered because they fail in different ways and
cost different amounts of setup:

* **CallMeBot** — one HTTPS GET, a five-minute setup, no account. Right for
  texting yourself. It is a free third-party relay, so it is best-effort: no
  delivery guarantee and a fair-use rate limit.
* **Twilio** — a real API with delivery receipts and support. Needs an account,
  and outside the 24-hour service window Meta requires pre-approved templates,
  which is a real constraint on a bot that texts at unpredictable times.

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
class CallMeBot:
    """WhatsApp to your own number via the CallMeBot relay.

    Setup, once: message +34 644 94 46 04 on WhatsApp with
    "I allow callmebot to send me messages", and it replies with the API key.
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
