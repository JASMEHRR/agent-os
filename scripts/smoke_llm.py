"""Live check that the free-tier backends actually answer.

Run this after setting your own keys in your own shell. It is the one thing
the test suite deliberately does not do: the suite substitutes the transport,
because a test that called Groq would be measuring Groq's uptime and spending
the quota the running system needs.

    setx GROQ_API_KEY "..."      (PowerShell, then reopen the shell)
    setx GEMINI_API_KEY "..."

    python scripts/smoke_llm.py

Reports each tier separately, because the interesting outcome is usually
partial: one provider configured and the other not, or one rate-limited.
"""

from __future__ import annotations

import pathlib
import sys

# The repo has no packaging step and modules live under services/*; conftest.py
# does this for pytest, and a standalone script has to do it for itself.
# Importing conftest rather than repeating its list, so the two cannot drift.
REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from scripts.env_file import load as load_env  # noqa: E402

load_env()
from llm_router.backends import (  # noqa: E402 - after the path setup above
    BackendNotConfigured,
    TierRateLimited,
    backends_from_environment,
)

PROMPT = "Reply with exactly the word: ready"


def main() -> int:
    backends = backends_from_environment()
    any_worked = False

    for tier, backend in backends.items():
        label = f"{tier:<9} {backend.model:<26}"
        if not backend.available():
            print(f"{label} unconfigured (no API key set)")
            continue
        try:
            output, tokens, cost = backend.complete(PROMPT, 32)
        except TierRateLimited:
            print(f"{label} rate limited; the Router would degrade to a lower tier")
            continue
        except BackendNotConfigured as exc:
            print(f"{label} key rejected: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 - a smoke test reports, it does not handle
            print(f"{label} failed: {type(exc).__name__}: {exc}")
            continue
        any_worked = True
        print(f"{label} ok  {tokens:>4} tokens  ${cost:.2f}  {output['text'].strip()[:60]!r}")

    if not any_worked:
        print("\nNo tier answered. Set GROQ_API_KEY for Nano and Standard, GEMINI_API_KEY for Premium.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
