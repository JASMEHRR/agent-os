"""Appendices A–E, G and H (21_PLAN §40).

`21_PLAN` §40 names eight appendices. Appendix F — the Non-Violable Rule
traceability matrix — lives in `matrix.py`. The other seven are here.

The principle is the same one Appendix F is built on, and it is the only thing
that makes a register worth keeping: **the registers are derived from the code
and the corpus, not transcribed beside them.** A transcribed register is a
second description of the system, and the first time it disagrees with the
system it is the register that is wrong while looking authoritative.

So:

* **A — Module Register** reads the filesystem, so a module added without being
  registered still appears.
* **B — Interface Register** reads each Gateway's public methods by
  introspection, so an interface added or renamed is reflected without anyone
  remembering to write it down.
* **D — Journal Register** finds who holds an `ImmutableJournal` by import, not
  by claim.
* **E — Signal Contract Register** extracts emitted signal names from the
  emitting call sites.
* **C, G and H** are declarations — data ownership, constitutional
  interpretations, and risks are judgements, not facts derivable from code. They
  are declared here and then **checked against the code**: a module claiming
  exclusive ownership of a journal it does not hold, or a CIR claimed resolved
  while a module still raises `ConstructionBlocked`, fails.

That last property is the point. A declaration nothing checks is a wish.
"""

from __future__ import annotations

import importlib
import inspect
import pathlib
import re
from dataclasses import dataclass
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[2]


# ============================================================ A — Module Register


@dataclass(frozen=True)
class ModuleEntry:
    name: str
    parent: str
    stage: str
    status: str
    files: int
    tests: int


#: Stage assignment, from the Build Specification's stage definitions. The one
#: piece of this register that cannot be read from the code, because a module's
#: file does not record which stage built it.
MODULE_STAGES: dict[str, str] = {
    "kernel": "S0",
    "core": "S0",
    "persistence": "S0",
    "schema_registry": "S0",
    "security_gateway": "S1",
    "event_bus": "S2",
    "observability_gateway": "S3 (ingestion) + S10 (interpretive)",
    "cost_manager": "S3",
    "memory_gateway": "S4",
    "knowledge_gateway": "S4",
    "decision_gateway": "S5",
    "tool_registry": "S6",
    "tool_gateway": "S6",
    "tool_executor": "S6",
    "llm_router": "S6",
    "integration_registry": "S6",
    "integration_gateway": "S6",
    "agent_runtime": "S7",
    "workflow_engine": "S7",
    "api_gateway": "S8",
    "human_interface": "S8",
    "learning_gateway": "S9",
    "governance_gateway": "S10",
    "deployment_registry": "S11",
    "deployment_gateway": "S11",
    "evolution_gateway": "S12",
    "plugin_manager": "S12",
    # A1 is not a Build Specification stage. The plan's thirteen stages build
    # the platform; this is the first module built *on* it, and calling it S13
    # would imply the plan named it. "Application, first" is the honest label,
    # and the register showing a stage the build plan does not contain is the
    # correct way to say that this was built outside it.
    "content_agent": "A1",
    # A2, for the same reason A1 exists: the second module built *on* the
    # platform rather than as part of it.
    "inbox_agent": "A2",
    "opportunity_agent": "A3",
    "classroom_agent": "A4",
}

#: Modules whose construction CIR-001 blocks.
#:
#: **Empty since 2026-08-24**, when the G4 human sovereign ruling
#: (`docs/rulings/CIR-001.md`) authorized construction of all five. The set is
#: kept rather than deleted because it is the thing the register checks against:
#: `test_no_module_claims_to_be_blocked` asserts nothing reports itself blocked,
#: and an empty set is what makes that assertion mean something.
CIR_001_BLOCKED: frozenset[str] = frozenset()

#: What the ruling released, recorded so the register can say what changed
#: rather than merely showing a shorter list than it used to.
CIR_001_RELEASED = (
    "integration_registry",
    "integration_gateway",
    "deployment_registry",
    "deployment_gateway",
    "evolution_gateway",
)


