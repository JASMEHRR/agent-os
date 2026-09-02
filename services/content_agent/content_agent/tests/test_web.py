"""The web interface, driven over a real socket.

Started for real rather than by calling handler methods, because the bugs this
layer actually has are routing, status codes and JSON shape, and none of those
show up when the handler is called directly.
"""

from __future__ import annotations

import base64
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime
from http.server import HTTPServer
from typing import Any

import pytest

from content_agent import ContentStudio
from content_agent.web import ALLOWED_HOSTS, HOST, serve
from persistence import InMemoryRepository

GOOD_NOTE = (
    "This week I wired Groq behind the model router. It took 3 attempts because the free "
    "tier rate limits at 429 rather than billing, so I built a cooldown that degrades to a "
    "smaller model. The suite is at 1803 passing tests."
)

CANNED = json.dumps(
    {
        "hook": "I spent 3 attempts learning that a free tier fails differently than a paid one.",
        "body": "A paid tier bills you. A free tier stops answering.",
        "close": "What small failure taught you most this week?",
        "hashtags": ["#agentarchitecture", "#buildinpublic", "#pythontesting"],
    }
)


def _studio() -> ContentStudio:
    return ContentStudio(
        complete=lambda prompt, max_tokens: CANNED,
        notes=InMemoryRepository(),
        drafts=InMemoryRepository(),
        clock=lambda: datetime(2026, 8, 25, tzinfo=UTC),
    )


def _run(httpd: HTTPServer) -> Iterator[str]:
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://{HOST}:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def server() -> Iterator[str]:
    # Port 0 lets the OS choose, so a developer with something on 8765 does not
    # get a confusing failure in an unrelated test run.
    yield from _run(serve(_studio(), port=0, forever=False))


PASSWORD = "open-sesame-4471"
PUBLIC_NAME = "studio.example"


@pytest.fixture
def guarded() -> Iterator[str]:
    """The hosted shape: a password, and a public hostname it answers to."""
    httpd = serve(
        _studio(),
        port=0,
        forever=False,
        password=PASSWORD,
        allowed_hosts=ALLOWED_HOSTS | {PUBLIC_NAME},
    )
    yield from _run(httpd)


