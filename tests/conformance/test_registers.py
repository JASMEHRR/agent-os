"""Appendices A–E, G and H, kept honest (21_PLAN §40).

Four of the seven registers are derived from the code, so they cannot be wrong
about it — only incomplete if the derivation is. Three are declarations, and a
declaration nothing checks is a wish.

So the tests here fall into two groups:

* **derivation is sound** — the readers actually read, and a broken parser
  cannot pass by finding nothing;
* **declarations agree with the code** — a module claiming exclusive ownership
  of a journal it does not hold, a CIR claimed resolved while the modules it
  blocks still raise, or a risk marked mitigated with nothing behind it, all
  fail here rather than being discovered by a reader who trusted the register.
"""

from __future__ import annotations

import pathlib as _pathlib

import pytest

from tests.conformance.registers import (
    CIR_001_BLOCKED,
    CIR_REGISTER,
    DATA_OWNERSHIP,
    MODULE_FACADES,
    MODULE_STAGES,
    RISK_REGISTER,
    CIRStatus,
    discovered_modules,
    interface_register,
    journal_holders,
    module_register,
    register_summary,
    render,
    signal_register,
)

PUBLISHED = _pathlib.Path(__file__).resolve().parents[2] / "docs" / "appendices_a_to_h_registers.md"

# ------------------------------------------------------- A — Module Register


def test_the_module_register_covers_every_module_on_disk() -> None:
    """Read from the filesystem, so a module added without being registered
    still appears rather than quietly falling outside the register."""
    registered = {entry.name for entry in module_register()}
    assert registered == set(discovered_modules())
    assert len(registered) >= 26, f"expected at least the 26 planned modules, found {len(registered)}"


def test_every_module_has_a_declared_stage() -> None:
    """An unassigned stage means a module was built outside the build plan."""
    unassigned = [entry.name for entry in module_register() if entry.stage == "unassigned"]
    assert not unassigned, f"these modules have no stage in the build plan: {unassigned}"


def test_the_stage_table_names_no_module_that_does_not_exist() -> None:
    """The other direction: a stage entry for a module nobody built."""
    phantom = sorted(set(MODULE_STAGES) - set(discovered_modules()))
    assert not phantom, f"the stage table names modules that do not exist: {phantom}"


def test_blocked_modules_actually_block() -> None:
    """The register's most falsifiable claim, checked against behaviour.

    A module listed as construction-blocked that quietly gained a working
    `register` would make this register a document that says the build is
    honest while the build is not.
    """
    import importlib

    for name in sorted(CIR_001_BLOCKED):
        module = importlib.import_module(name)
        facade = getattr(module, MODULE_FACADES[name])()
        assert facade.is_blocked(), f"'{name}' is registered as blocked but reports otherwise"
        assert facade.health()["construction_authorized"] is False


def test_no_unblocked_module_claims_to_be_blocked() -> None:
    """The inverse. A working module reporting itself blocked would be a
    different kind of dishonesty and just as invisible."""
    import importlib

    for name, facade_name in sorted(MODULE_FACADES.items()):
        if name in CIR_001_BLOCKED:
            continue
        module = importlib.import_module(name)
        facade = getattr(module, facade_name)
        assert not hasattr(facade, "is_blocked"), (
            f"'{name}' is not CIR-001 blocked but exposes a blocked-status surface"
        )


# ---------------------------------------------------- B — Interface Register


def test_the_interface_register_is_read_by_introspection() -> None:
    """A hand-maintained interface list goes stale on the first rename."""
    entries = interface_register()
    assert len(entries) > 200, f"only {len(entries)} interfaces found; the introspection is wrong"
    by_module = {entry.module for entry in entries}
    assert by_module == set(MODULE_FACADES), "some facade produced no interfaces"


@pytest.mark.parametrize("module", sorted(MODULE_FACADES))
def test_every_facade_publishes_at_least_one_interface(module: str) -> None:
    """A Gateway with no public method mediates nothing."""
    methods = [e.method for e in interface_register() if e.module == module]
    assert methods, f"'{module}' publishes no interface"


