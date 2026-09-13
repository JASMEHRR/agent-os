"""The Sign in with Google button.

Nothing here reaches Google. The exchange is injected, so these check the two
things that actually go wrong in an OAuth flow and cannot be checked by using
it once successfully: that a callback nobody started is refused, and that a
reply without a refresh token is reported rather than saved as a success.
"""

from __future__ import annotations

import json
import pathlib
import urllib.parse
from typing import Any

import pytest

from content_agent.google_signin import GoogleSignIn, SignInError

SCOPES = (
    "openid",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
)
REDIRECT = "http://127.0.0.1:8765/oauth/google"


def signin(
    tmp_path: pathlib.Path,
    *,
    credentials: bool = True,
    answer: dict[str, Any] | None = None,
) -> GoogleSignIn:
    env = tmp_path / ".env"
    env.write_text(
        "GROQ_API_KEY=gsk_x\n"
        + ("GOOGLE_CLIENT_ID=abc.apps.googleusercontent.com\nGOOGLE_CLIENT_SECRET=shh\n" if credentials else ""),
        encoding="utf-8",
    )
    reply = answer if answer is not None else {"refresh_token": "1//refresh", "scope": " ".join(SCOPES)}
    return GoogleSignIn(
        env_path=env,
        token_path=tmp_path / ".google.json",
        scopes=SCOPES,
        redirect_uri=REDIRECT,
        exchange=lambda payload: reply,
        mint=lambda: "fixed-state",
    )


# ------------------------------------------------------------------- before


def test_it_knows_when_the_credentials_are_not_there_yet(tmp_path: pathlib.Path) -> None:
    state = signin(tmp_path, credentials=False).state()
    assert state["configured"] is False
    assert state["can_start"] is False


def test_pressing_the_button_too_early_says_what_to_do(tmp_path: pathlib.Path) -> None:
    """The failure a first-time user hits, so it has to be a sentence rather
    than a stack trace."""
    with pytest.raises(SignInError, match="press Save"):
        signin(tmp_path, credentials=False).begin()


def test_the_credentials_are_read_from_the_file_not_the_environment(tmp_path: pathlib.Path) -> None:
    """The whole point of the button. Everywhere else a saved setting waits
    for a restart; here that would be the terminal step back in a hat."""
    assert signin(tmp_path).configured() is True


# --------------------------------------------------------------------- url


def test_the_url_asks_for_both_agents_scopes_in_one_consent(tmp_path: pathlib.Path) -> None:
    """Google issues one refresh token per consent, so a second sign-in would
    overwrite the first and leave whichever agent went first broken."""
    query = urllib.parse.parse_qs(urllib.parse.urlparse(signin(tmp_path).begin()).query)
    assert set(query["scope"][0].split()) == set(SCOPES)


def test_the_url_asks_for_a_refresh_token_and_forces_the_prompt(tmp_path: pathlib.Path) -> None:
    """Either one missing makes this work exactly once and then stop."""
    query = urllib.parse.parse_qs(urllib.parse.urlparse(signin(tmp_path).begin()).query)
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]


def test_the_url_points_the_callback_at_the_studio_itself(tmp_path: pathlib.Path) -> None:
    """The bug this replaced: the old script stood up a second server on the
    port the studio was already using, so the callback never arrived."""
    query = urllib.parse.parse_qs(urllib.parse.urlparse(signin(tmp_path).begin()).query)
    assert query["redirect_uri"] == [REDIRECT]


# ------------------------------------------------------------------ callback


def test_a_callback_nobody_started_is_refused(tmp_path: pathlib.Path) -> None:
    """An OAuth callback is a GET, which is the one thing in this app allowed
    to change state on a GET. The state token is what keeps that safe."""
    flow = signin(tmp_path)
    flow.begin()
    with pytest.raises(SignInError, match="did not start here"):
        flow.complete("code", "some-other-state")
    assert not flow.token_path.exists(), "it wrote a token for a sign-in it did not start"


def test_a_state_token_is_good_once(tmp_path: pathlib.Path) -> None:
    flow = signin(tmp_path)
    state = urllib.parse.parse_qs(urllib.parse.urlparse(flow.begin()).query)["state"][0]
    flow.complete("code", state)
    with pytest.raises(SignInError, match="did not start here"):
        flow.complete("code", state)


def test_a_successful_sign_in_saves_the_refresh_token(tmp_path: pathlib.Path) -> None:
    flow = signin(tmp_path)
    state = urllib.parse.parse_qs(urllib.parse.urlparse(flow.begin()).query)["state"][0]
    result = flow.complete("code", state)

    assert result["connected"] is True and result["missing"] == []
    saved = json.loads(flow.token_path.read_text(encoding="utf-8"))
    assert saved["refresh_token"] == "1//refresh"
    assert set(saved["scopes"]) == set(SCOPES)
    assert flow.state()["connected"] is True


def test_a_reply_with_no_refresh_token_is_an_error_not_a_success(tmp_path: pathlib.Path) -> None:
    """Google does this when it thinks you are already connected. Saving the
    access token instead would look like success and break within the hour."""
    flow = signin(tmp_path, answer={"access_token": "ya29.only"})
    state = urllib.parse.parse_qs(urllib.parse.urlparse(flow.begin()).query)["state"][0]
    with pytest.raises(SignInError, match="myaccount.google.com/permissions"):
        flow.complete("code", state)
    assert not flow.token_path.exists()


def test_a_consent_with_a_box_unticked_reports_what_is_missing(tmp_path: pathlib.Path) -> None:
    """Google lets you refuse one scope and grant the rest, which leaves one
    agent silently unable to work. The screen has to be able to say which."""
    flow = signin(tmp_path, answer={"refresh_token": "1//r", "scope": "openid"})
    state = urllib.parse.parse_qs(urllib.parse.urlparse(flow.begin()).query)["state"][0]
    result = flow.complete("code", state)
    assert "https://www.googleapis.com/auth/gmail.readonly" in result["missing"]


def test_no_code_is_refused_before_anything_is_exchanged(tmp_path: pathlib.Path) -> None:
    flow = signin(tmp_path)
    state = urllib.parse.parse_qs(urllib.parse.urlparse(flow.begin()).query)["state"][0]
    with pytest.raises(SignInError, match="no authorisation code"):
        flow.complete("", state)


# ----------------------------------------------------------------- after


def test_forgetting_deletes_the_token(tmp_path: pathlib.Path) -> None:
    flow = signin(tmp_path)
    state = urllib.parse.parse_qs(urllib.parse.urlparse(flow.begin()).query)["state"][0]
    flow.complete("code", state)
    assert flow.forget() == {"connected": False, "deleted": True}
    assert flow.state()["connected"] is False


def test_forgetting_twice_is_not_an_error(tmp_path: pathlib.Path) -> None:
    assert signin(tmp_path).forget()["deleted"] is False


def test_an_unreadable_token_file_reads_as_not_connected(tmp_path: pathlib.Path) -> None:
    """A token that cannot be parsed is a token that cannot be used, and
    "not connected" is both true and something a person can act on."""
    flow = signin(tmp_path)
    flow.token_path.write_text("{ not json", encoding="utf-8")
    assert flow.state()["connected"] is False


def test_a_token_file_with_no_refresh_token_reads_as_not_connected(tmp_path: pathlib.Path) -> None:
    flow = signin(tmp_path)
    flow.token_path.write_text(json.dumps({"scopes": list(SCOPES)}), encoding="utf-8")
    assert flow.state()["connected"] is False