def basic(password: str, user: str = "jasmehr") -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def call(
    base: str,
    path: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    sent = {"Content-Type": "application/json"} if data else {}
    sent.update(headers or {})
    request = urllib.request.Request(
        f"{base}{path}",
        data=data,
        headers=sent,
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ------------------------------------------------------------------ The page


def test_the_page_is_served_and_is_self_contained(server) -> None:
    """One external request only, for the webfont.

    Anything else would mean a draft could reach a third party before it
    reached the person who wrote it.
    """
    with urllib.request.urlopen(server, timeout=10) as response:  # nosec B310
        html = response.read().decode()

    assert "<title>Post Studio</title>" in html
    external = [line for line in html.splitlines() if "https://" in line and "fonts.g" not in line]
    assert not external, f"the page reaches somewhere other than Google Fonts: {external}"


# ------------------------------------------------------------------ The flow


def test_the_whole_flow_works_in_the_order_a_person_would_do_it(server) -> None:
    status, note = call(server, "/api/note", {"body": GOOD_NOTE})
    assert status == 200

    status, drafted = call(server, "/api/draft", {"note_id": note["note_id"], "channels": ["linkedin"]})
    assert status == 200
    assert drafted["drafts"][0]["state"] == "drafted"

    status, state = call(server, "/api/state")
    assert len(state["waiting"]) == 1

    status, approved = call(server, "/api/approve", {"draft_id": drafted["drafts"][0]["draft_id"]})
    assert status == 200
    assert approved["draft"]["state"] == "approved"

    _, after = call(server, "/api/state")
    assert after["waiting"] == [], "an approved draft must leave the waiting list"


def test_a_thin_note_is_refused_before_a_model_call_is_spent(server) -> None:
    """Rejected at capture, not after the round trip.

    The person is told immediately, and a free-tier request that was always
    going to be rejected is not spent.
    """
    status, body = call(server, "/api/note", {"body": "did stuff"})

    assert status == 400
    assert "too short" in body["error"]


def test_an_empty_note_is_refused(server) -> None:
    status, body = call(server, "/api/note", {"body": "   "})
    assert status == 400


def test_discard_removes_a_draft_from_the_waiting_list(server) -> None:
    _, note = call(server, "/api/note", {"body": GOOD_NOTE})
    _, drafted = call(server, "/api/draft", {"note_id": note["note_id"]})

    call(server, "/api/discard", {"draft_id": drafted["drafts"][0]["draft_id"]})

    _, state = call(server, "/api/state")
    assert state["waiting"] == []


# -------------------------------------------------------------------- Safety


def test_there_is_no_publish_route(server) -> None:
    """The studio has no publishing verb, so the server must have no route to
    one. Checked from the outside, because an endpoint added later would not
    fail any test that only inspects the studio."""
    for path in ("/api/publish", "/api/post", "/api/send", "/api/share"):
        status, _ = call(server, path, {"draft_id": "x"})
        assert status == 404, f"{path} exists and it must not"


def test_state_changing_routes_reject_get(server) -> None:
    """A GET that approved something could be fired by a prefetch or an image
    tag on any page the browser happens to load."""
    for path in ("/api/approve", "/api/discard", "/api/note", "/api/draft"):
        status, _ = call(server, path)
        assert status == 404, f"{path} responded to GET"


def test_it_binds_to_loopback_only() -> None:
    """There is no authentication here, so reachability is the authorization.

    Binding wider would put an unauthenticated approval surface on whatever
    network the laptop is joined to, which for a student is usually a
    university one.
    """
    assert HOST == "127.0.0.1"


def test_an_unknown_draft_id_is_an_error_not_a_crash(server) -> None:
    status, body = call(server, "/api/approve", {"draft_id": "nope"})

    assert status == 500
    assert "error" in body


def test_every_channel_can_be_requested_in_one_call(server) -> None:
    """One note, three drafts, one round trip. The canned model only satisfies
    LinkedIn's gates, so the others come back rejected, and that is the point:
    all three were attempted and none went missing."""
    _, note = call(server, "/api/note", {"body": GOOD_NOTE})

    _, result = call(
        server,
        "/api/draft",
        {"note_id": note["note_id"], "channels": ["linkedin", "newsletter", "devto"]},
    )

    assert {d["channel"] for d in result["drafts"]} == {"linkedin", "newsletter", "devto"}


def test_the_error_body_is_json_so_the_page_can_show_it(server) -> None:
    """A silent failure looks identical to a slow model to the person waiting."""
    status, body = call(server, "/api/draft", {"note_id": "missing"})

    assert status == 500
    assert isinstance(body.get("error"), str) and body["error"]


def test_a_request_with_a_foreign_host_header_is_refused(server) -> None:
    """DNS rebinding.

    Loopback binding stops another machine connecting. It does not stop your
    browser being told to connect: a page can point a hostname it controls at
    127.0.0.1 and reach this server carrying its own origin. The rebound
    request arrives with the attacker's hostname in Host, which is the tell.
    """
    port = server.rsplit(":", 1)[1]
    request = urllib.request.Request(
        f"{server}/api/state",
        headers={"Host": f"evil.example:{port}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310
            raise AssertionError(f"served a rebound request: {response.status}")
    except urllib.error.HTTPError as exc:
        assert exc.code == 403


def test_a_cross_origin_post_is_refused(server) -> None:
    """A cross-site form POST needs no preflight, so without this check any
    page you happened to visit could approve or discard your drafts."""
    request = urllib.request.Request(
        f"{server}/api/discard",
        data=json.dumps({"draft_id": "x"}).encode(),
        headers={"Content-Type": "application/json", "Origin": "https://evil.example"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310
            raise AssertionError(f"accepted a cross-origin write: {response.status}")
    except urllib.error.HTTPError as exc:
        assert exc.code == 403


def test_a_same_origin_post_is_accepted(server) -> None:
    """The check has to let the real page through, or it is just an outage."""
    request = urllib.request.Request(
        f"{server}/api/note",
        data=json.dumps({"body": GOOD_NOTE}).encode(),
        headers={"Content-Type": "application/json", "Origin": server},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310
        assert response.status == 200


# ------------------------------------------------------------------- Hosted


def test_binding_beyond_loopback_without_a_password_is_refused() -> None:
    """On loopback, reachability is the authorization. Anywhere else there is
    no such thing, so the server will not start without a password rather
    than start and hope."""
    with pytest.raises(ValueError, match="password"):
        serve(_studio(), port=0, forever=False, host="0.0.0.0")  # nosec B104 - refused before binding


def test_loopback_needs_no_password(server) -> None:
    status, _ = call(server, "/api/state")
    assert status == 200


def test_without_the_password_the_browser_is_asked_for_it(guarded) -> None:
    request = urllib.request.Request(f"{guarded}/api/state")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310
            raise AssertionError(f"served without a password: {response.status}")
    except urllib.error.HTTPError as exc:
        assert exc.code == 401
        assert exc.headers.get("WWW-Authenticate", "").startswith("Basic ")


def test_a_wrong_password_is_refused(guarded) -> None:
    status, _ = call(guarded, "/api/state", headers=basic("open-sesame-4472"))
    assert status == 401


def test_a_malformed_authorization_header_is_refused_not_crashed(guarded) -> None:
    for header in ("Basic", "Basic %%%not-base64%%%", "Bearer abc", "Basic " + base64.b64encode(b"\xff").decode()):
        status, _ = call(guarded, "/api/state", headers={"Authorization": header})
        assert status == 401, header


def test_the_right_password_opens_every_route(guarded) -> None:
    status, note = call(guarded, "/api/note", {"body": GOOD_NOTE}, headers=basic(PASSWORD))
    assert status == 200
    status, _ = call(guarded, "/api/draft", {"note_id": note["note_id"]}, headers=basic(PASSWORD))
    assert status == 200


def test_the_username_does_not_matter_only_the_password(guarded) -> None:
    status, _ = call(guarded, "/api/state", headers=basic(PASSWORD, user="anyone"))
    assert status == 200


def test_a_wrong_password_is_also_refused_on_writes(guarded) -> None:
    status, _ = call(guarded, "/api/note", {"body": GOOD_NOTE}, headers=basic("nope"))
    assert status == 401


def test_the_public_hostname_is_answered_with_or_without_a_port(guarded) -> None:
    """Behind a TLS proxy the browser's Host and Origin carry the public name
    and no port. The loopback names stay allowed alongside it."""
    for host in (PUBLIC_NAME, f"{PUBLIC_NAME}:443"):
        status, _ = call(
            guarded,
            "/api/note",
            {"body": GOOD_NOTE},
            headers={"Host": host, "Origin": f"https://{PUBLIC_NAME}", **basic(PASSWORD)},
        )
        assert status == 200, host
    status, _ = call(guarded, "/api/state", headers=basic(PASSWORD))
    assert status == 200


def test_a_foreign_host_is_still_refused_when_hosted(guarded) -> None:
    status, _ = call(guarded, "/api/state", headers={"Host": "evil.example", **basic(PASSWORD)})
    assert status == 403


def test_an_origin_with_an_unexpected_scheme_is_refused(guarded) -> None:
    status, _ = call(
        guarded,
        "/api/note",
        {"body": GOOD_NOTE},
        headers={"Origin": f"ftp://{PUBLIC_NAME}", **basic(PASSWORD)},
    )
    assert status == 403


def test_the_health_check_needs_neither_password_nor_our_hostname(guarded) -> None:
    """A host's health checker has no password and may not send our Host.
    It is told the process is up, and nothing else."""
    status, body = call(guarded, "/healthz", headers={"Host": "10.0.0.7"})
    assert status == 200
    assert body == {"ok": True}


def test_capture_runs_the_refresh_first() -> None:
    """A hosted copy pulls its clones before reading them, so the week it
    reports is this one and not the one it was deployed in."""
    calls: list[str] = []
    httpd = serve(_studio(), port=0, forever=False, before_capture=lambda: calls.append("refreshed"))
    base = next(_run(httpd))
    try:
        status, body = call(base, "/api/capture")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert status == 200
    assert calls == ["refreshed"]
    assert body["repos"] == []
