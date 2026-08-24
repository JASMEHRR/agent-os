"""Loads `.env` from the repository root into the process environment.

Exists because `setx` is an awkward way to hold a credential: it is invisible
once set, it only reaches shells opened afterwards, and correcting a typo means
retyping the whole secret. A file can be opened, read, and edited.

Two rules, both of which matter more than the convenience:

* **A real environment variable always wins.** A value already exported is one
  someone set deliberately, and a file quietly overriding it would make the two
  disagree with no way to tell which is in force.
* **`.env` is gitignored.** A secret in a commit stays in the history after it
  is deleted, and the only real remedy at that point is to rotate the key.

Deliberately not a dotenv library. The format here is `KEY=value` per line with
`#` comments, which is fifteen lines of parsing and no new dependency.
"""

from __future__ import annotations

import os
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
ENV_FILE = REPO / ".env"


def load(path: pathlib.Path = ENV_FILE) -> list[str]:
    """Applies `path` to `os.environ` and returns the names it set.

    A missing file is not an error: the environment may legitimately be
    supplied by the shell, by CI, or by a container, and requiring a file in
    those cases would break the deployments that are doing it correctly.
    """
    if not path.exists():
        return []

    applied: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        # Quotes are stripped because pasting a key from a web console often
        # brings them along, and a quote inside an Authorization header is a
        # 401 that looks exactly like a wrong key.
        value = value.strip().strip('"').strip("'")
        if not name or name in os.environ:
            continue
        os.environ[name] = value
        applied.append(name)
    return applied