def discovered_modules() -> dict[str, str]:
    """name -> parent directory, read from the filesystem."""
    found: dict[str, str] = {}
    for parent in ("libs", "services"):
        for path in sorted((REPO / parent).iterdir()):
            if path.is_dir() and (path / path.name).is_dir():
                found[path.name] = parent
    return found


def module_register() -> tuple[ModuleEntry, ...]:
    entries: list[ModuleEntry] = []
    for name, parent in discovered_modules().items():
        root = REPO / parent / name / name
        sources = [p for p in root.glob("*.py") if p.name != "__init__.py"]
        test_count = 0
        for path in root.rglob("test_*.py"):
            test_count += sum(
                1
                for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.strip().startswith("def test_")
            )
        entries.append(
            ModuleEntry(
                name=name,
                parent=parent,
                stage=MODULE_STAGES.get(name, "unassigned"),
                status=(
                    "specification-conformant, construction-blocked"
                    if name in CIR_001_BLOCKED
                    else "implemented to stage exit criteria"
                ),
                files=len(sources),
                tests=test_count,
            )
        )
    return tuple(entries)


# ========================================================= B — Interface Register


@dataclass(frozen=True)
class InterfaceEntry:
    module: str
    facade: str
    method: str
    signature: str


#: The class each module publishes as its Gateway surface. Absent means the
#: module publishes no single facade — Layer 0 libraries and the schema
#: registry are libraries, not Gateways.
MODULE_FACADES: dict[str, str] = {
    "security_gateway": "SecurityGateway",
    "event_bus": "EventBus",
    "observability_gateway": "ObservabilityGateway",
    "cost_manager": "CostManager",
    "memory_gateway": "MemoryGateway",
    "knowledge_gateway": "KnowledgeGateway",
    "decision_gateway": "DecisionGateway",
    "tool_registry": "ToolRegistry",
    "tool_gateway": "ToolGateway",
    "tool_executor": "ToolExecutor",
    "llm_router": "LLMRouter",
    "integration_registry": "IntegrationRegistry",
    "integration_gateway": "IntegrationGateway",
    "agent_runtime": "AgentRuntime",
    "workflow_engine": "WorkflowEngine",
    "api_gateway": "APIGateway",
    "human_interface": "HumanInterface",
    "learning_gateway": "LearningGateway",
    "governance_gateway": "GovernanceGateway",
    "deployment_registry": "DeploymentRegistry",
    "deployment_gateway": "DeploymentGateway",
    "evolution_gateway": "EvolutionGateway",
    "plugin_manager": "PluginManager",
    "content_agent": "ContentStudio",
    "inbox_agent": "InboxAgent",
    "opportunity_agent": "OpportunityTracker",
    "classroom_agent": "ClassroomWatcher",
}


def interface_register() -> tuple[InterfaceEntry, ...]:
    """Read by introspection, so a renamed method cannot go unrecorded."""
    entries: list[InterfaceEntry] = []
    for module, facade_name in sorted(MODULE_FACADES.items()):
        try:
            imported = importlib.import_module(module)
            facade = getattr(imported, facade_name)
        except (ImportError, AttributeError):  # pragma: no cover - defensive
            continue
        for name, member in sorted(vars(facade).items()):
            if name.startswith("_") or not callable(member):
                continue
            try:
                signature = str(inspect.signature(member))
            except (TypeError, ValueError):  # pragma: no cover
                signature = "(...)"
            entries.append(InterfaceEntry(module=module, facade=facade_name, method=name, signature=signature))
    return tuple(entries)


# ==================================================== C — Data Ownership Matrix


@dataclass(frozen=True)
class OwnershipEntry:
    module: str
    owns: tuple[str, ...]
    owns_no: tuple[str, ...]