def test_every_facade_is_importable_by_its_published_name() -> None:
    """The facade name is how the rest of the system reaches the module."""
    import importlib

    for module, facade in sorted(MODULE_FACADES.items()):
        imported = importlib.import_module(module)
        assert hasattr(imported, facade), f"'{module}' does not export '{facade}'"
        assert facade in getattr(imported, "__all__", []), (
            f"'{facade}' is importable from '{module}' but absent from its __all__"
        )


# ----------------------------------------------- C — Data Ownership Matrix


def test_every_owner_named_in_the_matrix_exists() -> None:
    phantom = sorted(set(DATA_OWNERSHIP) - set(discovered_modules()))
    assert not phantom, f"the ownership matrix names modules that do not exist: {phantom}"


def test_every_module_claiming_a_journal_actually_holds_one() -> None:
    """The check that makes the ownership matrix more than a wish.

    A module listing "x journal" among what it owns exclusively, while holding
    no journal, is claiming custody of a record that does not exist — and the
    claim would be believed, because a matrix is exactly the document a reader
    consults instead of the code.
    """
    holders = set(journal_holders())
    for module, owned in sorted(DATA_OWNERSHIP.items()):
        if any("journal" in item for item in owned):
            assert module in holders, (
                f"'{module}' claims exclusive ownership of a journal but holds no ImmutableJournal"
            )


def test_no_two_modules_claim_the_same_thing() -> None:
    """21A §10 allocates ownership exclusively; two owners is no owner."""
    seen: dict[str, str] = {}
    clashes: list[str] = []
    for module, owned in sorted(DATA_OWNERSHIP.items()):
        for item in owned:
            if item in seen:
                clashes.append(f"'{item}' claimed by both {seen[item]} and {module}")
            seen[item] = module
    assert not clashes, "; ".join(clashes)


# ------------------------------------------------------ D — Journal Register


def test_the_journal_register_finds_the_journals() -> None:
    """21A §6.2 makes the immutable journal a universal Gateway mechanism, so
    most modules should hold one. A near-empty result means a broken reader."""
    holders = journal_holders()
    assert len(holders) >= 12, f"only {len(holders)} journal holders found; the reader is wrong"
    for expected in ("security_gateway", "decision_gateway", "governance_gateway"):
        assert expected in holders, f"'{expected}' must hold a journal and does not appear to"


# ---------------------------------------------- E — Signal Contract Register


def test_the_signal_register_extracts_emitted_signals() -> None:
    """21A §5.2 item 7 makes signal emission a universal mechanism."""
    signals = signal_register()
    assert len(signals) >= 30, f"only {len(signals)} signals found; the extractor is wrong"
    assert all("." in entry.signal for entry in signals), "signal names are dotted by convention"


def test_signal_names_are_namespaced_to_something_meaningful() -> None:
    """A signal named without a namespace collides the moment a second
    subsystem emits something similar."""
    for entry in signal_register():
        namespace = entry.signal.split(".")[0]
        assert len(namespace) > 2, f"'{entry.signal}' from {entry.module} has no useful namespace"


def test_no_signal_name_is_emitted_by_two_unrelated_subsystems() -> None:
    """A shared name means a consumer cannot tell who spoke."""
    owners: dict[str, set[str]] = {}
    for entry in signal_register():
        owners.setdefault(entry.signal, set()).add(entry.module)
    shared = {signal: mods for signal, mods in owners.items() if len(mods) > 1}
    assert not shared, f"these signal names are emitted by more than one module: {shared}"


# ------------------------------ G — Constitutional Interpretation Register


def test_every_cir_has_a_status_and_a_note() -> None:
    for cir in CIR_REGISTER:
        assert cir.status in (CIRStatus.OPEN, CIRStatus.RESOLVED)
        assert len(cir.note) > 40, f"{cir.identifier} needs a disposition, not a label"


def test_cir_001_is_open_and_names_exactly_the_modules_it_blocks() -> None:
    """The register's load-bearing entry, checked against the modules.

    If CIR-001 were ever marked resolved here while the modules still raised,
    the register would be announcing an authorization nobody granted.
    """
    cir = next(c for c in CIR_REGISTER if c.identifier == "CIR-001")
    assert cir.status == CIRStatus.OPEN
    assert set(cir.blocks) == set(CIR_001_BLOCKED)


