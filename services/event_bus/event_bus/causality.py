"""Causality Tracker (21B §15.3, realizes 08.12.3, 08.13).

Causality is established by Causation IDs, never by wall-clock timestamps
(08.13.1). The happens-before relation of 08.13.4 has exactly three clauses:

1. Same stream, lower sequence → happens-before.
2. B's causation_id is A's event_id → A happens-before B.
3. Happens-before is transitive.

The tracker validates that consumers propagate context correctly when they
emit downstream events (08.12.3): the correlation ID must carry through
unchanged, and the causation ID must name the event actually consumed. A
producer that drops the chain breaks forensic reconstruction, so it is
rejected at admission rather than discovered later in an audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.exceptions import ValidationError
from event_bus.envelope import PublishedEvent


class CausalityViolation(ValidationError):
    """A downstream emission broke the causal chain (08.12.3)."""


@dataclass
class CausalityTracker:
    """Maintains happens-before relationships across all emissions."""

    #: event_id -> causation_id
    _caused_by: dict[str, str | None] = field(default_factory=dict, init=False)
    #: event_id -> (stream, sequence)
    _position: dict[str, tuple[str, int]] = field(default_factory=dict, init=False)
    #: event_id -> correlation_id
    _correlation: dict[str, str] = field(default_factory=dict, init=False)

    def record(self, published: PublishedEvent) -> None:
        self._caused_by[published.event_id] = published.provenance.causation_id
        self._position[published.event_id] = (published.stream, published.sequence)
        self._correlation[published.event_id] = published.provenance.correlation_id

    def validate_propagation(self, causation_id: str | None, correlation_id: str) -> None:
        """Checks a new emission against the event it claims to descend from.

        A root emission (no causation) is always valid. A caused emission must
        name a known ancestor and must carry that ancestor's correlation ID —
        08.12.3 requires an unbroken graph from the original trigger to every
        downstream effect.
        """
        if causation_id is None:
            return
        if causation_id not in self._correlation:
            raise CausalityViolation(
                f"causation_id '{causation_id}' names no published event; the causal chain would be broken"
            )
        expected = self._correlation[causation_id]
        if correlation_id != expected:
            raise CausalityViolation(
                f"correlation_id '{correlation_id}' does not match the ancestor's '{expected}'; "
                "consumers must propagate the correlation ID unchanged (08.12.3)"
            )

    def ancestors(self, event_id: str) -> list[str]:
        """Walks the causation chain back to the root, nearest ancestor first."""
        chain: list[str] = []
        seen: set[str] = {event_id}
        current = self._caused_by.get(event_id)
        while current is not None and current not in seen:
            chain.append(current)
            seen.add(current)
            current = self._caused_by.get(current)
        return chain

    def happens_before(self, first: str, second: str) -> bool:
        """The three clauses of 08.13.4, transitivity included."""
        if first == second:
            return False
        if first in self.ancestors(second):
            return True
        left, right = self._position.get(first), self._position.get(second)
        if left is not None and right is not None and left[0] == right[0]:
            return left[1] < right[1]
        # Different streams with no causal link are causally independent
        # (08.13.3) — timestamps do not establish an ordering between them.
        return False

    def correlation_of(self, event_id: str) -> str | None:
        return self._correlation.get(event_id)

    def trace(self, correlation_id: str) -> list[str]:
        """Every event belonging to one business operation, for forensic replay."""
        return [eid for eid, cid in self._correlation.items() if cid == correlation_id]