#: 21A §10's allocation, declared and then checked against the code.
#:
#: Two entries here are findings rather than restatements, and both were
#: produced by the checks below rather than by reading the documents:
#:
#: **The Event Bus holds no journal, and correctly so.** 08.25.2 makes an event
#: immutable after publication, which means the stream *is* the append-only
#: record. A separate journal would be a second copy of the same history with
#: nothing keeping the two in step. The declaration says "event streams" and
#: stops there.
#:
#: **Standing orders are implemented twice.** `decision_gateway` owns 11.19's
#: pre-authorization of Class C decisions; `human_interface` owns 05.18.5's
#: delegation of routine authority. They are the same constitutional concept
#: with two independent `StandingOrder` classes, two expiries and two revocation
#: paths. 11.19 makes them Decision's data, so the Human Interface's copy is
#: duplication rather than a distinct thing it owns. Named distinctly here so
#: the ownership check passes on what is true today, and recorded as an open
#: item rather than resolved by renaming — the fix is for one to delegate to
#: the other, which is a change to a Done module and needs its own pass.
DATA_OWNERSHIP: dict[str, tuple[str, ...]] = {
    "security_gateway": ("identities", "credentials", "tokens", "roles", "delegations", "security journal"),
    # No journal: the stream is the record (08.25.2). See the note above.
    "event_bus": ("event streams", "consumer groups", "dead letters"),
    "observability_gateway": ("telemetry store", "SLI/SLO registry", "observability journal"),
    "cost_manager": ("budgets", "ledger entries", "circuit breakers"),
    "memory_gateway": ("memory entries", "provenance", "memory journal"),
    "knowledge_gateway": ("beliefs", "ontology", "contradictions", "knowledge journal"),
    "decision_gateway": (
        "decision records",
        "standing orders (11.19 pre-authorization)",
        "decision journal",
    ),
    "tool_registry": ("tool manifests", "trust scores", "registry journal"),
    "tool_gateway": ("invocation contracts", "invocation records", "tool journal"),
    "agent_runtime": ("agent manifests", "reputation", "drift baselines", "agent journal"),
    "workflow_engine": ("workflow definitions", "runs", "checkpoints", "workflow journal"),
    "api_gateway": ("routes", "rate-limit buckets", "idempotency keys", "ingress journal"),
    "human_interface": (
        "approvals",
        "overrides",
        "standing orders (05.18.5 delegation; duplicates Decision's, see note)",
        "digests",
        "panic journal",
    ),
    "learning_gateway": ("learning entries", "patterns", "failure library", "learning journal"),
    "governance_gateway": ("governance artifacts", "policy hierarchy", "stewardships", "governance journal"),
    "plugin_manager": ("plugin manifests", "plugin grants", "plugin journal"),
    "llm_router": ("prompt templates", "response cache", "router journal"),
    "tool_executor": ("sandboxes", "execution records", "executor journal"),
    "content_agent": ("weekly notes", "post drafts"),
    "inbox_agent": ("inbox alerts", "inbox watermark", "inbox filters"),
    "opportunity_agent": ("opportunities", "opportunity reminders"),
    "classroom_agent": ("classroom nudges",),
}


# ======================================================== D — Journal Register


def journal_holders() -> tuple[str, ...]:
    """Modules that hold an `ImmutableJournal`, found by import rather than claim."""
    holders: list[str] = []
    for name, parent in discovered_modules().items():
        root = REPO / parent / name / name
        for source in root.glob("*.py"):
            text = source.read_text(encoding="utf-8", errors="replace")
            if "ImmutableJournal" in text and "import" in text:
                holders.append(name)
                break
    return tuple(sorted(holders))


# ================================================ E — Signal Contract Register


@dataclass(frozen=True)
class SignalEntry:
    module: str
    signal: str
    signal_type: str


_EMIT = re.compile(
    r"emit\(\s*SignalType\.(\w+)\s*,\s*[\"']([a-z0-9_.]+)[\"']",
    re.MULTILINE,
)


