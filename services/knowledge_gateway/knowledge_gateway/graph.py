"""Graph Engine and Ontology Manager (21B §17.3, realizes 10.16, 10.17).

The Graph Engine maintains three integrity constraints continuously (10.17.4),
and they are checked rather than assumed:

1. **No orphaned canonical nodes** — every canonical belief participates in at
   least one relationship.
2. **No unresolved contradictory cycles** — a belief may not contradict itself
   through a chain.
3. **No dangling supersession references** — a superseded belief links to its
   successor, and the successor exists.

The Ontology Manager holds **no autonomous mutation path**. 10.16.4 is
explicit that the ontology is not self-modifying: the Learning Gateway may
propose extensions, and adoption requires human ratification. `propose` and
`ratify` are separate calls, and only a human can perform the second — which
is 10 rule 13 expressed structurally rather than documented.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.exceptions import AgentOSError, NotFoundError, ValidationError
from knowledge_gateway.beliefs import BeliefState, RelationType


class GraphIntegrityError(AgentOSError):
    """An integrity constraint of 10.17.4 is violated. Critical (21B §17.9)."""

    def __init__(self, constraint: str, detail: str):
        super().__init__(f"graph integrity violated ({constraint}): {detail}")
        self.constraint = constraint


class RatificationRequired(AgentOSError):
    """An ontology change was attempted without human ratification (10 rule 13)."""


@dataclass(frozen=True)
class BeliefEdge:
    source_id: str
    target_id: str
    relation: RelationType
    created_at: datetime


@dataclass(frozen=True)
class OntologyProposal:
    """A proposed taxonomy extension awaiting human ratification (10.16.4)."""

    proposal_id: str
    kind: str  # "entity_class" | "relationship_type" | "belief_category"
    name: str
    proposed_by: str
    proposed_at: datetime
    rationale: str
    ratified_at: datetime | None = None
    ratified_by: str | None = None

    @property
    def is_ratified(self) -> bool:
        return self.ratified_at is not None


@dataclass
class GraphEngine:
    """Node and typed-edge storage, traversal, and integrity enforcement."""

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _edges: list[BeliefEdge] = field(default_factory=list, init=False)
    _out: dict[str, list[BeliefEdge]] = field(default_factory=dict, init=False)
    _in: dict[str, list[BeliefEdge]] = field(default_factory=dict, init=False)

    def link(self, source_id: str, target_id: str, relation: RelationType) -> BeliefEdge:
        if source_id == target_id and relation == RelationType.CONTRADICTORY:
            raise GraphIntegrityError("contradictory_cycle", f"belief '{source_id}' cannot contradict itself")
        edge = BeliefEdge(source_id=source_id, target_id=target_id, relation=relation, created_at=self.now())
        self._edges.append(edge)
        self._out.setdefault(source_id, []).append(edge)
        self._in.setdefault(target_id, []).append(edge)
        return edge

    def edges_from(self, belief_id: str) -> list[BeliefEdge]:
        return list(self._out.get(belief_id, []))

    def edges_to(self, belief_id: str) -> list[BeliefEdge]:
        return list(self._in.get(belief_id, []))

    def is_linked(self, belief_id: str) -> bool:
        return bool(self._out.get(belief_id) or self._in.get(belief_id))

    def traverse(self, belief_id: str, depth: int = 3, visible: Callable[[str], bool] | None = None) -> list[str]:
        """Relationship traversal within permission scope (21B §17.5).

        Three hops is the depth 10.24.1 publishes a latency target for; the
        parameter defaults there rather than being unbounded, because an
        unbounded walk has no budget it can be held to.
        """
        if depth < 1:
            raise ValidationError("traversal depth must be at least 1")
        seen = {belief_id}
        frontier = [belief_id]
        for _ in range(depth):
            next_frontier: list[str] = []
            for current in frontier:
                neighbours = [e.target_id for e in self.edges_from(current)]
                neighbours += [e.source_id for e in self.edges_to(current)]
                for neighbour in neighbours:
                    if neighbour in seen or (visible is not None and not visible(neighbour)):
                        continue
                    seen.add(neighbour)
                    next_frontier.append(neighbour)
            frontier = next_frontier
        return sorted(seen - {belief_id})

    def contradicts(self, belief_id: str) -> list[str]:
        return sorted(
            {e.target_id for e in self.edges_from(belief_id) if e.relation == RelationType.CONTRADICTORY}
            | {e.source_id for e in self.edges_to(belief_id) if e.relation == RelationType.CONTRADICTORY}
        )

    def check_integrity(self, records: dict[str, Any]) -> list[GraphIntegrityError]:
        """Runs all three constraints of 10.17.4, returning every violation.

        Returns rather than raises so a repair workflow can see the whole
        picture at once — 21B §17.9 responds to integrity violations with a
        repair workflow, which needs the full list, not the first failure.
        """
        violations: list[GraphIntegrityError] = []

        for belief_id, record in records.items():
            if record.state == BeliefState.CANONICAL and not self.is_linked(belief_id):
                violations.append(
                    GraphIntegrityError(
                        "orphaned_canonical",
                        f"canonical belief '{belief_id}' participates in no relationship",
                    )
                )

        for belief_id in records:
            if self._reaches_itself_by_contradiction(belief_id):
                violations.append(
                    GraphIntegrityError(
                        "contradictory_cycle", f"belief '{belief_id}' contradicts itself through a chain"
                    )
                )

        for belief_id, record in records.items():
            if record.state == BeliefState.SUPERSEDED:
                successor = record.superseded_by
                if successor is None or successor not in records:
                    violations.append(
                        GraphIntegrityError(
                            "dangling_supersession",
                            f"superseded belief '{belief_id}' does not link to an existing successor",
                        )
                    )
        return violations

    def _reaches_itself_by_contradiction(self, start: str) -> bool:
        """Walks contradiction edges outward looking for a cycle back to `start`."""
        seen: set[str] = set()
        frontier = [e.target_id for e in self.edges_from(start) if e.relation == RelationType.CONTRADICTORY]
        while frontier:
            current = frontier.pop()
            if current == start:
                return True
            if current in seen:
                continue
            seen.add(current)
            frontier.extend(e.target_id for e in self.edges_from(current) if e.relation == RelationType.CONTRADICTORY)
        return False

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def relationship_distribution(self) -> dict[str, int]:
        """Feeds the Graph Health metric family of 10.22.1."""
        counts: dict[str, int] = {}
        for edge in self._edges:
            counts[edge.relation.value] = counts.get(edge.relation.value, 0) + 1
        return counts


@dataclass
class OntologyManager:
    """Entity classes, relationship types, belief categories — under ratification.

    There is no method here that adds to the ontology in one step. Extension
    is always propose-then-ratify, and ratification requires a human. 10.16.4
    and 10 rule 13 leave no room for an autonomous path, so none exists.
    """

    is_human: Callable[[str], bool]
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _entity_classes: set[str] = field(default_factory=set, init=False)
    _relationship_types: set[str] = field(default_factory=set, init=False)
    _belief_categories: set[str] = field(default_factory=set, init=False)
    _proposals: dict[str, OntologyProposal] = field(default_factory=dict, init=False)
    _version: int = field(default=0, init=False)

    _KINDS = ("entity_class", "relationship_type", "belief_category")

    def seed(self, kind: str, names: set[str]) -> None:
        """Installs the ratified starting ontology.

        Seeding is the ratified baseline a deployment ships with, not a
        runtime extension path — it is called during bootstrap, before any
        agent exists to abuse it.
        """
        self._target(kind).update(names)
        self._version += 1

    def propose(self, proposal_id: str, kind: str, name: str, proposed_by: str, rationale: str) -> OntologyProposal:
        """**Ontology Change Proposal** (21B §17.5). Consumers: Learning, Evolution."""
        if kind not in self._KINDS:
            raise ValidationError(f"'{kind}' is not an ontology kind; expected one of {list(self._KINDS)}")
        if proposal_id in self._proposals:
            raise ValidationError(f"proposal '{proposal_id}' already exists")
        if not rationale.strip():
            raise ValidationError("an ontology proposal must carry a rationale")
        proposal = OntologyProposal(
            proposal_id=proposal_id,
            kind=kind,
            name=name,
            proposed_by=proposed_by,
            proposed_at=self.now(),
            rationale=rationale,
        )
        self._proposals[proposal_id] = proposal
        return proposal

    def ratify(self, proposal_id: str, ratified_by: str) -> OntologyProposal:
        """Adopts a proposal. Only a human may ratify (10.16.4, 10 rule 13)."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise NotFoundError(f"ontology proposal '{proposal_id}' does not exist")
        if proposal.is_ratified:
            return proposal
        if not self.is_human(ratified_by):
            raise RatificationRequired(
                f"'{ratified_by}' is not a Human principal; the ontology is not self-modifying (10.16.4)"
            )
        if proposal.proposed_by == ratified_by:
            raise RatificationRequired("a proposer may not ratify its own ontology change")
        ratified = OntologyProposal(
            proposal_id=proposal.proposal_id,
            kind=proposal.kind,
            name=proposal.name,
            proposed_by=proposal.proposed_by,
            proposed_at=proposal.proposed_at,
            rationale=proposal.rationale,
            ratified_at=self.now(),
            ratified_by=ratified_by,
        )
        self._proposals[proposal_id] = ratified
        self._target(proposal.kind).add(proposal.name)
        self._version += 1
        return ratified

    def query(self) -> dict[str, Any]:
        """**Ontology Query** (21B §17.5). Consumers: all reasoning consumers."""
        return {
            "version": self._version,
            "entity_classes": sorted(self._entity_classes),
            "relationship_types": sorted(self._relationship_types),
            "belief_categories": sorted(self._belief_categories),
            "pending_proposals": sorted(p for p, v in self._proposals.items() if not v.is_ratified),
        }

    def knows_category(self, category: str) -> bool:
        return category in self._belief_categories

    def proposal(self, proposal_id: str) -> OntologyProposal:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise NotFoundError(f"ontology proposal '{proposal_id}' does not exist")
        return proposal

    def _target(self, kind: str) -> set[str]:
        return {
            "entity_class": self._entity_classes,
            "relationship_type": self._relationship_types,
            "belief_category": self._belief_categories,
        }[kind]
