"""Tests for the Gmail adapter.

The watermark is what stops the agent re-alerting mail you have already been
told about, and Gmail makes it harder than IMAP does: its search filters by
whole seconds while its timestamps are milliseconds, so the query is always
slightly too generous and the overlap has to be dropped here.
"""

from __future__ import annotations

import base64
import urllib.error
from datetime import UTC, datetime

import pytest

from inbox_agent.gmail import SCOPES, GmailError, GmailSource

RAW = """From: Placement Cell <placements@college.edu>
To: jasmehr@college.edu
Subject: Shortlisted for interview
Message-ID: <abc@college.edu>
Content-Type: text/plain; charset="utf-8"

Report at 9am.
"""


def encoded(text: str = RAW) -> str:
    """Base64url with the padding stripped, exactly as Google sends it."""
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def gmail(*messages: tuple[str, int]) -> tuple[GmailSource, list[str]]:
    """A source backed by (id, internalDate) pairs. Records the URLs it asked for."""
    asked: list[str] = []
    bodies = {
        mid: {"raw": encoded(RAW.replace("<abc@", f"<{mid}@")), "internalDate": str(stamp)} for mid, stamp in messages
    }

    def fetch(url: str, token: str) -> dict[str, object]:
        asked.append(url)
        if "format=raw" in url:
            return dict(bodies[url.split("/messages/")[1].split("?")[0]])
        return {"messages": [{"id": mid} for mid, _ in messages]}

    source = GmailSource("id", "secret", "refresh", fetch=fetch)
    source.access_token = lambda: "token"  # type: ignore[method-assign]
    return source, asked


NOW_MS = 1_789_000_000_000


def test_the_scope_is_read_only_and_only_mail() -> None:
    """Not gmail.modify, not mail.google.com: it must not be able to send."""
    assert SCOPES == ("https://www.googleapis.com/auth/gmail.readonly",)


def test_a_message_is_parsed_by_the_same_code_as_imap() -> None:
    source, _ = gmail(("m1", NOW_MS))
    found = source.fetch_since("", 10)
    assert len(found) == 1
    assert found[0].sender == "placements@college.edu"
    assert found[0].subject == "Shortlisted for interview"
    assert found[0].addressed_to("jasmehr@college.edu")


def test_googles_receipt_time_wins_over_the_date_header() -> None:
    """A sender's clock can be wrong; internalDate is when Google took it."""
    source, _ = gmail(("m1", NOW_MS))
    assert source.fetch_since("", 10)[0].received_at == datetime.fromtimestamp(NOW_MS / 1000, tz=UTC)


def test_padding_google_strips_is_put_back() -> None:
    """Python's decoder raises on under-padded base64, losing the message."""
    source, _ = gmail(("m1", NOW_MS))
    assert "Report at 9am" in source.fetch_since("", 10)[0].body


def test_a_first_run_asks_for_the_inbox_without_a_date_filter() -> None:
    source, asked = gmail(("m1", NOW_MS))
    source.fetch_since("", 10)
    assert "label%3AINBOX" in asked[0]
    assert "after" not in asked[0]


def test_a_later_run_narrows_by_the_watermark() -> None:
    source, asked = gmail(("m1", NOW_MS))
    source.fetch_since(str(NOW_MS - 60_000), 10)
    assert f"after%3A{(NOW_MS - 60_000) // 1000}" in asked[0]


def test_the_message_at_the_watermark_is_not_re_alerted() -> None:
    """Gmail's second-wide `after:` hands the last one back every time."""
    source, _ = gmail(("m1", NOW_MS))
    assert source.fetch_since(str(NOW_MS), 10) == []


def test_a_message_in_the_same_second_but_later_still_arrives() -> None:
    """Dropping the whole second would lose it forever, not just once."""
    source, _ = gmail(("m1", NOW_MS + 400))
    assert len(source.fetch_since(str(NOW_MS), 10)) == 1


def test_results_come_back_oldest_first() -> None:
    source, _ = gmail(("newer", NOW_MS + 5000), ("older", NOW_MS))
    found = source.fetch_since("", 10)
    assert [e.uid for e in found] == [str(NOW_MS), str(NOW_MS + 5000)]


def test_an_empty_inbox_is_not_an_error() -> None:
    source, _ = gmail()
    assert source.fetch_since("", 10) == []


def test_a_message_with_no_raw_body_is_skipped_rather_than_crashing() -> None:
    def fetch(url: str, token: str) -> dict[str, object]:
        if "format=raw" in url:
            return {"internalDate": str(NOW_MS)}
        return {"messages": [{"id": "m1"}]}

    source = GmailSource("id", "secret", "refresh", fetch=fetch)
    source.access_token = lambda: "token"  # type: ignore[method-assign]
    assert source.fetch_since("", 10) == []


def test_the_uid_is_the_timestamp_so_the_watermark_orders() -> None:
    """Gmail ids are opaque strings; sorting by them would be meaningless."""
    source, _ = gmail(("m1", NOW_MS))
    assert source.fetch_since("", 10)[0].uid == str(NOW_MS)


def test_a_refused_refresh_token_says_how_to_fix_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real path: Google 400s a revoked token, and the message has to say
    what to do about it rather than printing the status code."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise urllib.error.HTTPError("https://oauth2.googleapis.com/token", 400, "Bad Request", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr("inbox_agent.gmail.urllib.request.urlopen", refuse)
    with pytest.raises(GmailError, match="google_auth"):
        GmailSource("id", "secret", "revoked").access_token()


def test_an_unreachable_google_is_reported_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def offline(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr("inbox_agent.gmail.urllib.request.urlopen", offline)
    with pytest.raises(GmailError, match="could not reach"):
        GmailSource("id", "secret", "t").access_token()


def test_a_reply_without_an_access_token_is_an_error_not_an_empty_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Reply:
        def read(self) -> bytes:
            return b'{"scope": "..."}'

        def __enter__(self) -> Reply:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr("inbox_agent.gmail.urllib.request.urlopen", lambda *a, **k: Reply())
    with pytest.raises(GmailError, match="no access token"):
        GmailSource("id", "secret", "t").access_token()