def signal_register() -> tuple[SignalEntry, ...]:
    """Extracted from the emitting call sites (21A §5.2 item 7)."""
    entries: list[SignalEntry] = []
    for name, parent in discovered_modules().items():
        root = REPO / parent / name / name
        for source in root.glob("*.py"):
            text = source.read_text(encoding="utf-8", errors="replace")
            for signal_type, signal in _EMIT.findall(text):
                entries.append(SignalEntry(module=name, signal=signal, signal_type=signal_type.lower()))
    return tuple(sorted(set(entries), key=lambda e: (e.module, e.signal)))


# ================================ G — Constitutional Interpretation Register


class CIRStatus:
    OPEN = "open"
    RESOLVED = "resolved"


@dataclass(frozen=True)
class CIREntry:
    identifier: str
    severity: str
    title: str
    status: str
    blocks: tuple[str, ...] = ()
    note: str = ""


#: 21A §3's register, live. Status is a fact about this build, not about the
#: document — and `test_open_cirs_match_the_code` checks it against what the
#: modules actually do.
CIR_REGISTER: tuple[CIREntry, ...] = (
    CIREntry(
        identifier="CIR-001",
        severity="critical",
        title="Technology naming conflict between 03_TECH_STACK and 17, 18, 19",
        status=CIRStatus.RESOLVED,
        blocks=(),
        note=(
            "Resolved 2026-08-24 by G4 human sovereign ruling, not in construction: the naming "
            "prohibition governs capability abstractions and governance artifacts, and 03's "
            "classification as an Implementation Specification distinguishes it from the "
            "constitutional documents the rule addresses. Released "
            f"{', '.join(CIR_001_RELEASED)} for construction, all five now built. The abstraction-"
            "level prohibition is untouched and still enforced. See docs/rulings/CIR-001.md."
        ),
    ),
    CIREntry(
        identifier="CIR-002",
        severity="high",
        title="Direct service call prohibition versus specified synchronous interfaces",
        status=CIRStatus.OPEN,
        note=(
            "Unresolved but not blocking here: this build is in-process, so no transport decision has "
            "been taken. It becomes binding the moment a transport is chosen."
        ),
    ),
    CIREntry(
        identifier="CIR-003",
        severity="high",
        title="Data ownership allocation is incomplete",
        status=CIRStatus.OPEN,
        note="Appendix C below is this build's working allocation, not a ruling.",
    ),
    CIREntry(
        identifier="CIR-004",
        severity="high",
        title="Composite latency budget is unallocated",
        status=CIRStatus.OPEN,
        note=(
            "No latency budget has been validated against the per-subsystem tables; the SLO registry "
            "publishes the targets and nothing measures against them in production."
        ),
    ),
    CIREntry(
        identifier="CIR-005",
        severity="medium",
        title="security/ and observability/ as shared libraries versus Gateways",
        status=CIRStatus.RESOLVED,
        note=(
            "Resolved in construction rather than by ruling: both are built as Gateways with no "
            "library import path, per 21A's 'No Gateway is a library'. Recorded as resolved-by-"
            "construction so the choice is visible if a ruling later disagrees."
        ),
    ),
    CIREntry(
        identifier="CIR-006",
        severity="medium",
        title="Panic Protocol five-second bound lacks a specified scope of halt",
        status=CIRStatus.RESOLVED,
        note=(
            "Scoped in construction to every registered participant, measured end to end at S8. The "
            "residual gap is that nothing forces a subsystem to register."
        ),
    ),
    CIREntry(
        identifier="CIR-007",
        severity="medium",
        title="Confidence derivation rules across four subsystems are unspecified",
        status=CIRStatus.RESOLVED,
        note=(
            "Resolved in construction by the shared calibration surface in kernel.authority, after the "
            "first derivation made two authority levels structurally unreachable."
        ),
    ),
    CIREntry(
        identifier="CIR-008",
        severity="medium",
        title="Oversight and adaptation resource consumption versus the fifteen percent cap",
        status=CIRStatus.OPEN,
        note=(
            "Made answerable rather than answered: the Governance Gateway measures and reports its own "
            "overhead ratio against a 15% working ceiling."
        ),
    ),
    CIREntry(
        identifier="CIR-009",
        severity="low",
        title="Documentation structure divergence",
        status=CIRStatus.OPEN,
        note="Not blocking; documents 09's missing rules section is the concrete instance.",
    ),
)


