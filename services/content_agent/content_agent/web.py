"""A local web interface for the content pipeline.

Built on `http.server` so it stays dependency-free like the rest of the repo.
That is a real constraint and it shows: this handles one request at a time and
is not a production server. It does not need to be. It binds to loopback, it
serves one person, and the alternative is a framework dependency for a page
with four buttons.

Design decisions that are actually about safety rather than taste:

* **Loopback by default.** `127.0.0.1`, never `0.0.0.0`. There is no
  authentication in that mode, so reachability *is* the authorization.
  Binding wider is allowed for a hosted copy, and only with a password, which
  `serve` enforces rather than documents: a wider bind without one is refused.
* **The API has no publish endpoint**, because the studio has no publish verb.
  Approving marks a draft ready and shows you the text. Nothing here reaches
  LinkedIn.
* **Every mutating route is POST.** A GET that approved a draft could be
  triggered by a prefetch or a stray image tag.
"""

from __future__ import annotations

import base64
import hmac
import json
import pathlib
import urllib.parse
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from content_agent.capabilities import survey, totals
from content_agent.capture import capture_week
from content_agent.formats import Channel
from content_agent.outreach import OutreachChannel, prospect_from
from content_agent.studio import ContentStudio

PAGE = (pathlib.Path(__file__).parent / "page.html").read_text(encoding="utf-8")

#: Loopback only. See the module docstring: this is the authorization model,
#: not a default someone should widen for convenience.
HOST = "127.0.0.1"

#: Host header values this server will answer to.
#:
#: Loopback binding stops another machine connecting. It does not stop *your*
#: browser being told to connect: a page you visit can point a hostname it
#: controls at 127.0.0.1 and reach this server with its own origin attached.
#: That is DNS rebinding, and the Host header is what distinguishes it, since
#: the rebound request carries the attacker's hostname rather than ours.
ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]"})

#: Addresses a server may bind without a password. Anything else is reachable
#: from another machine, and reachability stops being the authorization.
LOOPBACK_BINDS = frozenset({"127.0.0.1", "localhost", "::1"})

#: Sent with a 401 so the browser asks for the password once and then attaches
#: it to every request the page makes, fetch() included.
AUTH_CHALLENGE = 'Basic realm="Post Studio", charset="UTF-8"'


def _without_port(netloc: str) -> str:
    """`host:port` to `host`. A bracketed IPv6 literal with no port is left alone."""
    if netloc.endswith("]"):
        return netloc
    return netloc.rsplit(":", 1)[0]


def _draft_json(draft: Any) -> dict[str, Any]:
    return {
        "draft_id": draft.draft_id,
        "state": draft.state.value,
        "channel": draft.channel.value,
        "hook": draft.hook,
        "body": draft.body,
        "close": draft.close,
        "hashtags": list(draft.hashtags),
        "full_text": draft.full_text(),
        "redraft_count": draft.redraft_count,
        "outstanding": list(draft.outstanding),
        "created_at": draft.created_at.isoformat(),
    }


def _note_json(note: Any) -> dict[str, Any]:
    return {
        "draft_id": note.draft_id,
        "prospect_id": note.prospect_id,
        "channel": note.channel.value,
        "subject": note.subject,
        "body": note.body,
        "full_text": note.full_text(),
        "approved": note.approved,
        "redraft_count": note.redraft_count,
        "outstanding": list(note.outstanding),
    }


