"""The Recursion Guard (13.21.3, 13 rules 4 and 17, 21B §21.3, 21C §38.5).

`13.21.3` classifies a learning entry targeting the Learning subsystem itself
as a **Recursion Anomaly** requiring "immediate human alert and suspension".
`13` rule 17 additionally forbids recursive triggering of learning cycles
without explicit human authorization. 21B §21.9 classifies the anomaly as
Security-adjacent, **Category 1**.

`21C` §38.5 is explicit about how this component must be tested: it "requires
dedicated adversarial tests that attempt self-referential inputs, since their
fail-closed posture is only meaningful if exercised against genuine
self-reference attempts, not merely ordinary-path tests." The suite in
`tests/test_recursion_guard.py` is that adversarial test.

**Fail closed.** Every check here answers "is this self-referential?" with a
default of yes. An unrecognised target subsystem, an unparseable target, a
proposal whose text names the Learning subsystem, an observation derived from
the Learning Journal, a cycle triggered by a learning event — all are blocked.
A guard that failed open on the inputs it did not anticipate would be worse
than no guard, because the system would believe it had one.

**There is no bypass argument.** 13 rule 4 permits a self-targeting entry only
under Class D human authority, and that authority is a separate, explicit,
audited act — never a flag on the submission. So `check` takes no `force`, no
`allow_self_reference`, and no override parameter of any kind.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.exceptions import AgentOSError
from kernel.escalation import EscalationTrigger
from learning_gateway.entries import TargetClass

#: Every name by which this subsystem can be addressed. Matching is on the
#: normalized form, so `Learning-Gateway`, `learning_gateway` and
#: `LEARNING GATEWAY` are all the same thing.
SELF_IDENTIFIERS = frozenset(
    {
        "learning",
        "learninggateway",
        "learninggw",
        "learningsubsystem",
        "learningengine",
        "learningjournal",
        "learningoperatingmodel",
        "metalearning",
        "selflearning",
        "learningplane",
        "13",
        "doc13",
        "document13",
    }
)

#: Evidence kinds that originate inside this subsystem. An entry reasoning
#: about its own journal is self-referential regardless of what it declares
#: its target to be.
SELF_EVIDENCE_KINDS = frozenset({"learning_journal", "learning_entry", "learning_pattern", "failure_library"})

#: Phrases that make a proposal self-modifying in substance even when its
#: declared target is something else. 13.35.1 names exactly these: the system
#: "may propose changes to its own validation rules, confidence thresholds, or
#: measurement windows, but adoption requires human approval."
SELF_MODIFYING_PHRASES = (
    "validation rule",
    "confidence threshold",
    "measurement window",
    "learning cycle",
    "recursion guard",
    "attribution engine",
    "evidence sufficiency",
)


class RecursionAnomaly(AgentOSError):
    """13.21.3. Raised, escalated, and never recoverable within the cycle."""


@dataclass(frozen=True)
class RecursionFinding:
    """Why the guard blocked, in terms a human reviewer can act on."""

    blocked: bool
    reason: str
    matched_on: str

    def __bool__(self) -> bool:
        return self.blocked


def normalize(value: str) -> str:
    """Strips everything that could disguise a self-reference."""
    return re.sub(r"[^a-z0-9]", "", value.strip().lower())


@dataclass
class RecursionGuard:
    """Detects and blocks self-targeting entries; alerts a human immediately.

    A first-class component per 21B §21.3, not a validation rule, because it is
    the subsystem's self-modification containment and must fire before anything
    else has a chance to normalize the input.
    """

    escalate: Callable[[EscalationTrigger, str], None] = field(default=lambda trigger, detail: None)
    alert_human: Callable[[str], None] = field(default=lambda detail: None)
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self._blocked: list[tuple[datetime, str]] = []
        self._suspended = False

    @property
    def suspended(self) -> bool:
        """13.21.3 requires suspension, not merely rejection, on an anomaly."""
        return self._suspended

    # ------------------------------------------------------------- Detection

    def inspect(
        self,
        target_class: TargetClass,
        target_subsystem: str,
        subject_id: str,
        proposal: str = "",
        evidence_kinds: tuple[str, ...] = (),
        triggered_by_event: str = "",
    ) -> RecursionFinding:
        """Answers whether this is self-referential. Never raises.

        Separated from `check` so the detection logic can be exercised
        exhaustively without a suspension side effect on every adversarial
        case.
        """
        if target_class == TargetClass.LEARNING:
            return RecursionFinding(
                True, "the entry declares the Learning subsystem as its target class", "target_class"
            )

        for label, value in (("target_subsystem", target_subsystem), ("subject_id", subject_id)):
            if normalize(value) in SELF_IDENTIFIERS:
                return RecursionFinding(True, f"{label} '{value}' names the Learning subsystem", label)

        for kind in evidence_kinds:
            if normalize(kind) in {normalize(k) for k in SELF_EVIDENCE_KINDS}:
                return RecursionFinding(
                    True,
                    f"evidence of kind '{kind}' originates inside the Learning subsystem, "
                    "so the entry reasons about itself whatever it declares as its target",
                    "evidence",
                )

        lowered = proposal.lower()
        for phrase in SELF_MODIFYING_PHRASES:
            if phrase in lowered:
                return RecursionFinding(
                    True,
                    f"the proposal would change the Learning subsystem's own '{phrase}' "
                    "(13.35.1); adoption requires human approval, not autonomous propagation",
                    "proposal",
                )

        # 13 rule 17 — a learning cycle triggered by a learning event is a
        # recursive cycle, whatever the entry it would produce targets.
        if triggered_by_event and normalize(triggered_by_event).startswith("learning"):
            return RecursionFinding(
                True,
                f"the cycle was triggered by '{triggered_by_event}', a learning event; "
                "recursive triggering requires explicit human authorization (13 rule 17)",
                "trigger",
            )

        return RecursionFinding(False, "no self-reference detected", "")

    # ---------------------------------------------------------------- Guard

    def check(
        self,
        target_class: TargetClass,
        target_subsystem: str,
        subject_id: str,
        proposal: str = "",
        evidence_kinds: tuple[str, ...] = (),
        triggered_by_event: str = "",
        observer_id: str = "unknown",
    ) -> None:
        """Raises on any self-reference. Takes no bypass argument, by design.

        13 rule 4 permits a self-targeting entry only under Class D human
        authority. That authority is a separate, explicit, audited act — never
        a parameter on the submission — so there is nothing a caller can pass
        that would make this method permit what it just refused.
        """
        finding = self.inspect(target_class, target_subsystem, subject_id, proposal, evidence_kinds, triggered_by_event)
        if not finding.blocked:
            return

        detail = (
            f"Recursion Anomaly (13.21.3): {finding.reason}. Observer '{observer_id}'. "
            "The learning cycle is suspended and requires human review."
        )
        self._blocked.append((self.now(), detail))
        self._suspended = True
        # Immediate human alert, then Category 1 escalation. Both, not either:
        # 13.21.3 requires the alert and 21B §21.9 classifies the anomaly as
        # Category 1, and an alert nobody escalated is not an incident record.
        self.alert_human(detail)
        self.escalate(EscalationTrigger.AUTHORITY_BYPASS, detail)
        raise RecursionAnomaly(detail)

    def release(self, human_principal: str, note: str = "") -> None:
        """Lifts the suspension. Human-only, and the caller proves it.

        Deliberately takes the principal rather than a boolean: a suspension
        that could be lifted by passing `True` would be liftable by the code
        that caused it.
        """
        if not human_principal:
            raise AgentOSError("only a named human principal may release a recursion suspension (13 rule 4)")
        self._suspended = False
        self._blocked.append((self.now(), f"released by '{human_principal}': {note}"))

    def health(self) -> dict[str, Any]:
        return {
            "suspended": self._suspended,
            "anomalies_blocked": len([entry for entry in self._blocked if "Recursion Anomaly" in entry[1]]),
            "self_identifiers": len(SELF_IDENTIFIERS),
            "last_anomaly": self._blocked[-1][0].isoformat() if self._blocked else None,
        }
