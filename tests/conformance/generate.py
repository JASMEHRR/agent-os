"""Regenerates Appendix F into `docs/`.

Run after changing `matrix.py` or after the corpus changes:

    python tests/conformance/generate.py

`test_appendix_f.py::test_the_published_appendix_matches_the_generator` fails
until this has been run, which is what keeps the published table and the
generator from diverging.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tests.conformance.matrix import render, summary  # noqa: E402

TARGET = pathlib.Path(__file__).resolve().parents[2] / "docs" / "appendix_f_traceability.md"


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(render(), encoding="utf-8")
    stats = summary()
    print(f"wrote {TARGET}")
    print(
        f"  {stats['rules_extracted']} rules | {stats['proven']} proven | "
        f"{stats['blocked']} blocked | {stats['uncovered']} uncovered"
    )


if __name__ == "__main__":
    main()
