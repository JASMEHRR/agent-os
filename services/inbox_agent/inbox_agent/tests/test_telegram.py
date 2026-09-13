"""The Telegram route, and the step everybody trips on.

Nothing here reaches Telegram. What is checked is the handful of replies that
are a 200 and still a failure - which is most of how this API says no.
"""

from __future__ import annotations

import io
import json
import urllib.error
from typing import Any

import pytest

from inbox_agent.notify import NotifyError, Telegram, find_chat_id


def reply(payload: dict[str, Any]) -> Any:
    """Stands in for `urlopen`, returning what Telegram would."""

    class Response(io.BytesIO):
        def __enter__(self) -> Any:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    return lambda *a, **k: Response(json.dumps(payload).encode())


def refusal(code: int) -> Any:
    def boom(*a: object, **k: object) -> None:
        raise urllib.error.HTTPError("u", code, "no", {}, io.BytesIO(b"{}"))  # type: ignore[arg-type]

    return boom


# ------------------------------------------------------------------ sending


def test_a_message_goes_out(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    class Response(io.BytesIO):
        def __enter__(self) -> Any:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def urlopen(request: Any, timeout: int = 0) -> Any:
        seen["url"] = request.full_url
        seen["body"] = request.data.decode()
        return Response(b'{"ok": true}')

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    Telegram(token="123:ABC", chat_id="42").send("Placement drive closes at 5pm")

    assert "/bot123:ABC/sendMessage" in seen["url"]
    assert "chat_id=42" in seen["body"]
    assert "Placement" in seen["body"]


def test_a_refusal_is_raised_even_though_it_arrives_as_a_200(monkeypatch: pytest.MonkeyPatch) -> None:
    """Telegram says no with `{"ok": false}` and a 200. Trusting the status
    code alone would report every one of those as delivered."""
    monkeypatch.setattr(
        "urllib.request.urlopen",
        reply({"ok": False, "description": "Forbidden: bot was blocked by the user"}),
    )
    with pytest.raises(NotifyError, match="blocked by the user"):
        Telegram(token="123:ABC", chat_id="42").send("hello")


# ------------------------------------------------------------- finding you


def test_the_chat_id_is_read_from_your_last_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        reply({"ok": True, "result": [{"message": {"chat": {"id": 111}}}, {"message": {"chat": {"id": 222}}}]}),
    )
    assert find_chat_id("123:ABC") == "222", "an older conversation won over the latest one"


def test_never_having_messaged_the_bot_says_exactly_that(monkeypatch: pytest.MonkeyPatch) -> None:
    """The step people miss. A bot cannot open a conversation, so an empty
    result means "say hi first" rather than anything being broken."""
    monkeypatch.setattr("urllib.request.urlopen", reply({"ok": True, "result": []}))
    with pytest.raises(NotifyError, match="Say something to your bot"):
        find_chat_id("123:ABC")


def test_an_update_that_carries_no_conversation_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """`my_chat_member` arrives when the bot is added somewhere and has no
    chat to reply into. Taking its id would save something unusable."""
    monkeypatch.setattr(
        "urllib.request.urlopen",
        reply({"ok": True, "result": [{"message": {"chat": {"id": 111}}}, {"my_chat_member": {"chat": {"id": 999}}}]}),
    )
    assert find_chat_id("123:ABC") == "111"


def test_a_wrong_token_is_named_as_a_wrong_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Telegram answers 404 for a token it does not know, which reads as
    "page not found" and means "that is not your token"."""
    monkeypatch.setattr("urllib.request.urlopen", refusal(404))
    with pytest.raises(NotifyError, match="does not recognise that token"):
        find_chat_id("nonsense")


def test_telegram_satisfies_the_notifier_port() -> None:
    from inbox_agent.notify import Notifier

    notifier: Notifier = Telegram(token="1:a", chat_id="2")
    assert callable(notifier.send)
