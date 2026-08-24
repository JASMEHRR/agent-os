"""The free-tier backends, tested without touching the network.

Every test here substitutes `_post`. That is deliberate rather than
convenient: a test that called Groq would be measuring Groq's uptime and this
minute's rate-limit window, would fail in CI where no key exists, and would
consume free quota the running system needs. What is worth testing is the
logic this module actually owns, which is how a refusal is classified and what
the Router is told afterwards.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Any

import pytest

from llm_router.backends import (
    RATE_LIMIT_COOLDOWN_SECONDS,
    BackendNotConfigured,
    GeminiBackend,
    GroqBackend,
    TierRateLimited,
    backends_from_environment,
)


class _Response:
    """Minimal stand-in for what `HTTPError.read()` needs to return."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body


def _http_error(code: int, body: str = "{}") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://example.invalid",
        code=code,
        msg="refused",
        hdrs=None,  # type: ignore[arg-type]
        fp=_Response(body.encode("utf-8")),  # type: ignore[arg-type]
    )


def _refusing_with(code: int, body: str):
    """A urlopen that always refuses, so the classification logic is what is
    under test rather than the transport."""

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise _http_error(code, body)

    return refuse


# ------------------------------------------------------------- Happy path


def test_groq_extracts_the_completion_and_reports_zero_cost(monkeypatch) -> None:
    backend = GroqBackend(api_key="k", model="llama-3.1-8b-instant")
    monkeypatch.setattr(
        backend,
        "_post",
        lambda url, headers, body: {
            "choices": [{"message": {"content": "hello"}}],
            "usage": {"total_tokens": 42},
        },
    )

    output, tokens, cost = backend.complete("say hello", 100)

    assert output["text"] == "hello"
    assert output["provider"] == "groq"
    assert tokens == 42
    assert cost == 0.0, "the free tier costs nothing; an estimate here would be an invented number"


def test_gemini_joins_multipart_responses(monkeypatch) -> None:
    """Gemini splits a response across parts, and dropping all but the first
    would truncate silently rather than fail."""
    backend = GeminiBackend(api_key="k", model="gemini-2.0-flash")
    monkeypatch.setattr(
        backend,
        "_post",
        lambda url, headers, body: {
            "candidates": [{"content": {"parts": [{"text": "one "}, {"text": "two"}]}}],
            "usageMetadata": {"totalTokenCount": 9},
        },
    )

    output, tokens, _ = backend.complete("count", 100)

    assert output["text"] == "one two"
    assert tokens == 9


def test_an_empty_response_is_empty_text_rather_than_an_exception(monkeypatch) -> None:
    """A provider returning no candidates is a real outcome, most often a
    safety filter. The Router's grounding stage treats empty output as making
    no claims, which is the correct reading; raising here would instead push
    the request down the failover chain to be refused again."""
    backend = GeminiBackend(api_key="k", model="gemini-2.0-flash")
    monkeypatch.setattr(backend, "_post", lambda url, headers, body: {"candidates": []})

    output, tokens, _ = backend.complete("blocked", 100)

    assert output["text"] == ""
    assert tokens == 0


# --------------------------------------------------------------- Refusals


def test_a_rate_limit_darkens_the_tier_for_the_reset_window(monkeypatch) -> None:
    """The property the whole free-tier design rests on: an exhausted quota
    makes the tier unavailable, so the Router degrades instead of failing."""
    backend = GroqBackend(api_key="k", model="m")
    monkeypatch.setattr(urllib.request, "urlopen", _refusing_with(429, "rate limit reached"))

    assert backend.available()
    with pytest.raises(TierRateLimited):
        backend.complete("x", 10)
    assert not backend.available(), "a rate-limited tier must report itself dark"
    assert backend.status()["dark_for_seconds"] <= RATE_LIMIT_COOLDOWN_SECONDS


def test_a_rejected_key_darkens_permanently_rather_than_for_a_cooldown(monkeypatch) -> None:
    """A bad key does not heal in sixty seconds.

    Treating 401 as transient would hide a configuration error behind what
    looks like ordinary unavailability, and the tier would go on being retried
    forever without anyone being told why it never serves.
    """
    backend = GeminiBackend(api_key="wrong", model="m")
    monkeypatch.setattr(urllib.request, "urlopen", _refusing_with(401, "invalid key"))

    with pytest.raises(BackendNotConfigured):
        backend.complete("x", 10)
    assert not backend.available()
    assert backend.status()["dark_for_seconds"] == -1.0, "permanent darkness is reported as such"


def test_an_unconfigured_backend_is_unavailable_rather_than_raising() -> None:
    """The Router degrades past an unconfigured tier silently.

    A deployment given only a Groq key should run on Groq, not fail on
    Premium. Unavailability is how the Router is told that.
    """
    backend = GeminiBackend(api_key="", model="m")

    assert not backend.available()
    assert backend.status()["configured"] is False
    with pytest.raises(BackendNotConfigured):
        backend.complete("x", 10)


def test_the_error_detail_is_truncated_before_it_reaches_the_health_report() -> None:
    """A provider error body can echo the whole request back, prompt included.

    The health report is read by the Observability Gateway and is not a place
    for an unbounded copy of user input.
    """
    backend = GroqBackend(api_key="k", model="m")
    backend._go_dark(1.0, "x" * 5000)

    assert len(backend.status()["last_error"]) == 200


# ----------------------------------------------------------------- Assembly


def test_the_environment_builds_three_tiers_and_omits_none(monkeypatch) -> None:
    """A missing key yields an unavailable backend, not an absent entry.

    The distinction is what lets the health report say "Premium is
    unconfigured" instead of quietly not mentioning Premium at all.
    """
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    built = backends_from_environment()

    assert set(built) == {"nano", "standard", "premium"}
    assert built["nano"].available()
    assert not built["premium"].available()
    assert built["premium"].status()["configured"] is False


def test_model_names_are_overridable_by_environment(monkeypatch) -> None:
    """Hosted model names are retired on the provider's schedule, not ours."""
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("NANO_MODEL", "something-newer")

    assert backends_from_environment()["nano"].model == "something-newer"


def test_the_api_key_never_appears_in_a_url() -> None:
    """Gemini's documented quickstart puts the key in the query string.

    A URL reaches proxy and server access logs; a header does not. This test
    exists because the convenient way to write this module is the leaky one.
    """
    captured: dict[str, Any] = {}
    backend = GeminiBackend(api_key="secret-key-value", model="gemini-2.0-flash")

    def capture(url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        captured["url"] = url
        captured["headers"] = headers
        return {"candidates": []}

    backend._post = capture  # type: ignore[method-assign]
    backend.complete("x", 10)

    assert "secret-key-value" not in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "secret-key-value"