class Handler(BaseHTTPRequestHandler):
    """Routes. Kept in one class because there are six of them."""

    studio: ContentStudio
    principal: str = "jasmehr"
    #: Repositories capture reads, commit messages only. Set by `serve`.
    #: Empty means the button produces nothing, which the page reports.
    repos: tuple[str, ...] = ()
    #: Host header values answered. Loopback names by default; a hosted copy
    #: adds its public hostname. Set by `serve`.
    allowed_hosts: frozenset[str] = ALLOWED_HOSTS
    #: Empty means no password, which `serve` permits on loopback only.
    password: str = ""
    #: Run before each capture, so a hosted copy can refresh its clones and
    #: read this week rather than the week it was deployed in.
    before_capture: Callable[[], None] | None = None

    # Silences the default one-line-per-request logging, which buries the
    # single line that matters (the startup URL) within seconds.
    def log_message(self, format: str, *args: Any) -> None:
        return

    # ------------------------------------------------------------- Plumbing

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # No external anything: the page is self-contained apart from the
        # webfont, and a strict policy here means a compromised dependency
        # cannot exfiltrate drafts.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: Any, status: int = 200) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

    def _request_is_ours(self) -> bool:
        """Rejects a request this page did not make.

        Two checks, closing two different holes:

        * **Host.** Loopback binding stops another machine connecting; it does
          not stop your browser being *told* to connect. A page can point a
          hostname it controls at 127.0.0.1 and reach us. The rebound request
          carries the attacker's hostname in Host, so ours not being there is
          the tell.
        * **Origin.** A cross-site form POST needs no preflight and would
          otherwise be able to approve or discard your drafts. Same-origin
          requests either omit Origin or send ours.

        Not a token scheme. A token would be stronger and would need session
        state and a way to seed it into the page; for a loopback server with
        one user, these two headers close the paths that actually exist. The
        password, when there is one, is a separate check (`_authorised`).

        The Origin is matched on hostname, not on the full string, because a
        hosted copy sits behind a TLS proxy: the browser sees `https://name`
        with no port while this process listens on plain HTTP on whatever
        port it was given, and the two never agree literally.
        """
        host = _without_port(self.headers.get("Host", ""))
        if host not in self.allowed_hosts:
            return False
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        parts = urllib.parse.urlsplit(origin)
        return parts.scheme in ("http", "https") and _without_port(parts.netloc) in self.allowed_hosts

    def _authorised(self) -> bool:
        """The password, when one is set.

        HTTP Basic rather than a login page: the browser asks once, remembers,
        and attaches it to every request the page makes, so the page needs no
        session code. Compared in constant time, so a wrong guess takes as
        long as a near miss.
        """
        if not self.password:
            return True
        scheme, _, encoded = self.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "basic" or not encoded.strip():
            return False
        try:
            decoded = base64.b64decode(encoded.strip(), validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        _, _, supplied = decoded.partition(":")
        return hmac.compare_digest(supplied.encode("utf-8"), self.password.encode("utf-8"))

    def _challenge(self) -> None:
        body = json.dumps({"error": "password required"}).encode("utf-8")
        self.send_response(401)
        self.send_header("WWW-Authenticate", AUTH_CHALLENGE)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        parsed: dict[str, Any] = json.loads(self.rfile.read(length).decode("utf-8"))
        return parsed

    # ---------------------------------------------------------------- Routes

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's naming
        if self.path == "/healthz":
            # For a host's health check. No data and no checks: it says the
            # process is up and nothing else.
            self._json({"ok": True})
            return
        if not self._request_is_ours():
            self._json({"error": "refused"}, 403)
            return
        if not self._authorised():
            self._challenge()
            return
        try:
            if self.path in ("/", "/index.html"):
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/api/state":
                self._json(self._state())
            elif self.path == "/api/capabilities":
                self._json({"capabilities": survey(), "totals": totals()})
            elif self.path == "/api/capture":
                self._capture()
            elif self.path == "/api/voice":
                self._voice()
            else:
                self._json({"error": "not found"}, 404)
        except Exception as exc:  # noqa: BLE001
            # Reads fail too. A stored row the current code cannot decode
            # would otherwise take down the one screen that could tell you
            # what went wrong.
            self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def do_POST(self) -> None:  # noqa: N802
        # Drained before anything else, including on the refusal paths.
        # Replying without reading the body leaves it in the socket, and the
        # client sees a connection abort rather than the status that was sent.
        payload = self._read_json()
        if not self._request_is_ours():
            self._json({"error": "refused"}, 403)
            return
        if not self._authorised():
            self._challenge()
            return
        try:
            if self.path == "/api/note":
                self._note(payload)
            elif self.path == "/api/draft":
                self._draft(payload)
            elif self.path == "/api/approve":
                self._approve(payload)
            elif self.path == "/api/discard":
                self._discard(payload)
            elif self.path == "/api/prospect":
                self._prospect(payload)
            elif self.path == "/api/outreach":
                self._outreach(payload)
            elif self.path == "/api/approve-note":
                self._approve_note(payload)
            elif self.path == "/api/rate":
                self._rate(payload)
            elif self.path == "/api/sample":
                self._sample(payload)
            else:
                self._json({"error": "not found"}, 404)
        except Exception as exc:  # noqa: BLE001
            # Reported to the page rather than swallowed. A silent failure here
            # looks identical to a slow model, and the person waiting cannot
            # tell the difference.
            self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    # ---------------------------------------------------------------- Actions

    def _state(self) -> dict[str, Any]:
        return {
            "waiting": [_draft_json(d) for d in self.studio.awaiting_approval()],
            "attention": [_draft_json(d) for d in self.studio.needs_attention()],
            "health": self.studio.health(),
            "voice": self.studio.library.health(),
            "prospects": [
                {
                    "prospect_id": p.prospect_id,
                    "name": p.name,
                    "headline": p.headline,
                    "reason": p.reason,
                }
                for p in self.studio.prospects()
            ],
            "outreach": [_note_json(n) for n in self.studio.outreach_drafts()],
        }

    def _note(self, payload: dict[str, Any]) -> None:
        body = str(payload.get("body", "")).strip()
        if not body:
            self._json({"error": "Write something first."}, 400)
            return
        note = self.studio.capture(body, str(payload.get("angle", "")))
        if not note.is_substantive():
            # Refused here rather than at draft time, so the person is told
            # before waiting on a model call that was always going to be
            # rejected.
            self._json(
                {
                    "error": "That is too short to write from. Add a few sentences: "
                    "what you actually did, and any real numbers."
                },
                400,
            )
            return
        self._json({"note_id": note.note_id})

    def _draft(self, payload: dict[str, Any]) -> None:
        note = self.studio.note(str(payload.get("note_id", "")))
        requested = payload.get("channels") or [Channel.LINKEDIN.value]

        produced = []
        for name in requested:
            # Each channel is independent work. One that will not converge
            # must not cost the others, so failures come back in the list as
            # rejected drafts rather than aborting the request.
            try:
                produced.append(self.studio.draft(note, Channel(name)))
            except Exception as exc:  # noqa: BLE001
                produced.append(self.studio._blank(note, Channel(name), (f"model failure: {exc}",)))
        self._json({"drafts": [_draft_json(d) for d in produced]})

    def _approve(self, payload: dict[str, Any]) -> None:
        draft_id = str(payload.get("draft_id", ""))
        approved = self.studio.approve(draft_id, self.principal)
        self._json({"draft": _draft_json(approved)})

    def _discard(self, payload: dict[str, Any]) -> None:
        draft_id = str(payload.get("draft_id", ""))
        self._json({"draft": _draft_json(self.studio.discard(draft_id))})

    # ----------------------------------------------------------------- Voice

    def _rate(self, payload: dict[str, Any]) -> None:
        """Your verdict on a draft.

        "Sounds like me", with the text you approved, becomes an example the
        next draft learns from. Edited text is marked, because the diff between
        the draft and your edit is exactly where the model was wrong about you.
        """
        draft_id = str(payload.get("draft_id", ""))
        sounds = bool(payload.get("sounds_like_me", False))
        self.studio.library.rate(draft_id, sounds, str(payload.get("note", "")))
        if sounds:
            draft = self.studio._drafts.get(draft_id)
            final = str(payload.get("text", "")).strip() or draft.full_text()
            try:
                self.studio.library.add_sample(
                    draft.channel, final, from_draft_id=draft_id, edited=final != draft.full_text()
                )
            except ValueError as exc:
                self._json({"error": str(exc)}, 400)
                return
        self._json({"voice": self.studio.library.health()})

    def _sample(self, payload: dict[str, Any]) -> None:
        """Text you supply directly as an example of you: the refined posts."""
        channel = Channel(str(payload.get("channel", "linkedin")))
        try:
            sample = self.studio.library.add_sample(channel, str(payload.get("text", "")), edited=True)
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
            return
        self._json({"sample_id": sample.sample_id, "voice": self.studio.library.health()})

    def _voice(self) -> None:
        self._json(
            {
                "health": self.studio.library.health(),
                "samples": [
                    {"sample_id": s.sample_id, "channel": s.channel.value, "text": s.text, "edited": s.edited}
                    for s in self.studio.library.samples()
                ],
            }
        )

    def _capture(self) -> None:
        """Your week from your commits. Reads git history only, never files."""
        refresh = self.before_capture
        if refresh is not None:
            refresh()
        note, activity = capture_week([pathlib.Path(p) for p in self.repos], days=7)
        self._json(
            {
                "note": note,
                "repos": [{"name": a.name, "commits": len(a.commits), "error": a.error} for a in activity],
            }
        )

    # -------------------------------------------------------------- Outreach

    def _prospect(self, payload: dict[str, Any]) -> None:
        person = prospect_from(
            str(payload.get("name", "")),
            str(payload.get("headline", "")),
            str(payload.get("reason", "")),
            str(payload.get("source", "")),
        )
        if not person.name:
            self._json({"error": "Who is it? A name is the minimum."}, 400)
            return
        if not person.is_specific():
            # Refused before a model call, same as a thin weekly note. A vague
            # reason produces "I see you work in AI", which is exactly the note
            # this module exists to not send.
            self._json(
                {
                    "error": "The reason is too vague. Name the specific thing: a talk they "
                    "gave, a project they shipped, a post they wrote."
                },
                400,
            )
            return
        self.studio.add_prospect(person)
        self._json({"prospect_id": person.prospect_id})

    def _outreach(self, payload: dict[str, Any]) -> None:
        person = self.studio._prospects.get(str(payload.get("prospect_id", "")))
        channel = OutreachChannel(str(payload.get("channel", "linkedin_note")))
        self._json({"note": _note_json(self.studio.draft_note(person, channel))})

    def _approve_note(self, payload: dict[str, Any]) -> None:
        draft_id = str(payload.get("draft_id", ""))
        self._json({"note": _note_json(self.studio.approve_note(draft_id, self.principal))})


def serve(
    studio: ContentStudio,
    port: int = 8765,
    forever: bool = True,
    repos: tuple[str, ...] = (),
    host: str = HOST,
    allowed_hosts: frozenset[str] = ALLOWED_HOSTS,
    password: str | None = None,
    before_capture: Callable[[], None] | None = None,
) -> HTTPServer:
    """Starts the interface. Returns the server so tests can drive it.

    Binding anywhere but loopback needs a password. Without one the only
    thing keeping strangers out is that they cannot reach the socket, and a
    wider bind is precisely what lets them.
    """
    if host not in LOOPBACK_BINDS and not password:
        raise ValueError(f"refusing to listen on {host} without a password: set POST_STUDIO_PASSWORD")
    attrs: dict[str, object] = {
        "studio": studio,
        "repos": repos,
        "allowed_hosts": frozenset(allowed_hosts),
        "password": password or "",
        # Wrapped so the class does not turn it into a method of the handler.
        "before_capture": None if before_capture is None else staticmethod(before_capture),
    }
    handler: type[Handler] = type("BoundHandler", (Handler,), attrs)
    server = HTTPServer((host, port), handler)
    if forever:
        print(f"\n  Open http://{host}:{port} in your browser\n  Ctrl-C to stop\n")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("stopped")
        finally:
            server.server_close()
    return server


__all__ = ["serve", "Handler", "HOST", "ALLOWED_HOSTS", "LOOPBACK_BINDS"]
