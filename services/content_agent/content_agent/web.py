"""A local web interface for the content pipeline.

Built on `http.server` so it stays dependency-free like the rest of the repo.
That is a real constraint and it shows: this handles one request at a time and
is not a production server. It does not need to be. It binds to loopback, it
serves one person, and the alternative is a framework dependency for a page
with four buttons.

Design decisions that are actually about safety rather than taste:

* **Loopback only.** `127.0.0.1`, never `0.0.0.0`. There is no authentication
  here, so reachability *is* the authorization. Binding wider would put an
  unauthenticated approve-and-publish surface on the local network.
* **The API has no publish endpoint**, because the studio has no publish verb.
  Approving marks a draft ready and shows you the text. Nothing here reaches
  LinkedIn.
* **Every mutating route is POST.** A GET that approved a draft could be
  triggered by a prefetch or a stray image tag.
"""

from __future__ import annotations

import json
import pathlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from content_agent.capabilities import survey, totals
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
        one user, these two headers close the paths that actually exist.
        """
        host = self.headers.get("Host", "").rsplit(":", 1)[0]
        if host not in ALLOWED_HOSTS:
            return False
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        port = self.server.server_address[1] if isinstance(self.server.server_address, tuple) else 0
        allowed = {f"http://{name}:{port}" for name in ALLOWED_HOSTS}
        return origin in allowed

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        parsed: dict[str, Any] = json.loads(self.rfile.read(length).decode("utf-8"))
        return parsed

    # ---------------------------------------------------------------- Routes

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's naming
        if not self._request_is_ours():
            self._json({"error": "refused"}, 403)
            return
        try:
            if self.path in ("/", "/index.html"):
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/api/state":
                self._json(self._state())
            elif self.path == "/api/capabilities":
                self._json({"capabilities": survey(), "totals": totals()})
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


def serve(studio: ContentStudio, port: int = 8765, forever: bool = True) -> HTTPServer:
    """Starts the interface. Returns the server so tests can drive it."""
    handler: type[Handler] = type("BoundHandler", (Handler,), {"studio": studio})
    server = HTTPServer((HOST, port), handler)
    if forever:
        print(f"\n  Open http://{HOST}:{port} in your browser\n  Ctrl-C to stop\n")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("stopped")
        finally:
            server.server_close()
    return server


__all__ = ["serve", "Handler", "HOST"]
