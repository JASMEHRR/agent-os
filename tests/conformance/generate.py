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

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# The interface register reads each Gateway by import, so the module paths have
# to be on sys.path exactly as `conftest.py` puts them there for pytest.
# Without this the register renders zero interfaces and looks merely empty
# rather than broken.
import conftest  # noqa: E402,F401
from tests.conformance.matrix import render, summary  # noqa: E402
from tests.conformance.registers import register_summary  # noqa: E402
from tests.conformance.registers import render as render_registers  # noqa: E402

DOCS = pathlib.Path(__file__).resolve().parents[2] / "docs"
TARGET = DOCS / "appendix_f_traceability.md"
REGISTERS = DOCS / "appendices_a_to_h_registers.md"


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(render(), encoding="utf-8")
    REGISTERS.write_text(render_registers(), encoding="utf-8")
    stats = summary()
    registers = register_summary()
    print(f"wrote {TARGET}")
    print(
        f"  {stats['rules_extracted']} rules | {stats['proven']} proven | "
        f"{stats['blocked']} blocked | {stats['uncovered']} uncovered"
    )
    print(f"wrote {REGISTERS}")
    print(
        f"  {registers['modules']} modules | {registers['interfaces']} interfaces | "
        f"{registers['signals']} signals | {registers['cirs_open']} open CIRs"
    )


if __name__ == "__main__":
    main()
