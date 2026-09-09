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
* **The publish routes cannot reach an unapproved draft.** They used not to
  exist at all. They do now, because approving something and then having to
  paste it yourself is a step too many for a decision already made. What makes
  that safe is not this file: `/api/publish` and `/api/schedule` both go
  through `PostDraft`, which raises for any state a human did not put it in.
  This server can send a post you approved. It has no path to one you did not.
* **Publishing is injected, never imported.** `serve` takes a publisher; with
  none supplied the routes answer that posting is not configured. So the
  service package still has no idea LinkedIn exists, and a studio started
  without credentials cannot post by accident.
* **Every mutating route is POST.** A GET that approved a draft could be
  triggered by a prefetch or a stray image tag.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import pathlib
from collections.abc import Callable
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from content_agent.analytics import MetricsSource
from content_agent.capabilities import survey, totals
from content_agent.capture import capture_week
from content_agent.drafts import NotApproved
from content_agent.formats import Channel
from content_agent.outreach import OutreachChannel, prospect_from
from content_agent.persona import Area
from content_agent.schedule import Publisher
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
        "scheduled_for": draft.scheduled_for.isoformat() if draft.scheduled_for else "",
        "published_at": draft.published_at.isoformat() if draft.published_at else "",
        "published_url": draft.published_url,
        "failure_reason": draft.failure_reason,
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
    #: Empty means "this laptop": loopback only, no login, reachability is the
    #: authorisation. Set means "hosted": every /api route needs the cookie
    #: that a correct password grants. One user, one password, no accounts.
    password: str = ""
    #: Run before each capture, so a hosted copy can refresh its clones and
    #: read this week rather than the week it was deployed in. Set by `serve`.
    before_capture: Callable[[], None] | None = None
    #: How a post actually reaches LinkedIn. None means this copy cannot post
    #: at all, which is what a studio started without credentials should be:
    #: the routes say so rather than failing somewhere less legible.
    publisher: Publisher | None = None
    #: Where engagement numbers are read from. None means the numbers screen
    #: shows what was already collected and refuses to fetch more.
    metrics: MetricsSource | None = None

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
        host_header = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if self.password:
            # Hosted: the host is whatever the platform gave us, so the Host
            # check cannot be a fixed list. The Origin check still holds: a
            # cross-site write must carry a foreign Origin, and ours is the
            # Host we were reached at, over either scheme the proxy may use.
            if origin is None:
                return True
            return origin in {f"https://{host_header}", f"http://{host_header}"}
        host = host_header.rsplit(":", 1)[0]
        if host not in ALLOWED_HOSTS:
            return False
        if origin is None:
            return True
        port = self.server.server_address[1] if isinstance(self.server.server_address, tuple) else 0
        allowed = {f"http://{name}:{port}" for name in ALLOWED_HOSTS}
        return origin in allowed

    # ------------------------------------------------------------------ Auth

    def _token(self) -> str:
        """The cookie value a correct password earns. Derived, not stored, so a
        password change invalidates every existing session."""
        return hashlib.sha256(f"studio:{self.password}".encode()).hexdigest()

    def _authorized(self) -> bool:
        if not self.password:
            return True
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name == "studio" and hmac.compare_digest(value, self._token()):
                return True
        return False

    def _login(self, payload: dict[str, Any]) -> None:
        given = str(payload.get("password", ""))
        if not self.password or not hmac.compare_digest(given, self.password):
            self._json({"error": "Wrong password."}, 401)
            return
        body = json.dumps({"ok": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # HttpOnly so the page's own scripts never see it; SameSite=Strict so
        # no other site can ride it; Secure is added by the host's TLS proxy.
        self.send_header("Set-Cookie", f"studio={self._token()}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000")
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
            # For a host's health checker, which has no cookie and may not
            # send our Host. It is told the process is up, and whether a
            # password is wanted, which is not a secret: the login box is
            # visible to anyone who can reach the page anyway. The page uses
            # it to delete the box outright on a copy that has no password,
            # rather than keeping a dismissed overlay one CSS bug away from
            # covering the screen again.
            self._json({"ok": True, "login_required": bool(self.password)})
            return
        if not self._request_is_ours():
            self._json({"error": "refused"}, 403)
            return
        # The page itself is always served; it contains nothing private and it
        # is where the login form lives. Everything under /api needs the cookie.
        if self.path.startswith("/api/") and not self._authorized():
            self._json({"error": "login required", "login": True}, 401)
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
            elif self.path == "/api/persona":
                self._persona()
            elif self.path == "/api/analytics":
                self._analytics()
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
        if self.path == "/api/login":
            self._login(payload)
            return
        if not self._authorized():
            self._json({"error": "login required", "login": True}, 401)
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
            elif self.path == "/api/checkin":
                self._checkin(payload)
            elif self.path == "/api/confirm-fact":
                self._confirm_fact(payload)
            elif self.path == "/api/retire-fact":
                self._retire_fact(payload)
            elif self.path == "/api/schedule":
                self._schedule(payload)
            elif self.path == "/api/unschedule":
                self._unschedule(payload)
            elif self.path == "/api/mark-posted":
                self._mark_posted(payload)
            elif self.path == "/api/publish":
                self._publish(payload)
            elif self.path == "/api/track":
                self._track(payload)
            elif self.path == "/api/untrack":
                self._untrack(payload)
            elif self.path == "/api/snapshot":
                self._snapshot()
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
            "persona": self.studio.persona.health(),
            "approved": [_draft_json(d) for d in self.studio.scheduler.approved()],
            "queue": [_draft_json(d) for d in self.studio.scheduler.queue()],
            "published": [_draft_json(d) for d in self.studio.scheduler.published()],
            "schedule": self.studio.scheduler.health(),
            "can_post": self.publisher is not None,
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

    # ------------------------------------------------------------- Scheduling

    def _schedule(self, payload: dict[str, Any]) -> None:
        """Queues a draft you already approved for a time you pick.

        The page sends UTC. Parsing is strict and the failure is a sentence:
        a time this misreads is a post that goes out at the wrong hour, or
        never, and neither announces itself.
        """
        draft_id = str(payload.get("draft_id", ""))
        raw = str(payload.get("when", "")).strip()
        if not raw:
            self._json({"error": "Pick a time first."}, 400)
            return
        try:
            when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            self._json({"error": f"Could not read {raw!r} as a date and time."}, 400)
            return
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        try:
            scheduled = self.studio.scheduler.schedule(draft_id, when)
        except NotApproved as exc:
            self._json({"error": str(exc)}, 400)
            return
        self._json({"draft": _draft_json(scheduled)})

    def _unschedule(self, payload: dict[str, Any]) -> None:
        draft_id = str(payload.get("draft_id", ""))
        self._json({"draft": _draft_json(self.studio.scheduler.unschedule(draft_id))})

    def _mark_posted(self, payload: dict[str, Any]) -> None:
        """You posted it yourself; the archive should know.

        The route the manual path needs. Mentions cannot go through the API,
        so anything that needs a tag gets pasted into LinkedIn by hand, and
        this is how that stops being invisible to the tool.
        """
        draft_id = str(payload.get("draft_id", ""))
        try:
            posted = self.studio.scheduler.mark_posted(draft_id, str(payload.get("url", "")))
        except NotApproved as exc:
            self._json({"error": str(exc)}, 400)
            return
        self._json({"draft": _draft_json(posted)})

    def _publish(self, payload: dict[str, Any]) -> None:
        """Sends one approved draft now.

        Approval is checked before anything else, including whether this copy
        can post at all. An unapproved draft has to be refused for being
        unapproved rather than for a missing token, or the boundary starts
        looking like a thing configuration decides.
        """
        draft_id = str(payload.get("draft_id", ""))
        try:
            self.studio.scheduler.publishable(draft_id)
        except NotApproved as exc:
            self._json({"error": str(exc)}, 400)
            return
        if self.publisher is None:
            self._json(
                {
                    "error": "Posting is not set up on this copy. Run "
                    "`python scripts/linkedin_post.py auth` first, then restart the studio."
                },
                400,
            )
            return
        result = self.studio.scheduler.publish_now(draft_id, self.publisher)
        if not result.published:
            self._json({"error": result.error}, 502)
            return
        self._json({"published": True, "url": result.url})

    # -------------------------------------------------------------- Analytics

    def _analytics(self) -> None:
        self._json(
            {
                "health": self.studio.analytics.health(),
                "comparison": self.studio.analytics.compare(),
                "can_read": self.metrics is not None,
            }
        )

    def _track(self, payload: dict[str, Any]) -> None:
        try:
            post = self.studio.analytics.track(
                str(payload.get("url", "")),
                str(payload.get("label", "")),
                bool(payload.get("mine", False)),
            )
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
            return
        self._json({"post_id": post.post_id, "health": self.studio.analytics.health()})

    def _untrack(self, payload: dict[str, Any]) -> None:
        self.studio.analytics.untrack(str(payload.get("post_id", "")))
        self._json({"health": self.studio.analytics.health()})

    def _snapshot(self) -> None:
        """Reads every tracked post's current numbers.

        Slow by nature: one Apify actor run per post, sequentially, on a
        server that handles one request at a time. That is the honest cost of
        the only route to these numbers, and the page says so before you press
        it rather than appearing to hang.
        """
        if self.metrics is None:
            self._json(
                {"error": "No APIFY_TOKEN is set, so there is nothing to read numbers with."},
                400,
            )
            return
        results = self.studio.analytics.snapshot_all(self.metrics)
        self._json(
            {
                "results": [
                    {"label": r.label, "taken": r.taken, "engagement": r.engagement, "error": r.error} for r in results
                ],
                "comparison": self.studio.analytics.compare(),
                "health": self.studio.analytics.health(),
            }
        )

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

    # --------------------------------------------------------------- Persona

    def _checkin(self, payload: dict[str, Any]) -> None:
        """You talk about your week; it proposes what it learned. Nothing is
        kept until you confirm each fact."""
        try:
            checkin_id, proposed = self.studio.check_in(str(payload.get("said", "")))
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
            return
        self._json({"checkin_id": checkin_id, "proposed": proposed})

    def _confirm_fact(self, payload: dict[str, Any]) -> None:
        try:
            fact = self.studio.persona.confirm(
                Area(str(payload.get("area", "life"))),
                str(payload.get("text", "")),
                source_checkin=str(payload.get("checkin_id", "")),
                supersedes=str(payload.get("supersedes", "")),
            )
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
            return
        self._json({"fact_id": fact.fact_id, "persona": self.studio.persona.health()})

    def _retire_fact(self, payload: dict[str, Any]) -> None:
        self.studio.persona.retire(str(payload.get("fact_id", "")))
        self._json({"persona": self.studio.persona.health()})

    def _persona(self) -> None:
        self._json(
            {
                "health": self.studio.persona.health(),
                "facts": [
                    {"fact_id": f.fact_id, "area": f.area.value, "text": f.text} for f in self.studio.persona.facts()
                ],
                "areas": [a.value for a in Area],
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
    password: str = "",  # nosec B107 - empty means "no login, loopback only", not a credential
    before_capture: Callable[[], None] | None = None,
    publisher: Publisher | None = None,
    metrics: MetricsSource | None = None,
) -> HTTPServer:
    """Starts the interface. Returns the server so tests can drive it.

    A password is the switch between the two deployment shapes. Without one
    the server binds loopback and asks nothing, because only this machine can
    reach it. With one it binds every interface, because a host's proxy has to
    reach it, and every /api route demands the cookie a login grants.

    `publisher` and `metrics` are the two outward-facing adapters, both
    optional and both absent by default. A studio started without them drafts
    and reviews exactly as before and says plainly that it cannot post or read
    numbers, which is the right behaviour for a copy with no credentials.
    """
    attrs: dict[str, object] = {
        "studio": studio,
        "repos": repos,
        "password": password,
        # Wrapped so the class does not turn it into a method of the handler.
        "before_capture": None if before_capture is None else staticmethod(before_capture),
        "publisher": None if publisher is None else staticmethod(publisher),
        "metrics": None if metrics is None else staticmethod(metrics),
    }
    handler: type[Handler] = type("BoundHandler", (Handler,), attrs)
    bind = "0.0.0.0" if password else HOST  # nosec B104 - deliberate, gated on a password being set
    server = HTTPServer((bind, port), handler)
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
