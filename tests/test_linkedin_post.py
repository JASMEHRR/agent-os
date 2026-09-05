"""The LinkedIn poster, exercised without touching LinkedIn.

Every network call is replaced, because the failures worth catching here are
the ones in our own logic: which backend gets chosen, what happens when a
token has expired, and whether the bundle's contract is honoured exactly. A
test that needed a real token would run on nobody's machine.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import subprocess  # nosec B404 - runs this repository's own script, fixed argv
import sys
import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from scripts import linkedin_post as lp

REPO = pathlib.Path(__file__).resolve().parents[1]

LIVE = lp.Credentials("token-123", "urn:li:person:abc", (datetime.now(UTC) + timedelta(days=30)).isoformat())
STALE = lp.Credentials("token-123", "urn:li:person:abc", (datetime.now(UTC) - timedelta(days=1)).isoformat())


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """No real credentials leak in from the developer's own shell."""
    for name in (
        "PUBLORA_API_KEY",
        "PUBLORA_PLATFORM_ID",
        "LINKEDIN_PLATFORM_ID",
        "LINKEDIN_API_VERSION",
        "LINKEDIN_ESCAPE",
        "LINKEDIN_SKILLS_CUSTOM_POSTER",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LINKEDIN_TOKEN_PATH", str(tmp_path / "token.json"))


# ------------------------------------------------------------------- Escaping


def test_reserved_characters_are_escaped_so_they_survive_as_themselves() -> None:
    """A bracket left raw can be read as markup and take the line with it."""
    assert lp.escape_commentary("ventureadda (50 commits)") == "ventureadda \\(50 commits\\)"
    assert lp.escape_commentary("api/verify-thapar") == "api/verify-thapar"


def test_escaping_can_be_switched_off_but_should_almost_never_be(monkeypatch: pytest.MonkeyPatch) -> None:
    """An escape hatch for a rule that could change, not a preference.

    LinkedIn's little-text format requires the escaping, so switching it off
    is how you get a post truncated at its first bracket. It exists so a
    future format change is one variable rather than a code release.
    """
    monkeypatch.setenv("LINKEDIN_ESCAPE", "0")
    assert lp.escape_commentary("a (b)") == "a (b)"


def test_escaping_is_not_doubled_on_text_that_has_none() -> None:
    plain = "Firebase ran out of email sends this week."
    assert lp.escape_commentary(plain) == plain


# ---------------------------------------------------------------- Credentials


def test_a_token_with_no_expiry_is_not_treated_as_expired() -> None:
    assert lp.Credentials("t", "u").expired() is False


def test_an_old_token_is_expired_and_a_fresh_one_is_not() -> None:
    assert STALE.expired() is True
    assert LIVE.expired() is False


def test_a_corrupt_expiry_does_not_crash_the_publish_path() -> None:
    """A hand-edited file should degrade to "usable", not to a traceback on
    the one command you were trying to run."""
    assert lp.Credentials("t", "u", "not-a-date").expired() is False
    assert lp.Credentials("t", "u", "not-a-date").days_left() is None


def test_saving_then_loading_returns_the_same_credentials(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "nested" / "token.json"
    lp.save_credentials(LIVE, path)
    assert lp.load_credentials(path) == LIVE


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_the_token_file_is_readable_by_nobody_else(tmp_path: pathlib.Path) -> None:
    """It is a credential that posts as him. World-readable is not acceptable."""
    path = tmp_path / "token.json"
    lp.save_credentials(LIVE, path)
    assert path.stat().st_mode & 0o077 == 0


def test_a_missing_or_junk_token_file_reads_as_no_credentials(tmp_path: pathlib.Path) -> None:
    assert lp.load_credentials(tmp_path / "absent.json") is None
    junk = tmp_path / "junk.json"
    junk.write_text("{not json", encoding="utf-8")
    assert lp.load_credentials(junk) is None
    partial = tmp_path / "partial.json"
    partial.write_text(json.dumps({"access_token": "t"}), encoding="utf-8")
    assert lp.load_credentials(partial) is None, "a token with no author cannot post"


# -------------------------------------------------------------------- Errors


def test_each_status_says_what_to_do_rather_than_what_happened() -> None:
    assert "auth" in lp._explain(401, "")
    assert "product" in lp._explain(403, "")
    assert "LINKEDIN_API_VERSION" in lp._explain(426, "")
    assert "rate limiting" in lp._explain(429, "")


def test_the_version_is_overridable_because_a_pinned_date_ages(monkeypatch: pytest.MonkeyPatch) -> None:
    assert lp.api_version() == lp.DEFAULT_API_VERSION
    monkeypatch.setenv("LINKEDIN_API_VERSION", "202601")
    assert lp.api_version() == "202601"


# ------------------------------------------------------------------ Guardrails


def test_an_empty_post_is_refused_before_a_request_is_made() -> None:
    with pytest.raises(lp.LinkedInError, match="empty"):
        lp.publish_post(LIVE, "   ")


def test_a_post_over_the_limit_is_refused_with_both_numbers() -> None:
    with pytest.raises(lp.LinkedInError, match=f"{lp.MAX_POST_CHARS}"):
        lp.publish_post(LIVE, "x" * (lp.MAX_POST_CHARS + 1))


# ------------------------------------------------------- Backend choice


def test_linkedin_is_used_when_the_token_works(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lp, "load_credentials", lambda path=None: LIVE)
    monkeypatch.setattr(lp, "publish_post", lambda *a, **k: {"backend": "linkedin", "urn": "urn:li:share:1"})

    assert lp.post_text("hello")["backend"] == "linkedin"


def test_publora_takes_over_when_there_is_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """The backup exists for the morning the token quietly expired."""
    monkeypatch.setenv("PUBLORA_API_KEY", "sk_test")
    monkeypatch.setenv("PUBLORA_PLATFORM_ID", "linkedin-1")
    monkeypatch.setattr(lp, "load_credentials", lambda path=None: None)
    monkeypatch.setattr(lp, "publish_via_publora", lambda text: {"backend": "publora"})

    result = lp.post_text("hello")

    assert result["backend"] == "publora"
    assert "no LinkedIn token" in result["fell_back_from"]


def test_an_expired_token_falls_back_rather_than_failing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLORA_API_KEY", "sk_test")
    monkeypatch.setenv("PUBLORA_PLATFORM_ID", "linkedin-1")
    monkeypatch.setattr(lp, "load_credentials", lambda path=None: STALE)
    monkeypatch.setattr(lp, "publish_via_publora", lambda text: {"backend": "publora"})

    assert "expired" in lp.post_text("hello")["fell_back_from"]


def test_a_linkedin_failure_falls_back_when_publora_is_there(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise lp.LinkedInError(503, "LinkedIn is down")

    monkeypatch.setenv("PUBLORA_API_KEY", "sk_test")
    monkeypatch.setenv("PUBLORA_PLATFORM_ID", "linkedin-1")
    monkeypatch.setattr(lp, "load_credentials", lambda path=None: LIVE)
    monkeypatch.setattr(lp, "publish_post", refuse)
    monkeypatch.setattr(lp, "publish_via_publora", lambda text: {"backend": "publora"})

    assert lp.post_text("hello")["backend"] == "publora"


def test_a_linkedin_failure_is_raised_when_there_is_no_backup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swallowing this would look identical to a post that went out."""

    def refuse(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise lp.LinkedInError(503, "LinkedIn is down")

    monkeypatch.setattr(lp, "load_credentials", lambda path=None: LIVE)
    monkeypatch.setattr(lp, "publish_post", refuse)

    with pytest.raises(lp.LinkedInError):
        lp.post_text("hello")


def test_with_nothing_configured_the_error_names_the_next_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lp, "load_credentials", lambda path=None: None)
    with pytest.raises(lp.LinkedInError, match="auth"):
        lp.post_text("hello")


def test_publora_needs_its_own_platform_id_not_the_bundles(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting the bundle's LINKEDIN_PLATFORM_ID makes the bundle route to
    Publora before this poster is ever called, so the backup deliberately
    reads a different name."""
    monkeypatch.setenv("PUBLORA_API_KEY", "sk_test")
    monkeypatch.setenv("LINKEDIN_PLATFORM_ID", "linkedin-1")
    assert lp.publora_configured() is False

    monkeypatch.setenv("PUBLORA_PLATFORM_ID", "linkedin-1")
    assert lp.publora_configured() is True


# --------------------------------------------------- The bundle's contract


def test_a_post_from_the_bundle_is_published(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lp, "post_text", lambda text, **k: {"backend": "linkedin", "text": text})

    result = lp.run_as_poster("post", {"draft_text": "from the bundle", "target_url": "https://x"})

    assert result["text"] == "from the bundle"


def test_a_reply_carries_the_parent_comment_and_a_comment_does_not(monkeypatch: pytest.MonkeyPatch) -> None:
    """LinkedIn flattens threads, and the parent is what puts a reply in the
    right one."""
    seen: dict[str, Any] = {}

    def record(creds: Any, post_urn: str, text: str, parent: str = "") -> dict[str, Any]:
        seen.update({"post_urn": post_urn, "text": text, "parent": parent})
        return {"backend": "linkedin"}

    monkeypatch.setattr(lp, "load_credentials", lambda path=None: LIVE)
    monkeypatch.setattr(lp, "publish_comment", record)

    lp.run_as_poster("reply", {"draft_text": "hi", "post_urn": "urn:li:share:1", "parent_comment": "urn:li:comment:9"})
    assert seen["parent"] == "urn:li:comment:9"

    lp.run_as_poster(
        "comment", {"draft_text": "hi", "post_urn": "urn:li:share:1", "parent_comment": "urn:li:comment:9"}
    )
    assert seen["parent"] == "", "a top-level comment must not inherit a parent"


def test_a_kind_this_cannot_do_is_refused_rather_than_approximated() -> None:
    """A reshare quietly published as a plain post would be worse than an error."""
    with pytest.raises(lp.LinkedInError, match="reshare"):
        lp.run_as_poster("reshare", {"draft_text": "x"})


def test_commenting_without_a_token_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lp, "load_credentials", lambda path=None: None)
    with pytest.raises(lp.LinkedInError, match="auth"):
        lp.run_as_poster("comment", {"draft_text": "x", "post_urn": "urn:li:share:1"})


# ------------------------------------------------------------------ The CLI


def _run(args: list[str], stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 - this repository's own script, fixed argv
        [sys.executable, str(REPO / "scripts" / "linkedin_post.py"), *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(REPO),
    )


def test_dry_run_sends_nothing_and_shows_the_text() -> None:
    done = _run(["post", "--text", "a post about (things)", "--dry-run"])

    assert done.returncode == 0
    assert "a post about (things)" in done.stdout
    assert "dry run" in done.stdout


def test_dry_run_can_show_the_escaped_form_that_would_be_sent() -> None:
    done = _run(["post", "--text", "a (b)", "--dry-run", "--show-escaped"])
    assert "a \\(b\\)" in done.stdout


def test_post_text_can_come_from_stdin() -> None:
    done = _run(["post", "--dry-run"], stdin="piped in")
    assert "piped in" in done.stdout


def test_check_reports_an_unconfigured_setup_without_failing() -> None:
    """The command you run when nothing works has to work."""
    done = _run(["check"])

    assert done.returncode == 0
    assert "no token saved" in done.stdout


def test_the_poster_contract_answers_json_on_stdout_and_fails_cleanly() -> None:
    """No credentials anywhere, so this exercises the error path the bundle
    will show the user: a JSON object, not a traceback."""
    payload = json.dumps({"draft_text": "hello", "target_url": "https://www.linkedin.com/feed/"})

    done = _run(["poster", "post", "https://www.linkedin.com/feed/"], stdin=payload)

    assert done.returncode == 1
    answer = json.loads(done.stdout)
    assert answer["ok"] is False
    assert "auth" in answer["error"]


def test_the_poster_rejects_malformed_stdin_as_json_too() -> None:
    done = _run(["poster", "post"], stdin="{not json")

    assert done.returncode == 2
    assert json.loads(done.stdout)["ok"] is False


def test_auth_without_an_app_configured_explains_rather_than_opening_a_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    done = _run(["auth"])

    assert done.returncode == 1
    assert "LINKEDIN_CLIENT_ID" in done.stdout


def test_running_it_with_no_command_prints_help() -> None:
    done = _run([])
    assert done.returncode == 1
    assert "auth" in done.stdout


# --------------------------------------------------------------- OAuth safety


def _redirect_answering(answer: dict[str, list[str]]) -> Any:
    """Stands in for the callback listener, returning what LinkedIn 'sent'."""

    def fake(redirect_uri: str, on_ready: Any, timeout: float = 300.0) -> dict[str, list[str]]:
        return answer

    return fake


def test_a_redirect_carrying_the_wrong_state_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without this check, any page could send the browser to the callback
    with a code of its choosing and connect the tool to another account.
    """
    monkeypatch.setattr(lp, "_await_redirect", _redirect_answering({"code": ["c"], "state": ["not-the-one"]}))

    with pytest.raises(lp.LinkedInError, match="state"):
        lp.authorize("id", "secret", open_browser=False)


def test_a_redirect_that_never_arrives_times_out_with_a_sentence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lp, "_await_redirect", _redirect_answering({}))

    with pytest.raises(lp.LinkedInError, match="timed out"):
        lp.authorize("id", "secret", open_browser=False)


def test_a_refusal_on_linkedins_side_is_reported_as_theirs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        lp,
        "_await_redirect",
        _redirect_answering({"error": ["user_cancelled_login"], "error_description": ["you said no"]}),
    )

    with pytest.raises(lp.LinkedInError, match="you said no"):
        lp.authorize("id", "secret", open_browser=False)


def test_a_good_redirect_is_exchanged_and_the_author_looked_up(monkeypatch: pytest.MonkeyPatch) -> None:
    """The happy path, end to end, with only the network replaced."""
    captured: dict[str, str] = {}

    def fake_await(redirect_uri: str, on_ready: Any, timeout: float = 300.0) -> dict[str, list[str]]:
        on_ready()  # the real one runs this; a print must not break the flow
        url = captured["url"]
        state = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["state"][0]
        return {"code": ["the-code"], "state": [state]}

    def capture_print(*args: Any, **kwargs: Any) -> None:
        for arg in args:
            if isinstance(arg, str) and lp.AUTHORIZE_URL in arg:
                captured["url"] = arg.strip()

    monkeypatch.setattr("builtins.print", capture_print)
    monkeypatch.setattr(lp, "_await_redirect", fake_await)
    monkeypatch.setattr(lp, "exchange_code", lambda *a: lp.Credentials("tok", "", "2030-01-01T00:00:00+00:00"))
    monkeypatch.setattr(lp, "fetch_member_urn", lambda token: "urn:li:person:abc")

    creds = lp.authorize("id", "secret", open_browser=False)

    assert creds.access_token == "tok"
    assert creds.member_urn == "urn:li:person:abc", "the token is useless without knowing whose it is"


def test_the_member_urn_is_built_from_the_userinfo_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lp, "_call", lambda *a, **k: {"sub": "XyZ123"})
    assert lp.fetch_member_urn("t") == "urn:li:person:XyZ123"


def test_a_userinfo_response_with_no_subject_names_the_missing_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lp, "_call", lambda *a, **k: {})
    with pytest.raises(lp.LinkedInError, match="profile"):
        lp.fetch_member_urn("t")


def test_a_token_response_with_no_token_is_an_error_not_an_empty_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lp, "_call", lambda *a, **k: {"expires_in": 100})
    with pytest.raises(lp.LinkedInError, match="no access token"):
        lp.exchange_code("code", "id", "secret", lp.DEFAULT_REDIRECT)


def test_the_expiry_is_recorded_so_check_can_warn_before_it_bites(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lp, "_call", lambda *a, **k: {"access_token": "t", "expires_in": 60 * 60 * 24 * 60})

    creds = lp.exchange_code("code", "id", "secret", lp.DEFAULT_REDIRECT)

    days = creds.days_left()
    assert days is not None and 58 <= days <= 60


def test_credentials_round_trip_through_dataclass_asdict() -> None:
    """save_credentials writes asdict(), so a field added without a default
    would silently stop being saved."""
    assert set(dataclasses.asdict(LIVE)) == {"access_token", "member_urn", "expires_at"}


# ------------------------------------------------------ Version and headers


def test_the_default_version_is_not_one_linkedin_has_sunset() -> None:
    """202508 was sunset on 2026-08-17 and shipped here as the default, which
    would have failed the first real post. Versions last about a year, so the
    default has to be recent enough to still be alive."""
    assert lp.DEFAULT_API_VERSION >= "202608", "bump the default, see the versioning docs"


def test_a_400_naming_the_version_is_reported_as_the_version_problem() -> None:
    """A retired version is not always a 426. The fix is the same either way,
    so the message is the fix rather than the status."""
    message = lp._explain(400, "Requested version 202508 is not supported")

    assert "LINKEDIN_API_VERSION" in message or "version" in message.lower()
    assert "learn.microsoft.com" in message


def test_an_ordinary_400_is_not_mistaken_for_a_version_problem() -> None:
    assert "not accepted" not in lp._explain(400, "malformed request body")


def test_the_versioned_api_gets_a_version_header_and_the_old_one_does_not() -> None:
    """/rest/posts refuses a request without it; /v2/socialActions is the older
    unversioned endpoint and does not want it."""
    assert "LinkedIn-Version" in lp._api_headers("t")
    assert "LinkedIn-Version" not in lp._api_headers("t", versioned=False)
    assert lp._api_headers("t", versioned=False)["Authorization"] == "Bearer t"


def test_every_reserved_character_linkedin_lists_is_escaped() -> None:
    """LinkedIn's little-text rule: escape every reserved character, whether or
    not it is being used as markup. An unescaped bracket truncates the post at
    that point, so a missing one here is a silently cut-off post.
    """
    for char in "_|()[]{}@#*~<>\\":
        assert lp.escape_commentary(f"a{char}b") == f"a\\{char}b", f"{char!r} is not escaped"