def test_a_resolved_cir_says_how_it_was_resolved() -> None:
    """Three CIRs are marked resolved *by construction* rather than by ruling.

    That distinction matters enough to be stated in each note: a choice made in
    code is reversible by a later ruling, and a reader who mistook it for a
    ruling would treat it as settled.
    """
    for cir in CIR_REGISTER:
        if cir.status == CIRStatus.RESOLVED:
            assert "construction" in cir.note.lower(), (
                f"{cir.identifier} is marked resolved without saying it was resolved in construction "
                "rather than by a Governance ruling"
            )


def test_no_cir_is_silently_dropped() -> None:
    """21A §3 names nine. A register with eight would look complete."""
    identifiers = {c.identifier for c in CIR_REGISTER}
    assert identifiers == {f"CIR-{n:03d}" for n in range(1, 10)}


# ------------------------------------------------- H — Risk Register (live)


def test_every_risk_has_a_state_and_a_disposition() -> None:
    for risk in RISK_REGISTER:
        assert risk.state in ("open", "mitigated", "realized")
        assert len(risk.note) > 20, f"{risk.identifier} needs a disposition"


def test_no_risk_is_silently_dropped() -> None:
    """21_PLAN §6 names thirteen."""
    assert {r.identifier for r in RISK_REGISTER} == {f"R{n}" for n in range(1, 14)}


def test_the_realized_risks_are_the_ones_that_actually_happened() -> None:
    """A risk register that marked nothing realized would be a register nobody
    updated. Two did happen and both are recorded with what happened."""
    realized = {r.identifier for r in RISK_REGISTER if r.state == "realized"}
    assert realized == {"R8", "R13"}
    r8 = next(r for r in RISK_REGISTER if r.identifier == "R8")
    assert "unreachable" in r8.note, "R8's realization should say what went wrong"


def test_r1_matches_cir_001() -> None:
    """The risk register and the interpretation register describe one thing
    twice; if they disagree, one of them is being maintained and the other is
    not."""
    r1 = next(r for r in RISK_REGISTER if r.identifier == "R1")
    cir = next(c for c in CIR_REGISTER if c.identifier == "CIR-001")
    assert r1.state == "open" and cir.status == CIRStatus.OPEN


# ------------------------------------------------------------------ Summary


def test_the_summary_reports_every_register() -> None:
    stats = register_summary()
    assert stats["modules"] >= 26
    assert stats["modules_blocked"] == len(CIR_001_BLOCKED)
    assert stats["cirs_open"] + stats["cirs_resolved"] == 9
    assert stats["risks_open"] + stats["risks_realized"] <= 13


# ---------------------------------------------------- The published document


def test_the_published_registers_match_the_generator() -> None:
    """The same single-source discipline Appendix F and the bilingual boundary use.

    A register edited by hand is the failure mode these registers exist to
    prevent, occurring in the registers themselves.
    """
    assert PUBLISHED.exists(), "the registers have not been generated; run tests/conformance/generate.py"
    assert PUBLISHED.read_text(encoding="utf-8") == render(), (
        "docs/appendices_a_to_h_registers.md differs from what registers.py generates. "
        "Regenerate it rather than editing it by hand."
    )


def test_the_published_registers_carry_every_appendix() -> None:
    """A register silently omitted would look like a register that has nothing
    in it, which is indistinguishable from one nobody wrote."""
    text = PUBLISHED.read_text(encoding="utf-8")
    for appendix in ("Appendix A", "Appendix B", "Appendix C", "Appendix D", "Appendix E", "Appendix G", "Appendix H"):
        assert f"## {appendix}" in text, f"{appendix} is missing from the published registers"
    assert "Do not edit by hand" in text


def test_the_published_registers_are_not_empty_tables() -> None:
    """Guards against the failure that produced a zero-interface register: a
    reader cannot tell an empty table from a broken one."""
    rows = [line for line in PUBLISHED.read_text(encoding="utf-8").splitlines() if line.startswith("| `")]
    assert len(rows) > 300, f"only {len(rows)} rows published; a derivation is returning nothing"