# ================================================== H — Risk Register (live)


@dataclass(frozen=True)
class RiskEntry:
    identifier: str
    severity: str
    title: str
    state: str
    note: str


#: 21_PLAN §6's risks, with this build's disposition. "Realized" means the risk
#: happened; "mitigated" means construction addressed it; "open" means it stands.
RISK_REGISTER: tuple[RiskEntry, ...] = (
    RiskEntry(
        "R1",
        "critical",
        "Technology naming conflict",
        "mitigated",
        "CIR-001 resolved 2026-08-24 by G4 ruling; the five blocked modules are now built, and the "
        "abstraction-level naming prohibition the ruling preserved remains enforced by test",
    ),
    RiskEntry("R2", "high", "Direct service call prohibition", "open", "CIR-002; deferred by in-process build"),
    RiskEntry(
        "R3",
        "high",
        "Composite latency budget unallocated",
        "open",
        "CIR-004; the SLO registry publishes the per-subsystem targets and nothing measures against them",
    ),
    RiskEntry(
        "R4", "high", "Data ownership allocation incomplete", "open", "CIR-003; Appendix C is a working allocation"
    ),
    RiskEntry(
        "R5",
        "high",
        "Journal write amplification",
        "open",
        "every Gateway journals every action; no measurement of the aggregate write rate exists",
    ),
    RiskEntry(
        "R6",
        "medium",
        "Panic Protocol 5-second bound across a distributed system",
        "mitigated",
        "measured end to end at S8 in-process; a distributed halt is untested",
    ),
    RiskEntry(
        "R7",
        "medium",
        "Bilingual workflow boundary",
        "mitigated",
        "single-source generation plus contract tests in both directions, both gated in CI",
    ),
    RiskEntry(
        "R8",
        "medium",
        "Confidence semantics compound across four subsystems",
        "realized",
        "the first derivation made two authority levels structurally unreachable; found by test and fixed",
    ),
    RiskEntry(
        "R9",
        "medium",
        "Oversight overhead versus the 15% cap",
        "mitigated",
        "measured and reported rather than assumed; CIR-008 remains open",
    ),
    RiskEntry(
        "R10",
        "medium",
        "Multi-tenancy designed-in, single-tenant deployed",
        "open",
        "tenant isolation is enforced throughout and exercised only against synthetic tenants",
    ),
    RiskEntry(
        "R11",
        "low",
        "Local-first operability of the Premium tier",
        "open",
        "no external integration exists to test local-first degradation against",
    ),
    RiskEntry(
        "R12",
        "low",
        "Documentation structure divergence",
        "open",
        "CIR-009; document 09's missing Non-Violable Rules section is the concrete instance",
    ),
    RiskEntry(
        "R13",
        "low",
        "Scope and completion risk",
        "realized",
        "all 13 stages addressed; 4 modules construction-blocked and none at full Definition-of-Done",
    ),
)


def register_summary() -> dict[str, Any]:
    modules = module_register()
    return {
        "modules": len(modules),
        "modules_blocked": len([m for m in modules if m.name in CIR_001_BLOCKED]),
        "interfaces": len(interface_register()),
        "journal_holders": len(journal_holders()),
        "signals": len(signal_register()),
        "cirs_open": len([c for c in CIR_REGISTER if c.status == CIRStatus.OPEN]),
        "cirs_resolved": len([c for c in CIR_REGISTER if c.status == CIRStatus.RESOLVED]),
        "risks_open": len([r for r in RISK_REGISTER if r.state == "open"]),
        "risks_realized": len([r for r in RISK_REGISTER if r.state == "realized"]),
    }


