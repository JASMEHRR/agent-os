"""Real model backends for the free tiers of Groq and Google Gemini.

Implements `llm_router.router.ModelBackend`. Two properties shape everything
here, and both come from the tiers being **free** rather than from the
providers being different:

* **A free tier is rate-limited, not metered.** Exhausting it returns 429
  rather than a bill. So the interesting failure is not cost, it is a tier
  going dark for a minute, which is precisely what `available()` exists to let
  the Router see. A 429 opens a cooldown and the Router degrades down the
  failover chain instead of raising, satisfying `01.3.1` Local First by the
  same mechanism that was designed for a paid Premium tier going down.
* **Cost is genuinely zero**, so `complete` reports 0.0 rather than an
  estimate. Reporting a fabricated per-token price would put invented numbers
  into the Cost Manager's ledger, and a budget built on invented numbers is
  worse than no budget: it reads as authoritative.

No third-party HTTP client. This repository has no runtime dependencies and
`urllib.request` is sufficient for two JSON POSTs.

The key is read from the environment and never logged, never journalled, and
never placed in a URL. Gemini accepts its key as a query parameter; this
module sends it as a header instead, because a URL reaches access logs and
proxies that a header does not.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

#: How long a tier stays dark after the provider says it is rate-limited.
#: Groq's free tier resets per minute, so a minute is the honest wait rather
#: than a guess. Retrying sooner spends the next window's quota on a request
#: that will be refused again.
RATE_LIMIT_COOLDOWN_SECONDS = 60.0

#: A transport failure is not a rate limit and should not cost a full minute,
#: but retrying instantly against a provider that just refused the connection
#: converts one failure into a tight loop.
TRANSPORT_COOLDOWN_SECONDS = 5.0

REQUEST_TIMEOUT_SECONDS = 30.0


class BackendNotConfigured(RuntimeError):
    """Raised when a backend is asked to run without a usable API key.

    Distinct from unavailability. An unconfigured backend reports
    `available() is False` and the Router degrades past it silently, which is
    correct: a deployment that has not been given a Gemini key should run on
    Groq rather than fail. This exception exists for the case where something
    calls `complete` directly and would otherwise get an opaque 401.
    """


class TierRateLimited(RuntimeError):
    """The free tier's window is exhausted. The Router degrades, it does not retry."""


