"""The web interface, driven over a real socket.

Started for real rather than by calling handler methods, because the bugs this
layer actually has are routing, status codes and JSON shape, and none of those
show up when the handler is called directly.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

import pytest

from content_agent import ContentStudio
from content_agent.web import HOST, serve
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


@pytest.fixture
def server():
    studio = ContentStudio(
        complete=lambda prompt, max_tokens: CANNED,
        notes=InMemoryRepository(),
        drafts=InMemoryRepository(),
        clock=lambda: datetime(2026, 8, 25, tzinfo=UTC),
    )
    # Port 0 lets the OS choose, so a developer with something on 8765 does not
    # get a confusing failure in an unrelated test run.
    httpd = serve(studio, port=0, forever=False)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://{HOST}:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def call(base: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        f"{base}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
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


def test_the_only_publishing_route_is_the_one_that_was_designed(server) -> None:
    """Publishing arrived; the surface it arrived on did not widen.

    `/api/publish` exists now. The others never did, and a future edit that
    quietly adds a second door should fail here rather than in review.
    """
    for path in ("/api/post", "/api/send", "/api/share"):
        status, _ = call(server, path, {"draft_id": "x"})
        assert status == 404, f"{path} exists and it must not"


def test_an_unapproved_draft_cannot_be_published_over_the_api(server) -> None:
    """The property the old "no publish route at all" test was protecting.

    Checked from the outside, over a socket, because the interesting failure
    is a route reaching past the approval boundary rather than a studio method
    doing so, and only one of those is visible from inside the studio.
    """
    _, note = call(server, "/api/note", {"body": GOOD_NOTE})
    _, drafted = call(server, "/api/draft", {"note_id": note["note_id"]})
    draft_id = drafted["drafts"][0]["draft_id"]

    status, body = call(server, "/api/publish", {"draft_id": draft_id})

    assert status == 400
    assert "approval" in body["error"]

    _, state = call(server, "/api/state")
    assert state["waiting"][0]["draft_id"] == draft_id, "it should still be sitting there unpublished"


def test_an_unapproved_draft_cannot_be_scheduled_over_the_api(server) -> None:
    """Scheduling is the slower path to the same place, so it refuses too."""
    _, note = call(server, "/api/note", {"body": GOOD_NOTE})
    _, drafted = call(server, "/api/draft", {"note_id": note["note_id"]})

    status, body = call(
        server,
        "/api/schedule",
        {"draft_id": drafted["drafts"][0]["draft_id"], "when": "2026-09-10T09:00:00+00:00"},
    )

    assert status == 400
    assert "approval" in body["error"]


def test_a_studio_with_no_publisher_says_so_rather_than_pretending(server) -> None:
    """The fixture wires no publisher, which is a studio without credentials.

    An approved draft is as far as it can get, and the button has to say that
    plainly: one that silently does nothing is worse than one that refuses.
    """
    _, note = call(server, "/api/note", {"body": GOOD_NOTE})
    _, drafted = call(server, "/api/draft", {"note_id": note["note_id"]})
    draft_id = drafted["drafts"][0]["draft_id"]
    call(server, "/api/approve", {"draft_id": draft_id})

    status, body = call(server, "/api/publish", {"draft_id": draft_id})

    assert status == 400
    assert "not set up" in body["error"]

    _, state = call(server, "/api/state")
    assert state["can_post"] is False


def test_an_approved_draft_can_be_scheduled_and_shows_up_in_the_queue(server) -> None:
    _, note = call(server, "/api/note", {"body": GOOD_NOTE})
    _, drafted = call(server, "/api/draft", {"note_id": note["note_id"]})
    draft_id = drafted["drafts"][0]["draft_id"]
    call(server, "/api/approve", {"draft_id": draft_id})

    status, body = call(server, "/api/schedule", {"draft_id": draft_id, "when": "2026-09-10T09:00:00+00:00"})

    assert status == 200
    assert body["draft"]["scheduled_for"].startswith("2026-09-10T09:00")

    _, state = call(server, "/api/state")
    assert [d["draft_id"] for d in state["queue"]] == [draft_id]
    assert state["schedule"]["queued"] == 1


def test_a_time_that_cannot_be_read_is_refused_with_the_value_in_the_message(server) -> None:
    """A misread time is a post that goes out at the wrong hour, or never."""
    _, note = call(server, "/api/note", {"body": GOOD_NOTE})
    _, drafted = call(server, "/api/draft", {"note_id": note["note_id"]})
    draft_id = drafted["drafts"][0]["draft_id"]
    call(server, "/api/approve", {"draft_id": draft_id})

    status, body = call(server, "/api/schedule", {"draft_id": draft_id, "when": "next tuesday"})

    assert status == 400
    assert "next tuesday" in body["error"]


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


# ---------------------------------------------------------------- Hosted


@pytest.fixture
def hosted():
    """The hosted shape: a password set, every /api route gated."""
    studio = ContentStudio(
        complete=lambda prompt, max_tokens: CANNED,
        notes=InMemoryRepository(),
        drafts=InMemoryRepository(),
    )
    httpd = serve(studio, port=0, forever=False, password="correct-horse")
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def test_hosted_api_requires_login_but_the_page_does_not(hosted) -> None:
    """The page carries nothing private and holds the login form, so it is
    served; everything under /api needs the cookie."""
    with urllib.request.urlopen(hosted, timeout=10) as response:  # nosec B310
        assert response.status == 200
    status, body = call(hosted, "/api/state")
    assert status == 401 and body.get("login") is True


def test_hosted_wrong_password_is_refused_and_right_one_grants_a_cookie(hosted) -> None:
    status, _ = call(hosted, "/api/login", {"password": "nope"})
    assert status == 401

    request = urllib.request.Request(
        f"{hosted}/api/login",
        data=json.dumps({"password": "correct-horse"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310
        cookie = response.headers.get("Set-Cookie", "")
    assert cookie.startswith("studio=") and "HttpOnly" in cookie and "SameSite=Strict" in cookie

    token = cookie.split(";")[0]
    authed = urllib.request.Request(f"{hosted}/api/state", headers={"Cookie": token})
    with urllib.request.urlopen(authed, timeout=10) as response:  # nosec B310
        assert response.status == 200


def test_hosted_still_refuses_cross_origin_writes(hosted) -> None:
    """Login does not relax the Origin check; a foreign page with a stolen
    cookie still cannot approve or discard drafts."""
    request = urllib.request.Request(
        f"{hosted}/api/discard",
        data=json.dumps({"draft_id": "x"}).encode(),
        headers={"Content-Type": "application/json", "Origin": "https://evil.example"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10):  # nosec B310
            raise AssertionError("accepted a cross-origin write on the hosted copy")
    except urllib.error.HTTPError as exc:
        assert exc.code == 403


def test_the_health_check_needs_no_login(hosted) -> None:
    """A host's health checker has no cookie. It is told the process is up and
    whether a password is wanted, and nothing else.

    The second fact is not a secret: the login box is visible to anyone who can
    load the page. Everything that *is* private stays behind the cookie, and
    the exact-keys assertion is what stops that drifting.
    """
    status, body = call(hosted, "/healthz")
    assert status == 200
    assert body == {"ok": True, "login_required": True}


def test_the_health_check_says_no_password_is_wanted_on_a_laptop_copy(server) -> None:
    """What the page uses to delete the login box outright.

    A box that exists is a box one styling mistake away from covering the
    screen, which is precisely what happened.
    """
    status, body = call(server, "/healthz")
    assert status == 200
    assert body == {"ok": True, "login_required": False}


def test_capture_runs_the_refresh_first() -> None:
    """A hosted copy pulls its clones before reading them, so the week it
    reports is this one and not the one it was deployed in."""
    calls: list[str] = []
    studio = ContentStudio(
        complete=lambda prompt, max_tokens: CANNED,
        notes=InMemoryRepository(),
        drafts=InMemoryRepository(),
    )
    httpd = serve(studio, port=0, forever=False, before_capture=lambda: calls.append("refreshed"))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = call(f"http://{HOST}:{httpd.server_address[1]}", "/api/capture")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert status == 200
    assert calls == ["refreshed"]
    assert body["repos"] == []
