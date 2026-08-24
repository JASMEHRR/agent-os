"""Evolution Gateway — construction blocked by CIR-001 (21B §26).

The subsystem "through which Agent OS changes itself deliberately rather than
accidentally" (21B §26.1). `19.2` draws the line against Learning: Learning
adapts behaviour **within** standing constitutional and architectural bounds;
Evolution proposes changes **to** those bounds.

`19.3` is the sentence the whole module is shaped around: Evolution **"packages;
it does not ratify."** The authority to change the Constitution or the
architecture remains exclusively with Governance and, beyond it, the sovereigns
Governance answers to. `19.16.2` states the handoff as unidirectional —
"Evolution ensures the package is complete" while Governance presents it — and
that is what resolves the Evolution/Governance circular dependency.

**Construction blocked (21B §26 banner).** Evolution packages proposals that may
themselves include technology or provider changes, placing it in the same
naming-prohibition ambiguity as Integration and Deployment. 21A §3 names it the
third of the three subsystems CIR-001 blocks.

So: the pipeline, the states, the handoff direction and the Recursion Guard are
specified and tested. Drafting, packaging and handing off a real proposal are
construction and raise.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, NoReturn

from core.exceptions import AgentOSError

#: The blocker, quoted so a caller sees why rather than only that.
CIR_001 = (
    "CIR-001 (Critical): 03_TECH_STACK names approximately fifty specific technologies, which conflicts "
    "with non-violable rules in documents 17, 18 and 19 prohibiting constitutional documents from naming "
    "specific technologies or providers. Evolution packages amendment proposals that may themselves "
    "include technology or provider changes, placing it inside the same ambiguity. 21A §3 names Evolution "
    "the third of the three subsystems CIR-001 blocks. Construction does not begin until CIR-001 is "
    "resolved by a Governance ruling at G3 or G4. Build Specification Section 6 rule 9 forbids resolving "
    "it by unilateral interpretation."
)


class ConstructionBlocked(AgentOSError):
    """Raised by any operation that would constitute construction.

    Not a no-op: Build Spec Section 24 forbids silent conversion to Done, and a
    quiet no-op here would be the worst instance of it in the system — a caller
    would believe an amendment proposal had reached Governance when nothing had
    been packaged at all.
    """

    def __init__(self, operation: str):
        super().__init__(f"'{operation}' is construction of the Evolution Gateway, which is not authorized.\n{CIR_001}")
        self.operation = operation


def blocked(operation: str) -> NoReturn:
    raise ConstructionBlocked(operation)


class ArtifactClass(StrEnum):
    """What an evolutionary artifact proposes to change (19.9).

    A1 through A4 mirror the G-class spectrum: A4 is constitutional amendment,
    human-only and undelegable (19.36.2).
    """

    A1_OPERATIONAL = "a1_operational"
    A2_ARCHITECTURAL = "a2_architectural"
    A3_STRUCTURAL = "a3_structural"
    A4_CONSTITUTIONAL = "a4_constitutional"

    @property
    def is_human_only(self) -> bool:
        """19.36.2 — A4 authority is bound to human credentials and cannot be delegated."""
        return self is ArtifactClass.A4_CONSTITUTIONAL


class ProposalState(StrEnum):
    """The pipeline of 21B §26.4, as states.

    A rejected proposal is not deleted or mutated: 21B §26.8 requires the
    outcome appended to the same record, "preserving the full history for any
    future re-proposal".
    """

    DETECTED = "detected"
    DRAFTED = "drafted"
    IMPACT_ANALYSED = "impact_analysed"
    COMPENSATION_FRAMED = "compensation_framed"
    RECURSION_CHECKED = "recursion_checked"
    PACKAGED = "packaged"
    HANDED_OFF = "handed_off"
    #: Terminal, and Governance's to set. Evolution records the outcome.
    RATIFIED = "ratified"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    ABANDONED = "abandoned"


#: 21B §26.4's pipeline, in order. Named so the ordering survives as a
#: reviewable artifact while construction is blocked.
EVOLUTION_PIPELINE: tuple[str, ...] = (
    "signal_monitor",
    "proposal_drafter",
    "impact_analyzer",
    "compensation_framer",
    "recursion_guard",
    "packaging_and_handoff",
)

#: 19.5 / 21B §26.6 — Evolution consumes **only** Confirmed learning entries,
#: "never Proposed or Adopted-but-unconfirmed". An unconfirmed entry has not
#: yet been measured, and amending a constitutional bound on the strength of
#: something that might still be refuted is the failure this gate prevents.
CONSUMABLE_LEARNING_STATES: frozenset[str] = frozenset({"confirmed"})


@dataclass
class EvolutionGateway:
    """Specification-conformant, construction-blocked.

    A distinct status from Done, and not a step toward it.
    """

    # ------------------------------------------------- Specification (open)

    def pipeline(self) -> tuple[str, ...]:
        return EVOLUTION_PIPELINE

    def consumes_learning_state(self, state: str) -> bool:
        """19.5 — Confirmed entries only, never Proposed or unconfirmed."""
        return state.lower() in CONSUMABLE_LEARNING_STATES

    def recursion_guard_precedes_packaging(self) -> bool:
        """19.14 as a checkable property of the declared pipeline.

        The guard must run before packaging, not after: a self-referential
        proposal that reached Governance would arrive carrying Evolution's own
        endorsement of a change to Evolution's own bounds.
        """
        return EVOLUTION_PIPELINE.index("recursion_guard") < EVOLUTION_PIPELINE.index("packaging_and_handoff")

    def compensation_precedes_packaging(self) -> bool:
        """19.13 — every proposal carries a rollback plan **before** packaging."""
        return EVOLUTION_PIPELINE.index("compensation_framer") < EVOLUTION_PIPELINE.index("packaging_and_handoff")

    def is_blocked(self) -> bool:
        return True

    def blocker(self) -> str:
        return CIR_001

    # ------------------------------------------------ Construction (blocked)

    def monitor_signals(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("monitor_signals")

    def draft(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("draft")

    def analyse_impact(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("analyse_impact")

    def frame_compensation(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("frame_compensation")

    def package(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("package")

    def hand_off(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("hand_off")

    def record_outcome(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("record_outcome")

    def run_experiment(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("run_experiment")

    def health(self) -> Mapping[str, Any]:
        """Reports the block; a health surface that raised would make the
        blocked status itself unobservable."""
        return {
            "status": "specification-conformant, construction-blocked",
            "blocker": "CIR-001",
            "pipeline": list(EVOLUTION_PIPELINE),
            "proposals": 0,
            "construction_authorized": False,
            "ratification_authority": "governance_gateway",
            "resolution_required_at": "G3 or G4 Governance ruling",
        }


def ratification_verbs() -> Sequence[str]:
    """Deliberately empty, and asserted so by test.

    `19.3`: Evolution "packages; it does not ratify." The absence of any
    ratifying verb on this Gateway is what makes 19.16.2's unidirectional
    handoff structural — and it is what resolves the Evolution/Governance
    circular dependency, since the edge from Evolution back to ratification
    does not exist.
    """
    return ()
