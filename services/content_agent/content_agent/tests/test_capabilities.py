"""The capability list, which is the answer to "what can this actually do".

The single property worth enforcing: it cannot become marketing. Every entry
is counted from the real classes, so a capability whose module was deleted
reports zero rather than continuing to claim its operations, and `wired` is
separate from `built` so the gap between them stays visible.
"""

from __future__ import annotations

from content_agent.capabilities import CATALOGUE, FACADES, survey, totals


def test_every_capability_names_modules_that_exist() -> None:
    """A capability pointing at a module nobody has is a claim about nothing."""
    for capability in CATALOGUE:
        for module in capability.modules:
            assert module in FACADES, f"{capability.key} names unknown module {module!r}"


def test_operations_are_counted_from_the_code_not_declared() -> None:
    """A hand-written count goes stale on the first rename."""
    for entry in survey():
        assert int(str(entry["operations"])) > 0, f"{entry['key']} counted no operations; the introspection is wrong"


def test_anything_not_wired_says_what_is_missing() -> None:
    """The gap between built and wired is the honest part of this list.

    A capability marked unavailable with no explanation is indistinguishable
    from one nobody has thought about.
    """
    for entry in survey():
        if not entry["wired"]:
            assert len(str(entry["missing"])) > 20, f"{entry['key']} is unavailable without saying why"


def test_wired_capabilities_do_not_claim_something_is_missing() -> None:
    """A contradiction here would mean the list is wrong about itself."""
    for entry in survey():
        if entry["wired"]:
            assert not entry["missing"]


def test_not_everything_claims_to_be_working() -> None:
    """The failure this file guards against.

    If every capability ever reports wired, either the work is genuinely
    finished or someone flipped the flags. Worth a deliberate look either way.
    """
    surveyed = survey()
    unwired = [entry for entry in surveyed if not entry["wired"]]

    assert unwired, "every capability now claims to be wired; verify that before celebrating"


def test_the_totals_match_the_entries() -> None:
    surveyed = survey()
    summary = totals()

    assert summary["capabilities"] == len(surveyed)
    assert summary["wired"] == sum(1 for entry in surveyed if entry["wired"])
    assert summary["operations"] == sum(int(str(entry["operations"])) for entry in surveyed)


def test_every_capability_is_described_without_jargon() -> None:
    """The list exists to be read by the person using the thing, not by the
    person who wrote it."""
    for capability in CATALOGUE:
        assert len(capability.plain) > 60, f"{capability.key} has no real explanation"
        assert capability.title[0].isupper()
