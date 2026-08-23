"""Adds the Layer 0 substrate libs to sys.path for the Synthetic Gateway
conformance suite, mirroring what `poetry install` (workspace deps) would
wire up once each lib has its own virtualenv."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
for lib in ("libs/kernel", "libs/core", "libs/persistence"):
    sys.path.insert(0, str(ROOT / lib))
