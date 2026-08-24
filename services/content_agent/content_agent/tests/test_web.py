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

    status, drafted = call(server, "/api/draft", {"note_id": note["note_id"]})
    assert status == 200
    assert drafted["draft"]["state"] == "drafted"

    status, state = call(server, "/api/state")
    assert len(state["waiting"]) == 1

    status, approved = call(server, "/api/approve", {"draft_id": drafted["draft"]["draft_id"]})
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

    call(server, "/api/discard", {"draft_id": drafted["draft"]["draft_id"]})

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


def test_the_error_body_is_json_so_the_page_can_show_it(server) -> None:
    """A silent failure looks identical to a slow model to the person waiting."""
    status, body = call(server, "/api/draft", {"note_id": "missing"})

    assert status == 500
    assert isinstance(body.get("error"), str) and body["error"]