@dataclass
class HTTPBackend:
    """Shared transport, cooldown and availability logic.

    Subclasses supply the request shape and the response shape. Everything
    else, which is to say when a tier is dark and how long for and how a
    refusal is classified, is identical across providers and lives here so the
    two backends cannot drift in their failure behaviour.
    """

    api_key: str
    model: str
    timeout: float = REQUEST_TIMEOUT_SECONDS

    _dark_until: float = field(default=0.0, init=False)
    _last_error: str = field(default="", init=False)

    # ---------------------------------------------------------- Availability

    def available(self) -> bool:
        return bool(self.api_key) and time.monotonic() >= self._dark_until

    def status(self) -> dict[str, Any]:
        """For the Router's health report, which the Observability Gateway reads."""
        remaining = max(0.0, self._dark_until - time.monotonic())
        return {
            "model": self.model,
            "configured": bool(self.api_key),
            "available": self.available(),
            "dark_for_seconds": round(remaining, 1) if remaining != float("inf") else -1.0,
            "last_error": self._last_error,
        }

    def _go_dark(self, seconds: float, reason: str) -> None:
        self._dark_until = time.monotonic() + seconds
        # Truncated because a provider error body can echo the request back,
        # and this string reaches the health report.
        self._last_error = reason[:200]

    # ------------------------------------------------------------- Transport

    def complete(self, prompt: str, max_tokens: int) -> tuple[dict[str, Any], int, float]:
        """Overridden per provider. Declared here so the base satisfies
        `ModelBackend` and a subclass that forgets it fails loudly."""
        raise NotImplementedError

    def _post(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        # Endpoints are class defaults but are overridable, and a config that
        # set one to file:// would turn a model call into a local file read.
        # Checked rather than trusted, which is also what bandit's B310 asks for.
        if not url.startswith("https://"):
            raise ValueError(f"model endpoints must be https, got {url!r}")

        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            # The scheme is checked above, which is the audit B310 asks for.
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # nosec B310 # noqa: S310
                decoded: dict[str, Any] = json.loads(response.read().decode("utf-8"))
                return decoded
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429:
                self._go_dark(RATE_LIMIT_COOLDOWN_SECONDS, f"rate limited: {detail}")
                raise TierRateLimited(f"{self.model} is rate limited") from exc
            if exc.code in (401, 403):
                # Not a cooldown. A bad key does not heal in sixty seconds, and
                # pretending it might would hide a configuration error behind
                # what looks like transient unavailability.
                self._go_dark(float("inf"), f"auth rejected: {detail}")
                raise BackendNotConfigured(f"{self.model} rejected the API key") from exc
            self._go_dark(TRANSPORT_COOLDOWN_SECONDS, f"http {exc.code}: {detail}")
            raise
        except (urllib.error.URLError, TimeoutError) as exc:
            self._go_dark(TRANSPORT_COOLDOWN_SECONDS, f"transport: {exc}")
            raise


@dataclass
class GroqBackend(HTTPBackend):
    """Groq's OpenAI-compatible chat completions endpoint.

    Serves Nano and Standard. Groq's free tier is fast and rate-limited by
    request count rather than by spend, which is what makes it the right floor
    for a system expected to run continuously without funding.
    """

    endpoint: str = "https://api.groq.com/openai/v1/chat/completions"

    def complete(self, prompt: str, max_tokens: int) -> tuple[dict[str, Any], int, float]:
        if not self.api_key:
            raise BackendNotConfigured("GROQ_API_KEY is not set")
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        data = self._post(self.endpoint, {"Authorization": f"Bearer {self.api_key}"}, body)

        text = ""
        choices = data.get("choices") or []
        if choices:
            text = str(choices[0].get("message", {}).get("content", ""))
        usage = data.get("usage") or {}
        tokens = int(usage.get("total_tokens", 0))
        return {"text": text, "model": self.model, "provider": "groq"}, tokens, 0.0


@dataclass
class GeminiBackend(HTTPBackend):
    """Google's Generative Language API.

    Serves Premium. The key travels as `x-goog-api-key` rather than in the
    query string the documentation shows first: a URL reaches proxy and server
    access logs, and a credential in a log is a credential leaked.
    """

    base: str = "https://generativelanguage.googleapis.com/v1beta/models"

    def complete(self, prompt: str, max_tokens: int) -> tuple[dict[str, Any], int, float]:
        if not self.api_key:
            raise BackendNotConfigured("GEMINI_API_KEY is not set")
        url = f"{self.base}/{self.model}:generateContent"
        body: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        data = self._post(url, {"x-goog-api-key": self.api_key}, body)

        text = ""
        candidates = data.get("candidates") or []
        if candidates:
            parts = candidates[0].get("content", {}).get("parts") or []
            text = "".join(str(part.get("text", "")) for part in parts)
        usage = data.get("usageMetadata") or {}
        tokens = int(usage.get("totalTokenCount", 0))
        return {"text": text, "model": self.model, "provider": "gemini"}, tokens, 0.0


# ---------------------------------------------------------------- Assembly

#: Defaults chosen for what the free tiers actually serve today, and
#: overridable by environment so a model rename by either provider is a
#: configuration change rather than a code change. That matters more than
#: usual here: hosted model names are retired on the provider's schedule, not
#: on ours.
DEFAULT_NANO_MODEL = "llama-3.1-8b-instant"
DEFAULT_STANDARD_MODEL = "llama-3.3-70b-versatile"
DEFAULT_PREMIUM_MODEL = "gemini-2.0-flash"


def backends_from_environment() -> dict[str, HTTPBackend]:
    """Builds the three tiers from `GROQ_API_KEY` and `GEMINI_API_KEY`.

    A missing key yields a backend that reports itself unavailable rather than
    an absent entry, because the Router's health report should be able to say
    "Premium is unconfigured" rather than silently omitting the tier.

    Keyed by tier *name* rather than by `ModelTier` so this module does not
    import the Router and create a cycle; the caller maps them.
    """
    groq = os.environ.get("GROQ_API_KEY", "")
    gemini = os.environ.get("GEMINI_API_KEY", "")
    return {
        "nano": GroqBackend(
            api_key=groq,
            model=os.environ.get("NANO_MODEL", DEFAULT_NANO_MODEL),
        ),
        "standard": GroqBackend(
            api_key=groq,
            model=os.environ.get("STANDARD_MODEL", DEFAULT_STANDARD_MODEL),
        ),
        "premium": GeminiBackend(
            api_key=gemini,
            model=os.environ.get("PREMIUM_MODEL", DEFAULT_PREMIUM_MODEL),
        ),
    }