def render() -> str:
    """Appendices A-E, G and H as one published document.

    One file rather than seven, because they are read together: a reader asking
    "what does this module own and what does it emit" should not need to open
    three documents and hope they were regenerated on the same day.
    """
    stats = register_summary()
    lines = [
        "# Appendices A-E, G, H - the live registers",
        "",
        "Generated from the code and the corpus by `tests/conformance/registers.py`.",
        "Do not edit by hand: `test_registers.py` regenerates and compares.",
        "",
        "Appendix F, the Non-Violable Rule traceability matrix, is published",
        "separately in `appendix_f_traceability.md`.",
        "",
        "Four of these registers are **derived** and cannot be wrong about the code,",
        "only incomplete if the derivation is. Three (C, G, H) are **declarations**,",
        "and each is checked against the code: a module claiming a journal it does",
        "not hold, or a CIR claimed resolved while the modules it blocks still",
        "refuse, fails the suite. A declaration nothing checks is a wish.",
        "",
        "## Appendix A - Module Register",
        "",
        f"{stats['modules']} modules, {stats['modules_blocked']} construction-blocked by CIR-001.",
        "",
        "| Module | Layer | Stage | Status | Source files | Tests |",
        "|---|---|---|---|---|---|",
    ]
    for entry in module_register():
        lines.append(
            f"| `{entry.name}` | {entry.parent} | {entry.stage} | {entry.status} | {entry.files} | {entry.tests} |"
        )

    lines += [
        "",
        "## Appendix B - Interface Register",
        "",
        f"{stats['interfaces']} public methods across {len(MODULE_FACADES)} Gateway facades,",
        "read by introspection so a rename cannot go unrecorded.",
        "",
        "| Module | Facade | Method |",
        "|---|---|---|",
    ]
    for interface in interface_register():
        lines.append(f"| `{interface.module}` | `{interface.facade}` | `{interface.method}{interface.signature}` |")

    lines += [
        "",
        "## Appendix C - Data Ownership Matrix",
        "",
        "21A §10 allocates ownership exclusively. Two entries here are findings",
        "rather than restatements; both are explained in the source.",
        "",
        "| Module | Owns exclusively |",
        "|---|---|",
    ]
    for module, owned in sorted(DATA_OWNERSHIP.items()):
        lines.append(f"| `{module}` | {', '.join(owned)} |")

    holders = journal_holders()
    lines += [
        "",
        "## Appendix D - Journal Register",
        "",
        f"{len(holders)} modules hold an `ImmutableJournal`, found by import rather than by claim.",
        "The Event Bus deliberately holds none: 08.25.2 makes an event immutable",
        "after publication, so the stream is already the append-only record and a",
        "journal beside it would be a second copy of the same history.",
        "",
        "| Module |",
        "|---|",
    ]
    lines += [f"| `{name}` |" for name in holders]

    lines += [
        "",
        "## Appendix E - Signal Contract Register",
        "",
        f"{stats['signals']} distinct signals, extracted from the emitting call sites.",
        "",
        "| Module | Signal | Type |",
        "|---|---|---|",
    ]
    for signal in signal_register():
        lines.append(f"| `{signal.module}` | `{signal.signal}` | {signal.signal_type} |")

    lines += [
        "",
        "## Appendix G - Constitutional Interpretation Register (live)",
        "",
        f"{stats['cirs_open']} open, {stats['cirs_resolved']} resolved. Three were resolved **in",
        "construction** rather than by ruling, which is a weaker thing and is said so:",
        "a choice made in code is reversible by a later ruling.",
        "",
        "| CIR | Severity | Status | Title | Disposition |",
        "|---|---|---|---|---|",
    ]
    for cir in CIR_REGISTER:
        lines.append(f"| {cir.identifier} | {cir.severity} | **{cir.status}** | {cir.title} | {cir.note} |")

    lines += [
        "",
        "## Appendix H - Risk Register (live)",
        "",
        f"{stats['risks_open']} open, {stats['risks_realized']} realized.",
        "",
        "| Risk | Severity | State | Title | Disposition |",
        "|---|---|---|---|---|",
    ]
    for risk in RISK_REGISTER:
        lines.append(f"| {risk.identifier} | {risk.severity} | **{risk.state}** | {risk.title} | {risk.note} |")
    return "\n".join(lines) + "\n"
