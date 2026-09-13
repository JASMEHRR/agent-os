"""Sign in with Google, from the button rather than from a terminal.

Connecting Google used to mean pasting a client id into the app, then leaving
the app, opening a terminal, and running a script. That is two tools and a
context switch for something every other product does with one button, and it
had a defect that made it impossible rather than merely awkward: the script
stood up its own callback server on port 8765, which is the port the studio
itself is already listening on. So the sign-in worked only while the studio
was closed - and the studio is where you had just typed the client id.

The studio is already an HTTP server on the exact address Google needs to
redirect to. So it catches its own callback, and no second server exists to
collide with the first.

Three things worth knowing before changing this:

**The `state` parameter is doing real work.** An OAuth callback has to be a
GET, which is the one exception to this codebase's rule that nothing mutating
happens on a GET. What keeps that safe is that the callback is refused unless
it carries the exact random token this module minted when the button was
pressed, and each token is accepted once. A link a stranger sends you cannot
complete a sign-in.

**The credentials are read from `.env`, not from the environment.** Everywhere
else in the app a saved setting waits for a restart, deliberately. Here that
would mean save, restart, then press the button - which is the terminal step
back again wearing a hat. Reading the file directly is what makes the button a
button.

**One consent covers both agents.** Google issues one refresh token per
consent, so asking twice would have the second silently overwrite the first
and leave whichever agent signed in first broken. The scopes are passed in
together, by whoever composes the agents; this module never imports them, so
the web layer stays ignorant of what an inbox or a classroom is.
"""

from __future__ import annotations

import json
import pathlib
import secrets
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from content_agent.connect import read

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # nosec B105 - an endpoint, not a secret
TIMEOUT_SECONDS = 30

#: The two settings the Connect screen collects before this can run at all.
CLIENT_ID = "GOOGLE_CLIENT_ID"
CLIENT_SECRET = "GOOGLE_CLIENT_SECRET"  # nosec B105 - the name of a field, not a value


class SignInError(Exception):
    """Sign-in could not be completed, with a sentence a person can act on."""


def _exchange(payload: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(TOKEN_URL, data=urllib.parse.urlencode(payload).encode(), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310 # noqa: S310
            loaded: dict[str, Any] = json.loads(response.read().decode())
            return loaded
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        # Google's own words, because "invalid_client" and "redirect_uri_mismatch"
        # need completely different fixes and only Google knows which it is.
        raise SignInError(f"Google refused the exchange: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SignInError(f"could not reach Google: {exc}") from exc


@dataclass
class GoogleSignIn:
    """The Connect screen's Sign in with Google button, end to end."""

    env_path: pathlib.Path
    token_path: pathlib.Path
    #: Every scope both agents need, as one set. Injected rather than imported:
    #: `content_agent` has no business knowing that Gmail or Classroom exist.
    scopes: tuple[str, ...]
    #: Where Google sends the browser back to. The studio's own address, which
    #: is what removes the second server and the port clash with it.
    redirect_uri: str
    exchange: Callable[[dict[str, str]], dict[str, Any]] = field(default=_exchange, repr=False)
    mint: Callable[[], str] = field(default=lambda: secrets.token_urlsafe(24), repr=False)

    #: Tokens minted by `begin` and not yet spent. A set rather than a single
    #: value because pressing the button twice should not make the first tab
    #: fail; whichever finishes is the one that counts.
    _pending: set[str] = field(default_factory=set, init=False, repr=False)

    # ------------------------------------------------------------------ state

    def credentials(self) -> tuple[str, str]:
        """The client id and secret as saved, or `("", "")` if they are not."""
        saved = read(self.env_path)
        return saved.get(CLIENT_ID, ""), saved.get(CLIENT_SECRET, "")

    def configured(self) -> bool:
        return all(self.credentials())

    def granted(self) -> tuple[str, ...]:
        """The scopes the saved token actually carries, or `()` if there is none."""
        if not self.token_path.exists():
            return ()
        try:
            saved = json.loads(self.token_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # A token file that cannot be read is a token that cannot be used,
            # and saying "not connected" is both true and actionable.
            return ()
        if not saved.get("refresh_token"):
            return ()
        return tuple(str(s) for s in saved.get("scopes", []))

    def state(self) -> dict[str, Any]:
        granted = self.granted()
        return {
            "configured": self.configured(),
            "connected": bool(granted),
            "granted": list(granted),
            # What the button should say, so the page does not re-derive the
            # rule and get a different answer from this one.
            "can_start": self.configured(),
            # Shown on the screen, to be copied into Google's console.
            #
            # `redirect_uri_mismatch` is the single most common way an OAuth
            # setup fails, and it fails at the consent screen rather than
            # here, so the app never sees it and cannot explain it. Google
            # matches this string character for character - scheme, host,
            # port and path - and a person reconstructing it by hand from
            # prose gets `localhost` for `127.0.0.1`, or the wrong port, or
            # a trailing slash. Printing the exact bytes that will be sent
            # removes the guess.
            "redirect_uri": self.redirect_uri,
        }

    # --------------------------------------------------------------- the flow

    def begin(self) -> str:
        """The URL to open. Mints the one-time token the callback must carry."""
        client_id, _ = self.credentials()
        if not client_id:
            raise SignInError("Paste your Google Client ID and secret above and press Save, then try this again.")
        token = self.mint()
        self._pending.add(token)
        query = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.scopes),
                # Both, together. Without `access_type=offline` there is no
                # refresh token at all; without `prompt=consent` a second
                # sign-in returns none either, so this would work exactly once.
                "access_type": "offline",
                "prompt": "consent",
                "state": token,
            }
        )
        return f"{AUTH_URL}?{query}"

    def complete(self, code: str, state: str) -> dict[str, Any]:
        """Trades the code for a refresh token and saves it.

        The state check is what makes it safe for this to happen on a GET: a
        callback that does not carry a token this module minted is refused
        before anything is exchanged or written.
        """
        if not state or state not in self._pending:
            raise SignInError("That sign-in did not start here. Press the button in the app and try again.")
        self._pending.discard(state)
        if not code:
            raise SignInError("Google sent no authorisation code back.")

        client_id, client_secret = self.credentials()
        answer = self.exchange(
            {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            }
        )
        refresh = answer.get("refresh_token")
        if not refresh:
            raise SignInError(
                "Google returned no refresh token, which means it thinks you are already connected. "
                "Remove this app at myaccount.google.com/permissions and press the button again."
            )

        granted = str(answer.get("scope", "")).split()
        self.token_path.write_text(
            json.dumps({"refresh_token": str(refresh), "scopes": granted}, indent=2), encoding="utf-8"
        )
        missing = [s for s in self.scopes if s not in granted]
        return {"connected": True, "granted": granted, "missing": missing}

    def forget(self) -> dict[str, Any]:
        """Deletes the local token.

        Says plainly what it does not do: the grant still stands at Google's
        end until it is removed there, and implying otherwise would leave
        somebody believing they had revoked access they had not.
        """
        existed = self.token_path.exists()
        if existed:
            self.token_path.unlink()
        return {"connected": False, "deleted": existed}
