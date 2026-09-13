"""Why a key is being rejected, without printing the key.

Reports only the prefix and length. Both providers use a recognisable prefix,
so a swapped pair or a stray quote is visible from that alone, and neither the
terminal scrollback nor anything reading it ever sees the secret.

Also asks Gemini which models the key can actually reach, which is the only
reliable answer to a 404: model availability varies by key, region and API
version, so a name that works in the documentation may not work here.

    python scripts/diagnose_keys.py
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from llm_router.backends import DEFAULT_PREMIUM_MODEL, USER_AGENT  # noqa: E402
from scripts.env_file import ENV_FILE  # noqa: E402
from scripts.env_file import load as load_env  # noqa: E402

#: Google has issued at least two live prefixes for Gemini keys ("AIza", the
#: documented one, and "AQ.A", seen on a real working key) -- so this is the
#: set of forms known to work, not a spec, and a key outside it is a lead,
#: not a verdict.
EXPECTED_PREFIX = {"GROQ_API_KEY": ("gsk_",), "GEMINI_API_KEY": ("AIza", "AQ.A")}


def inspect(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None:
        print(f"{name:<16} not set at all")
        return None

    stripped = raw.strip().strip('"').strip("'")
    prefix = stripped[:4]
    want = EXPECTED_PREFIX[name]

    notes = []
    if raw != stripped:
        notes.append("has surrounding whitespace or quotes -- setx keeps them, and they break the header")
    if prefix not in want:
        other = next((k for k, v in EXPECTED_PREFIX.items() if prefix in v), None)
        if other:
            notes.append(f"this looks like a {other} value; the two keys may be swapped")
        else:
            notes.append(f"expected it to start with one of {want!r}, got {prefix!r}")

    print(f"{name:<16} len={len(stripped):<4} starts with {prefix!r}")
    for note in notes:
        print(f"{'':<16} -> {note}")
    return stripped


def list_gemini_models(key: str) -> None:
    """A 404 on generateContent almost always means the model name, not the path."""
    request = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models",
        headers={"x-goog-api-key": key, "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"\nGemini model list failed: HTTP {exc.code} {body}")
        return
    except Exception as exc:  # noqa: BLE001 - a diagnostic reports, it does not handle
        print(f"\nGemini model list failed: {type(exc).__name__}: {exc}")
        return

    usable = [
        m["name"].removeprefix("models/")
        for m in data.get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]
    print(f"\nGemini models this key can call ({len(usable)}):")
    for name in usable[:25]:
        print(f"  {name}")
    if usable:
        print(
            f"\n  Set PREMIUM_MODEL to one of the above. Current: "
            f"{os.environ.get('PREMIUM_MODEL', DEFAULT_PREMIUM_MODEL)}"
        )


def check_groq(key: str) -> None:
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {key}", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"\nGroq model list failed: HTTP {exc.code} {body}")
        return
    except Exception as exc:  # noqa: BLE001
        print(f"\nGroq model list failed: {type(exc).__name__}: {exc}")
        return

    names = sorted(m["id"] for m in data.get("data", []))
    print(f"\nGroq models this key can call ({len(names)}):")
    for name in names[:25]:
        print(f"  {name}")


def main() -> int:
    from_file = load_env()
    if from_file:
        print(f"Loaded from {ENV_FILE.name}: {', '.join(from_file)}")
    elif ENV_FILE.exists():
        print(f"{ENV_FILE.name} exists but set nothing new; the shell already exports these.")
    else:
        print(f"No {ENV_FILE.name} found; reading the shell environment only.")

    print("\nKeys as the process sees them (never the value itself):\n")
    groq = inspect("GROQ_API_KEY")
    gemini = inspect("GEMINI_API_KEY")

    if groq:
        check_groq(groq)
    if gemini:
        list_gemini_models(gemini)
    return 0


if __name__ == "__main__":
    sys.exit(main())
